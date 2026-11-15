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


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Como medir mi frecuencia cardiaca", {"type": "open_measure", "signal": "biometrics.heartRateBpm"}),
        ("¿Cómo puedo medir mi frecuencia cardíaca?", {"type": "open_measure", "signal": "biometrics.heartRateBpm"}),
        ("Donde medir mi sueño", {"type": "open_measure", "signal": "selfReport.sleepHoursLast24h"}),
        ("quiero saber cómo tomar la tensión", {"type": "open_measure", "signal": "selfReport.bloodPressure"}),
        ("how do I measure my glucose", {"type": "open_measure", "signal": "selfReport.glucoseMgDl"}),
        ("hoy he bebido 6 vasos de agua", {"type": "log_habit", "habit": "water", "amount": 6.0}),
        ("hoy he bebido seis vasos de agua", {"type": "log_habit", "habit": "water", "amount": 6.0}),
        ("me he tomado dos vasos de agua", {"type": "log_habit", "habit": "water", "amount": 2.0}),
        ("hoy he dormido ocho horas", {"type": "set_measure", "signal": "selfReport.sleepHoursLast24h", "values": {"sleepHoursLast24h": 8.0}}),
        ("cambia a inglés", {"type": "set_language", "lang": "en"}),
        ("habla en español", {"type": "set_language", "lang": "es"}),
        ("abre el menú de depuración", {"type": "dev_menu", "open": True}),
        ("cierra el menú de desarrollo", {"type": "dev_menu", "open": False}),
        ("activa la malla facial", {"type": "set_overlay", "target": "mesh", "on": True}),
        ("desactiva la comprobación IA", {"type": "set_overlay", "target": "ai_check", "on": False}),
        ("muéstrame la salud del corazón", {"type": "open_health", "id": "heart"}),
        ("cierra todas las ventanas", {"type": "close_panels"}),
        ("close everything", {"type": "close_panels"}),
    ],
)
def test_the_whole_ui_can_be_asked_for(text, expected):
    assert action(text) == expected


def test_how_is_a_reading_is_not_a_request_to_measure():
    assert hud_actions.parse("¿cómo está mi pulso?", "es") is None
    assert hud_actions.parse("¿cuál es mi temperatura?", "es") is None


def measures(text, lang="es"):
    reply = hud_actions.parse(text, lang) or {}
    return [(a["signal"], {k: float(v) for k, v in a["values"].items()}) for a in reply.get("actions", [])]


BP = "selfReport.bloodPressure"
HR = "biometrics.heartRateBpm"
TEMP = "selfReport.bodyTempC"
SLEEP = "selfReport.sleepHoursLast24h"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("anota la tension 120 80", [(BP, {"systolic": 120.0, "diastolic": 80.0})]),
        ("mi presion arterial es 120 con 80", [(BP, {"systolic": 120.0, "diastolic": 80.0})]),
        ("tension arterial 12 8", [(BP, {"systolic": 120.0, "diastolic": 80.0})]),
        ("mi tension es ciento veinte sobre ochenta", [(BP, {"systolic": 120.0, "diastolic": 80.0})]),
        ("mi pulso es setenta y dos", [(HR, {"heartRateBpm": 72.0})]),
        ("tengo noventa y cinco de glucosa", [("selfReport.glucoseMgDl", {"glucoseMgDl": 95.0})]),
        ("mi temperatura es treinta y seis coma ocho", [(TEMP, {"bodyTempC": 36.8})]),
        ("mi temperatura es 36 con 8", [(TEMP, {"bodyTempC": 36.8})]),
        ("temperatura treinta y seis y medio", [(TEMP, {"bodyTempC": 36.5})]),
        ("he dormido siete horas y media", [(SLEEP, {"sleepHoursLast24h": 7.5})]),
        ("mi animo es cuatro", [("selfReport.mood", {"mood": 4.0})]),
        ("my heart rate is seventy two", [(HR, {"heartRateBpm": 72.0})]),
        ("mi pulso es 72 y mi temperatura 36.8", [(HR, {"heartRateBpm": 72.0}), (TEMP, {"bodyTempC": 36.8})]),
        ("he dormido 7 horas y mi animo es 4", [(SLEEP, {"sleepHoursLast24h": 7.0}), ("selfReport.mood", {"mood": 4.0})]),
    ],
)
def test_every_measurement_can_be_typed_in_however_it_is_said(text, expected):
    assert measures(text) == expected


def test_all_six_measurements_in_one_sentence():
    text = "pulso 72, tension 120 80, glucosa 95, temperatura 36.8, sueño 7, animo 4"
    assert len(measures(text)) == 6


def test_one_value_out_of_range_does_not_stop_the_others():
    reply = hud_actions.parse("mi pulso es 72 y mi temperatura es 99", "es")
    assert [a["signal"] for a in reply["actions"]] == [HR]
    assert "fuera de lo que admite" in reply["say"]


def test_a_quantity_with_its_unit_is_enough_to_log_a_habit():
    assert action("dos vasos de agua") == {"type": "log_habit", "habit": "water", "amount": 2.0}


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("abre el menu de relajacion", "open_relax"),
        ("pon un ejercicio para los hombros", "open_relax"),
        ("soltar tension", "open_relax"),
        ("relajar los ojos", "open_relax"),
        ("como me tomo la temperatura", "open_measure"),
        ("quiero medirme el pulso", "open_measure"),
        ("abre registrar medidas", "open_measure"),
        ("muestrame el mes", "open_habits"),
        ("en ingles por favor", "set_language"),
        ("abre el panel de desarrollo", "dev_menu"),
        ("he hecho un ejercicio de respiracion", "log_habit"),
        ("hoy corri media hora", "log_habit"),
        ("salud de la columna", "open_health"),
        ("close all windows", "close_panels"),
        ("turn off the ai check", "set_overlay"),
    ],
)
def test_each_kind_of_action_has_several_ways_to_ask_for_it(text, kind):
    assert action(text)["type"] == kind
