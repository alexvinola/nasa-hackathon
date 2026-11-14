"""Dev bridge until the HUD calls /voice/advise: camera biometrics -> rules engine -> spoken verdict.

uv run python scripts/live_loop.py      (from backend/, with the backend and the HUD running)

Every 2 s it reads what the HUD's MediaPipe worker last posted (/biometrics/latest), fills the rest of the
contract with shared/examples/nominal.json, asks /voice/advise and, when the status changes, speaks the
answer through /tts and the Mac's speakers (afplay). Ctrl+C to stop.
"""

import json
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8000"
NOMINAL = Path(__file__).resolve().parents[2] / "shared" / "examples" / "nominal.json"
HEADERS = {"Content-Type": "application/json", "Origin": "http://localhost:3000"}


def call(path, body=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(API + path, data=data, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def main() -> None:
    telemetry = json.loads(NOMINAL.read_text())
    previous = None
    while True:
        try:
            telemetry["biometrics"] = json.loads(call("/biometrics/latest"))["biometrics"]
        except urllib.error.HTTPError:
            print("waiting for the HUD to post biometrics (open http://localhost:3000 and allow the camera)")
            time.sleep(2)
            continue
        telemetry["timestamp"] = int(time.time())
        advice = json.loads(call("/voice/advise", {"telemetry": telemetry}))
        b, d = telemetry["biometrics"], advice["decision"]
        print(f"perclos {b['perclos']:.2f}  yawns {b['yawnsPerMin']}  fatigue {b['fatigueScore']:.2f}  ->  "
              f"{d['status']} / {d['escalation']}  [{advice['source']}] {advice['say']}")
        if d["status"] != previous:
            with tempfile.NamedTemporaryFile(suffix=".wav") as wav:
                wav.write(call("/tts", {"text": advice["say"]}))
                wav.flush()
                subprocess.run(["afplay", wav.name], check=False)
            previous = d["status"]
        time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
