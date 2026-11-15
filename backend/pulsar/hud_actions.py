"""What the astronaut can ask PULSAR to do on the HUD, by voice or chat: open the relaxation menu (and start an
exercise), open how to measure something, type a measurement or a daily habit in for them, show the habits or a
health point, close the panels, switch language, open the developer menu and switch the face mesh or the AI check.

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
    {"type": "open_health", "id": <health point id>}
    {"type": "close_panels"}
    {"type": "set_language", "lang": "es" | "en"}
    {"type": "dev_menu", "open": bool}
    {"type": "set_overlay", "target": "mesh" | "ai_check", "on": bool}
"""

import json
import re
import unicodedata
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

# Numbers said in words ("seis vasos", "two glasses"); the digits are looked for first.
WORD_NUMBERS = {
    "un": 1, "una": 1, "uno": 1, "one": 1, "a": 1, "an": 1, "dos": 2, "two": 2, "tres": 3, "three": 3, "cuatro": 4, "four": 4,
    "cinco": 5, "five": 5, "seis": 6, "six": 6, "siete": 7, "seven": 7, "ocho": 8, "eight": 8, "nueve": 9, "nine": 9,
    "diez": 10, "ten": 10, "once": 11, "eleven": 11, "doce": 12, "twelve": 12,
}
NUMBER = r"(\d+(?:[.,]\d+)?)"
WORD_NUMBER = r"\b(" + "|".join(sorted(WORD_NUMBERS, key=len, reverse=True)) + r")\b"
# A number word counts only when a unit follows, so "a" and "un" in other places do not become amounts.
UNIT = r"(?:minutos?|min|horas?|hours?|hrs?|vasos?|glass(?:es)?|veces|vez|times?|sesi[oó]n(?:es)?|sessions?)"

