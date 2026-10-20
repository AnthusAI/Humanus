"""Turn editor decisions into per-detector probability calibration.

Raw decision-model probabilities are overconfident. Each accepted, fixed or
dismissed classifier finding is a label: the model's probability and whether
the editor agreed it was a violation. ``calibrate`` fits a monotone map per
detector, which the caller stores on the detector (``calibration``) so that
``check`` thresholds on what editors actually mean.

Isotonic regression needs more labels than Platt scaling; with very few
labels no calibration is returned at all.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

from .contracts import ContractValidationError, validate_payload

MIN_LABELS = 10
MIN_ISOTONIC_LABELS = 50


class FeedbackLabelsValidationError(ContractValidationError):
    """The payload is not a valid ``feedback-labels-v1`` document."""


def calibrate(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Fit a calibration for every detector that has labels (``calibration-v1``)."""
    validate_payload("feedback-labels-v1", payload, FeedbackLabelsValidationError)
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for label in payload["labels"]:
        grouped[(label["policyId"], label["detectorId"])].append(label)

    detectors = []
    for (policy_id, detector_id), labels in sorted(grouped.items()):
        probabilities = [float(label["probability"]) for label in labels]
        outcomes = [bool(label["violates"]) for label in labels]
        entry: dict[str, Any] = {"policyId": policy_id, "detectorId": detector_id, "labels": len(labels)}
        if len(labels) < MIN_LABELS or len(set(outcomes)) < 2:
            entry["note"] = f"not enough labels to calibrate (need {MIN_LABELS}, with both outcomes)"
        elif len(labels) < MIN_ISOTONIC_LABELS:
            a, b = fit_platt(probabilities, outcomes)
            entry["calibration"] = {"method": "platt", "a": round(a, 6), "b": round(b, 6), "labels": len(labels)}
        else:
            points = fit_isotonic(probabilities, outcomes)
            entry["calibration"] = {"method": "isotonic", "points": points, "labels": len(labels)}
        detectors.append(entry)
    return {"schemaVersion": 1, "detectors": detectors}


def apply_calibration(calibration: Mapping[str, Any] | None, probability: float) -> float:
    """Map a raw probability through a stored calibration (identity when there is none)."""
    if not calibration:
        return probability
    if calibration["method"] == "platt":
        return _sigmoid(calibration["a"] * _logit(probability) + calibration["b"])
    points = calibration["points"]
    if probability <= points[0][0]:
        return float(points[0][1])
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if probability <= x1:
            return float(y0 if x1 == x0 else y0 + (y1 - y0) * (probability - x0) / (x1 - x0))
    return float(points[-1][1])


def fit_isotonic(probabilities: Sequence[float], outcomes: Sequence[bool]) -> list[list[float]]:
    """Pool-adjacent-violators; returns increasing (raw, calibrated) knots."""
    pairs = sorted(zip(probabilities, (1.0 if y else 0.0 for y in outcomes)))
    blocks: list[list[float]] = []  # [sum_x, sum_y, count]
    for x, y in pairs:
        blocks.append([x, y, 1.0])
        while len(blocks) > 1 and blocks[-2][1] / blocks[-2][2] >= blocks[-1][1] / blocks[-1][2]:
            x2, y2, n2 = blocks.pop()
            blocks[-1][0] += x2
            blocks[-1][1] += y2
            blocks[-1][2] += n2
    return [[round(sx / n, 6), round(sy / n, 6)] for sx, sy, n in blocks]


def fit_platt(probabilities: Sequence[float], outcomes: Sequence[bool], iterations: int = 100) -> tuple[float, float]:
    """Logistic regression of the outcome on logit(p), by Newton's method."""
    xs = [_logit(p) for p in probabilities]
    ys = [1.0 if y else 0.0 for y in outcomes]
    a, b = 1.0, 0.0
    for _ in range(iterations):
        grad_a = grad_b = h_aa = h_ab = h_bb = 0.0
        for x, y in zip(xs, ys):
            p = _sigmoid(a * x + b)
            w = p * (1 - p) + 1e-9
            grad_a += (p - y) * x
            grad_b += p - y
            h_aa += w * x * x
            h_ab += w * x
            h_bb += w
        det = h_aa * h_bb - h_ab * h_ab
        if abs(det) < 1e-12:
            break
        step_a = (h_bb * grad_a - h_ab * grad_b) / det
        step_b = (h_aa * grad_b - h_ab * grad_a) / det
        a, b = a - step_a, b - step_b
        if abs(step_a) + abs(step_b) < 1e-9:
            break
    return a, b


def expected_calibration_error(probabilities: Iterable[float], outcomes: Iterable[bool], bins: int = 10) -> float:
    """Average |confidence - accuracy| over equal-width probability bins, weighted by size."""
    buckets: list[list[tuple[float, float]]] = [[] for _ in range(bins)]
    total = 0
    for p, y in zip(probabilities, outcomes):
        buckets[min(int(p * bins), bins - 1)].append((p, 1.0 if y else 0.0))
        total += 1
    if not total:
        return 0.0
    error = 0.0
    for bucket in buckets:
        if bucket:
            mean_p = sum(p for p, _ in bucket) / len(bucket)
            mean_y = sum(y for _, y in bucket) / len(bucket)
            error += len(bucket) / total * abs(mean_p - mean_y)
    return error


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x)) if x >= 0 else math.exp(x) / (1 + math.exp(x))
