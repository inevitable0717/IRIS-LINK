"""
One-command launcher for the whole Python side of the system.

Starts:
  1. The FastAPI backend (backend_main.py)
  2. The Streamlit dashboard (dashboard.py)

...as two child processes, so you only have to run ONE command instead of
juggling two separate terminals.

It does NOT start:
  - Mosquitto (the MQTT broker) - start that separately, see instructions below
  - The ESP32 sketch - that runs on the ESP32/Cirkit simulator, not your laptop
  - The fake telemetry generator - keep that OFF unless the real ESP32 fails
    live on stage (see the warning in that file)

USAGE:
    python run_all.py

Press Ctrl+C once to shut both down cleanly.
"""

import subprocess
import sys
import time
import signal

processes = []


def start(cmd, name):
    print(f"[Launcher] Starting {name}: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd)
    processes.append((name, proc))
    return proc


def shutdown(*_):
    print("\n[Launcher] Shutting down...")
    for name, proc in processes:
        print(f"[Launcher] Stopping {name}")
        proc.terminate()
    for name, proc in processes:
        proc.wait()
    print("[Launcher] All stopped.")
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, shutdown)

    # Use the same Python interpreter that's running this launcher, so it
    # matches whatever virtual environment you activated.
    python_exe = sys.executable

    start([python_exe, "backend_main.py"], "Backend (FastAPI)")

    # Give the backend a couple seconds to bind its port and connect to MQTT
    # before the dashboard starts trying to call it.
    time.sleep(2)

    start([python_exe, "-m", "streamlit", "run", "dashboard.py"], "Dashboard (Streamlit)")

    print("\n[Launcher] Both running. Press Ctrl+C to stop everything.\n")

    # Keep the launcher alive; exit if either child process dies unexpectedly.
    try:
        while True:
            time.sleep(1)
            for name, proc in processes:
                if proc.poll() is not None:
                    print(f"[Launcher] WARNING: {name} exited unexpectedly (code {proc.returncode}).")
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
