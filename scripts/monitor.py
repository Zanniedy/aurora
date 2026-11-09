import argparse
import json
from pathlib import Path
import time


def report(run):
    state_path = run / "state.json"
    if not state_path.exists():
        print(f"Waiting: no training state yet in {run}", flush=True)
        return "waiting"
    state = json.loads(state_path.read_text())
    age = time.time() - state.get("updated_at", time.time())
    print(f"status={state['status']} phase={state.get('phase', '-')} epoch={state.get('epoch', 0)}/{state.get('epochs', '?')} batch={state.get('batch', '-')}/{state.get('batches', '-')} heartbeat_age={age:.0f}s", flush=True)
    history = []
    path = run / "metrics.jsonl"
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                history.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if history:
        latest = history[-1]
        print(json.dumps({"last_completed_epoch": latest["epoch"], "train_loss": latest["train"]["loss"], "validation": latest["val"]}, ensure_ascii=False), flush=True)
        if len(history) >= 5 and all(record["val"]["recall"] == 0 for record in history[-5:]):
            print("WARNING: zero validation recall for five epochs; inspect labels, threshold and optimization.", flush=True)
        if len(history) >= 6 and history[-1]["train"]["loss"] < history[-6]["train"]["loss"] and history[-1]["val"]["loss"] > history[-6]["val"]["loss"] * 1.2:
            print("WARNING: train loss decreased while validation loss rose; possible overfitting, not a diagnosis.", flush=True)
    if age > 300 and state["status"] == "running":
        print("WARNING: heartbeat older than five minutes; check terminal, GPU memory and process. No automatic restart.", flush=True)
    if state.get("error"):
        print(f"ERROR: {state['error']}", flush=True)
    return state["status"]


def main():
    parser = argparse.ArgumentParser(description="Read-only training monitor; never starts or changes training.")
    parser.add_argument("--run", type=Path, default=Path(__file__).resolve().parents[1] / "runs/aurora_tunnel_v1")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=10.0)
    args = parser.parse_args()
    while True:
        status = report(args.run)
        if not args.watch or status in ("complete", "failed", "interrupted"):
            break
        time.sleep(max(args.interval, 1.0))


if __name__ == "__main__":
    main()
