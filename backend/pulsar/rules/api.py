"""HTTP surface of the rules engine.

Every route takes an optional `?lang=es|en` (default `PULSAR_LANG`, else es): the same rules and ids, worded in that language.

- POST /rules/evaluate        full telemetry contract -> `decision` block (422 if the contract is broken)
- GET  /rules                 every rule with its threshold and where it comes from (source or assumption)
- GET  /rules/policy          how triggered rules combine into one decision
- GET  /countermeasures       every countermeasure
- GET  /countermeasures/{id}  one countermeasure, with its steps
"""

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError

from pulsar import debug, settings
from pulsar.contract import telemetry_errors
from pulsar.rules.engine import RulesEngine
from pulsar.shared import registry

router = APIRouter(tags=["rules"])


def engine_for(request: Request, lang: str | None = None) -> RulesEngine:
    """The engine worded in `lang` (the default language when it is missing or unknown)."""
    return request.app.state.engines[settings.pick_lang(lang)]


def _engine(request: Request, lang: str | None = None) -> RulesEngine:
    return engine_for(request, lang)


@router.post("/rules/evaluate", summary="Decide status, escalation and HRP risk from telemetry")
def evaluate(request: Request, telemetry: dict[str, Any] = Body(...), lang: str | None = Query(None)) -> dict[str, Any]:
    errors = telemetry_errors(telemetry)
    if errors:
        raise RequestValidationError(errors)
    decision = _engine(request, lang).evaluate(telemetry)
    signals = ", ".join(factor.get("signal", "?") for factor in decision.get("factors", [])) or "nothing triggered"
    verdict = f"{decision.get('status')}: {signals}"
    if verdict != getattr(request.app.state, "last_verdict", None):  # asked every 2 s: only a change is news
        request.app.state.last_verdict = verdict
        debug.record("engine", verdict, status=decision.get("status"))
    return decision


@router.get("/rules", summary="Every rule the engine applies and where its threshold comes from")
def list_rules(request: Request, lang: str | None = Query(None)) -> list[dict[str, Any]]:
    shared = registry()
    return [
        {
            **rule.model_dump(),
            "hazardName": shared.hazard_name(rule.hazard),
            "hrpRiskName": shared.hrp_risk_name(rule.hrpRisk),
        }
        for rule in _engine(request, lang).rules
    ]


@router.get("/rules/policy", summary="How triggered rules combine into one decision")
def policy(request: Request) -> dict[str, Any]:
    return _engine(request).policy.model_dump()


@router.get("/countermeasures", tags=["countermeasures"], summary="Every countermeasure")
def list_countermeasures(request: Request, lang: str | None = Query(None)) -> list[dict[str, Any]]:
    return [cm.model_dump() for cm in _engine(request, lang).countermeasures.values()]


@router.get("/countermeasures/{countermeasure_id}", tags=["countermeasures"], summary="One countermeasure")
def get_countermeasure(request: Request, countermeasure_id: str, lang: str | None = Query(None)) -> dict[str, Any]:
    cm = _engine(request, lang).countermeasures.get(countermeasure_id)
    if cm is None:
        raise HTTPException(status_code=404, detail=f"unknown countermeasure {countermeasure_id}")
    return cm.model_dump()
