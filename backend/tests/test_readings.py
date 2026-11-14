"""Heart rate and cabin CO2 through the mock MCP server. The server is real (a subprocess); only Gemma is scripted."""

import json
from pathlib import Path

import pytest

from pulsar import readings


def scripted(monkeypatch, *replies):
    """Gemma's replies in order; `seen` collects the messages each call received."""
    seen, queue = [], list(replies)
    monkeypatch.setattr(readings, "chat_message", lambda messages, **extra: seen.append(list(messages)) or queue.pop(0))
    return seen


def ask_tool(name):
    return {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": name, "arguments": {}}}]}


def test_gemma_calls_the_co2_tool_and_answers_from_its_result(monkeypatch):
    seen = scripted(monkeypatch, ask_tool("get_cabin_co2"),
                    {"content": "El CO2 de la cabina está en 6,5 mmHg, por encima de 4 mmHg."})
    say, out_of_limits = readings.answer("¿Cómo está el CO2 de la cabina?")
    assert say == "El CO2 de la cabina está en 6,5 mmHg, por encima de 4 mmHg." and out_of_limits
    tool_result = seen[1][-1]
    assert tool_result["role"] == "tool" and '"cabinCo2_mmHg": 6.5' in tool_result["content"]
    assert "CO2 de la cabina en 6.5 mmHg" in tool_result["content"]  # the rules engine's verdict travels with the reading
    assert "stepsToTake" in tool_result["content"]  # and its steps


def test_heart_rate_is_within_limits_in_this_scenario(monkeypatch):
    scripted(monkeypatch, ask_tool("get_heart_rate"), {"content": "Tu pulso es de 76 pulsaciones por minuto."})
    assert readings.answer("¿Cuántas pulsaciones tengo?") == ("Tu pulso es de 76 pulsaciones por minuto.", False)


@pytest.mark.parametrize("reply", [
    {"content": "Tu pulso es de 90 pulsaciones por minuto."},  # a figure the tool never returned
    {"content": "No lo sé."},  # never asked the tool
])
def test_a_bad_answer_is_replaced_by_the_readings_themselves(monkeypatch, reply):
    scripted(monkeypatch, reply if "tool_calls" in reply else ask_tool("get_heart_rate"), reply)
    say, _ = readings.answer("¿Cuántas pulsaciones tengo?")
    assert say == "Tu pulso es de 76 pulsaciones por minuto."


def test_without_any_tool_call_the_question_decides_what_to_read(monkeypatch):
    scripted(monkeypatch, {"content": "Creo que bien."})
    say, out_of_limits = readings.answer("¿Y el CO2?")
    assert say == "El CO2 de la cabina está en 6.5 mmHg. Hay una lectura por encima de su límite. Sigue los pasos que te muestro en pantalla." and out_of_limits


def hud_telemetry(**biometrics):
    """What the HUD would send: the nominal scenario with the readings it is showing right now."""
    nominal = json.loads((Path(__file__).parents[2] / "shared/scenarios/01-nominal.json").read_text("utf-8"))["input"]
    nominal["biometrics"].update(biometrics)
    return nominal


def test_the_readings_are_the_ones_the_hud_shows(monkeypatch):
    seen = scripted(monkeypatch, ask_tool("get_vitals"), {"content": "Tu pulso es de 88 pulsaciones por minuto."})
    telemetry = hud_telemetry(heartRateBpm=88, perclos=0.12)
    telemetry["environment"]["cabinCo2_mmHg"] = 6.5
    readings.answer("¿Cómo van mis constantes vitales?", telemetry)
    result = json.loads(seen[1][-1]["content"])
    assert result["heartRateBpm"] == 88 and result["eyesClosedPercent"] == 12 and result["cabinCo2_mmHg"] == 6.5
    assert "CO2 de la cabina en 6.5 mmHg" in result["assessment"] and result["stepsToTake"]
    assert result["source"] == "the HUD's current readings"


def test_vitals_fallback_reads_the_vitals_tool_when_gemma_does_not_ask(monkeypatch):
    scripted(monkeypatch, {"content": "Voy a revisar tus constantes ahora."})
    say, out_of_limits = readings.answer("¿Cómo van mis constantes vitales?", hud_telemetry(heartRateBpm=70))
    assert say == "Tu pulso es de 70 pulsaciones por minuto. El CO2 de la cabina está en 2.9 mmHg. La dosis de radiación es de 0.8 mSv." and not out_of_limits


def test_wording_that_contradicts_the_verdict_is_replaced(monkeypatch):
    scripted(monkeypatch, ask_tool("get_vitals"),
             {"content": "Tu pulso es de 88 pulsaciones por minuto y el CO2 es de 6.5 mmHg. Ambos están dentro de los límites."})
    telemetry = hud_telemetry(heartRateBpm=88)
    telemetry["environment"]["cabinCo2_mmHg"] = 6.5
    say, out_of_limits = readings.answer("¿Cómo van mis constantes vitales?", telemetry)
    assert out_of_limits and "dentro de los límites" not in say and "por encima de su límite" in say


def test_radiation_above_its_limit_carries_its_own_steps_not_the_co2_ones(monkeypatch):
    seen = scripted(monkeypatch, ask_tool("get_radiation"),
                    {"content": "La dosis de radiación es de 6.2 mSv, por encima de 5 mSv."})
    telemetry = hud_telemetry()
    telemetry["environment"]["radiation_mSv"] = 6.2
    telemetry["environment"]["cabinCo2_mmHg"] = 6.5  # CO2 is also over: the decision's main countermeasure is CO2's
    readings.answer("¿Cómo está la radiación?", telemetry)
    result = json.loads(seen[1][-1]["content"])
    assert result["radiation_mSv"] == 6.2 and not result["withinLimits"]
    assert any("dosímetro" in step for step in result["stepsToTake"])
    assert not any("CO2" in step for step in result["stepsToTake"])


def test_radiation_question_without_a_tool_call_falls_back_to_the_reading(monkeypatch):
    scripted(monkeypatch, {"content": "Todo bien."})
    say, out_of_limits = readings.answer("¿Cuánta radiación llevo?", hud_telemetry())
    assert say == "La dosis de radiación es de 0.8 mSv." and not out_of_limits


def test_advice_nobody_asked_for_is_dropped_when_all_is_within_limits(monkeypatch):
    scripted(monkeypatch, ask_tool("get_radiation"),
             {"content": "La radiación es de 0.8 mSv. Estoy contigo, vamos paso a paso. Revisa el sistema de soporte vital."})
    assert readings.answer("¿Cómo está la radiación?", hud_telemetry())[0] == "La dosis de radiación es de 0.8 mSv."
