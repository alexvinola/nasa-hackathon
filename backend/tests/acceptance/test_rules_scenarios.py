"""G4: for every demo-script scenario, the rules engine returns what is expected."""

import pytest

from conftest import SHARED, load

SCENARIOS = sorted((SHARED / "scenarios").glob("*.json"))


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: p.stem)
def test_scenario(client, decision_validator, known_sources, path):
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
    for factor in decision["factors"]:
        assert factor["source"] is None or factor["source"] in known_sources, f"{factor['signal']}: unknown source"


def test_every_rule_traces_to_a_source_or_an_assumption(client, known_sources):
    """GET /rules lists the rules the engine applies, so the judges can see where each threshold comes from."""
    response = client.get("/rules")

    assert response.status_code == 200, response.text
    rules = response.json()
    assert rules, "the engine has no rules"
    for rule in rules:
        assert rule["id"] and rule["signal"], rule
        assert "threshold" in rule, rule
        if rule.get("source") is not None:
            assert rule["source"] in known_sources, f"{rule['id']}: unknown source {rule['source']}"
        else:
            assert rule.get("assumption"), f"{rule['id']}: no source and no assumption explaining the threshold"
