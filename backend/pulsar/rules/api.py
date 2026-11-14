"""HTTP surface of the rules engine.

- POST /rules/evaluate        full telemetry contract -> `decision` block (422 if the contract is broken)
- GET  /rules                 every rule with its threshold and where it comes from (source or assumption)
- GET  /rules/policy          how triggered rules combine into one decision
- GET  /countermeasures       every countermeasure
- GET  /countermeasures/{id}  one countermeasure, with its steps
"""

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.exceptions import RequestValidationError

from pulsar import debug
from pulsar.contract import telemetry_errors
from pulsar.rules.engine import RulesEngine
from pulsar.shared import registry

router = APIRouter(tags=["rules"])


def _engine(request: Request) -> RulesEngine:
    return request.app.state.rules_engine


@router.post("/rules/evaluate", summary="Decide status, escalation and HRP risk from telemetry")
def evaluate(request: Request, telemetry: dict[str, Any] = Body(...)) -> dict[str, Any]:
    errors = telemetry_errors(telemetry)
    if errors:
        raise RequestValidationError(errors)
    decision = _engine(request).evaluate(telemetry)
    signals = ", ".join(factor.get("signal", "?") for factor in decision.get("factors", [])) or "nothing triggered"
    verdict = f"{decision.get('status')}: {signals}"
    if verdict != getattr(request.app.state, "last_verdict", None):  # asked every 2 s: only a change is news
        request.app.state.last_verdict = verdict
        debug.record("engine", verdict, status=decision.get("status"))
    return decision


@router.get("/rules", summary="Every rule the engine applies and where its threshold comes from")
def list_rules(request: Request) -> list[dict[str, Any]]:
    shared = registry()
    return [
        {
            **rule.model_dump(),
            "hazardName": shared.hazard_name(rule.hazard),
            "hrpRiskName": shared.hrp_risk_name(rule.hrpRisk),
        }
        for rule in _engine(request).rules
    ]


@router.get("/rules/policy", summary="How triggered rules combine into one decision")
def policy(request: Request) -> dict[str, Any]:
    return _engine(request).policy.model_dump()


@router.get("/countermeasures", tags=["countermeasures"], summary="Every countermeasure")
def list_countermeasures(request: Request) -> list[dict[str, Any]]:
    return [cm.model_dump() for cm in _engine(request).countermeasures.values()]


@router.get("/countermeasures/{countermeasure_id}", tags=["countermeasures"], summary="One countermeasure")
def get_countermeasure(request: Request, countermeasure_id: str) -> dict[str, Any]:
    cm = _engine(request).countermeasures.get(countermeasure_id)
    if cm is None:
        raise HTTPException(status_code=404, detail=f"unknown countermeasure {countermeasure_id}")
    return cm.model_dump()