SIGNAL_WORDS = {
    "biometrics.heartRateBpm": re.compile(r"pulso|pulsaci|latido|card[ií]ac|heart|pulse|bpm", re.I),
    "selfReport.bloodPressure": re.compile(r"tensi[oó]n|presi[oó]n|blood pressure|pressure", re.I),
    "selfReport.glucoseMgDl": re.compile(r"glucosa|az[uú]car|glucose|sugar", re.I),
    "selfReport.bodyTempC": re.compile(r"temperatura|fiebre|temperature|temp\b", re.I),
    "selfReport.sleepHoursLast24h": re.compile(r"sue[ñn]o|dorm|durm|sleep|slept", re.I),
    "selfReport.mood": re.compile(r"[aá]nimo|humor|mood|me siento|feel", re.I),
}
OPEN = re.compile(r"\b(abre|abrir|abr[ií]me|muestra|mu[eé]strame|ens[eé][ñn]a\w*|quiero ver|ver|open|show|bring up|display)\b", re.I)
CLOSE = re.compile(r"\b(cierra|cerrar|cierre|close|hide|oculta|ocultar|quita|quitar|esconde)\b", re.I)
MEASURE = re.compile(
    r"\b(mide|medir\w*|mido|mides|midiendo|medici[oó]n|medidas|registr\w*|anota\w*|measure\w*|measurement\w*|log|record)\b|formulario|\bform\b",
    re.I,
)
# "how do I measure ...", "where do I take ...": only counts when a measurement is named too.
HOW_TO = re.compile(
    r"c[oó]mo (me |se |te )?(mid|tom|hag|puedo|debo|pued)\w*|d[oó]nde (me |se |te )?(mid|tom|pong|puedo|debo|pued)\w*|"
    r"how (do i|to|can i|should i|is)|where (do i|to|can i|should i)",
    re.I,
)
RELAX = re.compile(
    r"relaj|respir|breath|relax|estir|stretch|calm(a|ar)?me|tranquiliz|desestres|medit|"
    r"ejercicios? (para|de) (los |las |el |la |mi |mis )?(hombro|cuello|espalda|ojo|vista|mano|cuerpo)|"
    r"exercises? (for|to rest) (my )?(eyes|neck|shoulders|back|body)|"
    r"(solt|alivi|destens|descarg|liber|quit)[a-z]* (la |esa |mi )?tensi|release (the |my )?tension|let (the )?tension go|vista cansada|ojos (cansados|secos|irritados)|descansar (la )?vista|fatiga visual|eye strain|tired eyes|rest (my )?eyes",
    re.I,
)
CHOOSE = re.compile(
    r"elige|escoge|selecciona|ponme|pon uno|recomi[eé]nd|cualquiera|el que (quieras|creas)|sorpr[eé]ndeme|"
    r"choose|pick|you decide|recommend|surprise|whichever|any (one|of them)",
    re.I,
)
EXERCISE_WORDS = {
    "breathe": re.compile(r"respir|breath", re.I),
    "eyes": re.compile(r"\bojos?\b|\bvista\b|eyes?|vision", re.I),
    "body": re.compile(r"cuerpo|hombros?|cuello|espalda|tensi[oó]n muscular|estir|body|shoulders?|neck|stretch|(solt|alivi|destens|descarg|liber|quit)[a-z]* (la |esa |mi )?tensi|release (the |my )?tension|let (the )?tension go", re.I),
}
LOG_VERB = re.compile(
    r"\b(he|hice|hecho|llevo|acabo|acab[eé]|beb[ií]|bebido|tom[eé]|tomado|tomo|bebo|anota\w*|suma\w*|a[ñn]ade\w*|agrega\w*|registra\w*|"
    r"add|log|did|had|drank|just|finished|completed|done|trained|ran)\b|\+",
    re.I,
)
EXERCISE_HABIT = re.compile(r"ejercici|entren|gimnasi|cardio|corr[ií]|correr|caminad|yoga|pesas|exercis|workout|gym|trained|\bran\b", re.I)
WATER_HABIT = re.compile(r"\bagua\b|vasos?\b|beb[ií]|bebido|hidrat|water|glass|drank|drink", re.I)
RELAX_HABIT = re.compile(r"relaj|respiraci|breathing|relax|medit", re.I)
HABITS_WORDS = re.compile(r"h[aá]bitos?|habits?|puntuaci[oó]n|score|racha|streak|historial|history|c[oó]mo voy|how am i doing|(el|este|del) mes\b|this month", re.I)
EXPAND = re.compile(r"ampli|expand|historial|history|\bmes\b|month", re.I)
HOURS = re.compile(r"\bh\b|horas?|hours?|hrs?", re.I)
HEALTH_WORD = re.compile(r"\bsalud\b|health", re.I)
HEALTH_POINTS = {
    "head": re.compile(r"cabeza|head|mente|mind", re.I),
    "eyes": re.compile(r"\bojos?\b|\beyes?\b", re.I),
    "heart": re.compile(r"coraz[oó]n|\bheart\b", re.I),
    "lungs": re.compile(r"pulmon|lungs?", re.I),
    "gut": re.compile(r"est[oó]mago|intestin|digest|\bgut\b|stomach", re.I),
    "skin": re.compile(r"\bpiel\b|skin", re.I),
    "hands": re.compile(r"\bmanos?\b|hands?", re.I),
    "spine": re.compile(r"columna|espalda|spine|\bback\b", re.I),
    "legs": re.compile(r"piernas?|\blegs?\b", re.I),
}
EVERYTHING = re.compile(r"\b(todo|todas?|todos|ventanas?|paneles?|panel|everything|all|windows?|esto|this|it)\b", re.I)
LANG_WORDS = {"en": re.compile(r"ingl[eé]s|english", re.I), "es": re.compile(r"espa[ñn]ol|spanish|castellano", re.I)}
LANG_VERB = re.compile(r"\b(cambia\w*|pon\w*|habla\w*|h[aá]blame|switch|change|speak|talk|set|in)\b", re.I)
DEV_WORDS = re.compile(r"depuraci|debug|desarroll|developer|ajustes|configuraci|settings|\blogs?\b|engranaje|\bgear\b", re.I)
MESH_WORDS = re.compile(r"malla|mesh", re.I)
AI_WORDS = re.compile(r"comprobaci[oó]n( de)? ?ia|verificaci[oó]n( de)? ?ia|ai check|gemma", re.I)
ON_WORDS = re.compile(r"\b(activa\w*|enciende\w*|pon\w*|muestra\w*|abre|abrir|enable\w*|turn on|show|open|start)\b", re.I)
OFF_WORDS = re.compile(r"\b(desactiva\w*|apaga\w*|quita\w*|oculta\w*|cierra\w*|cerrar|disable\w*|turn off|hide|close|stop)\b", re.I)

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
        "health_open": "Te abro {name}.",
        "close": "Cierro las ventanas.",
        "lang_es": "Cambio a español.",
        "lang_en": "Cambio a inglés.",
        "dev_open": "Te abro el menú de desarrollo.",
        "dev_close": "Cierro el menú de desarrollo.",
        "overlay_on": "Activo {name}.",
        "overlay_off": "Desactivo {name}.",
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
        "health_open": "Opening {name}.",
        "close": "Closing the windows.",
        "lang_es": "Switching to Spanish.",
        "lang_en": "Switching to English.",
        "dev_open": "Opening the developer menu.",
        "dev_close": "Closing the developer menu.",
        "overlay_on": "Turning on {name}.",
        "overlay_off": "Turning off {name}.",
    },
}
NAMES: dict[str, dict[str, str]] = {
    "es": {
        "breathe": "respiración guiada", "eyes": "descanso de ojos", "body": "relajación del cuerpo",
        "biometrics.heartRateBpm": "el pulso", "selfReport.bloodPressure": "la tensión", "selfReport.glucoseMgDl": "la glucosa",
        "selfReport.bodyTempC": "la temperatura", "selfReport.sleepHoursLast24h": "el sueño", "selfReport.mood": "el ánimo",
        "exercise": "ejercicio", "water": "agua", "relax": "relajación",
        "min": "minutos", "glasses": "vasos", "times": "veces",
        "head": "la cabeza", "eyes_health": "los ojos", "heart": "el corazón", "lungs": "los pulmones", "gut": "el estómago",
        "skin": "la piel", "hands": "las manos", "spine": "la columna", "legs": "las piernas",
        "mesh": "la malla facial", "ai_check": "la comprobación de IA",
    },
    "en": {
        "breathe": "guided breathing", "eyes": "eye rest", "body": "body relaxation",
        "biometrics.heartRateBpm": "heart rate", "selfReport.bloodPressure": "blood pressure", "selfReport.glucoseMgDl": "glucose",
        "selfReport.bodyTempC": "temperature", "selfReport.sleepHoursLast24h": "sleep", "selfReport.mood": "mood",
        "exercise": "exercise", "water": "water", "relax": "relaxation",
        "min": "minutes", "glasses": "glasses", "times": "times",
        "head": "the head", "eyes_health": "the eyes", "heart": "the heart", "lungs": "the lungs", "gut": "the stomach",
        "skin": "the skin", "hands": "the hands", "spine": "the spine", "legs": "the legs",
        "mesh": "the face mesh", "ai_check": "the AI check",
    },
}
UNITS = {"exercise": "min", "water": "glasses", "relax": "times"}


