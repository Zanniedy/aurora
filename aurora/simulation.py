import hashlib
from pathlib import Path

import numpy as np
from pxr import Usd, UsdGeom, UsdPhysics
import warp as wp


@wp.kernel
def trace_rays(
    mesh_id: wp.uint64,
    origins: wp.array(dtype=wp.vec3),
    directions: wp.array(dtype=wp.vec3),
    maximum: float,
    distances: wp.array(dtype=float),
):
    index = wp.tid()
    query = wp.mesh_query_ray(mesh_id, origins[index], directions[index], maximum)
    distances[index] = -1.0
    if query.result:
        distances[index] = query.t


class Raycaster:
    def __init__(self, scene, device="cpu"):
        wp.config.kernel_cache_dir = str(Path(__file__).resolve().parents[1] / "outputs/warp_cache")
        wp.init()
        self.device = wp.get_device(device)
        stage = Usd.Stage.Open(str(scene))
        if stage is None or UsdGeom.GetStageUpAxis(stage) != "Z" or UsdGeom.GetStageMetersPerUnit(stage) != 1.0:
            raise ValueError("Scene must be a valid, meter-unit, Z-up USD")
        if not stage.GetPrimAtPath("/World").GetAttribute("aurora:manualDimensionsMatch").Get():
            raise ValueError("Scene has not passed the manual dimension audit")
        vertices = []
        triangles = []
        vertex_count = 0
        for prim in stage.Traverse():
            if not prim.IsA(UsdGeom.Mesh) or not prim.HasAPI(UsdPhysics.CollisionAPI):
                continue
            mesh = UsdGeom.Mesh(prim)
            counts = np.asarray(mesh.GetFaceVertexCountsAttr().Get())
            if not np.all(counts == 3):
                raise ValueError(f"Expected a triangle mesh: {prim.GetPath()}")
            transform = np.asarray(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default()))
            points = np.asarray(mesh.GetPointsAttr().Get(), dtype=np.float64)
            points = np.concatenate((points, np.ones((len(points), 1))), axis=1) @ transform
            vertices.append(points[:, :3].astype(np.float32))
            indices = np.asarray(mesh.GetFaceVertexIndicesAttr().Get(), dtype=np.int32)
            triangles.append(indices + vertex_count)
            vertex_count += len(points)
        if not vertices:
            raise ValueError("No collidable triangle geometry in the scene")
        self.mesh = wp.Mesh(
            points=wp.array(np.concatenate(vertices), dtype=wp.vec3, device=self.device),
            indices=wp.array(np.concatenate(triangles), dtype=int, device=self.device),
        )
        self.scene_sha256 = hashlib.sha256(Path(scene).read_bytes()).hexdigest()

    def cast(self, origins, directions, maximum=12.0):
        directions = np.ascontiguousarray(directions, dtype=np.float32)
        origins = np.ascontiguousarray(np.broadcast_to(origins, directions.shape), dtype=np.float32)
        output = wp.empty(len(directions), dtype=float, device=self.device)
        wp.launch(
            trace_rays,
            dim=len(directions),
            inputs=[
                self.mesh.id,
                wp.array(origins, dtype=wp.vec3, device=self.device),
                wp.array(directions, dtype=wp.vec3, device=self.device),
                float(maximum),
                output,
            ],
            device=self.device,
        )
        return output.numpy()

    def free_ground(self, position):
        offsets = np.array([[0, 0], [-0.12, -0.12], [-0.12, 0.12], [0.12, -0.12], [0.12, 0.12]])
        origins = np.column_stack((position[:2] + offsets, np.ones(len(offsets))))
        distances = self.cast(origins, np.tile([0, 0, -1], (len(origins), 1)), 2.0)
        return bool(np.all(np.abs(distances - 1.0) < 0.005))

    def verify_portals(self, portals):
        directions = np.array([[0, 0, 1], [0, 0, -1], [0, 1, 0], [0, -1, 0]], dtype=np.float32)
        for portal in portals:
            origin = np.array(portal["position_world"]) - np.array(portal["outward_world"]) * 0.01 + [0, 0, 0.12]
            distances = self.cast(origin, directions, 1.0)
            if not np.allclose(distances, [0.13, 0.12, 0.4, 0.4], atol=0.001):
                raise ValueError(f"Portal reference does not bound an 800 x 250 mm opening: {portal}, rays={distances}")


