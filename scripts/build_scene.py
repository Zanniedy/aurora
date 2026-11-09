import argparse
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdPhysics, UsdShade, Vt


ROOT = Path(__file__).resolve().parents[1]


def read_stl(path):
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError("The binary STL header is incomplete")
    count = struct.unpack_from("<I", data, 80)[0]
    if count < 1 or len(data) != 84 + count * 50:
        raise ValueError("Expected a binary STL with a valid triangle count")
    record = np.dtype([
        ("normal", "<f4", 3),
        ("vertices", "<f4", (3, 3)),
        ("attribute", "<u2"),
    ])
    triangles = np.frombuffer(data, dtype=record, count=count, offset=84)["vertices"].astype(np.float64)
    if not np.isfinite(triangles).all():
        raise ValueError("STL contains non-finite coordinates")
    return triangles, hashlib.sha256(data).hexdigest()


def region(triangles, minimum, maximum):
    inside = (triangles >= np.array(minimum) - 0.01) & (triangles <= np.array(maximum) + 0.01)
    selected = triangles[np.all(inside, axis=(1, 2))]
    if len(selected) == 0:
        raise ValueError(f"No complete triangles in expected source region: {minimum}, {maximum}")
    return selected


def horizontal_surfaces(triangles):
    flat = np.ptp(triangles[:, :, 1], axis=1) < 0.001
    selected = triangles[flat]
    areas = np.linalg.norm(
        np.cross(selected[:, 1] - selected[:, 0], selected[:, 2] - selected[:, 0]), axis=1
    ) / 2
    heights = np.round(selected[:, 0, 1], 3)
    return {float(height): float(areas[heights == height].sum()) for height in np.unique(heights)}


def audit(triangles, config, source_hash):
    points = triangles.reshape(-1, 3)
    ground = config["source_origin"][1]
    flat_faces = triangles[np.ptp(triangles[:, :, 1], axis=1) < 0.001]
    face_normals = np.cross(flat_faces[:, 1] - flat_faces[:, 0], flat_faces[:, 2] - flat_faces[:, 0])
    upward_surfaces = horizontal_surfaces(flat_faces[face_normals[:, 1] < 0])
    if max(upward_surfaces, key=upward_surfaces.get) != ground:
        raise ValueError("Configured ground is not the largest upward-facing surface; source up is -Y")
    for axis, value in ((0, 300), (0, 12300), (2, 300), (2, 8300)):
        plane_faces = np.all(np.isclose(triangles[:, :, axis], value, atol=0.001, rtol=0), axis=1)
        if not plane_faces.any():
            raise ValueError(f"Expected inner boundary plane absent: source axis {axis}, coordinate {value}")

    platform = region(triangles, (2800, 0, 3300), (4800, ground - 1, 7360))
    platform_points = platform.reshape(-1, 3)
    platform_planes = horizontal_surfaces(platform)
    platform_top = max(platform_planes, key=platform_planes.get)
    barrier = region(triangles, (4650, 20, 4200), (4800, 220, 6000)).reshape(-1, 3)
    bridge = region(triangles, (3625, 0, 7220), (3975, ground - 1, 8300))
    bridge_planes = horizontal_surfaces(bridge)
    if len(bridge_planes) != 2:
        raise ValueError(f"Expected two horizontal bridge plate surfaces, found {bridge_planes}")
    topside, underside = sorted(bridge_planes)
    bridge_bottom_faces = bridge[np.all(np.isclose(bridge[:, :, 1], underside), axis=1)]
    bridge_bottom_points = bridge_bottom_faces.reshape(-1, 3)
    opposite_bridge = region(triangles, (8625, 0, 300), (8975, ground - 1, 1380))
    if sorted(horizontal_surfaces(opposite_bridge)) != [topside, underside]:
        raise ValueError("The two tunnel bridge heights are not symmetric")

    measured = {
        "field_clear_length": 12300.0 - 300.0,
        "field_clear_width": 8300.0 - 300.0,
        "highland_width": float(np.ptp(platform_points[:, 0])),
        "highland_length": float(np.ptp(platform_points[:, 2])),
        "highland_height": ground - platform_top,
        "barrier_height": float(ground - barrier[:, 1].min()),
        "barrier_width": float(np.ptp(barrier[:, 0])),
        "barrier_length": float(np.ptp(barrier[:, 2])),
        "tunnel_clear_width": float(np.ptp(bridge_bottom_points[:, 2])),
        "tunnel_clear_height": ground - underside,
        "bridge_top_height": ground - topside,
        "bridge_width": float(np.ptp(bridge_bottom_points[:, 0])),
    }
    checks = []
    for name, expected in config["manual_dimensions_mm"].items():
        actual = measured[name]
        checks.append({
            "dimension": name,
            "manual_mm": expected,
            "stl_mm": actual,
            "difference_mm": actual - expected,
            "status": "match" if abs(actual - expected) < 0.01 else "MISMATCH",
            "manual_reference": "印刷页24 / 图3-5" if name.startswith("field_") else "印刷页25 / 图3-8",
        })
    return {
        "source_stl": config["source_stl"],
        "source_sha256": source_hash,
        "source_manual": config["source_manual"],
        "triangle_count": len(triangles),
        "source_bounds_mm": [points.min(axis=0).tolist(), points.max(axis=0).tolist()],
        "source_up_axis": "-Y",
        "source_ground_height_mm": ground,
        "transform": config["coordinate_transform"],
        "geometry_modified": False,
        "all_checked_dimensions_match": all(check["status"] == "match" for check in checks),
        "checks": checks,
        "limitations": [
            "仅核对表内尺寸，不等于对每个 STL 细节的完整工程验收。",
            "场内尺寸由已有边界平面核对；局部尺寸由图纸对应区域的三角面和水平面测量。",
            "通过面法线和整场底板确定源坐标向上为-Y；地面Y=420，底板下表面Y=520。",
            "两侧金属板底面Y=170、顶面Y=150，相对地面的净高250mm、顶面高度270mm。",
            "手册印刷页21规定了制造误差，并说明未注明尺寸以实际场地为准。",
            "STL不携带可靠的地形语义标签；当前材质分区仅用于显示，不是训练标注。",
        ],
    }


