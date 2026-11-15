"""PULSAR's requests to the HUD: a closed list of actions, matched without the model."""

import pytest
from fastapi.testclient import TestClient

from main import app
from pulsar import hud_actions, ratelimit


def action(text: str, lang: str = "es", **kw):
    reply = hud_actions.parse(text, lang, **kw)
    return reply and reply.get("action")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("abre relajación", {"type": "open_relax", "exercise": None}),
        ("quiero relajarme, ponme respiración", {"type": "open_relax", "exercise": "breathe"}),
        ("un descanso para los ojos", None),  # no relax word: not a HUD request
        ("relajación de ojos por favor", {"type": "open_relax", "exercise": "eyes"}),
        ("abre relajación y elige tú uno", {"type": "open_relax", "exercise": "breathe"}),
        ("quiero medir la tensión", {"type": "open_measure", "signal": "selfReport.bloodPressure"}),
        ("abre las medidas", {"type": "open_measure", "signal": None}),
        ("mi temperatura es 36,8", {"type": "set_measure", "signal": "selfReport.bodyTempC", "values": {"bodyTempC": 36.8}}),
        ("tengo 120 sobre 80 de tensión", {"type": "set_measure", "signal": "selfReport.bloodPressure", "values": {"systolic": 120.0, "diastolic": 80.0}}),
        ("he dormido 7 horas", {"type": "set_measure", "signal": "selfReport.sleepHoursLast24h", "values": {"sleepHoursLast24h": 7.0}}),
        ("he hecho 30 minutos de ejercicio", {"type": "log_habit", "habit": "exercise", "amount": 30.0}),
        ("he hecho una hora de ejercicio", {"type": "log_habit", "habit": "exercise", "amount": 60.0}),
        ("me he bebido 2 vasos de agua", {"type": "log_habit", "habit": "water", "amount": 2.0}),
        ("muéstrame el historial de hábitos", {"type": "open_habits", "expand": True}),
        ("abre mis hábitos", {"type": "open_habits", "expand": False}),
    ],
)
def test_requests_become_closed_actions(text, expected):
    assert action(text) == expected


def test_english_works_too():
    assert action("log 3 glasses of water", "en") == {"type": "log_habit", "habit": "water", "amount": 3.0}
    assert action("open relaxation", "en") == {"type": "open_relax", "exercise": None}


def test_the_agent_picks_an_exercise_from_the_camera_measurements():
    tired = {"biometrics": {"perclos": 0.3, "fatigueScore": 0.1}}
    assert action("elige uno por mí, relajación", telemetry=tired)["exercise"] == "eyes"
    assert action("elige uno por mí, relajación", telemetry={"biometrics": {"perclos": 0.02}})["exercise"] == "breathe"


def test_values_outside_the_contract_are_refused_without_an_action():
    reply = hud_actions.parse("mi temperatura es 99", "es")
    assert reply and "action" not in reply
    assert "action" not in hud_actions.parse("he hecho 5000 minutos de ejercicio", "es")


def test_questions_and_other_talk_are_not_actions():
    assert hud_actions.parse("¿cuál es mi pulso?", "es") is None
    assert hud_actions.parse("¿cuánta agua debo beber?", "es") is None
    assert hud_actions.parse("qué hora es", "es") is None


def test_how_is_today_going_is_answered_from_the_hud_numbers():
    habits = {"score": 0.5, "exercise": 60, "water": 4, "relax": 1, "sleep": 7.5}
    reply = hud_actions.parse("cómo voy con mis hábitos", "es", habits=habits)
    assert "action" not in reply and "50 por ciento" in reply["say"]


def test_the_director_returns_the_action_without_calling_the_model():
    client = TestClient(app, base_url="http://localhost:8000")
    app.state._state["rate_limiter"] = ratelimit.RateLimiter(None)
    body = client.post("/pulsar/act", json={"instruction": "abre relajación", "user_spoke": True}).json()
    assert body["action"] == {"type": "open_relax", "exercise": None}
    assert body["speak"] is True and body["say"]
