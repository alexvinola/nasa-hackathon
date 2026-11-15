"""The backend speaks the language it is asked in: Spanish by default, English with `lang=en`."""

from fastapi.testclient import TestClient

from main import app
from pulsar import readings
from pulsar.voice import pipeline

client = TestClient(app)
DECISION = {"status": "RED", "escalation": "FLIGHT_SURGEON", "factors": [], "countermeasureId": None}


def test_rules_are_worded_in_the_requested_language():
    es = client.get("/rules").json()
    en = client.get("/rules?lang=en").json()
    assert [r["id"] for r in es] == [r["id"] for r in en]
    assert es != en


def test_unknown_language_falls_back_to_the_default():
    assert client.get("/rules?lang=xx").json() == client.get("/rules").json()


def test_fallback_sentences_and_surgeon_check_follow_the_language():
    assert "cirujano de vuelo" in pipeline.fallback(DECISION, None, "es")
    assert "flight surgeon" in pipeline.fallback(DECISION, None, "en")
    assert pipeline.violations("Call someone now.", DECISION, "", "en") == ["does not name the flight surgeon"]
    assert pipeline.violations("Contact the flight surgeon now.", DECISION, "", "en") == []


def test_spoken_readings_follow_the_language():
    results = {"get_heart_rate": {"heartRateBpm": 70, "assessment": "within limits"}}
    assert "pulsaciones" in readings.spoken(results, "es")
    assert "beats per minute" in readings.spoken(results, "en")
