"""Mock MCP server (stdio): the astronaut's heart rate, the cabin CO2 and the radiation dose, as if they came from onboard sensors.

The values are the readings the HUD is showing right now: the backend hands them over in `PULSAR_MOCK_TELEMETRY`
(JSON, the contract). Without them (no front) they come from a scenario in `shared/scenarios/`
(`PULSAR_MOCK_SCENARIO`, default 03-high-co2). Each reading carries the rules engine's verdict on it (`assessment`) and, when it is outside its limit, the steps to
take: the model reports them, it never judges a reading itself (product rule: the rules engine decides).

    uv run --project backend python backend/mock_mcp.py      # speaks MCP over stdin/stdout
"""

import json
import os
from functools import cache
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from pulsar.rules import build_engine
from pulsar.settings import SHARED_DIR

DEFAULT_SCENARIO = SHARED_DIR / "scenarios" / "03-high-co2.json"

mcp = MCPServer("pulsar-mock-sensors")


@cache
def engine():
    return build_engine()


def report(*fields: tuple[str, str]) -> dict[str, Any]:
    live = os.environ.get("PULSAR_MOCK_TELEMETRY")
    path = Path(os.environ.get("PULSAR_MOCK_SCENARIO", DEFAULT_SCENARIO))
    telemetry = json.loads(live) if live else json.loads(path.read_text(encoding="utf-8"))["input"]
    decision = engine().evaluate(telemetry)
    wanted = {f"{section}.{key}" for section, key in fields}
    flagged = [f["message"] for f in decision["factors"] if f["signal"] in wanted]
    # The steps of the countermeasure each flagged reading's own rule points to (not just the decision's main one).
    steps: list[str] = []
    for finding in engine().findings(telemetry):
        countermeasure = engine().countermeasures.get(finding.rule.countermeasureId or "")
        if finding.rule.signal in wanted and countermeasure:
            steps += [step for step in countermeasure.steps if step not in steps]
    return {
        **{key: telemetry[section][key] for section, key in fields},
        "withinLimits": not flagged,
        "assessment": " ".join(flagged) or "within limits",
        **({"stepsToTake": steps} if steps else {}),
        "source": "the HUD's current readings" if live else f"mock sensors, scenario {path.stem}",
    }


@mcp.tool()
def get_heart_rate() -> dict[str, Any]:
    """The astronaut's current heart rate in beats per minute."""
    return report(("biometrics", "heartRateBpm"))


@mcp.tool()
def get_cabin_co2() -> dict[str, Any]:
    """The cabin's current CO2 partial pressure in mmHg."""
    return report(("environment", "cabinCo2_mmHg"))


@mcp.tool()
def get_radiation() -> dict[str, Any]:
    """The current radiation dose reading in mSv (simulated)."""
    return report(("environment", "radiation_mSv"))


@mcp.tool()
def get_vitals() -> dict[str, Any]:
    """All the current vital readings: heart rate (bpm), percentage of time the eyes are closed, fatigue score
    (0 to 1), yawns per minute, the cabin CO2 (mmHg) and the radiation dose (mSv)."""
    out = report(("biometrics", "heartRateBpm"), ("biometrics", "perclos"), ("biometrics", "fatigueScore"),
                 ("biometrics", "yawnsPerMin"), ("environment", "cabinCo2_mmHg"), ("environment", "radiation_mSv"))
    out["eyesClosedPercent"] = round(out.pop("perclos") * 100)  # as the HUD shows it
    return out


if __name__ == "__main__":
    mcp.run()
