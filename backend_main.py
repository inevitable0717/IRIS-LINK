import json
import threading
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import paho.mqtt.client as mqtt

telemetry_history: List[Dict[str, Any]] = []
alerts_list: List[Dict[str, Any]] = []
latest_resource: Dict[str, Any] = {}
device_state = {
    "online": False,
    "last_seen": None,
    "buffered_count": 0
}

# Wall-clock time (server-side) of the last message received, used only by the
# offline watchdog below. Kept separate from "last_seen" (the device's own
# reported timestamp) since the two can drift if the ESP32's clock is off.
last_message_wall_time: Optional[float] = None
OFFLINE_TIMEOUT_SECONDS = 5  # if no message in this long, mark the device offline

app = FastAPI(title="Iris-Link Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MQTT_BROKER = "localhost"
MQTT_PORT = 1883


def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Connected with result code {rc}")
    client.subscribe("device/telemetry")
    client.subscribe("device/status")
    client.subscribe("device/alert")


def on_message(client, userdata, msg):
    global latest_resource, device_state, last_message_wall_time
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        topic = msg.topic

        device_state["online"] = True
        device_state["last_seen"] = payload.get("timestamp", datetime.now(timezone.utc).isoformat())
        last_message_wall_time = time.time()  # feeds the offline watchdog below

        if topic == "device/telemetry":
            telemetry_history.append(payload)
            if payload.get("status") == "buffered":
                device_state["buffered_count"] += 1
            if len(telemetry_history) > 1000:
                telemetry_history.pop(0)

        elif topic == "device/status":
            latest_resource = payload

        elif topic == "device/alert":
            alerts_list.append(payload)

    except Exception as e:
        print(f"[MQTT Error] Failed to process message on {msg.topic}: {e}")


def start_mqtt_client():
    # callback_api_version is required for paho-mqtt 2.x (pip installs this by
    # default now) - without it, Client() raises a deprecation error.
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except Exception as e:
        print(f"[MQTT Error] Broker connection failed: {e}")


def offline_watchdog():
    """
    Runs forever in the background. If no MQTT message has arrived recently,
    flips device_state['online'] to False so the dashboard's outage banner
    actually shows up during the network-outage demo moment.
    """
    while True:
        time.sleep(1)
        if last_message_wall_time is None:
            continue
        if time.time() - last_message_wall_time > OFFLINE_TIMEOUT_SECONDS:
            if device_state["online"]:
                print("[Watchdog] No messages received recently - marking device OFFLINE")
            device_state["online"] = False


threading.Thread(target=start_mqtt_client, daemon=True).start()
threading.Thread(target=offline_watchdog, daemon=True).start()


@app.get("/api/telemetry/latest")
def get_latest_telemetry(limit: int = 10):
    return telemetry_history[-limit:]


@app.get("/api/telemetry/history")
def get_telemetry_history(since: Optional[str] = Query(None)):
    if not since:
        return telemetry_history
    return [item for item in telemetry_history if item.get("timestamp", "") >= since]


@app.get("/api/alerts")
def get_alerts():
    return alerts_list


@app.get("/api/device/status")
def get_device_status():
    return device_state


@app.get("/api/resource")
def get_resource():
    return latest_resource


if __name__ == "__main__":
    import uvicorn
    # host="0.0.0.0" is required for ANY other device (dashboard laptop, ESP32,
    # phone) to reach this server. 127.0.0.1 (the default) only accepts
    # connections from this same machine.
    uvicorn.run(app, host="0.0.0.0", port=8000)
