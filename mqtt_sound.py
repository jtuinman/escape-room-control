import json
import os
import paho.mqtt.client as mqtt

print("mqtt_sound loaded", flush=True)

SOUND_PI_HOST = os.getenv("SOUND_PI_HOST", "192.168.68.125")
SOUND_PI_PORT = int(os.getenv("SOUND_PI_PORT", "1883"))

TOPIC_BG = "escape/audio/bg"
TOPIC_HINT = "escape/audio/hint"
TOPIC_PANIC = "escape/audio/panic"

_client = None

def _get_client():
    global _client
    if _client is None:
        try:
            client = mqtt.Client()
            client.connect(SOUND_PI_HOST, SOUND_PI_PORT, keepalive=10)
            client.loop_start()
            _client = client
        except Exception as e:
            print(f"MQTT connect failed to {SOUND_PI_HOST}:{SOUND_PI_PORT}: {e}", flush=True)
            _client = None
    return _client

def _safe_publish(topic: str, payload: str):
    client = _get_client()
    if client is None:
        print(f"MQTT unavailable, skipping publish to {topic}", flush=True)
        return False
    try:
        client.publish(topic, payload, qos=0)
        return True
    except Exception as e:
        print(f"MQTT publish failed for {topic}: {e}", flush=True)
        return False

def bg_start(filename: str):
    payload = {"cmd": "start", "file": filename}
    _safe_publish(TOPIC_BG, json.dumps(payload))

def bg_switch(filename: str):
    payload = {"cmd": "switch", "file": filename}
    _safe_publish(TOPIC_BG, json.dumps(payload))

def bg_stop():
    payload = {"cmd": "stop"}
    _safe_publish(TOPIC_BG, json.dumps(payload))

def hint_play(filename: str):
    payload = {"cmd": "play", "file": filename}
    _safe_publish(TOPIC_HINT, json.dumps(payload))

def panic():
    _safe_publish(TOPIC_PANIC, "{}")