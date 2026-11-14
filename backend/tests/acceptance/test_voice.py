"""G5: offline voice. Gemma only phrases the rules engine's verdict, and the whole turn runs on this machine.

Needs what `make prefetch` installs: Ollama running with the model pulled, the whisper model cached and the
Piper voice. A missing piece fails the test: G5 is about the real pipeline on the demo laptop.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SHARED, load
from pulsar.rules import build_engine
from pulsar.voice.pipeline import first_step, phrase

BACKEND = Path(__file__).resolve().parents[2]
FIXTURES = BACKEND.parent / "data" / "fixtures" / "voice"
SCENARIOS = sorted((SHARED / "scenarios").glob("*.json"))
NUMBER = re.compile(r"\d+(?:\.\d+)?")


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


@pytest.fixture(scope="module")
def phrased():
    engine = build_engine()
    results = {}
    for path in SCENARIOS:
        decision = engine.evaluate(load(path)["input"])
        results[path.stem] = (decision, phrase(decision, "How am I doing?", first_step(engine, decision)))
    return results


@pytest.mark.parametrize("name", [p.stem for p in SCENARIOS])
def test_phrasing_follows_the_prompt_rules(phrased, name):
    decision, result = phrased[name]
    text = result.text

    assert text.strip()
    assert len(sentences(text)) <= 2, text
    allowed = {float(n) for n in NUMBER.findall(result.prompt)}
    assert {float(n) for n in NUMBER.findall(text)} <= allowed, f"figures that are not in the verdict: {text}"
    assert not re.search(r"\bCM-", text), f"reads a countermeasure id aloud: {text}"
    if decision["escalation"] == "FLIGHT_SURGEON":
        assert "flight surgeon" in text.lower(), text


def test_gemma_does_the_phrasing_and_the_fallback_is_rare(phrased):
    """The deterministic fallback keeps the demo safe; it must not be what passes the test."""
    from_llm = [name for name, (_, result) in phrased.items() if result.source == "llm"]
    rejected = {name: result.violations for name, (_, result) in phrased.items() if result.source != "llm"}
    assert len(from_llm) >= len(phrased) - 1, rejected


def test_bench_runs_offline_and_logs_every_stage():
    wavs = sorted(FIXTURES.glob("*.wav"))
    assert len(wavs) >= 3, f"record at least 3 voice commands in {FIXTURES}"
    out = BACKEND / "bench" / "voice_latency.json"

    subprocess.run([sys.executable, "scripts/voice_bench.py"], cwd=BACKEND, check=True, timeout=900,
                   env={**os.environ, "HF_HUB_OFFLINE": "1"})

    bench = json.loads(out.read_text())
    assert bench["offline"] is True
    assert [t["wav"] for t in bench["turns"]] == [w.name for w in wavs]
    for turn in bench["turns"]:
        assert turn["transcript"].strip() and turn["text"].strip() and turn["audio_bytes"] > 0, turn
        assert all(turn["ms"][stage] > 0 for stage in ("stt", "rules", "llm", "tts", "total")), turn
