import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import time

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from sensor_msgs.msg import PointCloud2
from sensor_msgs_py.point_cloud2 import dtype_from_fields
from std_msgs.msg import String
from tf2_ros import Buffer, TransformException, TransformListener
import torch
from visualization_msgs.msg import Marker, MarkerArray


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aurora.data import voxelize
from aurora.model import Aurora, decode


def cloud_xyz(message):
    dtype = dtype_from_fields(message.fields, point_step=message.point_step)
    dtype = dtype.newbyteorder(">" if message.is_bigendian else "<")
    values = np.ndarray(
        (message.height, message.width), dtype=dtype, buffer=message.data,
        strides=(message.row_step, message.point_step),
    )
    points = np.stack([values[name].reshape(-1) for name in ("x", "y", "z")], axis=1)
    return points[np.isfinite(points).all(axis=1)].astype(np.float32)


def rotation_matrix(quaternion):
    vector = np.array([quaternion.x, quaternion.y, quaternion.z], dtype=np.float64)
    scalar = quaternion.w
    norm = np.dot(vector, vector) + scalar * scalar
    if norm < 1e-12:
        raise ValueError("Invalid TF quaternion")
    cross = np.array([[0, -vector[2], vector[1]], [vector[2], 0, -vector[0]], [-vector[1], vector[0], 0]])
    return np.eye(3) + 2 * (scalar * cross + cross @ cross) / norm


class TunnelNode(Node):
    def __init__(self, args):
        super().__init__("aurora_tunnel")
        self.args = args
        torch.set_num_threads(args.threads)
        self.device = torch.device(args.device)
        checkpoint_bytes = args.checkpoint.read_bytes()
        checkpoint = torch.load(io.BytesIO(checkpoint_bytes), map_location="cpu", weights_only=True)
        self.config = checkpoint["config"]
        self.model = Aurora(self.config).to(self.device).eval()
        self.model.load_state_dict(checkpoint["model"])
        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self)
        self.latest = None
        self.received = 0
        self.processed = 0
        self.skipped = 0
        self.subscription = self.create_subscription(PointCloud2, args.topic, self.receive, qos_profile_sensor_data)
        self.markers = self.create_publisher(MarkerArray, "/aurora/tunnel_markers", 10)
        self.results = self.create_publisher(String, "/aurora/tunnel_detections", 10)
        self.cloud = self.create_publisher(PointCloud2, "/aurora/input_cloud", qos_profile_sensor_data)
        args.output.mkdir(parents=True, exist_ok=False)
        self.log = (args.output / "predictions.jsonl").open("w")
        metadata = {
            "checkpoint": str(args.checkpoint.resolve()),
            "checkpoint_sha256": hashlib.sha256(checkpoint_bytes).hexdigest(),
            "checkpoint_epoch": checkpoint.get("epoch"), "topic": args.topic,
            "orientation_frame": args.orientation_frame,
            "normalization": "rotation_only_sensor_origin_preserved",
            "score_threshold": self.config["score_threshold"], "device": args.device,
            "ground_truth_available": False,
        }
        (args.output / "session.json").write_text(json.dumps(metadata, indent=2))
        self.get_logger().info(f"Listening on {args.topic}; checkpoint epoch={metadata['checkpoint_epoch']}; no motion commands")

    def receive(self, message):
        self.latest = message
        self.received += 1

    def process_latest(self):
        if self.latest is None:
            return
        message, self.latest = self.latest, None
        started = time.monotonic()
        rotation = np.eye(3)
        if not message.header.frame_id:
            raise ValueError("Point cloud has no frame_id")
        if self.args.orientation_frame:
            try:
                transform = self.buffer.lookup_transform(
                    self.args.orientation_frame, message.header.frame_id,
                    Time.from_msg(message.header.stamp),
                )
                rotation = rotation_matrix(transform.transform.rotation)
            except TransformException as error:
                self.skipped += 1
                self.get_logger().warning(f"Skipping frame without orientation TF: {error}", throttle_duration_sec=5)
                return
        raw_points = cloud_xyz(message)
        if not len(raw_points):
            self.skipped += 1
            self.get_logger().warning("Skipping empty cloud", throttle_duration_sec=5)
            return
        points = (raw_points @ rotation.T).astype(np.float32)
        voxels = torch.from_numpy(voxelize(points, self.config["voxel"]))[None].to(self.device)
        with torch.inference_mode():
            detections = decode(self.model(voxels), self.config)[0]
        for detection in detections:
            detection["position"] = (np.asarray(detection["position"]) @ rotation).tolist()
        record = {
            "index": self.processed, "stamp": {"sec": message.header.stamp.sec, "nanosec": message.header.stamp.nanosec},
            "frame_id": message.header.frame_id, "units": "meters",
            "position_reference": "entrance_bottom_center", "points": len(points),
            "rotation_input_from_sensor": rotation.tolist(), "detections": detections,
            "processing_ms": (time.monotonic() - started) * 1000,
        }
        encoded = json.dumps(record, allow_nan=False)
        self.log.write(encoded + "\n")
        self.log.flush()
        self.results.publish(String(data=encoded))
        self.cloud.publish(message)
        array = MarkerArray()
        clear = Marker()
        clear.header = message.header
        clear.action = Marker.DELETEALL
        array.markers.append(clear)
        for index, detection in enumerate(detections):
            for kind in (Marker.SPHERE, Marker.TEXT_VIEW_FACING):
                marker = Marker()
                marker.header = message.header
                marker.ns = "aurora_tunnel"
                marker.id = index * 2 + (kind == Marker.TEXT_VIEW_FACING)
                marker.type = kind
                marker.action = Marker.ADD
                marker.pose.position.x, marker.pose.position.y, marker.pose.position.z = detection["position"]
                marker.pose.orientation.w = 1.0
                marker.scale.x = marker.scale.y = marker.scale.z = 0.12
                marker.color.r, marker.color.g, marker.color.b, marker.color.a = 1.0, 0.25, 0.05, 1.0
                marker.lifetime.sec = 2
                if kind == Marker.TEXT_VIEW_FACING:
                    marker.pose.position.z += 0.20
                    marker.text = f"tunnel {detection['score']:.2f}"
                array.markers.append(marker)
        self.markers.publish(array)
        if self.processed < self.args.save_frames:
            np.savez_compressed(self.args.output / f"frame_{self.processed:06d}.npz", xyz=points, raw_xyz=raw_points)
        self.processed += 1
        self.get_logger().info(f"frame={self.processed} points={len(points)} detections={len(detections)} inference+encoding={record['processing_ms']:.1f}ms", throttle_duration_sec=5)


