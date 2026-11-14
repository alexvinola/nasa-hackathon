"""Unit tests of the aggregation policy, on a small rule book built in the test (not the real rules file)."""

import copy
import json

import pytest

from pulsar.contract import decision_validator
from pulsar.rules.engine import RulesEngine, read_signal
from pulsar.rules.models import CountermeasureBook, RuleBook
from pulsar.settings import SHARED_DIR

NOMINAL = json.loads((SHARED_DIR / "examples" / "nominal.json").read_text(encoding="utf-8"))

POLICY = {
    "levels": ["GREEN", "AMBER", "RED"],
    "escalation": {"GREEN": "SELF_CARE", "AMBER": "CREW", "RED": "FLIGHT_SURGEON"},
    "assumption": "test",
    "description": ["test"],
}


def rule(rule_id, signal, threshold, status="AMBER", risk=None, systems=(), operator=">=", cm="CM-A"):
    return {
        "id": rule_id,
        "signal": signal,
        "operator": operator,
        "threshold": threshold,
        "unit": "",
        "status": status,
        "hazard": None,
        "hrpRisk": risk,
        "bodySystems": list(systems),
        "countermeasureId": cm,
        "source": None,
        "assumption": "test threshold",
        "message": "{value} vs {threshold}",
    }


def engine(*rules):
    book = RuleBook.model_validate({"policy": POLICY, "rules": list(rules)})
    cms = CountermeasureBook.model_validate(
        {"countermeasures": [{"id": cm, "title": cm, "steps": ["step"], "note": "test"} for cm in ("CM-A", "CM-B", "CM-C")]}
    )
    return RulesEngine(book, cms)


def telemetry(**overrides):
    doc = copy.deepcopy(NOMINAL)
    for path, value in overrides.items():
        node = doc
        *parents, leaf = path.split("__")
        for key in parents:
            node = node[key]
        node[leaf] = value
    return doc


def test_no_trigger_is_green_self_care_without_countermeasure():
    decision = engine(rule("perclos", "biometrics.perclos", 0.9)).evaluate(NOMINAL)

    assert decision == {
        "status": "GREEN",
        "escalation": "SELF_CARE",
        "affectedSystems": [],
        "hrpRisk": None,
        "factors": [],
        "countermeasureId": None,
    }
    decision_validator().validate(decision)


def test_status_and_escalation_follow_the_most_severe_rule():
    eng = engine(
        rule("a", "biometrics.perclos", 0.01, "AMBER", cm="CM-A"),
        rule("r", "biometrics.armAsymmetry", 0.05, "RED", cm="CM-B"),
    )
    decision = eng.evaluate(NOMINAL)

    assert (decision["status"], decision["escalation"]) == ("RED", "FLIGHT_SURGEON")
    assert decision["countermeasureId"] == "CM-B"
    assert [f["signal"] for f in decision["factors"]] == ["biometrics.armAsymmetry", "biometrics.perclos"]
    decision_validator().validate(decision)


def test_null_signal_triggers_nothing():
    eng = engine(rule("sleep", "selfReport.sleepHoursLast24h", 6, operator="<"))

    assert eng.evaluate(telemetry(selfReport__sleepHoursLast24h=None))["status"] == "GREEN"
    assert eng.evaluate(telemetry(selfReport__sleepHoursLast24h=5))["status"] == "AMBER"


def test_nested_nullable_signal():
    eng = engine(rule("bp", "selfReport.bloodPressure.systolic", 140))

    assert eng.evaluate(NOMINAL)["status"] == "GREEN"
    assert eng.evaluate(telemetry(selfReport__bloodPressure={"systolic": 150, "diastolic": 90}))["status"] == "AMBER"


def test_affected_systems_is_the_union():
    eng = engine(
        rule("a", "biometrics.perclos", 0.01, systems=["NERVOUS"]),
        rule("b", "biometrics.fatigueScore", 0.1, systems=["NERVOUS", "METABOLIC"]),
        rule("c", "environment.cabinCo2_mmHg", 1, systems=[]),
    )

    assert eng.evaluate(NOMINAL)["affectedSystems"] == ["NERVOUS", "METABOLIC"]


def test_hrp_risk_ignores_less_severe_findings():
    eng = engine(
        rule("a1", "biometrics.perclos", 0.01, "AMBER", risk="SLEEP_AND_SCHEDULES"),
        rule("a2", "biometrics.fatigueScore", 0.1, "AMBER", risk="SLEEP_AND_SCHEDULES"),
        rule("r", "biometrics.armAsymmetry", 0.05, "RED", risk="SENSORIMOTOR_VESTIBULAR"),
    )

    assert eng.evaluate(NOMINAL)["hrpRisk"] == "SENSORIMOTOR_VESTIBULAR"


def test_hrp_risk_skips_findings_that_name_none():
    eng = engine(
        rule("r", "biometrics.armAsymmetry", 0.05, "RED", risk=None),
        rule("a", "biometrics.perclos", 0.01, "AMBER", risk="SLEEP_AND_SCHEDULES"),
    )

    assert eng.evaluate(NOMINAL)["hrpRisk"] == "SLEEP_AND_SCHEDULES"


def test_hrp_risk_most_corroborated_then_file_order():
    first = rule("rad", "environment.radiation_mSv", 0.1, risk="RADIATION_CANCER")
    sleep = [
        rule("s1", "biometrics.perclos", 0.01, risk="SLEEP_AND_SCHEDULES"),
        rule("s2", "biometrics.fatigueScore", 0.1, risk="SLEEP_AND_SCHEDULES"),
    ]

    assert engine(first, *sleep).evaluate(NOMINAL)["hrpRisk"] == "SLEEP_AND_SCHEDULES"
    assert engine(first, sleep[0]).evaluate(NOMINAL)["hrpRisk"] == "RADIATION_CANCER"
    assert engine(sleep[0], first).evaluate(NOMINAL)["hrpRisk"] == "SLEEP_AND_SCHEDULES"


def test_only_cabin_risk_free_rules_give_null_risk():
    eng = engine(rule("co2", "environment.cabinCo2_mmHg", 1, risk=None, systems=["RESPIRATORY"]))
    decision = eng.evaluate(NOMINAL)

    assert decision["status"] == "AMBER" and decision["hrpRisk"] is None
    assert decision["countermeasureId"] == "CM-A"


@pytest.mark.parametrize(
    ("operator", "value", "expected"),
    [("<", 5.9, True), ("<", 6, False), ("<=", 6, True), (">", 6, False), (">=", 6, True)],
)
def test_operators(operator, value, expected):
    eng = engine(rule("sleep", "selfReport.sleepHoursLast24h", 6, operator=operator))

    assert (eng.evaluate(telemetry(selfReport__sleepHoursLast24h=value))["status"] == "AMBER") is expected


def test_read_signal_rejects_non_numbers():
    assert read_signal({"a": {"b": True}}, "a.b") is None
    assert read_signal({"a": {"b": "1"}}, "a.b") is None
    assert read_signal({"a": None}, "a.b") is None
    assert read_signal({"a": {"b": 2}}, "a.b") == 2
