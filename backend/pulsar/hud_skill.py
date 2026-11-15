"""The HUD skill: a catalogue of what PULSAR can do on the screen, written in plain words, and the model that picks
one when the astronaut's request matches none of the fixed phrases of `hud_actions`.

"Estoy agobiado" or "quiero soltar tensión" name no exercise and no panel, yet the right answer is to open the
relaxation window with the right exercise on. The catalogue (`assets/hud_skill.json`) tells the model, per action,
which kind of request belongs to it; the model answers with ONE id from that closed list, or `none`. Everything else
stays as it was: the id is looked up here and turned into the same action `hud_actions` would have produced, so the
model never writes an action, a number or a sentence, and it is never asked about health: a request that names a
symptom for someone to judge is for the rules engine (see `director.HEALTH_QUESTION`), this only maps a wish to a
panel. It is asked only when the request carries one of the catalogue's cue words, so ordinary chat costs nothing.
"""

import json
import re
from collections.abc import Callable
from functools import cache
from typing import Any

from pulsar import settings
from pulsar.hud_actions import NAMES, SAYS

CATALOGUE = json.loads((settings.BACKEND_DIR / "assets" / "hud_skill.json").read_text(encoding="utf-8"))["actions"]
NONE = "none"
MAX_WORDS = 30  # a request longer than this is a conversation, not a command


@cache
def cues() -> re.Pattern:
    """Every cue word of the catalogue: what makes a request worth asking the model about."""
    return re.compile("|".join(cue for entry in CATALOGUE.values() for cue in entry["cues"]), re.I)


def worth_asking(text: str) -> bool:
    return len(text.split()) <= MAX_WORDS and bool(cues().search(text))


@cache
def system_prompt() -> str:
    lines = [
        f"- {key}: {entry['when']} Examples: " + "; ".join(f'"{example}"' for example in entry["examples"][:3])
        for key, entry in CATALOGUE.items()
    ]
    return (
        "You route what an astronaut says to ONE action of their health-companion screen.\n"
        "Pick the action whose description fits what they ask for or need, in any language and however they put it.\n"
        "Answer with the action id only, nothing else. If no action fits (a question, a chat, anything else), answer "
        f"{NONE}.\nYou never judge anyone's health: you only choose the panel that fits the request.\nActions:\n"
        + "\n".join(lines)
    )


def pick(answer: str) -> str | None:
    """The catalogue id the model's answer names, or None (`none`, or anything not in the closed list)."""
    for word in re.findall(r"[a-z_]+", answer.lower()):
        if word in CATALOGUE:
            return word
    return None


def reply(action_id: str, lang: str) -> dict[str, Any]:
    entry = CATALOGUE[action_id]
    name = NAMES[lang].get(entry.get("name", ""), "")
    # An eye-rest exercise and "the eyes" of the health points share a word: the exercise name is the one used here.
    return {"say": SAYS[lang][entry["say"]].format(name=name), "action": dict(entry["action"])}


def choose(text: str, lang: str | None, chat: Callable[..., str]) -> dict[str, Any] | None:
    """Asks the model which catalogue action the request means; None when it names none of them."""
    if not worth_asking(text):
        return None
    lang = settings.pick_lang(lang)
    answer = chat(
        [{"role": "system", "content": system_prompt()}, {"role": "user", "content": text}],
        options={"temperature": 0, "num_predict": 8, "stop": ["\n"]},
    )
    action_id = pick(answer)
    return reply(action_id, lang) if action_id else None
