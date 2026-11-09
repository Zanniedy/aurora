import argparse
import json
from pathlib import Path
import sys

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aurora.data import voxelize
from aurora.model import Aurora, decode


def main():
    parser = argparse.ArgumentParser(description="Predict tunnel entrance bottom centers from one LiDAR-frame NPZ.")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--points", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--score-threshold", type=float)
    args = parser.parse_args()
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    config = checkpoint["config"]
    if args.score_threshold is not None:
        config["score_threshold"] = args.score_threshold
    with np.load(args.points, allow_pickle=False) as archive:
        points = archive["xyz"]
    if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all():
        raise ValueError("Expected finite xyz with shape [N,3], in meters and LiDAR coordinates")
    device = torch.device(args.device)
    model = Aurora(config).to(device).eval()
    model.load_state_dict(checkpoint["model"])
    voxels = torch.from_numpy(voxelize(points, config["voxel"]))[None].to(device)
    with torch.no_grad():
        detections = decode(model(voxels), config)[0]
    print(json.dumps({"frame_id": "lidar", "units": "meters", "position_reference": "entrance_bottom_center", "detections": detections}, indent=2))


if __name__ == "__main__":
    main()
