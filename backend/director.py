"""PULSAR's stage director: Gemma 4 (through Ollama, on this machine) decides where the mascot goes, what it
says and how it reacts, from what the camera sees and what the astronaut said.

This is presentation only. Gemma picks from closed lists (`SPOTS`, `REACTIONS`) and writes one short line; it never
decides a health status or an escalation (the rules engine does). Everything it returns is validated here: an
unknown spot or reaction, or a line with numbers or clinical words, is replaced by `FALLBACK`.
"""

import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from pulsar.contract import telemetry_errors
from pulsar.rules.engine import RulesEngine
from pulsar.readings import ASKS_READINGS, answer as read_sensors
from pulsar.voice.pipeline import first_step, phrase, verdict_text

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

FALLBACK = {"say": "Estoy aquí si me necesitas.", "spot": "home", "reaction": "calm", "speak": True}
SILENT = {"say": "", "spot": "", "reaction": "calm", "speak": False}  # nothing worth saying: the mascot stays as is

# A line is rejected when it states numbers or sounds like a diagnosis, a judgement of health or an order.
FORBIDDEN = re.compile(
    r"\d|diagnos|disease|syndrome|fatigue|tired|sick|\bill\b|\bpain(s|ful)?\b|heart|blood|pressure|oxygen|emergency|"
    r"danger|critical|you must|you should|doctor|surgeon|medic|"
    r"diagnós|enfermedad|síndrome|fatiga|cansad|agotad|enferm|dolor|coraz|sangre|presión|oxígeno|emergencia|"
    r"peligro|crític|debes|deberías|tienes que|médic|cirujan",
    re.I,
)

# Kept short and answered in one line on purpose. Measured on a CPU-only laptop with gemma4:e2b-it-qat: Ollama
# re-reads the whole prompt on every call (about 100 tokens a second) and writes about 8 tokens a second, so the
# earlier 400-token prompt with a 52-token JSON answer took about 11 s. `parse` turns the line back into the
# fields `validate` checks.
SYSTEM = f"""\
You are PULSAR, the astronaut's onboard companion: a small, warm, calm robot floating over their camera view.
Reply with one line only: side|spot|reaction|sentence
side: where the person is in the picture (left, right, centre, none).
spot: where you float, away from the person ({", ".join(SPOTS)}).
reaction: calm, or alert if something new just appeared or a health check is active.
sentence: always in Spanish, at most 16 words, first person, a direct answer; - to stay silent.
Examples:
centre|top_right|calm|Eso es una taza blanca en tu mano derecha.
none|bottom_left|calm|Voy hacia abajo a la izquierda.
centre|home|calm|-
Your skills:
ANSWER what was actually asked, from what you know and from the conversation. Say so when you do not know.
LOOK: when it is about what is visible, answer from the camera.
MOVE: when told to go somewhere, pick that spot.
CARE: you never judge health yourself. A health check, when given, comes from the rules engine and is final: \
say its first step in your own words and never contradict it.
Never write digits. Write - when only the camera changed and it does not matter, or you would repeat yourself.
"""

LINE = re.compile(r"(left|right|centre|center|none)\s*\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*(.+)", re.I)

# Whether to speak at all is decided here, not by the model: measured on gemma4:e2b, it answers whatever it is
# given. With the microphone open, PULSAR answers its name, a question or request, or a reply to what it just said.
WAKE = re.compile(r"\bpuls[aeo]r\b", re.I)
ASKS = re.compile(
    r"[?¿]|^\W*(what|where|who|when|why|how|which|is|are|do|does|did|can|could|would|will|please|tell|show|go|move|"
    r"come|look|describe|watch|stop|hello|hi|hey|thanks|thank|"
    r"qué|dónde|quién|cuándo|por qué|cómo|cuál|puedes|podrías|por favor|dime|muestra|enséñame|ve|muévete|ven|"
    r"mira|describe|observa|detente|hola|gracias)\b",
    re.I,
)


def addressed(heard: str) -> bool:
    """True when words caught by the open microphone look meant for PULSAR rather than for someone else."""
    return bool(WAKE.search(heard) or ASKS.search(heard))

