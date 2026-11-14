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
