"""HTTP surface of the voice pipeline.

- POST /voice/advise   {telemetry, question?} -> the engine's decision and the sentence PULSAR speaks
"""

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.exceptions import RequestValidationError

from pulsar import debug
from pulsar.contract import telemetry_errors
from pulsar.voice.pipeline import first_step, phrase

router = APIRouter(tags=["voice"])


@router.post("/voice/advise", summary="The engine decides, Gemma phrases the decision in two sentences")
def advise(request: Request, telemetry: dict[str, Any] = Body(...), question: str = Body("")) -> dict[str, Any]:
    errors = telemetry_errors(telemetry)
    if errors:
        raise RequestValidationError(errors)
    engine = request.app.state.rules_engine
    decision = engine.evaluate(telemetry)
    try:
        phrasing = phrase(decision, question, first_step(engine, decision))
    except OSError as error:  # Ollama down or the model missing
        raise HTTPException(503, f"the phrasing model is not answering: {error}") from error
    debug.record("voice", f"says ({phrasing.source}): {phrasing.text}")
    return {"decision": decision, "say": phrasing.text, "source": phrasing.source, "violations": phrasing.violations}
