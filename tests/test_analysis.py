from __future__ import annotations

import pytest

from driver_emotion_correlation.analysis import analyze_events, spearman


def _events(labels: list[str]) -> list[dict]:
    events = []
    start = 1_700_000_000.0
    for index, label in enumerate(labels):
        received_at = start + index
        events.append(
            {
                "received_at": received_at + 0.1,
                "stream": "emotion",
                "data": {"dominant_emotion": label, "confidence": 0.9},
            }
        )
        events.append(
            {
                "received_at": received_at + 0.2,
                "stream": "driving",
                "data": {
                    "features": {
                        "speed_mean_kmh": float(index),
                        "harsh_brake_per_100km": 10.0 if index == 9 else 0.0,
                    }
                },
            }
        )
    return events


def test_spearman_handles_ties_and_perfect_order() -> None:
    assert spearman([1, 2, 2, 4], [10, 20, 20, 40]) == pytest.approx(1.0)
    assert spearman([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)


def test_associations_rank_driving_signals_for_emotion_and_changes() -> None:
    labels = ["calm"] * 10 + ["stressed"] * 10
    report = analyze_events(_events(labels), min_pairs=5)

    assert report["matched_buckets"] == 20
    calm = report["by_emotion"]["calm"]
    assert calm[0]["signal"] == "speed_mean_kmh"
    assert calm[0]["spearman_rho"] < 0
    assert report["emotion_transition"]
    assert report["emotion_transition"][0]["signal"] == (
        "abs_change_harsh_brake_per_100km"
    )
    assert report["emotion_transition_direction"][0]["signal"] == (
        "change_harsh_brake_per_100km"
    )
    transition_strengths = [
        item["absolute_rho"] for item in report["emotion_transition"]
    ]
    assert transition_strengths == sorted(transition_strengths, reverse=True)
    assert any("not evidence of causation" in item for item in report["warnings"])


def test_analyze_excludes_low_confidence_emotion_and_unmatched_times() -> None:
    events = _events(["calm", "stressed", "calm"])
    events[0]["data"]["confidence"] = 0.2
    events = [event for event in events if not (
        event["stream"] == "driving" and event["received_at"] > 1_700_000_001.0
    )]
    report = analyze_events(
        events, min_pairs=2, min_confidence=0.5, max_gap_seconds=0.1
    )
    assert report["matched_buckets"] == 0


def test_spearman_returns_none_for_constant_values() -> None:
    assert spearman([1.0, 1.0], [1.0, 2.0]) is None


def test_synthetic_data_is_explicitly_flagged_in_report() -> None:
    events = _events(["calm", "stressed"] * 6)
    for event in events:
        event["synthetic"] = True

    report = analyze_events(events, min_pairs=2)

    assert "Synthetic simulation input" in report["warnings"][0]
