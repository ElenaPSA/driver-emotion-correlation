from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from .analysis import analyze_file
from .collector import JsonlStore, collect
from .simulation import generate_session

log = logging.getLogger("driver_emotion_correlation")


def _collect(args: argparse.Namespace) -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    store = JsonlStore(args.data)
    try:
        asyncio.run(
            collect(
                store,
                mqtt_host=args.mqtt_host,
                mqtt_port=args.mqtt_port,
                emotion_topic=args.emotion_topic,
                ws_host=args.ws_host,
                ws_port=args.ws_port,
            )
        )
    except KeyboardInterrupt:
        log.info("Collection stopped")
    except OSError as exc:
        log.error("Could not start collector: %s", exc)
        return 1
    return 0


def _analyze(args: argparse.Namespace) -> int:
    try:
        report = analyze_file(
            args.data,
            bucket_seconds=args.bucket_seconds,
            lag_seconds=args.lag_seconds,
            max_gap_seconds=args.max_gap_seconds,
            min_pairs=args.min_pairs,
            min_confidence=args.min_confidence,
        )
    except (OSError, ValueError) as exc:
        log.error("Could not analyze %s: %s", args.data, exc)
        return 1

    rendered = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Analysis saved to {args.output}")
    else:
        print(rendered)
    return 0


def _simulate(args: argparse.Namespace) -> int:
    try:
        count = generate_session(args.output, seconds=args.seconds, seed=args.seed)
    except (OSError, ValueError) as exc:
        log.error("Could not generate simulation: %s", exc)
        return 1
    print(
        f"Wrote {count} synthetic events ({args.seconds} seconds) to {args.output}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="driver-emotion-correlation",
        description="Collect and analyze emotion/driving-signal associations.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    collector = commands.add_parser("collect", help="collect both streams in real time")
    collector.add_argument("--data", type=Path, default=Path("outputs/session.jsonl"))
    collector.add_argument("--mqtt-host", default="127.0.0.1")
    collector.add_argument("--mqtt-port", type=int, default=1883)
    collector.add_argument(
        "--emotion-topic", default="telemetry/DriverEmotionState"
    )
    collector.add_argument("--ws-host", default="127.0.0.1")
    collector.add_argument("--ws-port", type=int, default=8765)

    analyzer = commands.add_parser("analyze", help="rank signal/emotion associations")
    analyzer.add_argument("data", type=Path, nargs="?", default=Path("outputs/session.jsonl"))
    analyzer.add_argument("--bucket-seconds", type=float, default=1.0)
    analyzer.add_argument(
        "--lag-seconds",
        type=float,
        default=0.0,
        help="compare driving samples this many seconds before each emotion bucket",
    )
    analyzer.add_argument("--max-gap-seconds", type=float, default=2.0)
    analyzer.add_argument("--min-pairs", type=int, default=10)
    analyzer.add_argument("--min-confidence", type=float, default=0.0)
    analyzer.add_argument("--output", type=Path)

    simulator = commands.add_parser(
        "simulate", help="generate a deterministic linked emotion/driving session"
    )
    simulator.add_argument(
        "--output", type=Path, default=Path("examples/simulated_session.jsonl")
    )
    simulator.add_argument("--seconds", type=int, default=240)
    simulator.add_argument("--seed", type=int, default=2026)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-7s %(message)s",
    )
    if args.command == "collect":
        return _collect(args)
    if args.command == "analyze":
        return _analyze(args)
    if args.command == "simulate":
        return _simulate(args)
    parser.error(f"Unknown command: {args.command}")
    return 2
