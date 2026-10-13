from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

BASE_RECEIPT_TIME = 1_782_000_000.0

_SCENARIOS = (
    {
        "style": "calm",
        "emotion": "neutral",
        "aggressiveness_level": 0.12,
        "style_index": 12.0,
        "speed_mean_kmh": 45.0,
        "harsh_accel_per_100km": 0.3,
        "harsh_brake_per_100km": 0.4,
        "hard_corner_per_100km": 0.2,
        "speeding_distance_share": 0.02,
        "tailgating_time_share": 0.01,
        "jerk_mean_mps3": 0.15,
    },
    {
        "style": "balanced",
        "emotion": "happy",
        "aggressiveness_level": 0.35,
        "style_index": 35.0,
        "speed_mean_kmh": 58.0,
        "harsh_accel_per_100km": 1.5,
        "harsh_brake_per_100km": 1.8,
        "hard_corner_per_100km": 1.2,
        "speeding_distance_share": 0.08,
        "tailgating_time_share": 0.04,
        "jerk_mean_mps3": 0.35,
    },
    {
        "style": "assertive",
        "emotion": "stressed",
        "aggressiveness_level": 0.67,
        "style_index": 67.0,
        "speed_mean_kmh": 73.0,
        "harsh_accel_per_100km": 5.0,
        "harsh_brake_per_100km": 7.0,
        "hard_corner_per_100km": 4.5,
        "speeding_distance_share": 0.3,
        "tailgating_time_share": 0.16,
        "jerk_mean_mps3": 0.9,
    },
    {
        "style": "aggressive",
        "emotion": "angry",
        "aggressiveness_level": 0.91,
        "style_index": 91.0,
        "speed_mean_kmh": 88.0,
        "harsh_accel_per_100km": 11.0,
        "harsh_brake_per_100km": 15.0,
        "hard_corner_per_100km": 9.0,
        "speeding_distance_share": 0.62,
        "tailgating_time_share": 0.38,
        "jerk_mean_mps3": 1.8,
    },
)


def _jitter(rng: random.Random, value: float, fraction: float = 0.035) -> float:
    return round(value * (1.0 + rng.uniform(-fraction, fraction)), 5)


def generate_session(
    output_path: Path,
    *,
    seconds: int = 240,
    seed: int = 2026,
) -> int:
    """Write a deterministic, explicitly synthetic paired-stream session.

    Each second contains one emotion detection and one detailed driving profile.
    Four emotion/style scenarios repeat in short blocks and are deliberately
    coupled; this fixture verifies collection/analysis behavior, not real-world
    causality.
    """
    if seconds < len(_SCENARIOS) * 2:
        raise ValueError(
            f"seconds must be at least {len(_SCENARIOS) * 2} "
            "to include every simulated style"
        )
    rng = random.Random(seed)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with output_path.open("w", encoding="utf-8", newline="\n") as output:
        for second in range(seconds):
            block_seconds = max(2, seconds // 12)
            scenario = _SCENARIOS[(second // block_seconds) % len(_SCENARIOS)]
            received_at = BASE_RECEIPT_TIME + second
            emotion: dict[str, Any] = {
                "dominant_emotion": scenario["emotion"],
                "confidence": round(rng.uniform(0.84, 0.99), 4),
                "frame": second * 10 + 1,
                "source_timestamp_s": float(second),
            }
            driving_values = {
                key: _jitter(rng, value)
                for key, value in scenario.items()
                if isinstance(value, float)
            }
            driving_values["speed_max_kmh"] = _jitter(
                rng, float(scenario["speed_mean_kmh"]) * 1.18
            )
            driving_values["headway_mean_s"] = _jitter(
                rng,
                max(0.65, 2.6 - float(scenario["aggressiveness_level"]) * 1.8),
                fraction=0.025,
            )
            driving_values["jerk_max_mps3"] = _jitter(
                rng, float(scenario["jerk_mean_mps3"]) * 2.2
            )
            driving_values["style"] = scenario["style"]

            entries = (
                ("emotion", received_at + 0.25, emotion),
                (
                    "driving",
                    received_at + 0.75,
                    {
                        "source_timestamp_s": float(second),
                        "features": driving_values,
                    },
                ),
            )
            for stream, timestamp, data in entries:
                event = {
                    "received_at": timestamp,
                    "stream": stream,
                    "data": data,
                    "synthetic": True,
                }
                output.write(
                    json.dumps(
                        event,
                        ensure_ascii=False,
                        allow_nan=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                written += 1
    return written
