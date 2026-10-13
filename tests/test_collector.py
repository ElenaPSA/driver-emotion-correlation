from __future__ import annotations

import json

from driver_emotion_correlation.collector import (
    DRIVING_NUMERIC_FIELDS,
    JsonlStore,
    driving_record,
    emotion_record,
)


def test_parse_emotion_publisher_envelope() -> None:
    parsed = emotion_record(
        {
            "name": "DriverEmotionState",
            "data": {
                "frame": 8,
                "timestamp": 0.8,
                "dominant_emotion": "Happy",
                "confidence": 0.91,
            },
        }
    )
    assert parsed == {
        "dominant_emotion": "happy",
        "confidence": 0.91,
        "frame": 8,
        "source_timestamp_s": 0.8,
    }


def test_parse_compact_profiler_diagnostic_and_ignore_non_numeric() -> None:
    parsed = driving_record(
        {
            "DrivingStyleProfile": {
                "timestamp_s": 12.0,
                "speed_mean_kmh": 56.0,
                "style": "balanced",
                "future_signal": 1.0,
                "harsh_brake_count": True,
            }
        }
    )
    assert parsed is not None
    assert parsed["features"] == {"speed_mean_kmh": 56.0}
    assert parsed["source_timestamp_s"] == 12.0
    assert "speed_mean_kmh" in DRIVING_NUMERIC_FIELDS


def test_parse_compact_style_score_without_signal_detail() -> None:
    parsed = driving_record({"DriverDrivingStyle": {"aggressiveness_level": 0.42}})
    assert parsed == {
        "source_timestamp_s": None,
        "features": {"aggressiveness_level": 0.42},
    }


def test_store_appends_separate_json_lines(tmp_path) -> None:
    path = tmp_path / "nested" / "events.jsonl"
    store = JsonlStore(path)
    store.append("emotion", {"dominant_emotion": "happy"})
    store.append("driving", {"features": {"speed_mean_kmh": 30.0}})

    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [record["stream"] for record in records] == ["emotion", "driving"]
    assert all(isinstance(record["received_at"], float) for record in records)
