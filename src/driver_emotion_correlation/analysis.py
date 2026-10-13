from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


def load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
            if (
                isinstance(event, dict)
                and event.get("stream") in {"emotion", "driving"}
                and isinstance(event.get("received_at"), (int, float))
                and isinstance(event.get("data"), dict)
            ):
                events.append(event)
    return events


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = mean(left)
    right_mean = mean(right)
    left_delta = [value - left_mean for value in left]
    right_delta = [value - right_mean for value in right]
    left_ss = sum(value * value for value in left_delta)
    right_ss = sum(value * value for value in right_delta)
    if left_ss == 0 or right_ss == 0:
        return None
    return sum(a * b for a, b in zip(left_delta, right_delta)) / math.sqrt(
        left_ss * right_ss
    )


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position + 1
        while end < len(order) and values[order[end]] == values[order[position]]:
            end += 1
        average_rank = (position + 1 + end) / 2.0
        for item in order[position:end]:
            ranks[item] = average_rank
        position = end
    return ranks


def spearman(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    return _pearson(_ranks(left), _ranks(right))


def _bucket_events(
    events: list[dict[str, Any]], bucket_seconds: float
) -> tuple[dict[int, list[dict[str, Any]]], dict[int, list[dict[str, Any]]]]:
    emotions: dict[int, list[dict[str, Any]]] = defaultdict(list)
    driving: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        bucket = math.floor(float(event["received_at"]) / bucket_seconds)
        if event["stream"] == "emotion":
            data = event["data"]
            label = data.get("dominant_emotion")
            confidence = data.get("confidence")
            if isinstance(label, str):
                emotions[bucket].append(
                    {
                        "label": label.lower(),
                        "confidence": (
                            float(confidence)
                            if isinstance(confidence, (int, float))
                            and not isinstance(confidence, bool)
                            and math.isfinite(float(confidence))
                            else 0.0
                        ),
                    }
                )
        else:
            features = event["data"].get("features")
            if isinstance(features, dict):
                driving[bucket].append(features)
    return emotions, driving


def _target_driving_bucket(
    target_bucket: int,
    driving_buckets: list[int],
    bucket_seconds: float,
    lag_seconds: float,
    max_gap_seconds: float,
) -> int | None:
    target_time = (target_bucket + 0.5) * bucket_seconds - lag_seconds
    closest = min(
        driving_buckets,
        key=lambda bucket: abs((bucket + 0.5) * bucket_seconds - target_time),
    )
    if abs((closest + 0.5) * bucket_seconds - target_time) > max_gap_seconds:
        return None
    return closest


def _ranked_correlations(
    rows: list[dict[str, Any]],
    target: str,
    min_pairs: int,
) -> list[dict[str, Any]]:
    features = sorted({key for row in rows for key in row["features"]})
    result = []
    for feature in features:
        pairs = [
            (row["features"][feature], float(row["targets"][target]))
            for row in rows
            if feature in row["features"]
        ]
        if len(pairs) < min_pairs:
            continue
        coefficient = spearman(
            [pair[0] for pair in pairs], [pair[1] for pair in pairs]
        )
        if coefficient is None:
            continue
        result.append(
            {
                "signal": feature,
                "spearman_rho": round(coefficient, 6),
                "absolute_rho": round(abs(coefficient), 6),
                "pairs": len(pairs),
            }
        )
    return sorted(result, key=lambda item: (-item["absolute_rho"], item["signal"]))


def analyze_events(
    events: list[dict[str, Any]],
    *,
    bucket_seconds: float = 1.0,
    lag_seconds: float = 0.0,
    max_gap_seconds: float = 2.0,
    min_pairs: int = 10,
    min_confidence: float = 0.0,
) -> dict[str, Any]:
    if bucket_seconds <= 0 or max_gap_seconds < 0:
        raise ValueError("bucket_seconds must be positive and max_gap_seconds nonnegative")
    if min_pairs < 2:
        raise ValueError("min_pairs must be at least 2")
    if lag_seconds < 0:
        raise ValueError("lag_seconds must be nonnegative")
    if not 0.0 <= min_confidence <= 1.0:
        raise ValueError("min_confidence must be between 0 and 1")

    emotion_buckets, driving_buckets = _bucket_events(events, bucket_seconds)
    driving_times = sorted(driving_buckets)
    if not emotion_buckets or not driving_times:
        return {
            "method": "Spearman rank association on receipt-time buckets",
            "bucket_seconds": bucket_seconds,
            "lag_seconds": lag_seconds,
            "matched_buckets": 0,
            "warning": "Collect both streams before analyzing.",
            "by_emotion": {},
            "emotion_transition": [],
        }

    matched: list[dict[str, Any]] = []
    for emotion_bucket in sorted(emotion_buckets):
        valid = [
            item
            for item in emotion_buckets[emotion_bucket]
            if item["confidence"] >= min_confidence
        ]
        if not valid:
            continue
        labels = Counter(item["label"] for item in valid)
        label = sorted(labels.items(), key=lambda item: (-item[1], item[0]))[0][0]
        drive_bucket = _target_driving_bucket(
            emotion_bucket,
            driving_times,
            bucket_seconds,
            lag_seconds,
            max_gap_seconds,
        )
        if drive_bucket is None:
            continue
        features: dict[str, list[float]] = defaultdict(list)
        for sample in driving_buckets[drive_bucket]:
            for key, value in sample.items():
                if (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isfinite(float(value))
                ):
                    features[key].append(float(value))
        averaged = {key: mean(values) for key, values in features.items()}
        if averaged:
            matched.append(
                {
                    "bucket": emotion_bucket,
                    "emotion": label,
                    "features": averaged,
                }
            )

    labels = sorted({row["emotion"] for row in matched})
    targets_by_emotion: dict[str, list[dict[str, Any]]] = {}
    for label in labels:
        rows = [
            {
                "features": row["features"],
                "targets": {"emotion": float(row["emotion"] == label)},
            }
            for row in matched
        ]
        targets_by_emotion[label] = _ranked_correlations(rows, "emotion", min_pairs)

    matched.sort(key=lambda row: row["bucket"])
    rows_with_transition_magnitude: list[dict[str, Any]] = []
    rows_with_transition_direction: list[dict[str, Any]] = []
    previous_label: str | None = None
    previous_bucket: int | None = None
    previous_features: dict[str, float] | None = None
    for row in matched:
        if (
            previous_label is not None
            and previous_bucket is not None
            and row["bucket"] == previous_bucket + 1
            and previous_features is not None
        ):
            shared_features = row["features"].keys() & previous_features.keys()
            changes = {
                key: row["features"][key] - previous_features[key]
                for key in shared_features
            }
            rows_with_transition_magnitude.append(
                {
                    "features": {
                        f"abs_change_{key}": abs(value)
                        for key, value in changes.items()
                    },
                    "targets": {
                        "transition": float(row["emotion"] != previous_label)
                    },
                }
            )
            rows_with_transition_direction.append(
                {
                    "features": {
                        f"change_{key}": value for key, value in changes.items()
                    },
                    "targets": {
                        "transition": float(row["emotion"] != previous_label)
                    },
                }
            )
        previous_label = row["emotion"]
        previous_bucket = row["bucket"]
        previous_features = row["features"]

    state_warning = (
        "The profiler's score fields are session-level aggregates, not raw "
        "per-frame measurements; interpret their associations as coarse."
    )
    if any(row["emotion"] == "unknown" for row in matched):
        state_warning += " Emotion labels marked 'unknown' were included."

    warnings = [
        "Associations are not evidence of causation or proof that a signal "
        "caused an emotion change.",
        state_warning,
        "Repeated time buckets are not statistically independent; use the "
        "ranking for exploration, not clinical or safety decisions.",
    ]
    if any(event.get("synthetic") is True for event in events):
        warnings.insert(
            0,
            "Synthetic simulation input: the relationships were deliberately "
            "encoded and are not evidence about real drivers.",
        )

    return {
        "method": "Spearman rank association on receipt-time buckets",
        "bucket_seconds": bucket_seconds,
        "lag_seconds": lag_seconds,
        "max_gap_seconds": max_gap_seconds,
        "min_confidence": min_confidence,
        "matched_buckets": len(matched),
        "by_emotion": targets_by_emotion,
        "emotion_transition": _ranked_correlations(
            rows_with_transition_magnitude, "transition", min_pairs
        ),
        "emotion_transition_direction": _ranked_correlations(
            rows_with_transition_direction, "transition", min_pairs
        ),
        "warnings": warnings,
    }


def analyze_file(path: Path, **options: Any) -> dict[str, Any]:
    return analyze_events(load_events(path), **options)