def _num(text: str) -> float:
    return float(text.replace(",", "."))


def amount_in(text: str) -> tuple[float | None, int]:
    """The first amount in `text`, as digits or as a word with a unit after it ("seis vasos"), and where it ends."""
    digits = re.search(NUMBER, text)
    word = re.search(WORD_NUMBER + r"\s+" + UNIT, text, re.I)
    if digits and (not word or digits.start() < word.start()):
        return _num(digits.group(1)), digits.end()
    if word:
        return float(WORD_NUMBERS[word.group(1).lower()]), word.end(1)
    return None, 0


_UNITS = {
    "cero": 0, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17, "dieciocho": 18,
    "diecinueve": 19, "veinte": 20, "veintiuno": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24, "veinticinco": 25,
    "veintiseis": 26, "veintisiete": 27, "veintiocho": 28, "veintinueve": 29,
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}
_TENS = {
    "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_HUNDREDS = {"cien": 100, "ciento": 100, "doscientos": 200, "trescientos": 300, "hundred": 100}
_NUMERIC = {**_UNITS, **_TENS, **_HUNDREDS}
_CONNECTORS = {"y", "and"}


def _plain(word: str) -> str:
    return unicodedata.normalize("NFD", word.lower()).encode("ascii", "ignore").decode()


def _half_and_tenths(text: str) -> str:
    """Digits said the spoken way: "7 y media" and "7 horas y media" are 7.5, "36 con 8" is 36.8 (a single digit after
    "con", after a number under 60: "120 con 80" is a blood pressure, not 120.8)."""
    text = re.sub(r"(\d+)(\s*(?:horas?|hours?|h)?)\s+y\s+medi[oa]\b", lambda m: f"{m.group(1)}.5{m.group(2)}", text, flags=re.I)
    return re.sub(r"\b(\d{1,2})\s+con\s+(\d)\b", lambda m: f"{m.group(1)}.{m.group(2)}" if int(m.group(1)) < 60 else m.group(0), text, flags=re.I)


def digitize(text: str) -> str:
    """The numbers said in words, written as digits, so the rest of the parsing sees what a keyboard would give:
    "setenta y dos" -> 72, "treinta y seis coma ocho" -> 36.8, "siete y media" -> 7.5, "treinta y seis con ocho" -> 36.8.
    Speech to text writes digits most of the time, and words some of the time."""
    text = _half_and_tenths(text)
    parts = re.findall(r"\w+|\W+", text)
    out: list[str] = []
    i = 0

    def number_at(start: int) -> tuple[float, int] | None:
        """The number phrase beginning at part `start` and the part where it ends, or None."""
        total, j, seen = 0.0, start, False
        while j < len(parts):
            word = _plain(parts[j])
            if word in _NUMERIC:
                if word == "hundred":
                    total = max(total, 1) * 100
                else:
                    total += _NUMERIC[word]
                seen, j = True, j + 1
            elif parts[j].strip() == "" and seen and j + 1 < len(parts) and _plain(parts[j + 1]) in _NUMERIC:
                j += 1  # "ciento veinte", "one hundred twenty"
            elif (
                parts[j].strip() == "" and seen and j + 3 < len(parts) and _plain(parts[j + 1]) in _CONNECTORS
                and parts[j + 2].strip() == "" and _plain(parts[j + 3]) in _UNITS and total % 10 == 0 and total >= 20
            ):
                j += 3  # "treinta y seis": the connector between a ten and a unit
            else:
                break
        return (total, j) if seen else None

    while i < len(parts):
        found = number_at(i) if _plain(parts[i]) in _NUMERIC else None
        if not found:
            out.append(parts[i])
            i += 1
            continue
        value, end = found
        rest = end
        # "coma ocho", "point eight", "con ocho" (only a small number with a single digit after "con")
        if rest + 2 < len(parts) and parts[rest].strip() == "" and _plain(parts[rest + 1]) in {"coma", "punto", "point", "con"}:
            after = number_at(rest + 3) if rest + 3 < len(parts) else None
            marker = _plain(parts[rest + 1])
            if after and (marker != "con" or (value < 60 and after[0] < 10)):
                value = float(f"{int(value)}.{int(after[0])}")
                end = after[1]
        elif rest + 2 < len(parts) and parts[rest].strip() == "" and _plain(parts[rest + 1]) == "y" and rest + 3 < len(parts) and _plain(parts[rest + 3]) in {"medio", "media"}:
            value += 0.5  # "siete y media"
            end = rest + 4
        out.append(str(int(value)) if value == int(value) else str(value))
        i = end
    return _half_and_tenths("".join(out))


def measurements_in(text: str) -> list[tuple[str, dict[str, float]]]:
    """Every measurement the text gives a number for, as (signal, {field: value}), in the order they are said.
    Each number belongs to the nearest measurement name: after it ("mi pulso es 72") or, when nothing follows it
    before the next name, before it ("95 de glucosa")."""
    names = sorted(
        ((match.start(), match.end(), signal) for signal, words in SIGNAL_WORDS.items() if (match := words.search(text))),
    )
    numbers = [(m.start(), m.end(), _num(m.group(1))) for m in re.finditer(NUMBER, text)]
    used: set[int] = set()
    found: list[tuple[str, dict[str, float]]] = []
    for index, (start, end, signal) in enumerate(names):
        until = names[index + 1][0] if index + 1 < len(names) else len(text)
        if signal == "selfReport.bloodPressure":
            both = rf"{NUMBER}\s*(?:/|sobre|over|de|entre|con|y|and|por)?\s*{NUMBER}"
            offset, pair = end, re.search(both, text[end:])  # "tension 120 80", else "120 sobre 80 de tension"
            if not pair:
                offset, pair = 0, re.search(both, text[:start])
            if pair:
                top, bottom = _num(pair.group(1)), _num(pair.group(2))
                if top < 30 and bottom < 30:
                    top, bottom = top * 10, bottom * 10  # "12 8" said for 120/80
                found.append((signal, {"systolic": top, "diastolic": bottom}))
                span = (offset + pair.start(), offset + pair.end())
                used |= {i for i, number in enumerate(numbers) if span[0] <= number[0] < span[1]}
            continue
        after = [i for i, number in enumerate(numbers) if i not in used and end <= number[0] < until]
        before = [i for i, number in enumerate(numbers) if i not in used and number[1] <= start]
        pick = after[0] if after else (before[-1] if before else None)
        if pick is not None:
            used.add(pick)
            found.append((signal, {SIGNALS[signal][0]: numbers[pick][2]}))
    return found


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


def _interface(text: str, lang: str) -> dict[str, Any] | None:
    """Requests about the HUD itself: language, developer menu, face mesh and AI check, health points, closing."""
    names = NAMES[lang]
    # Language: "cambia a inglés", "switch to Spanish".
    for code, words in LANG_WORDS.items():
        if words.search(text) and (LANG_VERB.search(text) or re.match(r"\W*(en|in)\s", text, re.I)) and not RELAX.search(text):
            return _reply(lang, f"lang_{code}", {"type": "set_language", "lang": code})
    # The face mesh and the AI check (they live in the developer menu): need to say whether on or off.
    for target, words in (("ai_check", AI_WORDS), ("mesh", MESH_WORDS)):
        if words.search(text):
            off = bool(OFF_WORDS.search(text))
            if off or ON_WORDS.search(text):
                return _reply(lang, "overlay_off" if off else "overlay_on", {"type": "set_overlay", "target": target, "on": not off}, name=names[target])
    # The developer menu (AI check, debug, log).
    if DEV_WORDS.search(text) and (OFF_WORDS.search(text) or ON_WORDS.search(text) or OPEN.search(text)):
        shut = bool(OFF_WORDS.search(text))
        return _reply(lang, "dev_close" if shut else "dev_open", {"type": "dev_menu", "open": not shut})
    # A health point panel: "abre salud del corazón".
    if HEALTH_WORD.search(text):
        for point, words in HEALTH_POINTS.items():
            if words.search(text):
                return _reply(lang, "health_open", {"type": "open_health", "id": point}, name=names["eyes_health" if point == "eyes" else point])
    # Close everything.
    if CLOSE.search(text) and EVERYTHING.search(text):
        return _reply(lang, "close", {"type": "close_panels"})
    return None


def parse(text: str, lang: str | None = None, telemetry: dict[str, Any] | None = None, habits: dict[str, float] | None = None) -> dict[str, Any] | None:
    """The reply (`say`, and an `action` when the HUD must do something) for a request that is one of the closed
    list of HUD actions, else None so the request goes on to the usual answer."""
    lang = settings.pick_lang(lang)
    text = digitize(text)
    names = NAMES[lang]
    query = "?" in text or "¿" in text
    open_verb = OPEN.search(text)

    # 0. The HUD itself.
    interface = _interface(text, lang)
    if interface:
        return interface

    # 1. A daily habit to log: "he hecho 30 minutos de ejercicio", "hoy he bebido seis vasos de agua".
    if (LOG_VERB.search(text) or re.search(NUMBER + r"\s*" + UNIT + r"|media hora|half an hour", text)) and not (query and HOW_TO.search(text)):
        for habit, words in (("exercise", EXERCISE_HABIT), ("water", WATER_HABIT), ("relax", RELAX_HABIT)):
            if not words.search(text):
                continue
            found, end = amount_in(text)
            amount = found if found is not None else 1.0  # "un vaso", "una relajación"
            if habit == "exercise" and found is not None and HOURS.search(text[end: end + 10]):
                amount *= 60
            elif habit == "exercise" and re.search(r"media hora|half an hour", text, re.I):
                amount = 30.0
            elif habit == "exercise" and re.search(r"\b(una|un|an?|one) (hora|hour)\b", text, re.I):
                amount = 60.0
            elif habit == "exercise" and found is None:
                continue  # no amount of exercise to log: maybe it is the relaxation habit ("un ejercicio de respiración")
            if not 0 < amount <= MAX_PER_REQUEST[habit]:
                return _reply(lang, "habit_big")
            amount = round(amount, 1)
            shown = int(amount) if amount == int(amount) else amount
            return _reply(lang, "habit_log", {"type": "log_habit", "habit": habit, "amount": amount},
                          amount=shown, unit=names[UNITS[habit]], name=names[habit])

    # 2. A measurement said out loud: "mi temperatura es 36,8", "tengo 120 sobre 80", "he dormido siete horas".
    if not query:
        said, actions = [], []
        for signal, values in measurements_in(text):
            if not all(_fits(key, value) for key, value in values.items()):
                said.append(SAYS[lang]["measure_bad"].format(name=names[signal]))
                continue
            shown = "/".join(str(int(v) if v == int(v) else v) for v in values.values())
            said.append(SAYS[lang]["measure_set"].format(name=names[signal], value=shown))
            actions.append({"type": "set_measure", "signal": signal, "values": values})
        if said:
            out: dict[str, Any] = {"say": " ".join(said)}
            if actions:
                out.update(action=actions[0], actions=actions)  # `action` stays the first one, for a client that reads one
            return out

    # 3. The habits panel, or how today is going.
    if HABITS_WORDS.search(text) and not RELAX.search(text):
        if open_verb or EXPAND.search(text) or not habits:
            expand = bool(EXPAND.search(text))
            return _reply(lang, "habits_expand" if expand else "habits_open", {"type": "open_habits", "expand": expand})
        score = round(100 * habits.get("score", 0))
        return _reply(lang, "habits_status", None, score=score, exercise=round(habits.get("exercise", 0)),
                      water=round(habits.get("water", 0)), relax=round(habits.get("relax", 0)), sleep=round(habits.get("sleep", 0), 1))

    # 4. The relaxation menu, an exercise of it, or "choose one for me".
    if RELAX.search(text) and not (query and HOW_TO.search(text)):
        for exercise, words in EXERCISE_WORDS.items():
            if words.search(text):
                return _reply(lang, "relax_exercise", {"type": "open_relax", "exercise": exercise}, name=names[exercise])
        if CHOOSE.search(text):
            exercise = pick_exercise(telemetry)
            return _reply(lang, "relax_pick", {"type": "open_relax", "exercise": exercise}, name=names[exercise])
        return _reply(lang, "relax_menu", {"type": "open_relax", "exercise": None})

    # 5. How to measure something: the panel, on the signal asked for ("cómo medir mi frecuencia cardiaca").
    named = next((signal for signal, words in SIGNAL_WORDS.items() if words.search(text)), None)
    if named and (MEASURE.search(text) or HOW_TO.search(text)):
        return _reply(lang, "measure_signal", {"type": "open_measure", "signal": named}, name=names[named])
    if MEASURE.search(text) or (open_verb and re.search(r"medidas|measure", text, re.I)):
        return _reply(lang, "measure_form", {"type": "open_measure", "signal": None})
    return None