def main():
    parser = argparse.ArgumentParser(description="Read-only ROS tunnel inference; never publishes motion commands.")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--topic", default="/livox/lidar")
    parser.add_argument("--orientation-frame", default="base_link", help="Rotate axes into this TF frame while keeping sensor origin; empty disables")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--rate", type=float, default=2.0)
    parser.add_argument("--duration", type=float, default=0, help="Wall seconds; zero runs until Ctrl+C")
    parser.add_argument("--save-frames", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args, ros_args = parser.parse_known_args()
    if not np.isfinite([args.rate, args.duration]).all() or args.rate <= 0 or args.duration < 0 or args.threads < 1 or args.save_frames < 0:
        parser.error("Invalid rate, duration, thread count or save-frame limit")
    rclpy.init(args=ros_args)
    node = None
    try:
        node = TunnelNode(args)
        started = time.monotonic()
        next_frame = started
        while rclpy.ok() and (args.duration == 0 or time.monotonic() - started < args.duration):
            rclpy.spin_once(node, timeout_sec=0.05)
            if time.monotonic() >= next_frame:
                node.process_latest()
                next_frame = time.monotonic() + 1 / args.rate
        if not node.processed:
            raise RuntimeError("No frames processed; check topic, simulation and orientation TF")
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.log.close()
            (args.output / "summary.json").write_text(json.dumps({
                "received": node.received, "processed": node.processed, "skipped": node.skipped,
            }, indent=2))
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
