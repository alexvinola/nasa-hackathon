"""What the astronaut can ask PULSAR to do on the HUD, by voice or chat: open the relaxation menu (and start an
exercise), open the measurement form on one signal, type a measurement or a daily habit in for them, and show the
habits.

Product rule kept: the rules engine decides health, Gemma only phrases. Here nobody decides anything about health
either: a request is matched against a CLOSED list of actions (no model call, so it answers at once and offline), the
numbers are checked against the contract's own bounds, and the HUD only ever receives one of the actions below. The
model never writes an action. The sensor readings (fatigue, CO2, radiation, heart rate) already reach PULSAR through
the sensor MCP server (`mock_mcp.py`, `readings.py`); this module is the other direction, from the astronaut to the HUD.

Action shapes (mirrored by `frontend/src/modules/hud/hudActions.ts`):
    {"type": "open_relax", "exercise": "breathe" | "eyes" | "body" | None}
    {"type": "open_measure", "signal": <guide signal> | None}
    {"type": "set_measure", "signal": <guide signal>, "values": {<field key>: number}}
    {"type": "log_habit", "habit": "exercise" | "water" | "relax", "amount": number}
    {"type": "open_habits", "expand": bool}
"""

import json
import re
from typing import Any

from pulsar import settings

# Guide signal -> its fields, in the order the form asks for them (frontend/src/modules/guides/selfReport.ts).
SIGNALS = {
    "biometrics.heartRateBpm": ("heartRateBpm",),
    "selfReport.bloodPressure": ("systolic", "diastolic"),
    "selfReport.glucoseMgDl": ("glucoseMgDl",),
    "selfReport.bodyTempC": ("bodyTempC",),
    "selfReport.sleepHoursLast24h": ("sleepHoursLast24h",),
    "selfReport.mood": ("mood",),
}
EXERCISE_IDS = ("breathe", "eyes", "body")
MAX_PER_REQUEST = {"exercise": 600, "water": 20, "relax": 10}  # minutes, glasses, sessions

_SCHEMA = json.loads((settings.SHARED_DIR / "telemetry.schema.json").read_text(encoding="utf-8"))["properties"]
_SELF = _SCHEMA["selfReport"]["properties"]
_PRESSURE = _SELF["bloodPressure"]["oneOf"][1]["properties"]
BOUNDS = {
    "heartRateBpm": _SCHEMA["biometrics"]["properties"]["heartRateBpm"],
    "systolic": _PRESSURE["systolic"],
    "diastolic": _PRESSURE["diastolic"],
    "glucoseMgDl": _SELF["glucoseMgDl"],
    "bodyTempC": _SELF["bodyTempC"],
    "sleepHoursLast24h": _SELF["sleepHoursLast24h"],
    "mood": _SELF["mood"],
}

NUMBER = r"(\d+(?:[.,]\d+)?)"
SIGNAL_WORDS = {
    "biometrics.heartRateBpm": re.compile(r"pulso|pulsaci|latido|card[ií]ac|heart|pulse|bpm", re.I),
    "selfReport.bloodPressure": re.compile(r"tensi[oó]n|presi[oó]n|blood pressure|pressure", re.I),
    "selfReport.glucoseMgDl": re.compile(r"glucosa|az[uú]car|glucose|sugar", re.I),
    "selfReport.bodyTempC": re.compile(r"temperatura|fiebre|temperature|temp\b", re.I),
    "selfReport.sleepHoursLast24h": re.compile(r"sue[ñn]o|dorm|durm|sleep|slept", re.I),
    "selfReport.mood": re.compile(r"[aá]nimo|humor|mood|me siento|feel", re.I),
}
OPEN = r"abre|abrir|abr[ií]me|muestra|mu[eé]strame|ens[eé][ñn]a|quiero ver|ver\b|open|show|bring up"
MEASURE = re.compile(r"\b(mide|medir|medici[oó]n|medidas|registr\w*|anota\w*|measure\w*|measurement\w*|log|record|take my)\b|formulario|\bform\b", re.I)
RELAX = re.compile(r"relaj|respir|breath|relax|estir|stretch|calm(a|ar)?me|tranquiliz|desestres|medit", re.I)
CHOOSE = re.compile(
    r"elige|escoge|selecciona|ponme|pon uno|recomi[eé]nd|cualquiera|el que (quieras|creas)|sorpr[eé]ndeme|"
    r"choose|pick|you decide|recommend|surprise|whichever|any (one|of them)",
    re.I,
)
EXERCISE_WORDS = {
    "breathe": re.compile(r"respir|breath", re.I),
    "eyes": re.compile(r"\bojos?\b|\bvista\b|eyes?|vision", re.I),
    "body": re.compile(r"cuerpo|hombros?|tensi[oó]n muscular|estir|body|shoulders?|stretch", re.I),
}
LOG_VERB = re.compile(
    r"\b(he|hice|hecho|llevo|acabo|acab[eé]|beb[ií]|bebido|tom[eé]|tomado|anota\w*|suma\w*|a[ñn]ade\w*|agrega\w*|registra\w*|"
    r"add|log|did|had|drank|just|finished|completed|done|trained|ran)\b|\+",
    re.I,
)
EXERCISE_HABIT = re.compile(r"ejercici|entren|gimnasi|cardio|corr[ií]|correr|caminad|yoga|pesas|exercis|workout|gym|trained|\bran\b", re.I)
WATER_HABIT = re.compile(r"\bagua\b|vasos?\b|beb[ií]|bebido|hidrat|water|glass|drank|drink", re.I)
RELAX_HABIT = re.compile(r"relaj|respiraci|breathing|relax|medit", re.I)
HABITS_WORDS = re.compile(r"h[aá]bitos?|habits?|puntuaci[oó]n|score|racha|streak|historial|history|c[oó]mo voy|how am i doing", re.I)
EXPAND = re.compile(r"ampli|expand|historial|history|mes\b|month|todo|all", re.I)
HOURS = re.compile(r"\bh\b|horas?|hours?|hrs?", re.I)

