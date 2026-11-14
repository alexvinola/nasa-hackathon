"""Heart rate and cabin CO2 through the mock MCP server. The server is real (a subprocess); only Gemma is scripted."""

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
    assert "Cabin CO2 at 6.5 mmHg" in tool_result["content"]  # the rules engine's verdict travels with the reading
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
    assert say == "El CO2 de la cabina está en 6.5 mmHg, por encima del límite. Sigue los pasos que te muestro en pantalla." and out_of_limits
