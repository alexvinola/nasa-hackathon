"""The HUD skill: the model picks ONE id from the catalogue; nothing it says is trusted beyond that."""

import pytest

from pulsar import hud_actions, hud_skill


def asked(answer):
    calls = []

    def chat(messages, options=None):
        calls.append(messages)
        return answer

    return chat, calls


def test_the_catalogue_is_offered_to_the_model_with_every_action():
    prompt = hud_skill.system_prompt()
    for key in hud_skill.CATALOGUE:
        assert f"- {key}:" in prompt
    assert "answer none" in prompt or "none" in prompt


def test_every_catalogue_action_is_one_the_hud_understands():
    for key, entry in hud_skill.CATALOGUE.items():
        action = entry["action"]
        assert action["type"] in {"open_relax", "open_measure", "open_habits", "close_panels", "set_language", "dev_menu",
                                  "set_overlay", "open_health", "log_habit", "set_measure"}, key
        assert entry["say"] in hud_actions.SAYS["es"] and entry["say"] in hud_actions.SAYS["en"], key
        if "name" in entry:
            assert entry["name"] in hud_actions.NAMES["es"], key


def test_a_wish_without_a_fixed_phrase_opens_the_matching_panel():
    chat, calls = asked("relax_body")
    reply = hud_skill.choose("tengo el cuello hecho un cuadro, algo que me ayude", "es", chat)
    assert reply["action"] == {"type": "open_relax", "exercise": "body"}
    assert reply["say"] == "Empezamos relajación del cuerpo."
    assert calls and calls[0][0]["role"] == "system"


@pytest.mark.parametrize("answer", ["none", "nothing fits", "open_everything", "", "relax_body_please_and_more"])
def test_an_answer_outside_the_closed_list_does_nothing(answer):
    chat, _ = asked(answer)
    assert hud_skill.choose("estoy agobiado", "es", chat) is None


def test_the_model_is_not_asked_about_ordinary_chat():
    chat, calls = asked("relax_menu")
    assert hud_skill.choose("cuéntame un chiste de astronautas", "es", chat) is None
    assert hud_skill.choose("estoy agobiado " + "y " * 40, "es", chat) is None  # a long text is a conversation
    assert calls == []


def test_the_answer_is_found_even_with_noise_around_it():
    chat, _ = asked("Action: relax_eyes.")
    assert hud_skill.choose("me pican los ojos de tanta pantalla", "es", chat)["action"]["exercise"] == "eyes"


@pytest.mark.parametrize(
    ("answer", "action"),
    [
        ("lang_en", {"type": "set_language", "lang": "en"}),
        ("mesh_off", {"type": "set_overlay", "target": "mesh", "on": False}),
        ("health_eyes", {"type": "open_health", "id": "eyes"}),
        ("dev_open", {"type": "dev_menu", "open": True}),
    ],
)
def test_interface_wishes_are_in_the_catalogue(answer, action):
    chat, _ = asked(answer)
    assert hud_skill.choose("quiero la malla", "es", chat)["action"] == action


def test_a_habit_the_model_reads_is_checked_like_a_fixed_phrase():
    chat, _ = asked("log_water 3")
    reply = hud_skill.choose("me he bebido tres vasos", "es", chat)
    assert reply["action"] == {"type": "log_habit", "habit": "water", "amount": 3.0}
    assert reply["say"] == "Anotado: 3 vasos de agua."
    chat, _ = asked("log_water 500")
    assert hud_skill.choose("me he bebido un monton de agua", "es", chat) is None
    chat, _ = asked("log_water")
    assert hud_skill.choose("he bebido agua", "es", chat) is None


def test_a_measurement_the_model_reads_must_fit_the_contract():
    chat, _ = asked("set_bloodPressure 120 80")
    reply = hud_skill.choose("mi tension arterial son ciento veinte y ochenta", "es", chat)
    assert reply["action"] == {"type": "set_measure", "signal": "selfReport.bloodPressure", "values": {"systolic": 120.0, "diastolic": 80.0}}
    chat, _ = asked("set_bodyTempC 99")
    assert hud_skill.choose("tengo 99 de temperatura", "es", chat) is None