SAYS: dict[str, dict[str, str]] = {
    "es": {
        "relax_menu": "Te abro las opciones de relajación.",
        "relax_pick": "Te pongo {name}.",
        "relax_exercise": "Empezamos {name}.",
        "measure_form": "Te abro el formulario de medidas.",
        "measure_signal": "Te abro cómo medir {name}.",
        "measure_set": "Anotado: {name} {value}.",
        "measure_bad": "No puedo anotar ese valor de {name}: está fuera de lo que admite el formulario.",
        "habit_log": "Anotado: {amount} {unit} de {name}.",
        "habit_big": "Eso es demasiado de golpe para anotarlo; dímelo en partes.",
        "habits_open": "Te abro tus hábitos.",
        "habits_expand": "Te abro el historial de hábitos.",
        "habits_status": "Hoy llevas {score} por ciento del día: {exercise} minutos de ejercicio, {water} vasos de agua, {relax} relajaciones y {sleep} horas de sueño.",
    },
    "en": {
        "relax_menu": "Opening the relaxation options for you.",
        "relax_pick": "I'll put on {name} for you.",
        "relax_exercise": "Let's start {name}.",
        "measure_form": "Opening the measurement form.",
        "measure_signal": "Opening how to measure {name}.",
        "measure_set": "Logged: {name} {value}.",
        "measure_bad": "I can't log that {name} value: it is outside what the form accepts.",
        "habit_log": "Logged: {amount} {unit} of {name}.",
        "habit_big": "That is too much to log at once; tell me in parts.",
        "habits_open": "Opening your habits.",
        "habits_expand": "Opening your habit history.",
        "habits_status": "Today you are at {score} percent of the day: {exercise} minutes of exercise, {water} glasses of water, {relax} relaxations and {sleep} hours of sleep.",
    },
}
NAMES: dict[str, dict[str, str]] = {
    "es": {
        "breathe": "respiración guiada", "eyes": "descanso de ojos", "body": "relajación del cuerpo",
        "biometrics.heartRateBpm": "el pulso", "selfReport.bloodPressure": "la tensión", "selfReport.glucoseMgDl": "la glucosa",
        "selfReport.bodyTempC": "la temperatura", "selfReport.sleepHoursLast24h": "el sueño", "selfReport.mood": "el ánimo",
        "exercise": "ejercicio", "water": "agua", "relax": "relajación",
        "min": "minutos", "glasses": "vasos", "times": "veces",
    },
    "en": {
        "breathe": "guided breathing", "eyes": "eye rest", "body": "body relaxation",
        "biometrics.heartRateBpm": "heart rate", "selfReport.bloodPressure": "blood pressure", "selfReport.glucoseMgDl": "glucose",
        "selfReport.bodyTempC": "temperature", "selfReport.sleepHoursLast24h": "sleep", "selfReport.mood": "mood",
        "exercise": "exercise", "water": "water", "relax": "relaxation",
        "min": "minutes", "glasses": "glasses", "times": "times",
    },
}
UNITS = {"exercise": "min", "water": "glasses", "relax": "times"}


def _num(text: str) -> float:
    return float(text.replace(",", "."))


def _fits(key: str, value: float) -> bool:
    bounds = BOUNDS[key]
    return bounds["minimum"] <= value <= bounds["maximum"]


def pick_exercise(telemetry: dict[str, Any] | None) -> str:
    """Which exercise PULSAR puts on when the astronaut leaves the choice to it. Only a choice among three
    relaxation exercises, from the camera's own measurements; it says nothing about anyone's health."""
    bio = (telemetry or {}).get("biometrics", {})
    if (bio.get("perclos") or 0) >= 0.15 or (bio.get("fatigueScore") or 0) >= 0.5:
        return "eyes"  # eyes closing a lot: rest them
    return "breathe"


