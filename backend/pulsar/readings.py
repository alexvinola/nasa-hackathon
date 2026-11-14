"""Answers questions about the astronaut's heart rate and the cabin CO2 by letting Gemma call the sensor MCP server.

Gemma gets the server's tools through Ollama, asks for the readings it needs, and phrases them. Its answer is
checked like the verdict phrasing (`pulsar.voice.pipeline`): a bounded number of sentences and no figure the tools
did not return. When it breaks that, or never calls a tool, a sentence built straight from the readings is spoken instead.
The judgement of a reading stays with the rules engine: it travels inside each tool result.
"""

import asyncio
import json
import re
import sys
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from pulsar.settings import BACKEND_DIR
from pulsar.voice.pipeline import NUMBER, decimal_point
from senses import chat_message

SERVER = BACKEND_DIR / "mock_mcp.py"
MAX_ROUNDS = 3

# What makes a question one for the sensors; the rest of the director's questions never reach this module.
ASKS_READINGS = re.compile(
    r"pulso|pulsaci|latido|card[ií]ac|heart|pulse|bpm|co2|co₂|di[oó]xido|carbono|cabin|radiaci|radiation|dosis|msv|dos[ií]metro|constantes|vitales|vitals|lecturas",
    re.I,
)
FOR_HEART = re.compile(r"pulso|pulsaci|latido|card[ií]ac|heart|pulse|bpm", re.I)
FOR_CO2 = re.compile(r"co2|co₂|di[oó]xido|carbono|cabin|aire", re.I)
FOR_RADIATION = re.compile(r"radiaci|radiation|dosis|msv|dos[ií]metro", re.I)
FOR_VITALS = re.compile(r"constantes|vitales|vitals|lecturas", re.I)

SYSTEM = """You are PULSAR, the astronaut's warm, calm onboard companion. Your words are read aloud. Always answer in Spanish (Spain).
To tell a reading you MUST call the matching tool first: never guess or remember a value.
Use only the figures the tools returned. Never mention tools, sensors, the rules engine or "the system": just say it.
Each result has "withinLimits" (true or false) and an "assessment". You never judge a reading yourself; follow them.
If "withinLimits" is false, something is over its limit, even when the other readings are fine: never say all is fine.
- "withinLimits" is true: no instructions, no advice, no words of company. At most 3 short sentences: the values (for several readings, give heart rate and CO2 first, then
  the rest briefly) and that they are fine.
- "withinLimits" is false: exactly 3 sentences, in this order: 1) the value and that it is over the limit;
  2) one short, warm, personal sentence of company, such as "Estoy contigo, vamos paso a paso." (never say it is
  harmless or dangerous); 3) the first 2 or 3 steps of "stepsToTake", joined in ONE sentence of instructions.
Take the steps only from "stepsToTake": never add causes, diagnoses, questions or steps of your own."""

MAX_SENTENCES = 3
MAX_SENTENCES_OUT_OF_LIMITS = 4  # one more than asked: small models run long


def figures(text: str) -> set[float]:
    return {float(n) for n in NUMBER.findall(decimal_point(text))}


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def agrees(text: str, out_of_limits: bool) -> bool:
    """The wording must not contradict the engine: never "all fine" over a limit, never "over" while all is fine."""
    fine = re.search(r"dentro de(?:l| los)? l[ií]mites?|todo (?:est[aá] )?bien|todo en orden", text, re.I)
    over = re.search(r"por encima|supera|excede|elevad|demasiado alt|sobrepasa|alcanza|igual al l[ií]mite", text, re.I)
    if out_of_limits:
        return not fine and bool(over)
    # All fine: just the values, never invented advice.
    return not over and not re.search(r"paso a paso|(?:revisa|ajusta|reporta|informa|sigue|contacta|mant[eé]n)", text, re.I)


def spoken(results: dict[str, dict[str, Any]]) -> str:
    """The readings as Spanish sentences, with no model involved."""
    parts = []
    heart = results.get("get_heart_rate") or results.get("get_vitals")
    co2 = results.get("get_cabin_co2") or results.get("get_vitals")
    if heart:
        parts.append(f"Tu pulso es de {heart['heartRateBpm']} pulsaciones por minuto.")
    if co2:
        parts.append(f"El CO2 de la cabina está en {co2['cabinCo2_mmHg']} mmHg.")
    if radiation := results.get("get_radiation") or results.get("get_vitals"):
        parts.append(f"La dosis de radiación es de {radiation['radiation_mSv']} mSv.")
    if any(r["assessment"] != "within limits" for r in results.values()):
        parts.append("Hay una lectura por encima de su límite. Sigue los pasos que te muestro en pantalla.")
    return " ".join(parts) or "No he podido leer los sensores."


async def converse(question: str, telemetry: dict[str, Any] | None = None) -> tuple[str, bool]:
    """Runs the tool-calling conversation. Returns (what to say, whether the readings are outside their limits)."""
    # The server reads the readings the HUD is showing from its environment; with none it falls back to a scenario.
    env = {"PULSAR_MOCK_TELEMETRY": json.dumps(telemetry)} if telemetry else {}
    server = StdioServerParameters(command=sys.executable, args=[str(SERVER)], env=env)
    async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = [{"type": "function", "function": {"name": t.name, "description": t.description or "",
                                                   "parameters": t.input_schema}}
                 for t in (await session.list_tools()).tools]
        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
        results: dict[str, dict[str, Any]] = {}

        async def call(name: str) -> str:
            text = (await session.call_tool(name, {})).content[0].text
            results[name] = json.loads(text)
            return text

        text = ""
        for _ in range(MAX_ROUNDS):
            reply = await asyncio.to_thread(chat_message, messages, tools=tools,
                                            options={"temperature": 0.2, "num_predict": 220})
            calls = reply.get("tool_calls") or []
            if not calls:
                text = reply["content"].strip()
                break
            messages.append(reply)
            for tool_call in calls:
                name = tool_call["function"]["name"]
                content = await call(name) if name in {t["function"]["name"] for t in tools} else "unknown tool"
                messages.append({"role": "tool", "tool_name": name, "content": content})
        if not results:  # the model never asked: read what the question is about ourselves
            for name, wanted in (("get_vitals", FOR_VITALS), ("get_heart_rate", FOR_HEART), ("get_cabin_co2", FOR_CO2),
                              ("get_radiation", FOR_RADIATION)):
                if wanted.search(question):
                    await call(name)
        known = figures(json.dumps(results))
        out_of_limits = any(r["assessment"] != "within limits" for r in results.values())
        limit = MAX_SENTENCES_OUT_OF_LIMITS if out_of_limits else MAX_SENTENCES
        valid = (text and len(sentences(text)) <= limit and figures(text) <= known and re.search(r"\d", text)
                 and agrees(text, out_of_limits))
        return (text if valid else spoken(results)), out_of_limits


def answer(question: str, telemetry: dict[str, Any] | None = None) -> tuple[str, bool]:
    """Sync entry point for the director (it runs in a worker thread, so it has no event loop of its own)."""
    return asyncio.run(converse(question, telemetry))
