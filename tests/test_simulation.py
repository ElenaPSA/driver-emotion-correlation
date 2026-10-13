from __future__ import annotations

import json
import sys

import pytest

from driver_emotion_correlation.cli import main
from driver_emotion_correlation.simulation import generate_session


def test_simulation_generates_deterministic_paired_streams(tmp_path) -> None:
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    assert generate_session(first, seconds=40, seed=7) == 80
    assert generate_session(second, seconds=40, seed=7) == 80
    assert first.read_bytes() == second.read_bytes()

    events = [json.loads(line) for line in first.read_text().splitlines()]
    assert {event["stream"] for event in events} == {"emotion", "driving"}
    assert all(event["synthetic"] is True for event in events)
    assert {
        event["data"]["dominant_emotion"]
        for event in events
        if event["stream"] == "emotion"
    } == {"neutral", "happy", "stressed", "angry"}


def test_simulation_rejects_sessions_too_short_for_all_styles(tmp_path) -> None:
    with pytest.raises(ValueError, match="at least 8"):
        generate_session(tmp_path / "too_short.jsonl", seconds=7)


def test_main_simulate_and_analyze_commands_run_end_to_end(
    tmp_path, monkeypatch, capsys
) -> None:
    session = tmp_path / "session.jsonl"
    report = tmp_path / "report.json"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "driver-emotion-correlation",
            "simulate",
            "--output",
            str(session),
            "--seconds",
            "40",
            "--seed",
            "2026",
        ],
    )
    assert main() == 0
    assert "Wrote 80 synthetic events" in capsys.readouterr().out

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "driver-emotion-correlation",
            "analyze",
            str(session),
            "--min-pairs",
            "5",
            "--output",
            str(report),
        ],
    )
    assert main() == 0
    assert "Analysis saved to" in capsys.readouterr().out
    analysis = json.loads(report.read_text(encoding="utf-8"))
    assert analysis["matched_buckets"] == 40
    assert analysis["by_emotion"]
    assert "Synthetic simulation input" in analysis["warnings"][0]
