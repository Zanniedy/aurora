import argparse
import json
from pathlib import Path
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aurora.model import Aurora
from aurora.training import dataset_fingerprint, evaluate, make_loader, write_json_atomic


def main():
    parser = argparse.ArgumentParser(description="Evaluate a trained checkpoint; never updates model weights.")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--split", choices=("val", "test"), default="test")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--score-threshold", type=float)
    args = parser.parse_args()
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    config = checkpoint["config"]
    root = (args.dataset or Path(config["dataset"])).resolve()
    fingerprint = dataset_fingerprint(root)
    if args.score_threshold is not None:
        config["score_threshold"] = args.score_threshold
    device = torch.device(args.device)
    model = Aurora(config).to(device)
    model.load_state_dict(checkpoint["model"])
    result = evaluate(model, make_loader(root, args.split, config, device), config, device)
    result.update(dataset=str(root), split=args.split, checkpoint=str(args.checkpoint.resolve()), dataset_manifest_fingerprint=fingerprint, score_threshold=config["score_threshold"])
    path = args.checkpoint.parent / f"evaluation_{args.split}.json"
    write_json_atomic(path, result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
