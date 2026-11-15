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
        assert action["type"] in {"open_relax", "open_measure", "open_habits", "close_panels"}, key
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
