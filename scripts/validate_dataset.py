import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aurora.data import sample_paths
from aurora.training import dataset_fingerprint, write_json_atomic


def preview(samples, root, output):
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    canvas = Image.new("RGB", (1600, 240 + 400 * len(samples)), "#101a26")
    draw = ImageDraw.Draw(canvas)
    draw.text((24, 20), "AURORA / POINT-CLOUD AND ENTRANCE LABEL REVIEW", font=font, fill="white")
    draw.text((24, 52), "Geometric MID360-FOV approximation, NOT calibrated Livox scan data", font=font, fill="#e9b76d")
    draw.text((24, 82), "Green: valid entrance bottom center | Orange: ignored / ambiguous | Blue: sensor", font=font, fill="#bdcad9")
    draw.text((24, 112), "Left: XY top view (-5..5 m) | Right: XZ side view (X -5..5 m, Z -0.8..1.0 m)", font=font, fill="#bdcad9")
    for sample_index, sample_id in enumerate(samples):
        point_path, label_path = sample_paths(root, sample_id)
        with np.load(point_path, allow_pickle=False) as archive:
            points = archive["xyz"]
        label = json.loads(label_path.read_text())
        top = 175 + sample_index * 400
        draw.text((24, top), f"{sample_id}  |  points={len(points)} targets={len(label['objects'])}", font=font, fill="white")
        for axis, left, vertical_range in ((1, 30, (-5.0, 5.0)), (2, 830, (-0.8, 1.0))):
            panel_top = top + 35
            panel_width, panel_height = 740, 330
            draw.rectangle((left, panel_top, left + panel_width, panel_top + panel_height), fill="#172636", outline="#4a5b6c")
            def project(position):
                horizontal = left + (position[0] + 5) / 10 * panel_width
                vertical = panel_top + (vertical_range[1] - position[axis]) / (vertical_range[1] - vertical_range[0]) * panel_height
                return horizontal, vertical
            valid = (points[:, 0] >= -5) & (points[:, 0] <= 5) & (points[:, axis] >= vertical_range[0]) & (points[:, axis] <= vertical_range[1])
            for point in points[valid]:
                pixel = project(point)
                draw.point(pixel, fill="#b5c5ce")
            for entries, color in ((label.get("ignored", []), "#f4ae55"), (label["objects"], "#64f79a")):
                for entry in entries:
                    horizontal, vertical = project(entry["position"])
                    draw.ellipse((horizontal - 7, vertical - 7, horizontal + 7, vertical + 7), outline=color, width=2)
                    draw.line((horizontal - 10, vertical, horizontal + 10, vertical), fill=color, width=2)
                    draw.line((horizontal, vertical - 10, horizontal, vertical + 10), fill=color, width=2)
            horizontal, vertical = project([0, 0, 0])
            draw.ellipse((horizontal - 4, vertical - 4, horizontal + 4, vertical + 4), fill="#6caeff")
    canvas.save(output)


