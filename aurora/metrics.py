import numpy as np


class PositionMetrics:
    def __init__(self, distance_threshold):
        self.threshold = distance_threshold
        self.true_positive = 0
        self.false_positive = 0
        self.false_negative = 0
        self.errors = []
        self.frames = 0
        self.negative_frames = 0
        self.false_positive_negative_frames = 0

    def update(self, predictions, targets, ignored):
        self.frames += 1
        unmatched = set(range(len(targets)))
        false_positives = 0
        for prediction in sorted(predictions, key=lambda entry: entry["score"], reverse=True):
            position = np.asarray(prediction["position"])
            if unmatched:
                choices = sorted(unmatched)
                distances = np.linalg.norm(targets[choices] - position, axis=1)
                nearest = int(np.argmin(distances))
                if distances[nearest] <= self.threshold:
                    unmatched.remove(choices[nearest])
                    self.true_positive += 1
                    self.errors.append(float(distances[nearest]))
                    continue
            if len(ignored) and np.min(np.linalg.norm(ignored - position, axis=1)) <= self.threshold:
                continue
            self.false_positive += 1
            false_positives += 1
        self.false_negative += len(unmatched)
        if not len(targets):
            self.negative_frames += 1
            self.false_positive_negative_frames += int(false_positives > 0)

    def summary(self):
        precision = self.true_positive / max(self.true_positive + self.false_positive, 1)
        recall = self.true_positive / max(self.true_positive + self.false_negative, 1)
        return {
            "precision": precision, "recall": recall,
            "f1": 2 * precision * recall / max(precision + recall, 1e-12),
            "true_positive": self.true_positive, "false_positive": self.false_positive,
            "false_negative": self.false_negative,
            "position_mae_m": float(np.mean(self.errors)) if self.errors else None,
            "position_p95_m": float(np.percentile(self.errors, 95)) if self.errors else None,
            "negative_frame_false_positive_rate": self.false_positive_negative_frames / max(self.negative_frames, 1),
            "frames": self.frames, "match_distance_m": self.threshold,
        }
