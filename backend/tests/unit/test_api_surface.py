"""Endpoints beyond the acceptance tests: rule listing details, countermeasures, health, malformed bodies."""

from fastapi.testclient import TestClient

from main import app
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
