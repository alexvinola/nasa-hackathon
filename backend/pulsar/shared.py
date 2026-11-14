"""Read-only access to `shared/`: the telemetry schema, the source registry and the official HRP names.

The backend never copies ids out of these files. Enumerations (statuses, hazards, HRP risks, body systems)
are read from the schema so a contract change reaches the backend without editing Python.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from pulsar import settings


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class SharedRegistry:
    schema: dict[str, Any]
    sources: dict[str, Any]
    hrp: dict[str, Any]

    def _enum(self, *path: str) -> tuple[str, ...]:
        node: Any = self.schema
        for key in path:
            node = node[key]
        return tuple(node["enum"])

    @property
    def source_ids(self) -> frozenset[str]:
        return frozenset(self.sources)

    @property
    def statuses(self) -> tuple[str, ...]:
        return self._enum("properties", "decision", "properties", "status")

    @property
    def escalations(self) -> tuple[str, ...]:
        return self._enum("properties", "decision", "properties", "escalation")

    @property
    def hazards(self) -> tuple[str, ...]:
        return self._enum("$defs", "hazard")

    @property
    def hrp_risks(self) -> tuple[str, ...]:
        return self._enum("$defs", "hrpRisk")

    @property
    def body_systems(self) -> tuple[str, ...]:
        return self._enum("$defs", "bodySystem")

    def hazard_name(self, hazard_id: str | None) -> str | None:
        return self.hrp["hazards"][hazard_id]["name"] if hazard_id else None

    def hrp_risk_name(self, risk_id: str | None) -> str | None:
        return self.hrp["risks"][risk_id]["name"] if risk_id else None


@lru_cache(maxsize=1)
def registry() -> SharedRegistry:
    shared = settings.SHARED_DIR
    return SharedRegistry(
        schema=_load(shared / "telemetry.schema.json"),
        sources=_load(shared / "sources.json")["sources"],
        hrp=_load(shared / "hrp.json"),
    )