def material(stage, name, color):
    result = UsdShade.Material.Define(stage, f"/World/Materials/{name}")
    shader = UsdShade.Shader.Define(stage, f"{result.GetPath()}/Surface")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.75)
    result.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return result


def camera(stage, name, eye, focus, focal_length=32.0):
    result = UsdGeom.Camera.Define(stage, f"/World/Cameras/{name}")
    transform = Gf.Matrix4d().SetLookAt(Gf.Vec3d(*eye), Gf.Vec3d(*focus), Gf.Vec3d(0, 0, 1))
    result.AddTransformOp().Set(transform.GetInverse())
    result.CreateFocalLengthAttr(focal_length)
    result.CreateClippingRangeAttr(Gf.Vec2f(0.01, 1000.0))


def build(config_path, output, report_path, source_override=None):
    config = json.loads(config_path.read_text(encoding="utf-8"))
    source = (source_override or Path(config["source_stl"])).resolve()
    config["source_stl"] = str(source)
    triangles, source_hash = read_stl(source)
    report = audit(triangles, config, source_hash)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not report["all_checked_dimensions_match"]:
        mismatches = [check["dimension"] for check in report["checks"] if check["status"] != "match"]
        raise ValueError(f"Manual dimensions take precedence; refusing import: {mismatches}. See {report_path}")
    scale = config["meters_per_source_unit"]
    if scale != 0.001 or config["source_origin"] != [6300.0, 420.0, 4300.0]:
        raise ValueError("This audited asset requires millimeters and source origin [6300, 420, 4300]")
    transformed = (triangles - config["source_origin"]) * scale
    transformed = transformed[:, :, [0, 2, 1]]
    transformed[:, :, 2] *= -1
    points, indices = np.unique(transformed.reshape(-1, 3), axis=0, return_inverse=True)

    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Usd.Stage.CreateNew(str(output))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    world = UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(world.GetPrim())
    stage.GetRootLayer().documentation = config["description"]
    world.GetPrim().CreateAttribute("aurora:sourceSha256", Sdf.ValueTypeNames.String).Set(source_hash)
    world.GetPrim().CreateAttribute("aurora:manualDimensionsMatch", Sdf.ValueTypeNames.Bool).Set(
        report["all_checked_dimensions_match"]
    )
    physics = UsdPhysics.Scene.Define(stage, "/World/PhysicsScene")
    physics.CreateGravityDirectionAttr(Gf.Vec3f(0, 0, -1))
    physics.CreateGravityMagnitudeAttr(9.81)

    mesh = UsdGeom.Mesh.Define(stage, "/World/Field")
    mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(points.astype(np.float32)))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray.FromNumpy(np.full(len(triangles), 3, dtype=np.int32)))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(indices.astype(np.int32)))
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    mesh.CreateDoubleSidedAttr(True)
    mesh.CreateExtentAttr([Gf.Vec3f(*points.min(axis=0)), Gf.Vec3f(*points.max(axis=0))])
    UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
    UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim()).CreateApproximationAttr("none")
    base = material(stage, "Structure", (0.38, 0.44, 0.48))
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(base)

    centroids = triangles.mean(axis=1)
    ground_faces = np.all(np.isclose(triangles[:, :, 1], 420), axis=1)
    boundary_faces = (
        (centroids[:, 0] < 300) | (centroids[:, 0] > 12300)
        | (centroids[:, 2] < 300) | (centroids[:, 2] > 8300)
    ) & ~ground_faces
    metal_faces = (
        ((centroids[:, 0] >= 3625) & (centroids[:, 0] <= 3975) & (centroids[:, 2] >= 7220))
        | ((centroids[:, 0] >= 8625) & (centroids[:, 0] <= 8975) & (centroids[:, 2] <= 1380))
    ) & (centroids[:, 1] < 420) & ~boundary_faces
    for name, mask, color in (
        ("Ground", ground_faces, (0.20, 0.24, 0.28)),
        ("Boundary", boundary_faces, (0.075, 0.095, 0.12)),
        ("Bridge", metal_faces, (0.53, 0.43, 0.23)),
    ):
        subset = UsdGeom.Subset.CreateGeomSubset(
            mesh, name, UsdGeom.Tokens.face, np.flatnonzero(mask).tolist(), "materialBind"
        )
        UsdShade.MaterialBindingAPI.Apply(subset.GetPrim()).Bind(material(stage, name, color))
    UsdGeom.Subset.SetFamilyType(mesh, "materialBind", UsdGeom.Tokens.nonOverlapping)

    dome = UsdLux.DomeLight.Define(stage, "/World/Lights/Fill")
    dome.CreateIntensityAttr(700.0)
    sun = UsdLux.DistantLight.Define(stage, "/World/Lights/Key")
    sun.CreateIntensityAttr(2400.0)
    sun.CreateAngleAttr(8.0)
    sun.AddRotateXYZOp().Set(Gf.Vec3f(25, -35, -30))
    camera(stage, "Overview", (11.5, -14.5, 13.0), (0, 0, 0))
    camera(stage, "Tunnel", (-4.15, 3.25, 0.72), (-2.5, 3.46, 0.12), 27.0)
    camera(stage, "Stairs", (-6.2, -1.4, 3.1), (-2.8, 0.8, 0.15), 34.0)
    camera(stage, "Top", (0, -0.001, 17), (0, 0, 0), 28.0)
    stage.GetRootLayer().Save()
    print(f"Imported {len(triangles)} triangles without geometric edits: {output}")
    for check in report["checks"]:
        print(f"{check['status']:8} {check['dimension']}: STL {check['stl_mm']:g} mm / manual {check['manual_mm']:g} mm")
    print(f"Audit report: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Import and audit the supplied RMUL 2027 binary STL.")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/rmul_2027.json")
    parser.add_argument("--stl", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "scenes/aurora_terrain.usda")
    parser.add_argument("--report", type=Path, default=ROOT / "outputs/dimension_audit.json")
    args = parser.parse_args()
    build(args.config.resolve(), args.output.resolve(), args.report.resolve(), args.stl)


if __name__ == "__main__":
    main()
