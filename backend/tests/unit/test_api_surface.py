"""Endpoints beyond the acceptance tests: rule listing details, countermeasures, health, malformed bodies."""

import json

from fastapi.testclient import TestClient

from main import app
from pulsar import debug
from pulsar.settings import SHARED_DIR as SHARED
from pulsar.voice.config import DEFAULT_LLM_MODEL, load_voice_settings

client = TestClient(app)


def test_rules_listing_shows_official_names():
    rules = {rule["id"]: rule for rule in client.get("/rules").json()}

    assert rules["sleep-under-6h"]["source"] == "jones-2022-sleep"
    assert rules["sleep-under-6h"]["hrpRiskName"] == "Risk of Inadequate Sleep and Irregular Schedules"
    assert rules["cabin-co2-high"]["hrpRisk"] is None and rules["cabin-co2-high"]["assumption"]


def test_policy_is_served():
    policy = client.get("/rules/policy").json()

    assert policy["escalation"]["RED"] == "FLIGHT_SURGEON"
    assert policy["description"]


def test_every_rule_countermeasure_is_served():
    for rule in client.get("/rules").json():
        response = client.get(f"/countermeasures/{rule['countermeasureId']}")
        assert response.status_code == 200
        assert response.json()["steps"]
    assert client.get("/countermeasures/CM-NOPE").status_code == 404


def test_non_object_bodies_are_422():
    assert client.post("/rules/evaluate", json=[1, 2]).status_code == 422
    assert client.post("/rules/evaluate", content=b"not json", headers={"content-type": "application/json"}).status_code == 422


def test_the_debug_log_shows_requests_and_verdicts_but_not_its_own_polling():
    debug.clear()
    app.state.last_verdict = None
    assert client.get("/rules").status_code == 200
    assert client.post("/rules/evaluate", json=json.loads((SHARED / "examples" / "red-emergency.json").read_text())).status_code == 200
    assert client.get("/countermeasures/CM-NOPE").status_code == 404
    log = client.get("/debug/events").json()
    kinds = [event["kind"] for event in log["events"]]
    assert kinds == ["http", "engine", "http", "error"]
    assert log["events"][1]["text"].startswith("RED: ") and log["events"][0]["path"] == "/rules"
    assert [event["noisy"] for event in log["events"]] == [False, False, True, False]  # the evaluate request itself
    assert log["last"] == log["events"][-1]["id"]

    assert client.get("/health").status_code == 200  # not logged, and neither is the poll itself
    assert client.get(f"/debug/events?after={log['last']}").json() == {"events": [], "last": log["last"]}


def test_repeated_requests_cannot_push_the_other_events_out_and_a_verdict_is_logged_once():
    debug.clear()
    app.state.last_verdict = None
    debug.record("gemma", "kept")
    body = json.loads((SHARED / "examples" / "nominal.json").read_text())
    for _ in range(debug.MAX_NOISY + 20):
        assert client.post("/rules/evaluate", json=body).status_code == 200
    found = debug.events_after(0)
    assert [event["kind"] for event in found if not event["noisy"]] == ["gemma", "engine"]
    assert sum(event["noisy"] for event in found) == debug.MAX_NOISY
    assert client.get("/debug/events?after=999999").json()["last"] == found[-1]["id"]  # never an echo of `after`


def test_a_debug_event_is_one_short_line():
    debug.clear()
    debug.record("gemma", "a\n  b " + "x" * 500)
    (event,) = debug.events_after(0)
    assert event["text"].startswith("a b x") and len(event["text"]) == debug.MAX_TEXT


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_voice_settings_default_and_localhost_only():
    settings = load_voice_settings({})
    assert settings.llm_model == DEFAULT_LLM_MODEL == "gemma4:e4b-it-qat"
    assert settings.ollama_url == "http://127.0.0.1:11434"
    assert load_voice_settings({"PULSAR_LLM_MODEL": "gemma4:e2b-it-qat"}).llm_model == "gemma4:e2b-it-qat"
    assert load_voice_settings({"PULSAR_OLLAMA_URL": "http://localhost:11434/"}).ollama_url == "http://localhost:11434"

    for remote in ("http://ollama.example.com:11434", "http://10.0.0.5:11434", "ftp://localhost"):
        try:
            load_voice_settings({"PULSAR_OLLAMA_URL": remote})
        except ValueError:
            continue
        raise AssertionError(f"{remote} should be refused")
