"""Speech and vision endpoints. The round trip needs the Piper voice and the whisper model (make prefetch)."""

import io
import json
import urllib.error

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
