"""Speech and vision endpoints. The round trip needs the Piper voice and the whisper model (make prefetch)."""

import io
import json
import urllib.error
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import senses
from main import app

client = TestClient(app, base_url="http://localhost:8000")
JPEG = b"\xff\xd8\xff\xe0fake-frame"


def test_refuses_pages_from_elsewhere():
    assert client.post("/stt", content=b"x", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/stt", content=b"x", headers={"Host": "rebound.example:8000"}).status_code == 403
    assert client.post("/stt", content=b"", headers={"Origin": "http://localhost:3000"}).status_code == 400


def test_rejects_bad_input():
    assert client.post("/tts", json={"text": ""}).status_code == 422
    assert client.post("/tts", json={"text": "x" * 601}).status_code == 422
    assert client.post("/stt", content=b"").status_code == 400
    assert client.post("/stt", content=b"x" * (senses.MAX_AUDIO + 1)).status_code == 413
    assert client.post("/vision/describe", content=b"not a jpeg").status_code == 415


def test_describe_sends_the_frame_to_the_local_model(monkeypatch):
    sent = {}

    def fake_urlopen(request, timeout):
        sent.update(url=request.full_url, body=json.loads(request.data))
        return io.BytesIO(json.dumps({"message": {"content": " A person sits at a desk. "}}).encode())

    monkeypatch.setattr(senses.urllib.request, "urlopen", fake_urlopen)
    response = client.post("/vision/describe", content=JPEG)

    assert response.json() == {"description": "A person sits at a desk."}
    assert sent["url"].startswith("http://127.0.0.1")
    system, user = sent["body"]["messages"]
    assert "Do not diagnose" in system["content"]
    assert sent["body"]["think"] is False
    assert len(user["images"]) == 1


def test_describe_says_so_when_ollama_is_down(monkeypatch):
    def refused(request, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(senses.urllib.request, "urlopen", refused)
    assert client.post("/vision/describe", content=JPEG).status_code == 503


@pytest.mark.skipif(not senses.VOICE.exists(), reason="Piper voice not downloaded: make prefetch")
def test_what_piper_says_whisper_understands():
    spoken = client.post("/tts", json={"text": "The quick brown fox jumps over the lazy dog."})
    assert spoken.status_code == 200 and spoken.content[:4] == b"RIFF"

    heard = client.post("/stt", content=spoken.content)
    assert heard.status_code == 200, heard.text
    assert "fox" in heard.json()["text"].lower()

    silence = io.BytesIO()
    with wave.open(silence, "wb") as wav:
        wav.setparams((1, 2, 16000, 0, "NONE", "NONE"))
        wav.writeframes(bytes(2 * 16000 * 3))
    assert client.post("/stt", content=silence.getvalue()).json() == {"text": ""}  # silence is not turned into words


def test_director_only_accepts_closed_choices_and_safe_lines():
    import director

    ok = {"say": "Hello there, I see you.", "spot": "mid_left", "reaction": "alert"}
    assert director.validate(ok) == {**ok, "speak": True}
    assert director.validate({**ok, "spot": "the moon"}) == director.FALLBACK
    assert director.validate({**ok, "reaction": "panic"}) == director.FALLBACK
    assert director.validate({**ok, "say": "You look tired."}) == director.FALLBACK
    assert director.validate({**ok, "say": "Your heart rate is 90."}) == director.FALLBACK
    assert director.validate({**ok, "say": ""}) == director.FALLBACK
    # frames arrive mirrored like the HUD: a person on the frame's left is on the screen's left, so the mascot leaves it
    assert director.validate({**ok, "spot": "mid_left", "person_side": "left"})["spot"] == "mid_right"
    assert director.validate({**ok, "spot": "home", "person_side": "left"})["spot"] == "mid_right"
    assert director.validate({**ok, "spot": "mid_right", "person_side": "left"})["spot"] == "mid_right"
    assert director.validate({**ok, "spot": "top_right", "person_side": "right"})["spot"] == "mid_left"


def answering(monkeypatch, line, sent=None):
    def fake_urlopen(request, timeout):
        if sent is not None:
            sent.update(body=json.loads(request.data))
        return io.BytesIO(json.dumps({"message": {"content": line}}).encode())

    monkeypatch.setattr(senses.urllib.request, "urlopen", fake_urlopen)


def test_director_asks_gemma_for_one_short_line(monkeypatch):
    sent = {}
    answering(monkeypatch, "none|bottom_right|calm|Good to see you.\n", sent)
    scene = {"instruction": "hello", "user_spoke": True, "image": "/9j/4AAQ"}
    response = client.post("/pulsar/act", json=scene)

    assert response.json() == {"spot": "bottom_right", "reaction": "calm", "say": "Good to see you.", "speak": True}
    system, user = sent["body"]["messages"]
    assert "side|spot|reaction|sentence" in system["content"] and user["images"] == ["/9j/4AAQ"]
    assert sent["body"]["think"] is False and sent["body"]["keep_alive"]
    assert client.post("/pulsar/act", json={}).status_code == 400
    assert client.post("/pulsar/act", json={"instruction": "hi", "image": "not a jpeg"}).status_code == 422


def test_director_decides_when_to_speak_without_asking_the_model(monkeypatch):
    import director

    def no_model(request, timeout):
        raise AssertionError("the model must not be called")

    monkeypatch.setattr(senses.urllib.request, "urlopen", no_model)
    heard = {"user_spoke": True, "via_voice": True}
    for not_for_pulsar in ("Yeah, I'll call you back after lunch, bye mum.", "Uh. Hmm."):
        assert client.post("/pulsar/act", json={**heard, "instruction": not_for_pulsar}).json() == director.SILENT
    for meant_for_it in ("Pulsar, come here", "What is that?", "¿Qué ves?", "Please move left"):
        assert director.addressed(meant_for_it)
    # health is never the model's call, typed or spoken
    assert client.post("/pulsar/act", json={"user_spoke": True, "instruction": "Do I look tired?"}).json()["say"] == director.NOT_MINE
    assert not director.FORBIDDEN.search("I will still paint it.")  # "ill" and "pain" only count as whole words


def test_director_takes_a_reply_and_remembers_compactly(monkeypatch):
    sent = {}
    answering(monkeypatch, "none|home|calm|It is white.", sent)
    history = [f"Astronaut: line number {n} is a rather long sentence with many more words than nine" for n in range(10)]
    scene = {"user_spoke": True, "via_voice": True, "engaged": True, "instruction": "the white one", "history": history}

    assert client.post("/pulsar/act", json=scene).json()["say"] == "It is white."  # no name, no question: a reply
    prompt = sent["body"]["messages"][1]["content"]
    assert "number 9 is a rather long sentence with many more words than nine" in prompt  # the latest turns, whole
    assert "number 5 is a rather long sentence..." in prompt  # older ones, cut short
    assert "number 3" not in prompt  # the oldest, forgotten


def drowsy_telemetry():
    shared = Path(__file__).resolve().parents[2] / "shared"
    telemetry = json.loads((shared / "examples" / "nominal.json").read_text(encoding="utf-8"))
    telemetry["biometrics"]["perclos"] = 0.45  # past the engine's drowsiness rule
    return telemetry


def test_director_respects_the_rules_engines_health_check(monkeypatch):
    sent = {}
    answering(monkeypatch, "centre|home|alert|Let us pause the task for now.", sent)
    scene = {"user_spoke": True, "instruction": "Shall we start the docking drill?", "telemetry": drowsy_telemetry()}

    assert client.post("/pulsar/act", json=scene).json()["say"] == "Let us pause the task for now."
    prompt = sent["body"]["messages"][1]["content"]
    assert "Health check (final)" in prompt and "Pause any task" in prompt  # the engine's verdict and its first step

    # asked about health with readings: the engine decides, Gemma only phrases its verdict
    answering(monkeypatch, "Your eyes have been closed a lot. Pause any task that needs fast reactions.", sent)
    asked = client.post("/pulsar/act", json={**scene, "instruction": "Am I too tired to work?"}).json()
    assert asked["say"].startswith("Your eyes have been closed") and asked["reaction"] == "alert"
    assert "[VERDICT]" in sent["body"]["messages"][1]["content"]

    assert client.post("/pulsar/act", json={**scene, "telemetry": {"not": "the contract"}}).status_code == 422

    # RED (exhausted): whatever is asked, PULSAR only repeats what the engine requires
    exhausted = drowsy_telemetry()
    exhausted["biometrics"]["fatigueScore"] = 0.8
    answering(monkeypatch, "It is not safe to stay awake on task. Contact the flight surgeon, then stop and make it safe.", sent)
    told = client.post("/pulsar/act", json={**scene, "instruction": "Tell me a joke.", "telemetry": exhausted}).json()
    assert "flight surgeon" in told["say"] and told["reaction"] == "alert"
    assert "Stop what you are doing" in sent["body"]["messages"][1]["content"]  # the required step reached Gemma


def test_director_survives_a_line_in_the_wrong_shape(monkeypatch):
    import director

    scene = {"seen": "A person waves.", "instruction": "hello", "user_spoke": True}
    for broken in ("home|none|calm|Fields in the wrong order.", "Sure! Here is my answer.", ""):
        answering(monkeypatch, broken)
        assert client.post("/pulsar/act", json=scene).json() == director.FALLBACK
    answering(monkeypatch, "centre|home|calm|-")
    assert client.post("/pulsar/act", json={"seen": "A person waves."}).json() == director.SILENT


def test_director_stays_quiet_instead_of_repeating_itself():
    import director

    said = ["A person sits at a desk and types."]
    same = {"say": "A person is sitting at a desk, typing.", "spot": "home", "reaction": "calm", "speak": True}
    assert director.validate(same, said, user_spoke=False) == director.SILENT  # camera-only update, nothing new
    assert director.validate(same, said, user_spoke=True)["speak"] is True  # but it always answers the astronaut
    quiet = {**same, "say": "", "speak": False}
    assert director.validate(quiet, [], user_spoke=False) == director.SILENT
    new = {**same, "say": "Someone just walked in behind you."}
    assert director.validate(new, said, user_spoke=False)["say"] == new["say"]


def test_biometrics_are_checked_against_the_contract():
    good = {
        "heartRateBpm": None,
        "heartRateConfidence": 0,
        "fatigueScore": 0.42,
        "perclos": 0.3,
        "yawnsPerMin": 1.0,
        "postureStability": 0.8,
        "armAsymmetry": 0.1,
        "lastPvtMeanMs": None,
        "lastPvtLapses": None,
    }
    assert client.post("/biometrics", json=good).json() == {"ok": True, "biometrics": good}
    assert client.get("/biometrics/latest").json() == good
    assert client.post("/biometrics", json={**good, "fatigueScore": 1.5}).status_code == 422
    assert client.post("/biometrics", json={**good, "perclos": "high"}).status_code == 422
    assert client.post("/biometrics", json={**good, "extra": 1}).status_code == 422
    missing = {k: v for k, v in good.items() if k != "perclos"}
    assert client.post("/biometrics", json=missing).status_code == 422
    assert client.post("/biometrics", json=[1, 2]).status_code == 422
