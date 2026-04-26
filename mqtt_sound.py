import json
import os
import threading
import time
from typing import Callable, Optional

import paho.mqtt.client as mqtt

print("mqtt_sound loaded", flush=True)

SOUND_PI_HOST = os.getenv("SOUND_PI_HOST", "192.168.68.125")
SOUND_PI_PORT = int(os.getenv("SOUND_PI_PORT", "1883"))

TOPIC_BG = "escape/audio/bg"
TOPIC_HINT = "escape/audio/hint"
TOPIC_PANIC = "escape/audio/panic"
TOPIC_LANGUAGE = "escape/audio/language"
TOPIC_STATUS = "escape/audio/status"

_client: Optional[mqtt.Client] = None
_lock = threading.Lock()
_monitor_started = False
_broker_connected = False
_sound_ready = False
_last_status_payload = ""
_last_status_at = None
_desired_language: Optional[str] = None
_desired_bg_payload: Optional[str] = None
_last_sent_language: Optional[str] = None
_last_sent_bg_payload: Optional[str] = None
_ready_callbacks: list[Callable[[], None]] = []
_status_callbacks: list[Callable[[dict], None]] = []


def _log(message: str) -> None:
    print(f"[mqtt_sound] {message}", flush=True)


def _make_client() -> mqtt.Client:
    client = mqtt.Client()
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect
    client.on_message = _on_message
    return client


def start_monitor(on_ready: Optional[Callable[[], None]] = None, on_status: Optional[Callable[[dict], None]] = None) -> None:
    global _client, _monitor_started

    if on_ready is not None:
        register_ready_callback(on_ready)
    if on_status is not None:
        register_status_callback(on_status)

    with _lock:
        if _monitor_started:
            return
        _monitor_started = True
        if _client is None:
            _client = _make_client()
        client = _client

    try:
        _log(f"starting MQTT monitor for {SOUND_PI_HOST}:{SOUND_PI_PORT}")
        client.connect_async(SOUND_PI_HOST, SOUND_PI_PORT, keepalive=10)
        client.loop_start()
    except Exception as exc:
        _log(f"MQTT monitor start failed: {exc}")
        _set_broker_connected(False)


def register_ready_callback(callback: Callable[[], None]) -> None:
    with _lock:
        _ready_callbacks.append(callback)


def register_status_callback(callback: Callable[[dict], None]) -> None:
    with _lock:
        _status_callbacks.append(callback)


def _on_connect(client, userdata, flags, rc):
    if rc == 0:
        _log("MQTT broker reachable")
        _set_broker_connected(True)
        try:
            client.subscribe(TOPIC_STATUS)
            _log(f"subscribed to {TOPIC_STATUS}")
        except Exception as exc:
            _log(f"MQTT status subscribe failed: {exc}")
    else:
        _log(f"MQTT broker connect failed rc={rc}")
        _set_broker_connected(False)


def _on_disconnect(client, userdata, rc):
    _log(f"MQTT broker unreachable rc={rc}")
    _set_broker_connected(False)


def _on_message(client, userdata, msg):
    if msg.topic != TOPIC_STATUS:
        return

    payload = msg.payload.decode("utf-8", errors="replace").strip()
    retained = bool(getattr(msg, "retain", False))
    ok = _status_payload_is_ok(payload)
    _log(f"sound status received ready={ok} retained={retained} payload={payload!r}")
    _set_sound_status(ok, payload)


def _status_payload_is_ok(payload: str) -> bool:
    if not payload:
        return False

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return payload.strip().lower() == "ok"

    if isinstance(data, dict):
        status = str(data.get("status", "")).strip().lower()
        state = str(data.get("state", "")).strip().lower()
        return status == "ok" or state == "ok" or data.get("ok") is True or data.get("ready") is True

    if isinstance(data, str):
        return data.strip().lower() == "ok"

    return False


def _set_broker_connected(connected: bool) -> None:
    status_callbacks: list[Callable[[dict], None]] = []

    with _lock:
        global _broker_connected, _sound_ready, _last_sent_language, _last_sent_bg_payload
        changed = _broker_connected != connected
        ready_changed = False
        _broker_connected = connected
        if not connected and _sound_ready:
            _sound_ready = False
            ready_changed = True
        if not connected:
            _last_sent_language = None
            _last_sent_bg_payload = None
        if changed or ready_changed:
            status_callbacks = list(_status_callbacks)

    if status_callbacks:
        _emit_status(status_callbacks)


