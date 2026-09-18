"""
Person E's backup telemetry generator ("insurance policy").

Publishes fake sine-wave temperature/vibration data to the SAME topic and in
the SAME JSON shape as the real ESP32 (Person B), so it's a seamless drop-in
if the real hardware simulation crashes or lags on stage.

IMPORTANT: Do NOT run this at the same time as the real outage-toggle demo.
The backend's offline watchdog marks the device "offline" only when NO
messages arrive at all. If this script is also publishing in the background,
the backend will never see silence, and the dashboard's
"OFFLINE - BUFFERING" banner (your key demo moment) will never appear.

Intended use: keep this OFF during the real demo. Only start it manually as
a live rescue if B's ESP32/Wokwi sim visibly breaks or freezes on stage.
"""

import argparse
import json
import math
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

# --- CHANGE THIS to Person C's laptop IP (same broker the real ESP32 uses) ---
MQTT_BROKER = "localhost"
MQTT_PORT = 1883

# Same device_id as the real ESP32 - makes the swap invisible to the dashboard,
# since it doesn't need to know or care which source the data came from.
DEVICE_ID = "esp32-01"

TELEMETRY_TOPIC = "device/telemetry"
ALERT_TOPIC = "device/alert"

TEMP_THRESHOLD = 70.0
VIBRATION_THRESHOLD = 4.5
SAMPLE_PERIOD_SEC = 1.0


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_reading(t: float):
    """Smooth sine-wave values that look like plausible sensor drift, not noise."""
    temp = 45 + 15 * math.sin(t / 20.0)      # oscillates roughly 30-60C normally
    vibration = 2.0 + 1.5 * math.sin(t / 8.0 + 1)  # oscillates roughly 0.5-3.5
    return round(temp, 1), round(vibration, 2)


def main():
    parser = argparse.ArgumentParser(description="Person E's fake telemetry backup generator")
    parser.add_argument(
        "--force-alert",
        action="store_true",
        help="Force values above threshold, to demo the anomaly path without waiting for the sine wave to drift there.",
    )
    args = parser.parse_args()

    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
    print(f"[FakeGen] Connecting to broker {MQTT_BROKER}:{MQTT_PORT} ...")
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()

    print(f"[FakeGen] Publishing backup telemetry as device_id={DEVICE_ID}")
    print("[FakeGen] This should be OFF unless B's real device fails live. Press Ctrl+C to stop.")

    t = 0.0
    try:
        while True:
            temperature, vibration = make_reading(t)
            if args.force_alert:
                temperature, vibration = 90.0, 6.0  # guaranteed to cross both thresholds

            anomaly = temperature > TEMP_THRESHOLD or vibration > VIBRATION_THRESHOLD
            status = "alert" if anomaly else "normal"

            payload = {
                "device_id": DEVICE_ID,
                "timestamp": iso_now(),
                "temperature": temperature,
                "vibration": vibration,
                "status": status,
            }
            client.publish(TELEMETRY_TOPIC, json.dumps(payload))

            if anomaly:
                client.publish(ALERT_TOPIC, json.dumps(payload))

            print(f"[FakeGen] temp={temperature}C vibration={vibration} status={status}")
            t += 1.0
            time.sleep(SAMPLE_PERIOD_SEC)

    except KeyboardInterrupt:
        print("\n[FakeGen] Stopped.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
