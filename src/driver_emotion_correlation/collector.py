from __future__ import annotations

import asyncio
import json
import logging
import math
import threading
import time
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
import websockets

log = logging.getLogger(__name__)

DRIVING_NUMERIC_FIELDS = frozenset(
    {
        "aggressiveness_level",
        "style_index",
        "recent_style_index",
        "pace",
        "smoothness",
        "cornering",
        "following",
        "harsh_accel_count",
        "harsh_brake_count",
        "hard_corner_count",
        "harsh_accel_per_100km",
        "harsh_brake_per_100km",
        "hard_corner_per_100km",
        "events_total_per_100km",
        "speeding_distance_share",
        "speeding_mean_excess_kmh",
        "speeding_max_excess_kmh",
        "tailgating_time_share",
        "headway_mean_s",
        "headway_min_s",
        "speed_mean_kmh",
        "speed_max_kmh",
        "speed_stddev_kmh",
        "brake_max_mps2",
        "accel_max_mps2",
        "cornering_max_mps2",
        "jerk_mean_mps3",
        "jerk_max_mps3",
    }
)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _unwrap(payload: dict[str, Any], expected_name: str) -> dict[str, Any]:
    """Accept the existing app's named envelope and compact envelope."""
    if isinstance(payload.get("data"), dict) and (
        payload.get("name") in (None, expected_name)
    ):
        return payload["data"]
    wrapped = payload.get(expected_name)
    return wrapped if isinstance(wrapped, dict) else payload


def emotion_record(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    data = _unwrap(payload, "DriverEmotionState")
    emotion = data.get("dominant_emotion")
    if emotion is not None and not isinstance(emotion, str):
        return None
    confidence = _number(data.get("confidence"))
    if confidence is not None and not 0.0 <= confidence <= 1.0:
        confidence = None
    return {
        "dominant_emotion": emotion.lower() if emotion else None,
        "confidence": confidence,
        "frame": data.get("frame"),
        "source_timestamp_s": _number(data.get("timestamp")),
    }


def driving_record(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    data = _unwrap(payload, "DrivingStyleProfile")
    if data is payload:
        data = _unwrap(payload, "DriverDrivingStyle")
    features = {
        key: value
        for key in DRIVING_NUMERIC_FIELDS
        if (value := _number(data.get(key))) is not None
    }
    if not features:
        return None
    return {
        "source_timestamp_s": _number(data.get("timestamp_s")),
        "features": features,
    }


class JsonlStore:
    """Append-only event log shared safely by the MQTT and WebSocket callbacks."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def append(self, stream: str, data: dict[str, Any]) -> None:
        event = {
            "received_at": time.time(),
            "stream": stream,
            "data": data,
        }
        encoded = json.dumps(
            event, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self.path.open("a", encoding="utf-8") as output:
            output.write(encoded + "\n")


class EmotionMqttSubscriber:
    def __init__(
        self, store: JsonlStore, host: str, port: int, topic: str
    ) -> None:
        self.store = store
        self.host = host
        self.port = port
        self.topic = topic
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="driver-emotion-correlation",
            protocol=mqtt.MQTTv311,
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any = None,
    ) -> None:
        if reason_code != 0:
            log.error("MQTT connection rejected: %s", reason_code)
            return
        result, _ = client.subscribe(self.topic, qos=1)
        if result != mqtt.MQTT_ERR_SUCCESS:
            log.error("Could not subscribe to MQTT topic %s: %s", self.topic, result)
            return
        log.info("Subscribed to MQTT topic %s at %s:%d", self.topic, self.host, self.port)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        disconnect_flags: Any,
        reason_code: Any,
        properties: Any = None,
    ) -> None:
        if reason_code != 0:
            log.warning("Disconnected from MQTT broker: %s", reason_code)

    def _on_message(
        self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage
    ) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            log.warning("Ignoring invalid emotion MQTT payload: %s", exc)
            return
        record = emotion_record(payload)
        if record is None:
            log.warning("Ignoring unrecognized emotion MQTT payload")
            return
        try:
            self.store.append("emotion", record)
        except OSError:
            log.exception("Could not append emotion event to %s", self.store.path)

    def start(self) -> None:
        self.client.connect(self.host, self.port, keepalive=60)
        self.client.loop_start()

    def stop(self) -> None:
        self.client.disconnect()
        self.client.loop_stop()


class DrivingScoreReceiver:
    """WebSocket endpoint for the profiler's full diagnostic score publisher."""

    def __init__(self, store: JsonlStore) -> None:
        self.store = store

    async def handle(self, connection: Any) -> None:
        async for message in connection:
            try:
                payload = json.loads(message)
            except (TypeError, json.JSONDecodeError) as exc:
                log.warning("Ignoring invalid driving-score WebSocket message: %s", exc)
                continue
            record = driving_record(payload)
            if record is None:
                log.warning("Ignoring driving score with no recognized numeric fields")
                continue
            try:
                self.store.append("driving", record)
            except OSError:
                log.exception("Could not append driving event to %s", self.store.path)


async def collect(
    store: JsonlStore,
    mqtt_host: str,
    mqtt_port: int,
    emotion_topic: str,
    ws_host: str,
    ws_port: int,
) -> None:
    subscriber = EmotionMqttSubscriber(store, mqtt_host, mqtt_port, emotion_topic)
    try:
        subscriber.start()
        log.info("Listening for profiler diagnostic scores on ws://%s:%d", ws_host, ws_port)
        async with websockets.serve(
            DrivingScoreReceiver(store).handle,
            ws_host,
            ws_port,
            max_size=None,
            ping_interval=None,
        ) as server:
            await server.wait_closed()
    finally:
        subscriber.stop()