def _set_sound_status(ready: bool, payload: str) -> None:
    callbacks: list[Callable[[], None]] = []
    status_callbacks: list[Callable[[dict], None]] = []

    with _lock:
        global _sound_ready, _last_status_payload, _last_status_at, _last_sent_language, _last_sent_bg_payload
        was_ready = _sound_ready
        _sound_ready = bool(ready)
        _last_status_payload = payload
        _last_status_at = time.time()
        if not _sound_ready:
            _last_sent_language = None
            _last_sent_bg_payload = None
        if was_ready != _sound_ready:
            _log(f"sound ready {was_ready} -> {_sound_ready}")
            status_callbacks = list(_status_callbacks)
            if _sound_ready:
                callbacks = list(_ready_callbacks)
        else:
            status_callbacks = list(_status_callbacks)

    if status_callbacks:
        _emit_status(status_callbacks)
    if callbacks:
        _emit_ready(callbacks)
    elif ready:
        flush_desired_state(reason="sound_status_ok")


def _emit_ready(callbacks: list[Callable[[], None]]) -> None:
    for callback in callbacks:
        try:
            callback()
        except Exception as exc:
            _log(f"sound ready callback failed: {exc}")


def _emit_status(callbacks: list[Callable[[dict], None]]) -> None:
    snapshot = get_status()
    for callback in callbacks:
        try:
            callback(snapshot)
        except Exception as exc:
            _log(f"sound status callback failed: {exc}")


def get_status() -> dict:
    with _lock:
        return {
            "broker_connected": _broker_connected,
            "ready": _broker_connected and _sound_ready,
            "status_topic": TOPIC_STATUS,
            "last_status_payload": _last_status_payload,
            "last_status_at": _last_status_at,
            "desired_language": _desired_language,
            "desired_background": json.loads(_desired_bg_payload) if _desired_bg_payload else None,
        }


def _get_client() -> Optional[mqtt.Client]:
    start_monitor()
    with _lock:
        return _client


def _is_ready() -> bool:
    with _lock:
        return _broker_connected and _sound_ready


def _publish_now(topic: str, payload: str) -> bool:
    client = _get_client()
    if client is None:
        _log(f"MQTT unavailable, cannot publish to {topic}")
        return False

    if not _is_ready():
        _log(f"sound not ready, deferred publish to {topic}")
        return False

    try:
        result = client.publish(topic, payload, qos=0)
    except Exception as exc:
        _log(f"MQTT publish failed for {topic}: {exc}")
        return False

    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        _log(f"MQTT publish failed for {topic}: rc={result.rc}")
        return False

    _log(f"published to {topic}: {payload}")
    return True


def flush_desired_state(reason: str = "manual") -> None:
    global _last_sent_language, _last_sent_bg_payload

    with _lock:
        language = _desired_language
        bg_payload = _desired_bg_payload
        last_language = _last_sent_language
        last_bg_payload = _last_sent_bg_payload

    if not _is_ready():
        _log(f"audio desired state deferred reason={reason}")
        return

    _log(f"audio desired state flushed/resynced reason={reason}")
    if language and language != last_language:
        if _publish_now(TOPIC_LANGUAGE, json.dumps({"language": language})):
            with _lock:
                _last_sent_language = language
    if bg_payload and bg_payload != last_bg_payload:
        if _publish_now(TOPIC_BG, bg_payload):
            with _lock:
                _last_sent_bg_payload = bg_payload


def bg_start(filename: str):
    payload = json.dumps({"cmd": "start", "file": filename})
    with _lock:
        global _desired_bg_payload
        _desired_bg_payload = payload
    flush_desired_state(reason=f"bg_start:{filename}")


def bg_switch(filename: str):
    payload = json.dumps({"cmd": "switch", "file": filename})
    with _lock:
        global _desired_bg_payload
        _desired_bg_payload = payload
    flush_desired_state(reason=f"bg_switch:{filename}")


def bg_stop():
    payload = json.dumps({"cmd": "stop"})
    with _lock:
        global _desired_bg_payload
        _desired_bg_payload = payload
    flush_desired_state(reason="bg_stop")


def hint_play(filename: str):
    payload = json.dumps({"cmd": "play", "file": filename})
    if not _publish_now(TOPIC_HINT, payload):
        _log(f"hint not replayed because sound is not ready: {filename}")


def panic():
    if not _publish_now(TOPIC_PANIC, "{}"):
        _log("panic not replayed because sound is not ready")


def set_language(language: str):
    with _lock:
        global _desired_language
        _desired_language = language
    flush_desired_state(reason=f"language:{language}")
