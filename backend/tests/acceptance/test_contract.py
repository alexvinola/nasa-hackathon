"""G0, backend side: the backend accepts the contract and rejects whatever breaks it."""

import pytest

from conftest import SHARED, load

VALID = sorted((SHARED / "examples").glob("*.json"))
INVALID = sorted((SHARED / "examples" / "invalid").glob("*.json"))


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_accepts_valid_telemetry(client, decision_validator, path):
    response = client.post("/rules/evaluate", json=load(path))

    assert response.status_code == 200, response.text
    decision_validator.validate(response.json())


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_rejects_invalid_telemetry(client, path):
    response = client.post("/rules/evaluate", json=load(path))

    assert response.status_code == 422, response.text
