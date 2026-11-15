"""G5 pipeline: transcript -> rules engine decision -> Gemma phrasing -> Piper audio.

Gemma receives the verdict the engine already produced, as plain sentences (factor messages and the first
countermeasure step, never ids), and only phrases it. Its answer is checked against the prompt rules; when it
breaks one, a deterministic sentence built from the verdict is spoken instead, so the demo never says something
the engine did not decide.
"""

import re
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pulsar import settings
from pulsar.ollama import chat
from pulsar.rules.engine import RulesEngine

_SYSTEM = """\
You are PULSAR, the onboard health assistant of a long-duration space mission.
The astronaut is not a doctor and may be in hands-free mode: your words are read aloud.
Always answer in {language}, whatever language the verdict or the question is in.
Your only task is to turn the rules engine's verdict into spoken guidance. The verdict is final: never change,
add to or soften it.
RULES:
1. At most 2 short sentences.
2. Use only the facts in [VERDICT]. No diagnoses, causes or numbers that are not written there.
3. Sentence 1: what was detected, in plain words. Sentence 2: the first step to take now.
4. If the escalation is the flight surgeon, sentence 2 starts with "{surgeon}," and then gives the first step.
5. Never read codes or identifiers aloud.
6. If the status is GREEN, say that all readings are within limits and nothing is needed now."""

# Per language: the prompt, the words the flight-surgeon check looks for, and the sentences spoken when Gemma breaks a rule.
SURGEON = {"es": "cirujano de vuelo", "en": "flight surgeon"}
SYSTEMS = {
    "es": _SYSTEM.format(language="Spanish (Spain)", surgeon="Contacta con el cirujano de vuelo"),
    "en": _SYSTEM.format(language="English", surgeon="Contact the flight surgeon"),
}
SYSTEM = SYSTEMS["es"]  # the default language's prompt, for callers that do not choose
NOBODY_ASKED = {"es": "nada: es una alerta automática", "en": "nothing: this is an automatic alert"}
FALLBACKS = {
    "es": {
        "GREEN": "Todas las lecturas están dentro de los límites. No hace falta nada ahora mismo.",
        "FLIGHT_SURGEON": "Hay una lectura fuera de su límite. Contacta ahora con el cirujano de vuelo.",
        "CREW": "Hay una lectura fuera de su límite. Avisa a un miembro de la tripulación.",
        "SELF_CARE": "Hay una lectura fuera de su límite. Sigue el primer paso de la contramedida.",
    },
    "en": {
        "GREEN": "All readings are within limits. Nothing is needed right now.",
        "FLIGHT_SURGEON": "A reading is outside its limit. Contact the flight surgeon now.",
        "CREW": "A reading is outside its limit. Tell a crew member.",
        "SELF_CARE": "A reading is outside its limit. Follow the first step of the countermeasure.",
    },
}

ESCALATION = {
    "SELF_CARE": "self-care: the astronaut can handle it alone",
    "CREW": "tell a crew member",
    "FLIGHT_SURGEON": "contact the flight surgeon",
}
MAX_FACTORS = 3  # two spoken sentences cannot carry more
NUMBER = re.compile(r"\d+(?:\.\d+)?")


def decimal_point(text: str) -> str:
    """Spanish writes 6,5 where the verdict says 6.5: compare both as the same figure."""
    return re.sub(r"(?<=\d),(?=\d)", ".", text)


@dataclass
class Phrasing:
    text: str
    source: str  # "llm" or "fallback"
    prompt: str  # the verdict as Gemma saw it: the only facts the text may contain
    violations: list[str] = field(default_factory=list)


@dataclass
class VoiceTurn:
    transcript: str
    decision: dict[str, Any]
    phrasing: Phrasing
    audio: bytes
    ms: dict[str, float]


def first_step(engine: RulesEngine, decision: Mapping[str, Any]) -> str | None:
    countermeasure = engine.countermeasures.get(decision.get("countermeasureId") or "")
    return countermeasure.steps[0] if countermeasure else None


def verdict_text(decision: Mapping[str, Any], step: str | None) -> str:
    lines = [f"Status: {decision['status']}", f"Escalation: {ESCALATION[decision['escalation']]}"]
    factors = [f["message"] for f in decision["factors"][:MAX_FACTORS]]
    if factors:
        lines += ["Detected:", *(f"- {message}" for message in factors)]
    if step:
        lines.append(f"First step: {step}")
    return "\n".join(lines)


def violations(text: str, decision: Mapping[str, Any], prompt: str, lang: str | None = None) -> list[str]:
    found = []
    if not text.strip():
        found.append("empty")
    if len([s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]) > 2:
        found.append("more than 2 sentences")
    extra = {float(n) for n in NUMBER.findall(decimal_point(text))} - {float(n) for n in NUMBER.findall(prompt)}
    if extra:
        found.append(f"figures not in the verdict: {sorted(extra)}")
    if re.search(r"\bCM-", text):
        found.append("reads a countermeasure id")
    if decision["escalation"] == "FLIGHT_SURGEON" and SURGEON[settings.pick_lang(lang)] not in text.lower():
        found.append("does not name the flight surgeon")
    return found


def fallback(decision: Mapping[str, Any], step: str | None, lang: str | None = None) -> str:
    """A generic sentence built from the verdict alone, in `lang`: it never quotes the engine's text."""
    texts = FALLBACKS[settings.pick_lang(lang)]
    return texts["GREEN"] if decision["status"] == "GREEN" else texts[decision["escalation"]]


def ask_gemma(system: str, user: str) -> str:
    return chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                options={"temperature": 0.2, "num_predict": 90})


def phrase(decision: Mapping[str, Any], transcript: str, step: str | None, lang: str | None = None) -> Phrasing:
    lang = settings.pick_lang(lang)
    prompt = verdict_text(decision, step)
    asked = transcript.strip() or NOBODY_ASKED[lang]
    text = ask_gemma(SYSTEMS[lang], f"[VERDICT]\n{prompt}\n[THE ASTRONAUT ASKED]\n{asked}")
    broken = violations(text, decision, f"{prompt}\n{asked}", lang)
    if broken:
        return Phrasing(fallback(decision, step, lang), "fallback", prompt, broken)
    return Phrasing(text, "llm", prompt)


def respond(audio: bytes, telemetry: Mapping[str, Any], engine: RulesEngine, lang: str | None = None) -> VoiceTurn:
    from senses import synthesize, transcribe  # whisper and Piper, loaded once and shared with /stt and /tts

    ms: dict[str, float] = {}

    def timed(stage, fn, *args):
        started = time.perf_counter()
        result = fn(*args)
        ms[stage] = (time.perf_counter() - started) * 1000
        return result

    transcript = timed("stt", transcribe, audio, lang)
    decision = timed("rules", engine.evaluate, telemetry)
    phrasing = timed("llm", phrase, decision, transcript, first_step(engine, decision), lang)
    speech = timed("tts", synthesize, phrasing.text, lang)
    ms["total"] = sum(ms.values())
    return VoiceTurn(transcript, decision, phrasing, speech, ms)
