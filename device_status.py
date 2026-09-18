import paho.mqtt.client as mqtt
import json
import time
import random
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────
BROKER        = "localhost"   # MUST match the exact same IP used in the ESP32 sketch and backend - all pointing at Person C's laptop
PORT          = 1883
PUBLISH_TOPIC = "device/status"
SUB_TOPIC_1   = "device/telemetry"
SUB_TOPIC_2   = "device/alert"
DEVICE_ID     = "esp32-01"

# ── States ────────────────────────────────────────────────────────────────────
STATE = "STREAMING"   # starts as STREAMING

PROFILES = {
    "IDLE":        {"cpu": (5,15),  "ram": (20,30), "power": 0.01},
    "STREAMING":   {"cpu": (30,55), "ram": (35,50), "power": 0.40},
    "ALERT_BURST": {"cpu": (70,90), "ram": (55,75), "power": 8.80},
}

alert_triggered_at = None

# ── When a message arrives from Person B ──────────────────────────────────────
def on_message(client, userdata, msg):
    global STATE, alert_triggered_at
    try:
        data = json.loads(msg.payload.decode())
        status = data.get("status", "normal")
        temp   = data.get("temperature", 0)
        vibr   = data.get("vibration", 0)

        if status == "alert" or temp > 85 or vibr > 4.5:
            STATE = "ALERT_BURST"
            alert_triggered_at = time.time()
            print(f"[TRIGGER] Alert from Person B → ALERT_BURST (8.8W)")
    except:
        pass

def on_connect(client, userdata, flags, rc):
    print(f"Connected to broker! rc={rc}")
    client.subscribe(SUB_TOPIC_1)
    client.subscribe(SUB_TOPIC_2)
    print(f"Listening on {SUB_TOPIC_1} and {SUB_TOPIC_2}")

# ── Build and publish device/status ──────────────────────────────────────────
def publish_status(client):
    global STATE, alert_triggered_at

    # Cool down from ALERT_BURST after 15 seconds
    if STATE == "ALERT_BURST" and alert_triggered_at:
        if time.time() - alert_triggered_at > 15:
            STATE = "STREAMING"
            print("[STATE] → STREAMING (alert cooled down)")

    # Random idle/streaming transitions
    if STATE == "STREAMING" and random.random() < 0.05:
        STATE = "IDLE"
        print("[STATE] → IDLE")
    elif STATE == "IDLE" and random.random() < 0.30:
        STATE = "STREAMING"
        print("[STATE] → STREAMING")

    p = PROFILES[STATE]
    payload = {
        "device_id":   DEVICE_ID,
        "timestamp":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cpu_percent": random.randint(*p["cpu"]),
        "ram_percent": random.randint(*p["ram"]),
        "power_watts": p["power"]
    }

    client.publish(PUBLISH_TOPIC, json.dumps(payload))
    print(f"[device/status] state={STATE:<12} "
          f"cpu={payload['cpu_percent']}% "
          f"ram={payload['ram_percent']}% "
          f"power={payload['power_watts']}W")

# ── Main ──────────────────────────────────────────────────────────────────────
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
client.on_connect = on_connect
client.on_message = on_message

print(f"Connecting to {BROKER}...")
client.connect(BROKER, PORT, 60)
client.loop_start()

# Wait for connection
time.sleep(2)

print("Publishing device/status every 2 seconds. Press Ctrl+C to stop.\n")
try:
    while True:
        publish_status(client)
        time.sleep(2)
except KeyboardInterrupt:
    print("\nStopped.")
    client.loop_stop()
    client.disconnect()