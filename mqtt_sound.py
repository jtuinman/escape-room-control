print("mqtt_sound module loaded")

import json
import paho.mqtt.client as mqtt

SOUND_PI_HOST = "192.168.68.127"   # bv: 192.168.1.42
SOUND_PI_PORT = 1883

TOPIC_BG = "escape/audio/bg"
TOPIC_HINT = "escape/audio/hint"
TOPIC_PANIC = "escape/audio/panic"

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = mqtt.Client()
        _client.connect(SOUND_PI_HOST, SOUND_PI_PORT, keepalive=10)
    return _client

def bg_start(filename: str):
    print("BG_START called with", filename)
    payload = {"cmd": "start", "file": filename}
    _get_client().publish(TOPIC_BG, json.dumps(payload), qos=0)

def bg_switch(filename: str):
    print("BG_SWITCH called with", filename)
    payload = {"cmd": "switch", "file": filename}
    _get_client().publish(TOPIC_BG, json.dumps(payload), qos=0)

def bg_stop():
    payload = {"cmd": "stop"}
    _get_client().publish(TOPIC_BG, json.dumps(payload), qos=0)

def hint_play(filename: str):
    payload = {"cmd": "play", "file": filename}
    _get_client().publish(TOPIC_HINT, json.dumps(payload), qos=0)

def panic():
    _get_client().publish(TOPIC_PANIC, "{}", qos=0)
