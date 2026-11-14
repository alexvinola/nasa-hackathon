"""PULSAR's stage director: Gemma 4 (through Ollama, on this machine) decides where the mascot goes, what it
says and how it reacts, from what the camera sees and what the astronaut said.

This is presentation only. Gemma picks from closed lists (`SPOTS`, `REACTIONS`) and writes one short line; it never
decides a health status or an escalation (the rules engine does). Everything it returns is validated here: an
unknown spot or reaction, or a line with numbers or clinical words, is replaced by `FALLBACK`.
"""

import json
import re
import urllib.error
import urllib.request

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from senses import OLLAMA_URL, VISION_MODEL

router = APIRouter()

# Screen zones the mascot can fly to; the frontend maps each one to coordinates.
SPOTS = ["home", "top_right", "mid_left", "mid_right", "bottom_left", "bottom_center", "bottom_right"]
# "calm" is its usual look, "alert" is the attention pose; the sprite turns "calm" into talking while it types.
REACTIONS = ["calm", "alert"]

# Which side of the screen each zone is on. The view is mirrored, so a person on the left of the camera frame
# stands on the right of the screen.
SCREEN_SIDE = {"home": "left", "mid_left": "left", "bottom_left": "left",
               "top_right": "right", "mid_right": "right", "bottom_right": "right", "bottom_center": "centre"}
CLEAR_OF = {"left": "mid_right", "right": "mid_left"}  # where to go to leave a person on that screen side alone
FRAME_TO_SCREEN = {"left": "right", "right": "left"}

FALLBACK = {"say": "I'm here if you need me.", "spot": "home", "reaction": "calm", "speak": True}
SILENT = {"say": "", "spot": "", "reaction": "calm", "speak": False}  # nothing worth saying: the mascot stays as is

# A line is rejected when it states numbers or sounds like a diagnosis, a judgement of health or an order.
FORBIDDEN = re.compile(
    r"\d|diagnos|disease|syndrome|fatigue|tired|sick|ill\b|pain|heart|blood|pressure|oxygen|emergency|"
    r"danger|critical|you must|you should|doctor|surgeon|medic",
    re.I,
)

SYSTEM = (
    "You are the stage director of PULSAR, a small friendly robot mascot that floats over a camera view for an "
    "astronaut. You decide where PULSAR floats to, how it reacts and the one short sentence it says (at most 14 "
    "words, warm, plain English). The astronaut gives PULSAR instructions by voice or text: the latest one is the "
    "'standing instruction' and you must follow it (for example watch for something, describe what is visible, "
    "answer a question about the picture, or stay quiet). "
    "When the astronaut has just spoken to PULSAR, always answer (speak=true), using what the camera sees. "
    "When only the camera changed, speak=true only if the change matters for the standing instruction or something "
    "clearly new and notable appeared; otherwise speak=false. Never repeat or rephrase anything in 'already said'. "
    "Say in 'person_side' which side of the camera frame the person is on (left, right, centre, or none), then "
    "choose 'spot' away from them. Use 'alert' only when something new or unusual just appeared, otherwise 'calm'. "
    "Only describe or acknowledge what was seen or heard. Never diagnose, never judge health, fatigue or mood, "
    "never give medical advice or orders, never use numbers."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "spot": {"type": "string", "enum": SPOTS},
        "reaction": {"type": "string", "enum": REACTIONS},
        "say": {"type": "string"},
        "person_side": {"type": "string", "enum": ["left", "right", "centre", "none"]},
        "speak": {"type": "boolean"},
    },
    "required": ["speak", "person_side", "spot", "reaction", "say"],
}


class Scene(BaseModel):
    seen: str = Field("", max_length=400)  # the vision model's description of the camera frame
    instruction: str = Field("", max_length=400)  # the astronaut's latest instruction (voice transcript or typed)
    user_spoke: bool = False  # True when `instruction` is new in this request, False for a camera-only update
    said: list[str] = Field(default_factory=list, max_length=6)  # PULSAR's last lines, so it does not repeat itself
    spot: str = Field("home", max_length=20)  # where PULSAR is now, so it can decide to move


FILLER = {"the", "and", "you", "your", "are", "was", "has", "have", "with", "for", "that", "this"}


def words(text: str) -> set[str]:
    """Rough word stems (first three letters, no filler) so 'sits' and 'sitting' count as the same word."""
    return {w[:3] for w in re.findall(r"[a-z']+", text.lower()) if len(w) > 2 and w not in FILLER}


def repeats(say: str, said: list[str]) -> bool:
    """True when `say` is mostly the same words as something PULSAR already said."""
    mine = words(say)
    return any(mine and len(mine & words(old)) / len(mine | words(old)) >= 0.5 for old in said)


def validate(raw: dict, said: list[str] = (), user_spoke: bool = True) -> dict:
    """Returns the director's decision when it is allowed, else FALLBACK (or SILENT when there is nothing new)."""
    if raw.get("speak") is False and not user_spoke:
        return SILENT
    say = str(raw.get("say", "")).strip()
    if not user_spoke and repeats(say, list(said)):
        return SILENT
    if raw.get("spot") not in SPOTS or raw.get("reaction") not in REACTIONS:
        return FALLBACK
    if not say or len(say.split()) > 20 or FORBIDDEN.search(say):
        return FALLBACK
    spot = raw["spot"]
    person = FRAME_TO_SCREEN.get(raw.get("person_side"))
    if person and SCREEN_SIDE[spot] == person:  # Gemma put the mascot over the person: move it to the free side
        spot = CLEAR_OF[person]
    return {"say": say, "spot": spot, "reaction": raw["reaction"], "speak": True}


def direct(scene: Scene) -> dict:
    facts = []
    if scene.seen:
        facts.append(f"The camera sees: {scene.seen}")
    if scene.instruction:
        when = "just told PULSAR" if scene.user_spoke else "told PULSAR earlier (standing instruction)"
        facts.append(f"The astronaut {when}: {scene.instruction}")
    if scene.said:
        facts.append("Already said by PULSAR: " + " | ".join(scene.said))
    facts.append("Trigger: " + ("the astronaut spoke" if scene.user_spoke else "the camera changed"))
    facts.append(f"PULSAR is currently at: {scene.spot}")
    payload = {
        "model": VISION_MODEL,
        "stream": False,
        "think": False,
        "format": SCHEMA,
        "options": {"temperature": 0.6, "num_predict": 120},
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "\n".join(facts)}],
    }
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            content = json.load(response)["message"]["content"]
        return validate(json.loads(content), scene.said, scene.user_spoke)
    except urllib.error.HTTPError as error:
        raise HTTPException(502, f"Ollama refused the request: {error.read().decode(errors='replace')}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise HTTPException(503, f"Ollama is not answering at {OLLAMA_URL}: start it and pull {VISION_MODEL}") from error
    except (json.JSONDecodeError, KeyError, TypeError):
        return FALLBACK  # the model broke the format: the mascot just stays calm


@router.post("/pulsar/act")
async def act(scene: Scene) -> dict:
    """Body: what was seen and the astronaut's instruction. Returns where PULSAR goes, how it reacts and what it says."""
    if not scene.seen and not scene.instruction:
        raise HTTPException(400, "nothing seen or instructed")
    return await run_in_threadpool(direct, scene)
