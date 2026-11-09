import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aurora.simulation import Raycaster, annotate, rotation_matrix, sample_scan
from aurora.splitting import grouped_splits


def save_json(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def base_pose(config, rng, negative):
    if negative:
        position = np.array([rng.uniform(-5.4, 5.4), rng.uniform(-3.5, 3.5), rng.uniform(*config["sampling"]["height_m"])])
    else:
        portal = config["portals"][rng.integers(len(config["portals"]))]
        position = np.array(portal["position_world"]) + np.array(portal["outward_world"]) * rng.uniform(*config["sampling"]["distance_m"])
        position += [0, rng.uniform(-0.7, 0.7), rng.uniform(*config["sampling"]["height_m"])]
    return position


def collect(config, output, device):
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}; use a new --output path")
    if config["sequences"] < 12 or config["frames_per_sequence"] < 1:
        raise ValueError("Use at least 12 sequences and one frame per sequence for grouped splits")
    scene = ROOT / config["scene"]
    raycaster = Raycaster(scene, device)
    raycaster.verify_portals(config["portals"])
    rng = np.random.default_rng(config["seed"])
    output.mkdir(parents=True)
    metadata = {
        "schema_version": "1.0", "status": "collecting", "classes": ["tunnel"],
        "units": "meters", "frame_id": "lidar", "position_reference": "entrance_bottom_center",
        "scene_sha256": raycaster.scene_sha256, "config": config,
        "limitations": [
            "Geometry-only raycasting of the same audited USD used by Isaac Sim; not Isaac RTX sensor output.",
            "MID360 nominal-FOV approximation, NOT the calibrated Livox non-repetitive scan pattern.",
            "Static pose within each 100 ms frame; no motion distortion, intensity, multipath or robot self-occlusion.",
            "One fixed field layout; grouped held-out poses do not establish real-world or new-layout generalization.",
            "Sensor height and tilt are sampling assumptions, not measured mounting calibration.",
            "Visibility labels are automatic geometric heuristics and require visual review before training.",
        ],
    }
    save_json(output / "dataset.json", metadata)
    negative_count = round(config["sequences"] * config["negative_sequence_fraction"])
    kinds = np.array([True] * negative_count + [False] * (config["sequences"] - negative_count))
    rng.shuffle(kinds)
    sequences = {False: [], True: []}
    counts = {"frames": 0, "positive_frames": 0, "negative_frames": 0, "objects": 0, "ignored": 0}
    started = time.monotonic()
    for sequence_index, negative in enumerate(kinds):
        sequence_name = f"sim/sequence_{sequence_index:04d}"
        sequence_path = output / sequence_name
        (sequence_path / "points").mkdir(parents=True)
        (sequence_path / "labels").mkdir()
        sequence_seed = int(rng.integers(2**31))
        frame_rng = np.random.default_rng(sequence_seed)
        noise_std = float(frame_rng.uniform(*config["sensor"]["range_noise_std_m"]))
        dropout = float(frame_rng.uniform(*config["sensor"]["dropout_fraction"]))
        base = None
        yaw_base = frame_rng.uniform(-np.pi, np.pi)
        sample_ids = []
        for frame_index in range(config["frames_per_sequence"]):
            for attempt in range(config["sampling"]["max_attempts_per_frame"]):
                if base is None or (attempt > 0 and attempt % 5 == 0):
                    base = base_pose(config, frame_rng, bool(negative))
                position = base + [frame_rng.uniform(-0.18, 0.18), frame_rng.uniform(-0.18, 0.18), frame_rng.uniform(-0.015, 0.015)]
                if abs(position[0]) > 5.7 or abs(position[1]) > 3.85 or not raycaster.free_ground(position):
                    continue
                yaw = yaw_base + frame_rng.uniform(-0.3, 0.3)
                pitch = np.deg2rad(frame_rng.uniform(*config["sampling"]["pitch_deg"]))
                roll = np.deg2rad(frame_rng.uniform(*config["sampling"]["roll_deg"]))
                rotation = rotation_matrix(yaw, pitch, roll)
                points, offsets = sample_scan(raycaster, position, rotation, config["sensor"], frame_rng, noise_std, dropout)
                if len(points) < 100:
                    continue
                objects, ignored = annotate(raycaster, points, position, rotation, config)
                if bool(objects) == bool(negative):
                    continue
                break
            else:
                raise RuntimeError(f"Could not obtain a valid {'negative' if negative else 'positive'} frame in {sequence_name}; partial dataset is marked collecting")
            name = f"{frame_index:06d}"
            np.savez_compressed(sequence_path / "points" / f"{name}.npz", xyz=points, time_offset=offsets)
            transform = np.eye(4)
            transform[:3, :3], transform[:3, 3] = rotation, position
            label = {
                "schema_version": "1.0", "frame_id": "lidar", "units": "meters",
                "position_reference": "entrance_bottom_center", "objects": objects, "ignored": ignored,
                "timestamp_s": frame_index * config["sensor"]["frame_duration_s"],
                "frame_duration_s": config["sensor"]["frame_duration_s"],
                "T_world_lidar": transform.tolist(),
            }
            save_json(sequence_path / "labels" / f"{name}.json", label)
            sample_ids.append(f"{sequence_name}/{name}")
            counts["frames"] += 1
            counts["positive_frames" if objects else "negative_frames"] += 1
            counts["objects"] += len(objects)
            counts["ignored"] += len(ignored)
        save_json(sequence_path / "sequence.json", {
            "seed": sequence_seed, "negative_sequence": bool(negative), "noise_std_m": noise_std,
            "dropout_fraction": dropout, "samples": sample_ids,
            "sampling": "nearby_static_viewpoints_not_a_motion_distorted_trajectory",
        })
        sequences[bool(negative)].append(sample_ids)
        print(f"sequence {sequence_index + 1}/{config['sequences']} | frames={counts['frames']} | positive={counts['positive_frames']} negative={counts['negative_frames']}", flush=True)
    fractions = config["split_fractions"]
    if not np.isclose(sum(fractions), 1.0) or any(fraction <= 0 for fraction in fractions):
        raise ValueError("Split fractions must be positive and sum to one")
    splits = grouped_splits(output, sequences, fractions, np.random.default_rng(config["seed"] + 1))
    (output / "splits").mkdir()
    for split, samples in splits.items():
        (output / "splits" / f"{split}.txt").write_text("\n".join(samples) + "\n")
    metadata.update(status="complete", statistics=counts, split_counts={name: len(samples) for name, samples in splits.items()}, split_strategy="sequence_disjoint_stratified_by_negative_and_dominant_portal", elapsed_s=time.monotonic() - started)
    save_json(output / "dataset.json", metadata)
    print(json.dumps(metadata["statistics"], indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description="Collect approximate geometric LiDAR frames; never starts model training.")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/collection.json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--sequences", type=int)
    parser.add_argument("--frames-per-sequence", type=int)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if args.sequences is not None:
        config["sequences"] = args.sequences
    if args.frames_per_sequence is not None:
        config["frames_per_sequence"] = args.frames_per_sequence
    output = (args.output or ROOT / config["output"]).resolve()
    collect(config, output, args.device)


if __name__ == "__main__":
    main()
