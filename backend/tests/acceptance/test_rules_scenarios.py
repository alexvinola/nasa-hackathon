"""G4: for every demo-script scenario, the rules engine returns what is expected."""

import pytest

from conftest import SHARED, load

SCENARIOS = sorted((SHARED / "scenarios").glob("*.json"))


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: p.stem)
def test_scenario(client, decision_validator, path):
    scenario = load(path)
    expect = scenario["expect"]

    response = client.post("/rules/evaluate", json=scenario["input"])

    assert response.status_code == 200, response.text
    decision = response.json()
    decision_validator.validate(decision)
    assert decision["status"] == expect["status"]
    assert decision["escalation"] == expect["escalation"]
    assert decision["hrpRisk"] == expect["hrpRisk"]
    assert set(decision["affectedSystems"]) == set(expect["affectedSystems"])
    signals = {factor["signal"] for factor in decision["factors"]}
    assert set(expect["factorSignals"]) <= signals, f"missing factors: {set(expect['factorSignals']) - signals}"
    if decision["status"] != "GREEN":
        assert decision["countermeasureId"], "an alert without a countermeasure does not tell the astronaut what to do"
        assert all(factor["message"] for factor in decision["factors"])