def _reply(lang: str, key: str, action: dict | None = None, **fields: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"say": SAYS[lang][key].format(**fields)}
    if action:
        out["action"] = action
    return out


def parse(text: str, lang: str | None = None, telemetry: dict[str, Any] | None = None, habits: dict[str, float] | None = None) -> dict[str, Any] | None:
    """The reply (`say`, and an `action` when the HUD must do something) for a request that is one of the closed
    list of HUD actions, else None so the request goes on to the usual answer."""
    lang = settings.pick_lang(lang)
    names = NAMES[lang]
    query = "?" in text or "¿" in text
    open_verb = re.search(OPEN, text, re.I)

    # 1. A daily habit to log: "he hecho 30 minutos de ejercicio", "me he bebido dos vasos de agua".
    if LOG_VERB.search(text) and not query:
        for habit, words in (("exercise", EXERCISE_HABIT), ("water", WATER_HABIT), ("relax", RELAX_HABIT)):
            if not words.search(text):
                continue
            digits = re.search(NUMBER, text)
            amount = _num(digits.group(1)) if digits else 1.0  # "un vaso", "una relajación"
            if habit == "exercise" and digits and HOURS.search(text[digits.end(): digits.end() + 10]):
                amount *= 60
            elif habit == "exercise" and re.search(r"media hora|half an hour", text, re.I):
                amount = 30.0
            elif habit == "exercise" and re.search(r"\b(una|un|an?|one) (hora|hour)\b", text, re.I):
                amount = 60.0
            elif habit == "exercise" and digits is None:
                break  # no amount of exercise to log: let it go on as a plain question
            if not 0 < amount <= MAX_PER_REQUEST[habit]:
                return _reply(lang, "habit_big")
            amount = round(amount, 1)
            shown = int(amount) if amount == int(amount) else amount
            return _reply(lang, "habit_log", {"type": "log_habit", "habit": habit, "amount": amount},
                          amount=shown, unit=names[UNITS[habit]], name=names[habit])

    # 2. A measurement said out loud: "mi temperatura es 36,8", "tengo 120 sobre 80", "he dormido 7 horas".
    if not query:
        for signal, words in SIGNAL_WORDS.items():
            if not words.search(text):
                continue
            if signal == "selfReport.bloodPressure":
                found = re.search(rf"(\d{{2,3}})\s*(?:/|sobre|over|de|entre)\s*(\d{{2,3}})", text, re.I)
                values = {"systolic": float(found.group(1)), "diastolic": float(found.group(2))} if found else None
            else:
                digits = re.search(NUMBER, text)
                values = {SIGNALS[signal][0]: _num(digits.group(1))} if digits else None
            if not values:
                continue
            if not all(_fits(key, value) for key, value in values.items()):
                return _reply(lang, "measure_bad", name=names[signal])
            shown = "/".join(str(int(v) if v == int(v) else v) for v in values.values())
            return _reply(lang, "measure_set", {"type": "set_measure", "signal": signal, "values": values}, name=names[signal], value=shown)

    # 3. The habits panel, or how today is going.
    if HABITS_WORDS.search(text) and not RELAX.search(text):
        if open_verb or EXPAND.search(text) or not habits:
            expand = bool(EXPAND.search(text)) and bool(re.search(r"ampli|expand|historial|history|mes\b|month", text, re.I))
            return _reply(lang, "habits_expand" if expand else "habits_open", {"type": "open_habits", "expand": expand})
        score = round(100 * habits.get("score", 0))
        return _reply(lang, "habits_status", None, score=score, exercise=round(habits.get("exercise", 0)),
                      water=round(habits.get("water", 0)), relax=round(habits.get("relax", 0)), sleep=round(habits.get("sleep", 0), 1))

    # 4. The relaxation menu, an exercise of it, or "choose one for me".
    if RELAX.search(text) and not query:
        for exercise, words in EXERCISE_WORDS.items():
            if words.search(text):
                return _reply(lang, "relax_exercise", {"type": "open_relax", "exercise": exercise}, name=names[exercise])
        if CHOOSE.search(text):
            exercise = pick_exercise(telemetry)
            return _reply(lang, "relax_pick", {"type": "open_relax", "exercise": exercise}, name=names[exercise])
        return _reply(lang, "relax_menu", {"type": "open_relax", "exercise": None})

    # 5. How to measure something: the form, on the signal asked for.
    if MEASURE.search(text) or (open_verb and re.search(r"medidas|measure", text, re.I)):
        for signal, words in SIGNAL_WORDS.items():
            if words.search(text):
                return _reply(lang, "measure_signal", {"type": "open_measure", "signal": signal}, name=names[signal])
        return _reply(lang, "measure_form", {"type": "open_measure", "signal": None})
    return None
