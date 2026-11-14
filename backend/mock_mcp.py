"""Mock MCP server (stdio): the astronaut's heart rate and the cabin CO2, as if they came from onboard sensors.

The values are read from a scenario in `shared/scenarios/` (`PULSAR_MOCK_SCENARIO`, default 03-high-co2), so the
mock always agrees with the demo data. Each reading carries the rules engine's verdict on it (`assessment`) and, when it is outside its limit, the steps to
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


def reading(section: str, key: str, **extra: str) -> dict[str, Any]:
    path = Path(os.environ.get("PULSAR_MOCK_SCENARIO", DEFAULT_SCENARIO))
    telemetry = json.loads(path.read_text(encoding="utf-8"))["input"]
    decision = engine().evaluate(telemetry)
    flagged = [f["message"] for f in decision["factors"] if f["signal"] == f"{section}.{key}"]
    countermeasure = engine().countermeasures.get(decision["countermeasureId"] or "")
    return {
        key: telemetry[section][key],
        **{name: telemetry[section][field] for name, field in extra.items()},
        "assessment": " ".join(flagged) or "within limits",
        # The team's own steps for this finding; shared across readings, so only a flagged one carries them.
        **({"stepsToTake": countermeasure.steps} if flagged and countermeasure else {}),
        "source": f"mock sensors, scenario {path.stem}",
    }


@mcp.tool()
def get_heart_rate() -> dict[str, Any]:
    """The astronaut's current heart rate in beats per minute, with the measurement confidence (0 to 1)."""
    return reading("biometrics", "heartRateBpm", confidence="heartRateConfidence")


@mcp.tool()
def get_cabin_co2() -> dict[str, Any]:
    """The cabin's current CO2 partial pressure in mmHg."""
    return reading("environment", "cabinCo2_mmHg")


if __name__ == "__main__":
    mcp.run()
