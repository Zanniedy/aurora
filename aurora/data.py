import json
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset


def grid_shape(config):
    bounds = np.asarray(config["range"], dtype=np.float64)
    sizes = np.asarray(config["size"], dtype=np.float64)
    shape_float = (bounds[3:] - bounds[:3]) / sizes
    shape = np.rint(shape_float).astype(int)
    if np.any(sizes <= 0) or np.any(shape <= 0) or not np.allclose(shape, shape_float):
        raise ValueError("Voxel bounds must contain a positive integral number of cells")
    if config["output_stride"] != 2 or np.any(shape[:2] % 8):
        raise ValueError("Aurora requires output stride 2 and XY grid dimensions divisible by 8")
    return tuple(shape.tolist())


def voxelize(points, config):
    width, height, depth = grid_shape(config)
    bounds = np.asarray(config["range"])
    sizes = np.asarray(config["size"])
    valid = np.isfinite(points).all(axis=1) & np.all(points >= bounds[:3], axis=1) & np.all(points < bounds[3:], axis=1)
    indices = np.floor((points[valid] - bounds[:3]) / sizes).astype(np.int64)
    indices = np.minimum(indices, np.array([width, height, depth]) - 1)
    flattened = (indices[:, 2] * height + indices[:, 1]) * width + indices[:, 0]
    counts = np.bincount(flattened, minlength=width * height * depth).reshape(depth, height, width)
    return np.minimum(np.log1p(counts) / np.log(16.0), 1.0).astype(np.float32)


def in_range(position, config):
    bounds = config["range"]
    return all(bounds[axis] <= position[axis] < bounds[axis + 3] for axis in range(3))


def targets_for(positions, ignored, config, radius):
    width, height, _ = grid_shape(config)
    stride = config["output_stride"]
    width, height = width // stride, height // stride
    heatmap = np.zeros((1, height, width), dtype=np.float32)
    regression = np.zeros((3, height, width), dtype=np.float32)
    regression_mask = np.zeros((1, height, width), dtype=np.float32)
    heatmap_mask = np.ones((1, height, width), dtype=np.float32)
    sizes = np.asarray(config["size"][:2]) * stride
    origin = np.asarray(config["range"][:2])
    for position in ignored:
        if not in_range(position, config):
            continue
        column, row = np.floor((np.asarray(position[:2]) - origin) / sizes).astype(int)
        margin = radius + 2
        heatmap_mask[:, max(0, row - margin):min(height, row + margin + 1), max(0, column - margin):min(width, column + margin + 1)] = 0
    retained = []
    for position in positions:
        if not in_range(position, config):
            continue
        continuous = (np.asarray(position[:2]) - origin) / sizes
        column, row = np.floor(continuous).astype(int)
        if regression_mask[0, row, column]:
            raise ValueError("Two entrance targets collide in one output cell; reduce output resolution")
        lower_row, upper_row = max(0, row - radius), min(height, row + radius + 1)
        lower_column, upper_column = max(0, column - radius), min(width, column + radius + 1)
        rows = np.arange(lower_row, upper_row) - row
        columns = np.arange(lower_column, upper_column) - column
        sigma = max((2 * radius + 1) / 6, 0.5)
        gaussian = np.exp(-(rows[:, None] ** 2 + columns[None, :] ** 2) / (2 * sigma**2))
        region = heatmap[0, lower_row:upper_row, lower_column:upper_column]
        np.maximum(region, gaussian, out=region)
        regression[:, row, column] = [continuous[0] - column, continuous[1] - row, position[2]]
        regression_mask[0, row, column] = 1
        heatmap_mask[0, row, column] = 1
        retained.append(position)
    return {
        "heatmap": heatmap, "regression": regression,
        "regression_mask": regression_mask, "heatmap_mask": heatmap_mask,
        "positions": np.asarray(retained, dtype=np.float32).reshape(-1, 3),
        "ignored_positions": np.asarray([position for position in ignored if in_range(position, config)], dtype=np.float32).reshape(-1, 3),
    }


def sample_paths(root, sample_id):
    sample = Path(sample_id)
    if sample.is_absolute() or ".." in sample.parts:
        raise ValueError(f"Invalid sample identifier: {sample_id}")
    return root / sample.parent / "points" / f"{sample.name}.npz", root / sample.parent / "labels" / f"{sample.name}.json"


class TunnelDataset(Dataset):
    def __init__(self, root, split, config, augment=False):
        self.root = Path(root)
        self.config = config
        self.augment = augment
        self.metadata = json.loads((self.root / "dataset.json").read_text())
        if self.metadata.get("status") != "complete":
            raise ValueError("Refusing to train on an incomplete dataset")
        if self.metadata.get("classes") != ["tunnel"] or self.metadata.get("position_reference") != "entrance_bottom_center":
            raise ValueError("Dataset must use the tunnel class and entrance bottom-center targets")
        self.samples = [line.strip() for line in (self.root / "splits" / f"{split}.txt").read_text().splitlines() if line.strip()]
        if not self.samples or len(self.samples) != len(set(self.samples)):
            raise ValueError(f"Split {split} is empty or contains duplicate samples")
        grid_shape(config["voxel"])

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):
        point_path, label_path = sample_paths(self.root, self.samples[index])
        with np.load(point_path, allow_pickle=False) as archive:
            points = archive["xyz"].astype(np.float32)
        label = json.loads(label_path.read_text())
        if label["frame_id"] != "lidar" or label["units"] != "meters":
            raise ValueError(f"Unexpected frame or units in {label_path}")
        positions = np.asarray([entry["position"] for entry in label["objects"]], dtype=np.float32).reshape(-1, 3)
        ignored = np.asarray([entry["position"] for entry in label.get("ignored", [])], dtype=np.float32).reshape(-1, 3)
        if self.augment:
            augmentation = self.config["augmentation"]
            if augmentation["yaw_rotation"]:
                angle = np.random.uniform(-np.pi, np.pi)
                rotation = np.array([[np.cos(angle), -np.sin(angle), 0], [np.sin(angle), np.cos(angle), 0], [0, 0, 1]], dtype=np.float32)
                points, positions, ignored = points @ rotation.T, positions @ rotation.T, ignored @ rotation.T
            points = points[np.random.random(len(points)) >= augmentation["point_dropout"]]
            points += np.random.normal(0, augmentation["noise_std_m"], points.shape).astype(np.float32)
        target = targets_for(positions, ignored, self.config["voxel"], self.config["target_radius_cells"])
        target["voxels"] = voxelize(points, self.config["voxel"])
        target["sample_id"] = self.samples[index]
        return target


def collate_samples(samples):
    tensor_fields = ("voxels", "heatmap", "regression", "regression_mask", "heatmap_mask")
    batch = {name: torch.from_numpy(np.stack([sample[name] for sample in samples])) for name in tensor_fields}
    for name in ("positions", "ignored_positions", "sample_id"):
        batch[name] = [sample[name] for sample in samples]
    return batch
