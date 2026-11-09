from collections import Counter
import json
from pathlib import Path


def allocate_groups(buckets, total):
    sizes = {key: len(groups) for key, groups in buckets.items()}
    capacities = {key: max(0, size - 1) for key, size in sizes.items()}
    if sum(capacities.values()) < total:
        raise ValueError("Too few independent groups to preserve training examples in each stratum")
    desired = {key: total * size / max(sum(sizes.values()), 1) for key, size in sizes.items()}
    allocation = {key: 0 for key in buckets}
    for _ in range(total):
        candidates = [key for key in buckets if allocation[key] < capacities[key]]
        chosen = max(candidates, key=lambda key: (desired[key] - allocation[key], key))
        allocation[chosen] += 1
    selected = []
    for key, count in allocation.items():
        selected.extend(buckets[key][:count])
        del buckets[key][:count]
    return selected


def grouped_splits(root, sequences, fractions, rng):
    result = {"train": [], "val": [], "test": []}
    for negative, groups in sequences.items():
        buckets = {}
        for group in groups:
            if negative:
                key = "negative"
            else:
                appearances = Counter()
                for sample_id in group:
                    sample = Path(sample_id)
                    label = json.loads((root / sample.parent / "labels" / f"{sample.name}.json").read_text())
                    appearances.update(f"{entry['instance_id']}/{entry['entrance_id']}" for entry in label["objects"])
                if not appearances:
                    raise ValueError("Positive sequence has no valid entrance labels")
                key = appearances.most_common(1)[0][0]
            buckets.setdefault(key, []).append(group)
        for bucket in buckets.values():
            rng.shuffle(bucket)
        validation_count = max(1, round(len(groups) * fractions[1]))
        test_count = max(1, round(len(groups) * fractions[2]))
        validation = allocate_groups(buckets, validation_count)
        testing = allocate_groups(buckets, test_count)
        training = [group for bucket in buckets.values() for group in bucket]
        for name, selected in (("train", training), ("val", validation), ("test", testing)):
            result[name].extend(sample for group in selected for sample in group)
    return result
