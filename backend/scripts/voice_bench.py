"""G5 bench: plays every data/fixtures/voice/*.wav through the full offline turn and logs per-stage latency.

uv run python scripts/voice_bench.py      (from backend/; writes bench/voice_latency.json)

The telemetry is the demo emergency (shared/scenarios/04-demo-emergency.json). One untimed warm-up turn loads
the models first. These numbers are the only latencies that may be quoted in the pitch.
"""

import json
import os
import platform
import statistics
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")  # before faster-whisper is imported: never reach the network

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from pulsar.rules import build_engine  # noqa: E402
from pulsar.voice.config import load_voice_settings  # noqa: E402
from pulsar.voice.pipeline import respond  # noqa: E402

FIXTURES = BACKEND.parent / "data" / "fixtures" / "voice"
SCENARIO = BACKEND.parent / "shared" / "scenarios" / "04-demo-emergency.json"
OUT = BACKEND / "bench" / "voice_latency.json"


def main() -> None:
    wavs = sorted(FIXTURES.glob("*.wav"))
    if not wavs:
        sys.exit(f"no fixtures in {FIXTURES}")
    engine = build_engine()
    telemetry = json.loads(SCENARIO.read_text())["input"]
    respond(wavs[0].read_bytes(), telemetry, engine)  # warm-up: model loading is not a turn

    turns = []
    for wav in wavs:
        turn = respond(wav.read_bytes(), telemetry, engine)
        turns.append({"wav": wav.name, "transcript": turn.transcript, "status": turn.decision["status"],
                      "text": turn.phrasing.text, "source": turn.phrasing.source,
                      "violations": turn.phrasing.violations, "audio_bytes": len(turn.audio),
                      "ms": {k: round(v, 3) for k, v in turn.ms.items()}})
        print(f"{wav.name}: {turn.ms['total']:.0f} ms  [{turn.phrasing.source}] {turn.transcript!r} -> {turn.phrasing.text}")

    stages = ("stt", "rules", "llm", "tts", "total")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "model": load_voice_settings().llm_model,
        "machine": f"{platform.machine()} {platform.platform()}",
        "offline": os.environ.get("HF_HUB_OFFLINE") == "1",
        "scenario": SCENARIO.name,
        "median_ms": {s: round(statistics.median(t["ms"][s] for t in turns), 3) for s in stages},
        "turns": turns,
    }, indent=2) + "\n")
    print(f"wrote {OUT.relative_to(BACKEND)}")


if __name__ == "__main__":
    main()
