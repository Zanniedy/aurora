import hashlib
import json
from pathlib import Path
import random
import time

import numpy as np
import torch
from torch.utils.data import DataLoader

from aurora.data import TunnelDataset, collate_samples
from aurora.metrics import PositionMetrics
from aurora.model import decode, detection_loss


def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed % 2**32)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def seed_worker(worker_id):
    seed = torch.initial_seed() % 2**32
    random.seed(seed)
    np.random.seed(seed)


def dataset_fingerprint(root):
    root = Path(root)
    digest = hashlib.sha256((root / "dataset.json").read_bytes())
    groups = {}
    for split in ("train", "val", "test"):
        contents = (root / "splits" / f"{split}.txt").read_bytes()
        digest.update(contents)
        samples = [line.strip() for line in contents.decode().splitlines() if line.strip()]
        if not samples or len(samples) != len(set(samples)):
            raise ValueError(f"Invalid {split} manifest")
        groups[split] = {str(Path(sample).parent) for sample in samples}
    if groups["train"] & groups["val"] or groups["train"] & groups["test"] or groups["val"] & groups["test"]:
        raise ValueError("Sequence leakage between train/val/test")
    return digest.hexdigest()


def make_loader(root, split, config, device, augment=False, seed=None):
    dataset = TunnelDataset(root, split, config, augment=augment)
    generator = torch.Generator().manual_seed(config["seed"] if seed is None else seed)
    return DataLoader(
        dataset, batch_size=config["batch_size"], shuffle=augment,
        num_workers=config["workers"], collate_fn=collate_samples,
        pin_memory=device.type == "cuda", worker_init_fn=seed_worker, generator=generator,
    )


def move_batch(batch, device):
    return {name: value.to(device, non_blocking=True) if torch.is_tensor(value) else value for name, value in batch.items()}


@torch.no_grad()
def evaluate(model, loader, config, device):
    model.eval()
    metrics = PositionMetrics(config["match_distance_m"])
    loss_sum, frames = 0.0, 0
    started = time.monotonic()
    for batch in loader:
        batch = move_batch(batch, device)
        prediction = model(batch["voxels"])
        losses = detection_loss(prediction, batch, config["position_loss_weight"])
        if not torch.isfinite(losses["loss"]):
            raise FloatingPointError("Non-finite validation loss")
        predictions = decode(prediction, config)
        for detections, positions, ignored in zip(predictions, batch["positions"], batch["ignored_positions"]):
            metrics.update(detections, positions, ignored)
        batch_size = len(predictions)
        loss_sum += losses["loss"].item() * batch_size
        frames += batch_size
    result = metrics.summary()
    result["loss"] = loss_sum / max(frames, 1)
    result["elapsed_s_including_io"] = time.monotonic() - started
    return result


def write_json_atomic(path, content):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(content, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def save_checkpoint(path, content):
    path = Path(path)
    temporary = path.with_suffix(".tmp")
    torch.save(content, temporary)
    temporary.replace(path)