# Health is the rules engine's call, never the model's, so these questions do not reach Gemma at all.
HEALTH_QUESTION = re.compile(
    r"\b(tired|sleepy|exhausted|sick|ill|unwell|health\w*|pain\w*|hurt\w*|fever|dizzy|diagnos\w*|stress\w*|"
    r"depress\w*|anxi\w*|fatigue\w*|medic\w*|symptom\w*|"
    r"cansad\w*|agotad\w*|sueño|enferm\w*|salud|dolor\w*|duele\w*|fiebre|marea\w*|diagnós\w*|estrés|estresad\w*|"
    r"deprim\w*|ansi\w*|fatiga\w*|médic\w*|síntoma\w*)\b",
    re.I,
)
NOT_MINE = "No me corresponde juzgar eso. Solo puedo decirte lo que veo."


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
    via_voice: bool = False  # the instruction came through the open microphone and may not be meant for PULSAR
    engaged: bool = False  # PULSAR answered moments ago, so what the microphone hears now is taken as a reply to it
    # The current readings (the full contract). The rules engine turns them into the health check PULSAR must respect.
    telemetry: dict[str, Any] | None = None
    # Earlier turns, oldest first, each "Astronaut: ..." or "PULSAR: ..."; `compact` bounds what reaches the model.
    history: list[Annotated[str, Field(max_length=300)]] = Field(default_factory=list, max_length=12)
    # The current frame as a base64 JPEG, sent when the astronaut speaks so the answer comes from the picture itself.
    image: str = Field("", max_length=4 * MAX_IMAGE // 3 + 4, pattern=r"^(/9j/[A-Za-z0-9+/]*={0,2})?$")


FILLER = {"the", "and", "you", "your", "are", "was", "has", "have", "with", "for", "that", "this",
          "los", "las", "una", "por", "con", "para", "que", "del", "esto", "eso", "est"}


def words(text: str) -> set[str]:
    """Rough word stems (first three letters, no filler) so 'sits' and 'sitting' count as the same word."""
    return {w[:3] for w in re.findall(r"[^\W\d_]+", text.lower()) if len(w) > 2 and w not in FILLER}


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


def compact(history: list[str]) -> list[str]:
    """PULSAR's memory of the conversation, small and bounded so every call stays fast: the last two lines whole,
    the four before them cut to their first words, anything older forgotten."""
    recent = history[-6:]
    return [
        line if index >= len(recent) - 2 or len(line.split()) <= 9 else " ".join(line.split()[:9]) + "..."
        for index, line in enumerate(recent)
    ]


def direct(scene: Scene, engine: RulesEngine | None = None) -> dict:
    if scene.user_spoke and scene.via_voice and not (scene.engaged or addressed(scene.instruction)):
        return SILENT  # talk in the room that is not for PULSAR: no answer, and no model call either
    decision = engine.evaluate(scene.telemetry) if engine and scene.telemetry else None
    step = first_step(engine, decision) if decision else None
    danger = bool(decision) and decision["status"] == "RED"
    if scene.user_spoke and (danger or HEALTH_QUESTION.search(scene.instruction)):
        # The engine decides and Gemma only phrases its verdict; with no readings there is nothing to phrase.
        # While the verdict is RED this is the only thing PULSAR says, whatever it is asked: it keeps telling the
        # astronaut the step the engine requires until the readings clear, instead of helping with something else.
        say = phrase(decision, scene.instruction, step).text if decision else NOT_MINE
        reaction = "alert" if decision and decision["status"] != "GREEN" else "calm"
        return {"say": say, "spot": scene.spot if scene.spot in SPOTS else "home", "reaction": reaction, "speak": True}
    if scene.user_spoke and ASKS_READINGS.search(scene.instruction):
        # Heart rate and cabin CO2 come from the sensor MCP server: Gemma calls its tools and phrases the readings.
        say, out_of_limits = read_sensors(scene.instruction)
        return {"say": say, "spot": scene.spot if scene.spot in SPOTS else "home",
                "reaction": "alert" if out_of_limits else "calm", "speak": True}
    facts = []
    if decision and decision["status"] != "GREEN":
        facts.append("Health check (final):\n" + verdict_text(decision, step))
    if scene.history:
        facts.append("Conversation so far:\n" + "\n".join(compact(scene.history)))
    elif scene.said:
        facts.append("Already said by PULSAR: " + " | ".join(scene.said))
    if scene.seen:
        facts.append(f"The camera sees: {scene.seen}")
    if scene.instruction and not scene.user_spoke:
        facts.append(f"Standing instruction from the astronaut: {scene.instruction}")
    facts.append(f"You are at: {scene.spot}")
    if not scene.user_spoke:
        facts.append("Only the camera changed. Write - unless this matters.")
    else:
        facts.append(f"The astronaut says to you: {scene.instruction}")
    user = {"role": "user", "content": "\n".join(facts)}
    if scene.image:
        user["content"] += "\nThe current camera frame is attached."
        user["images"] = [scene.image]
    content = chat(
        [{"role": "system", "content": SYSTEM}, user],
        options={"temperature": 0.3, "num_predict": 48, "stop": ["\n"]},  # one line of about 20 tokens
    )
    try:
        return validate(parse(content), scene.said, scene.user_spoke)
    except AttributeError:
        return FALLBACK  # the model broke the format: the mascot just stays calm


@router.post("/pulsar/act")
async def act(scene: Scene, request: Request) -> dict:
    """Body: what was seen and the astronaut's instruction. Returns where PULSAR goes, how it reacts and what it says."""
    if not scene.seen and not scene.instruction:
        raise HTTPException(400, "nothing seen or instructed")
    if scene.telemetry and telemetry_errors(scene.telemetry):
        raise HTTPException(422, "telemetry does not match the contract")
    return await run_in_threadpool(direct, scene, request.app.state.rules_engine)
