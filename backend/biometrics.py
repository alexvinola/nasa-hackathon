"""Receives the `biometrics` block the browser computes with MediaPipe and checks it against the contract.

The browser does the landmark work (frontend/src/modules/vision-hud/faceWorker.ts) and posts the numbers here once a
second. This endpoint only validates them against shared/telemetry.schema.json and keeps the last reading in memory
for the rules engine; nothing is written to disk.
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from jsonschema import Draft202012Validator

router = APIRouter()

CONTRACT = json.loads((Path(__file__).resolve().parent.parent / "shared" / "telemetry.schema.json").read_text())
_BIOMETRICS = CONTRACT["properties"]["biometrics"]
VALIDATOR = Draft202012Validator(
    {
        "$schema": CONTRACT["$schema"],
        "$defs": CONTRACT["$defs"],
        "type": "object",
        "additionalProperties": False,
        "required": _BIOMETRICS["required"],
        "properties": _BIOMETRICS["properties"],
    }
)

last: dict | None = None


def check(reading: dict) -> dict:
    """Returns the reading when it matches the contract, else raises 422 with the first problem found."""
    error = next(VALIDATOR.iter_errors(reading), None)
    if error is not None:
        where = "/".join(str(part) for part in error.absolute_path) or "biometrics"
        raise HTTPException(422, f"{where}: {error.message}")
    return reading


@router.post("/biometrics")
async def receive(request: Request) -> dict:
    """Body: the `biometrics` object of the telemetry contract. Returns it once validated."""
    global last
    try:
        reading = await request.json()
    except json.JSONDecodeError as error:
        raise HTTPException(400, "the body must be JSON") from error
    if not isinstance(reading, dict):
        raise HTTPException(422, "the body must be the biometrics object")
    last = await run_in_threadpool(check, reading)
    return {"ok": True, "biometrics": last}


@router.get("/biometrics/latest")
async def latest() -> dict:
    """The last reading the browser sent, for the rules engine and for the demo."""
    if last is None:
        raise HTTPException(404, "no reading yet")
    return last