def validate(root):
    fingerprint = dataset_fingerprint(root)
    metadata = json.loads((root / "dataset.json").read_text())
    if metadata["status"] != "complete":
        raise ValueError("Collection is incomplete")
    config = metadata["config"]
    references = {(entry["instance_id"], entry["entrance_id"]): np.asarray(entry["position_world"]) for entry in config["portals"]}
    clouds_seen = {}
    counts = {}
    portal_counts = {}
    point_counts = []
    examples_positive, examples_negative = [], []
    content_digest = hashlib.sha256()
    for split in ("train", "val", "test"):
        portal_counts[split] = Counter()
        counts[split] = {"frames": 0, "positive": 0, "negative": 0, "objects": 0, "ignored": 0}
        samples = (root / "splits" / f"{split}.txt").read_text().splitlines()
        for sample_id in samples:
            point_path, label_path = sample_paths(root, sample_id)
            with np.load(point_path, allow_pickle=False) as archive:
                points = archive["xyz"]
                offsets = archive["time_offset"]
            label = json.loads(label_path.read_text())
            if points.dtype != np.float32 or points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all() or len(points) < 100:
                raise ValueError(f"Invalid point cloud: {sample_id}")
            if offsets.shape != (len(points),) or not np.isfinite(offsets).all() or np.any(offsets < 0) or np.any(offsets >= label["frame_duration_s"]):
                raise ValueError(f"Invalid per-point timestamps: {sample_id}")
            if label["frame_id"] != "lidar" or label["units"] != "meters" or label["position_reference"] != "entrance_bottom_center":
                raise ValueError(f"Incorrect coordinate convention: {sample_id}")
            transform = np.asarray(label["T_world_lidar"])
            if transform.shape != (4, 4) or not np.isfinite(transform).all() or not np.allclose(transform[3], [0, 0, 0, 1]):
                raise ValueError(f"Invalid sensor transform: {sample_id}")
            rotation = transform[:3, :3]
            if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-6) or not np.isclose(np.linalg.det(rotation), 1):
                raise ValueError(f"Invalid rotation: {sample_id}")
            for entry in label["objects"] + label.get("ignored", []):
                position = np.asarray(entry["position"])
                key = (entry["instance_id"], entry["entrance_id"])
                reconstructed = rotation @ position + transform[:3, 3]
                if entry["class"] != "tunnel" or not np.allclose(reconstructed, references[key], atol=1e-5):
                    raise ValueError(f"Reference point transform failed: {sample_id}, {key}")
                if entry["annotation_state"] == "valid" and (
                    entry["visible_probe_fraction"] < config["annotation"]["min_visible_probe_fraction"]
                    or entry["support_points"] < config["annotation"]["min_support_points"]
                ):
                    raise ValueError(f"Positive visibility rule violated: {sample_id}")
            digest = hashlib.sha256(points.tobytes()).hexdigest()
            if digest in clouds_seen and clouds_seen[digest] != split:
                raise ValueError(f"Identical point cloud leaked across splits: {sample_id}")
            clouds_seen[digest] = split
            content_digest.update(sample_id.encode())
            content_digest.update(point_path.read_bytes())
            content_digest.update(label_path.read_bytes())
            counts[split]["frames"] += 1
            counts[split]["positive" if label["objects"] else "negative"] += 1
            counts[split]["objects"] += len(label["objects"])
            portal_counts[split].update(f"{entry['instance_id']}/{entry['entrance_id']}" for entry in label["objects"])
            counts[split]["ignored"] += len(label.get("ignored", []))
            point_counts.append(len(points))
            if split != "test":
                candidates = examples_positive if label["objects"] else examples_negative
                if len(candidates) < 2 and not any(Path(previous).parent == Path(sample_id).parent for previous in candidates):
                    candidates.append(sample_id)
        if not counts[split]["positive"] or not counts[split]["negative"]:
            raise ValueError(f"Split {split} lacks positive or negative samples")
    report = {
        "status": "passed", "manifest_fingerprint": fingerprint, "content_sha256": content_digest.hexdigest(),
        "splits": counts, "point_count": {"min": min(point_counts), "max": max(point_counts), "mean": float(np.mean(point_counts))},
        "portal_counts": portal_counts,
        "checks": ["finite float32 clouds", "timestamp alignment", "valid rigid poses", "portal world/local coordinate roundtrip", "positive observability thresholds", "no sequence leakage", "no identical clouds across splits", "positive and negative frames in every split"],
        "not_proven": ["exact MID360 scan physics", "real-world accuracy", "automatic visibility labels are perfect"],
    }
    write_json_atomic(root / "validation_report.json", report)
    preview(examples_positive + examples_negative, root, root / "preview.png")
    print(json.dumps(report, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description="Audit collected data and render a point-cloud/label contact sheet.")
    parser.add_argument("--dataset", type=Path, default=ROOT / "datasets/tunnel_v1")
    args = parser.parse_args()
    validate(args.dataset.resolve())


if __name__ == "__main__":
    main()
