"""The AI cross-check compares fairly: unclear answers and frames without a person are not counted."""

import json

import pytest
from fastapi.testclient import TestClient

from main import app
from pulsar.vision import verify as verify_module
from pulsar.vision.verify import Claim, Seen, agreement

client = TestClient(app, base_url="http://localhost:8000")
JPEG_B64 = "/9j/4AAQSkZJRgABAQ"


@pytest.mark.parametrize(
    ("claim", "seen", "expected"),
    [
        (Claim(eyes="closed", mouth="closed"), Seen(person=True, eyes="closed", mouth="closed"), {"eyes": True, "mouth": True}),
        (Claim(eyes="open", mouth="closed"), Seen(person=True, eyes="closed", mouth="open"), {"eyes": False, "mouth": False}),
        (Claim(eyes="open", mouth="open"), Seen(person=True, eyes="unclear", mouth="open"), {"eyes": None, "mouth": True}),
        (Claim(eyes="open", mouth="open"), Seen(person=False, eyes="open", mouth="open"), {"eyes": None, "mouth": None}),
    ],
)
def test_agreement(claim, seen, expected):
    assert agreement(claim, seen) == expected


def test_endpoint_returns_what_gemma_saw(monkeypatch):
    monkeypatch.setattr(verify_module, "chat", lambda *a, **k: json.dumps({"person": True, "eyes": "closed", "mouth": "closed"}))

    response = client.post("/vision/verify", json={"image": JPEG_B64, "claim": {"eyes": "closed", "mouth": "open"}})

    assert response.status_code == 200, response.text
    assert response.json()["agrees"] == {"eyes": True, "mouth": False}


def test_endpoint_rejects_what_is_not_a_jpeg():
    response = client.post("/vision/verify", json={"image": "iVBORw0KGgoAAAANSUhEUg", "claim": {"eyes": "open", "mouth": "open"}})

    assert response.status_code == 422


def test_model_down_is_a_503(monkeypatch):
    def down(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(verify_module, "chat", down)

    assert client.post("/vision/verify", json={"image": JPEG_B64, "claim": {"eyes": "open", "mouth": "open"}}).status_code == 503
