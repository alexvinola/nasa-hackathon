"""PULSAR's stage director: Gemma 4 (through Ollama, on this machine) decides where the mascot goes, what it
says and how it reacts, from what the camera sees and what the astronaut said.

This is presentation only. Gemma picks from closed lists (`SPOTS`, `REACTIONS`) and writes one short line; it never
decides a health status or an escalation (the rules engine does). Everything it returns is validated here: an
unknown spot or reaction, or a line with numbers or clinical words, is replaced by `FALLBACK`.
"""

import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from senses import MAX_IMAGE, chat, local_only

router = APIRouter(dependencies=[Depends(local_only)])

# Screen zones the mascot can fly to; the frontend maps each one to coordinates.
SPOTS = ["home", "top_right", "mid_left", "mid_right", "bottom_left", "bottom_center", "bottom_right"]
# "calm" is its usual look, "alert" is the attention pose; the sprite turns "calm" into talking while it types.
REACTIONS = ["calm", "alert"]

# Which side of the screen each zone is on. The frontend sends frames already mirrored like the HUD, so the left of
# the frame is the left of the screen.
SCREEN_SIDE = {"home": "left", "mid_left": "left", "bottom_left": "left",
               "top_right": "right", "mid_right": "right", "bottom_right": "right", "bottom_center": "centre"}
CLEAR_OF = {"left": "mid_right", "right": "mid_left"}  # where to go to leave a person on that screen side alone

FALLBACK = {"say": "I'm here if you need me.", "spot": "home", "reaction": "calm", "speak": True}
SILENT = {"say": "", "spot": "", "reaction": "calm", "speak": False}  # nothing worth saying: the mascot stays as is

# A line is rejected when it states numbers or sounds like a diagnosis, a judgement of health or an order.
FORBIDDEN = re.compile(
    r"\d|diagnos|disease|syndrome|fatigue|tired|sick|ill\b|pain|heart|blood|pressure|oxygen|emergency|"
    r"danger|critical|you must|you should|doctor|surgeon|medic",
    re.I,
)

# Kept short and answered in one line on purpose. Measured on a CPU-only laptop with gemma4:e2b-it-qat: Ollama
# re-reads the whole prompt on every call (about 100 tokens a second) and writes about 8 tokens a second, so the
# earlier 400-token prompt with a 52-token JSON answer took about 11 s. `parse` turns the line back into the
# fields `validate` checks.
SYSTEM = f"""\
You are PULSAR, the astronaut's personal companion: a small, warm, calm robot floating over their camera view.
Reply with one line only: side|spot|reaction|sentence
side: where the person is in the picture (left, right, centre, none).
spot: where you float, away from the person ({", ".join(SPOTS)}).
reaction: calm, or alert if something new just appeared.
sentence: at most 14 words, first person, naming the concrete things in view; - to stay silent.
Example: centre|top_right|calm|I can see you holding a white mug.
Always answer when the astronaut just spoke. If only the camera changed, write - unless it matters for their \
instruction or is clearly new; never repeat a line already said.
Only describe what is visible: never comment on health, tiredness or mood, never advise or give orders, never \
write digits. If asked, say that is not yours to judge.
"""

LINE = re.compile(r"(left|right|centre|center|none)\s*\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*(.+)", re.I)


def parse(content: str) -> dict:
    """`side|spot|reaction|sentence` as the dict `validate` expects; an answer in any other shape raises."""
    side, spot, reaction, say = (part.strip() for part in LINE.fullmatch(content.strip()).groups())
    quiet = say == "-"
    return {"person_side": side.lower(), "spot": spot, "reaction": reaction, "say": "" if quiet else say, "speak": not quiet}


class Scene(BaseModel):
    seen: str = Field("", max_length=400)  # the vision model's description of the camera frame
    instruction: str = Field("", max_length=400)  # the astronaut's latest instruction (voice transcript or typed)
    user_spoke: bool = False  # True when `instruction` is new in this request, False for a camera-only update
    said: list[str] = Field(default_factory=list, max_length=6)  # PULSAR's last lines, so it does not repeat itself
    spot: str = Field("home", max_length=20)  # where PULSAR is now, so it can decide to move
    # The current frame as a base64 JPEG, sent when the astronaut speaks so the answer comes from the picture itself.
    image: str = Field("", max_length=4 * MAX_IMAGE // 3 + 4, pattern=r"^(/9j/[A-Za-z0-9+/]*={0,2})?$")


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
    person = raw.get("person_side")
    if person in CLEAR_OF and SCREEN_SIDE[spot] == person:  # Gemma put the mascot over the person: move it to the free side
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
    user = {"role": "user", "content": "\n".join(facts)}
    if scene.image:
        user["content"] += "\nThe current camera frame is attached: look at it and answer from it."
        user["images"] = [scene.image]
    # The system prompt goes first and never changes, so Ollama reuses its cached evaluation on every call.
    content = chat(
        [{"role": "system", "content": SYSTEM}, user],
        options={"temperature": 0.3, "num_predict": 48, "stop": ["\n"]},  # one line of about 20 tokens
    )
    try:
        return validate(parse(content), scene.said, scene.user_spoke)
    except AttributeError:
        return FALLBACK  # the model broke the format: the mascot just stays calm


@router.post("/pulsar/act")
async def act(scene: Scene) -> dict:
    """Body: what was seen and the astronaut's instruction. Returns where PULSAR goes, how it reacts and what it says."""
    if not scene.seen and not scene.instruction:
        raise HTTPException(400, "nothing seen or instructed")
    return await run_in_threadpool(direct, scene)
