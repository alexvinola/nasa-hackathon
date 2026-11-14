"""Validation against `shared/telemetry.schema.json`, the contract shared with the frontend.

The schema itself is the validator (JSON Schema 2020-12), so the backend accepts exactly what the frontend's
Ajv accepts. Errors are returned in FastAPI's shape so the API answers 422 like any other validation error.
"""

from functools import lru_cache
from typing import Any

from jsonschema import Draft202012Validator

from pulsar.shared import registry


@lru_cache(maxsize=1)
def telemetry_validator() -> Draft202012Validator:
    schema = registry().schema
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@lru_cache(maxsize=1)
def decision_validator() -> Draft202012Validator:
    """Validator for the `decision` block alone (what POST /rules/evaluate returns)."""
    schema = registry().schema
    decision = dict(schema["properties"]["decision"])
    decision["$defs"] = schema["$defs"]
    return Draft202012Validator(decision)


def telemetry_errors(payload: Any) -> list[dict[str, Any]]:
    """Contract violations in `payload`, as FastAPI-style error dicts. Empty when the payload is valid."""
    errors = sorted(telemetry_validator().iter_errors(payload), key=lambda error: list(map(str, error.absolute_path)))
    return [
        {
            "loc": ["body", *error.absolute_path],
            "msg": error.message,
            "type": f"contract.{error.validator}",
        }
        for error in errors
    ]
