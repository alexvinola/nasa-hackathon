"""Backend acceptance tests. Protected: the agent does not edit them to make them pass.

Interface they fix: backend/main.py exposes `app` (FastAPI), and
POST /rules/evaluate takes the full contract and returns the `decision` block.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

SHARED = Path(__file__).resolve().parents[3] / "shared"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def client():
    from main import app

    return TestClient(app)


@pytest.fixture(scope="session")
def decision_validator():
    schema = load(SHARED / "telemetry.schema.json")
    decision = dict(schema["properties"]["decision"])
    decision["$defs"] = schema["$defs"]
    return Draft202012Validator(decision)