def rotation_matrix(yaw, pitch, roll):
    yaw_cos, yaw_sin = np.cos(yaw), np.sin(yaw)
    pitch_cos, pitch_sin = np.cos(pitch), np.sin(pitch)
    roll_cos, roll_sin = np.cos(roll), np.sin(roll)
    rotation_yaw = np.array([[yaw_cos, -yaw_sin, 0], [yaw_sin, yaw_cos, 0], [0, 0, 1]])
    rotation_pitch = np.array([[pitch_cos, 0, pitch_sin], [0, 1, 0], [-pitch_sin, 0, pitch_cos]])
    rotation_roll = np.array([[1, 0, 0], [0, roll_cos, -roll_sin], [0, roll_sin, roll_cos]])
    return rotation_yaw @ rotation_pitch @ rotation_roll


def sample_scan(raycaster, position, rotation, sensor, rng, noise_std, dropout):
    count = sensor["rays_per_frame"]
    azimuth = rng.uniform(-np.pi, np.pi, count)
    elevation = np.deg2rad(rng.uniform(*sensor["elevation_deg"], count))
    directions = np.column_stack((np.cos(elevation) * np.cos(azimuth), np.cos(elevation) * np.sin(azimuth), np.sin(elevation)))
    distances = raycaster.cast(position, directions @ rotation.T, sensor["range_m"][1])
    valid = (distances >= sensor["range_m"][0]) & (distances <= sensor["range_m"][1])
    valid &= rng.random(count) >= dropout
    ranges = distances[valid] + rng.normal(0, noise_std, valid.sum())
    ranges = np.clip(ranges, *sensor["range_m"])
    points = (directions[valid] * ranges[:, None]).astype(np.float32)
    times = (np.arange(count, dtype=np.float32) / count * sensor["frame_duration_s"])[valid]
    return points, times


def annotate(raycaster, points, position, rotation, config):
    world_points = points @ rotation.T + position
    objects, ignored = [], []
    parameters = config["annotation"]
    for portal in config["portals"]:
        anchor = np.array(portal["position_world"])
        outward = np.array(portal["outward_world"])
        difference = position - anchor
        planar_distance = np.linalg.norm(difference[:2])
        if planar_distance < 0.3 or planar_distance > parameters["max_distance_m"]:
            continue
        if np.dot(difference, outward) / planar_distance < parameters["minimum_facing_cosine"]:
            continue
        probes = np.array([anchor + outward * 0.008 + [0, lateral, height] for lateral in (-0.30, 0, 0.30) for height in (0.06, 0.15, 0.23)])
        vectors = probes - position
        lengths = np.linalg.norm(vectors, axis=1)
        directions = vectors / lengths[:, None]
        distances = raycaster.cast(position, directions, 12.0)
        local_directions = directions @ rotation
        elevations = np.rad2deg(np.arcsin(np.clip(local_directions[:, 2], -1, 1)))
        in_fov = (elevations >= config["sensor"]["elevation_deg"][0]) & (elevations <= config["sensor"]["elevation_deg"][1])
        visible = ((distances < 0) | (distances >= lengths - 0.015)) & in_fov
        relative = world_points - anchor
        nearby = (np.abs(relative[:, 0]) <= 0.28) & (np.abs(relative[:, 1]) <= 0.55)
        nearby &= (relative[:, 2] >= 0.04) & (relative[:, 2] <= 0.43)
        count = int(nearby.sum())
        entry = {
            "class": "tunnel",
            "instance_id": portal["instance_id"],
            "entrance_id": portal["entrance_id"],
            "position": ((anchor - position) @ rotation).tolist(),
            "visible_probe_fraction": float(visible.mean()),
            "support_points": count,
        }
        if visible.mean() >= parameters["min_visible_probe_fraction"] and count >= parameters["min_support_points"]:
            entry["annotation_state"] = "valid"
            objects.append(entry)
        elif count >= 3 or visible.any():
            entry["annotation_state"] = "ignore"
            ignored.append(entry)
    return objects, ignored
