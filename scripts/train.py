import argparse
import json
import os
from pathlib import Path
import sys
import time
import traceback

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aurora.model import Aurora, decode, detection_loss
from aurora.training import dataset_fingerprint, evaluate, make_loader, move_batch, save_checkpoint, seed_everything, write_json_atomic


def main():
    parser = argparse.ArgumentParser(description="Explicitly start Aurora training, or inspect a batch without training using --dry-run.")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/train_tunnel.json")
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--workers", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--dry-run", action="store_true")
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--resume", type=Path)
    sources.add_argument("--finetune", type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    for name in ("epochs", "workers", "batch_size"):
        if getattr(args, name) is not None:
            config[name] = getattr(args, name)
    root = (args.dataset or ROOT / config["dataset"]).resolve()
    run = (args.run or ROOT / config["run"]).resolve()
    config["dataset"], config["run"] = str(root), str(run)
    if config["epochs"] < 1 or config["batch_size"] < 1 or config["workers"] < 0:
        parser.error("epochs and batch size must be positive; workers must be nonnegative")
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        parser.error("CUDA is unavailable; activate isaaclab on the host or pass --device cpu")
    fingerprint = dataset_fingerprint(root)
    seed_everything(config["seed"])
    model = Aurora(config).to(device)
    checkpoint = None
    if args.resume or args.finetune:
        checkpoint = torch.load(args.resume or args.finetune, map_location="cpu", weights_only=True)
        for key in ("voxel", "model"):
            if checkpoint["config"][key] != config[key]:
                raise ValueError(f"Checkpoint {key} settings do not match")
        model.load_state_dict(checkpoint["model"])
    if args.dry_run:
        loader = make_loader(root, "train", config, device, augment=False)
        batch = move_batch(next(iter(loader)), device)
        model.eval()
        with torch.no_grad():
            prediction = model(batch["voxels"])
            losses = detection_loss(prediction, batch, config["position_loss_weight"])
            if not all(torch.isfinite(value) for value in losses.values()):
                raise FloatingPointError("Dry-run produced a non-finite loss")
            detections = decode(prediction, config)
        print(json.dumps({
            "mode": "dry_run_NO_optimizer_NO_training_NO_checkpoint", "voxel_shape": list(batch["voxels"].shape),
            "heatmap_shape": list(prediction["heatmap"].shape),
            "parameters": sum(parameter.numel() for parameter in model.parameters()),
            "losses_untrained_not_a_quality_metric": {name: value.item() for name, value in losses.items()},
            "decoded_frames": len(detections),
        }, indent=2))
        return
    if run.exists() and any(run.iterdir()) and not args.resume:
        raise FileExistsError(f"Run already exists: {run}. Use --resume explicitly or choose a new --run.")
    if args.resume and checkpoint["dataset_manifest_fingerprint"] != fingerprint:
        raise ValueError("Resume dataset differs from checkpoint; use --finetune in a new run instead")
    if args.resume and checkpoint["config"]["epochs"] != config["epochs"]:
        raise ValueError("Resume must keep the original epoch schedule; use --finetune for a new schedule")
    if args.resume:
        for key in ("seed", "batch_size", "learning_rate", "weight_decay", "augmentation", "target_radius_cells", "position_loss_weight", "score_threshold", "match_distance_m", "amp"):
            if checkpoint["config"][key] != config[key]:
                raise ValueError(f"Resume must preserve {key}; use --finetune for a new experiment")
    run.mkdir(parents=True, exist_ok=True)
    write_json_atomic(run / "config.json", config)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=config["epochs"])
    amp_enabled = config["amp"] and device.type == "cuda"
    amp_dtype = torch.bfloat16 if amp_enabled and torch.cuda.is_bf16_supported() else torch.float16
    scaler = torch.amp.GradScaler("cuda", enabled=amp_enabled and amp_dtype == torch.float16)
    start_epoch, global_step, best_f1, best_error = 0, 0, -1.0, None
    if args.resume:
        optimizer.load_state_dict(checkpoint["optimizer"])
        scheduler.load_state_dict(checkpoint["scheduler"])
        scaler.load_state_dict(checkpoint["scaler"])
        start_epoch = checkpoint["epoch"] + 1
        global_step = checkpoint["global_step"]
        best_f1, best_error = checkpoint["best_f1"], checkpoint["best_error"]
        if start_epoch >= config["epochs"]:
            raise ValueError("Checkpoint already completed the configured epochs")
    from torch.utils.tensorboard import SummaryWriter

    writer = SummaryWriter(str(run / "tensorboard"), purge_step=start_epoch if args.resume else None)
    state = {"status": "running", "pid": os.getpid(), "run": str(run), "epoch": start_epoch, "epochs": config["epochs"], "global_step": global_step}
    validation_loader = make_loader(root, "val", config, device)
    try:
        for epoch in range(start_epoch, config["epochs"]):
            seed_everything(config["seed"] + epoch)
            loader = make_loader(root, "train", config, device, augment=True, seed=config["seed"] + epoch)
            model.train()
            sums = {name: 0.0 for name in ("loss", "heatmap_loss", "position_loss")}
            frames = 0
            epoch_start = time.monotonic()
            for batch_index, batch in enumerate(loader):
                batch = move_batch(batch, device)
                optimizer.zero_grad(set_to_none=True)
                with torch.autocast(device_type=device.type, dtype=amp_dtype, enabled=amp_enabled):
                    prediction = model(batch["voxels"])
                    losses = detection_loss(prediction, batch, config["position_loss_weight"])
                if not torch.isfinite(losses["loss"]):
                    raise FloatingPointError(f"Non-finite loss at epoch {epoch + 1}, batch {batch_index}")
                scaler.scale(losses["loss"]).backward()
                scaler.unscale_(optimizer)
                norm = torch.nn.utils.clip_grad_norm_(model.parameters(), config["gradient_clip"])
                if not torch.isfinite(norm):
                    raise FloatingPointError("Non-finite gradient norm")
                scaler.step(optimizer)
                scaler.update()
                batch_size = len(batch["sample_id"])
                frames += batch_size
                global_step += 1
                for name, value in losses.items():
                    sums[name] += value.item() * batch_size
                if batch_index % 10 == 0 or batch_index == len(loader) - 1:
                    state.update(status="running", phase="train", epoch=epoch + 1, batch=batch_index + 1, batches=len(loader), global_step=global_step, last_loss=losses["loss"].item(), updated_at=time.time())
                    if device.type == "cuda":
                        state["cuda_allocated_mb"] = torch.cuda.memory_allocated(device) / 1024**2
                        state["cuda_peak_allocated_mb"] = torch.cuda.max_memory_allocated(device) / 1024**2
                    write_json_atomic(run / "state.json", state)
                    print(f"epoch {epoch + 1}/{config['epochs']} batch {batch_index + 1}/{len(loader)} loss={losses['loss'].item():.4f}", flush=True)
            state.update(phase="validation", updated_at=time.time())
            write_json_atomic(run / "state.json", state)
            validation = evaluate(model, validation_loader, config, device)
            record = {
                "epoch": epoch + 1, "global_step": global_step, "timestamp": time.time(),
                "train": {name: value / frames for name, value in sums.items()}, "val": validation,
                "learning_rate": optimizer.param_groups[0]["lr"], "epoch_seconds": time.monotonic() - epoch_start,
            }
            with (run / "metrics.jsonl").open("a") as stream:
                stream.write(json.dumps(record, allow_nan=False) + "\n")
            for name, value in record["train"].items():
                writer.add_scalar(f"train/{name}", value, epoch + 1)
            for name, value in validation.items():
                if isinstance(value, (int, float)):
                    writer.add_scalar(f"val/{name}", value, epoch + 1)
            writer.flush()
            error = validation["position_mae_m"]
            is_best = validation["f1"] > best_f1 or (
                validation["f1"] == best_f1 and error is not None and (best_error is None or error < best_error)
            )
            if is_best:
                best_f1, best_error = validation["f1"], error
            scheduler.step()
            saved = {
                "schema_version": "1.0", "model": model.state_dict(), "optimizer": optimizer.state_dict(),
                "scheduler": scheduler.state_dict(), "scaler": scaler.state_dict(), "config": config,
                "epoch": epoch, "global_step": global_step, "best_f1": best_f1, "best_error": best_error,
                "dataset_manifest_fingerprint": fingerprint,
            }
            save_checkpoint(run / "last.pt", saved)
            if is_best:
                save_checkpoint(run / "best.pt", saved)
            state.update(last_completed_epoch=epoch + 1, best_f1=best_f1, updated_at=time.time())
            write_json_atomic(run / "state.json", state)
            print(json.dumps(record, ensure_ascii=False), flush=True)
        state.update(status="complete", phase="finished", updated_at=time.time())
    except KeyboardInterrupt:
        state.update(status="interrupted", error="User interrupted; last.pt contains the last completed epoch", updated_at=time.time())
        raise
    except Exception as error:
        state.update(status="failed", error=str(error), traceback=traceback.format_exc(), updated_at=time.time())
        raise
    finally:
        write_json_atomic(run / "state.json", state)
        writer.close()


if __name__ == "__main__":
    main()
