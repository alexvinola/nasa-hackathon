"""The real rules file traces back to shared/, and the loader refuses one that does not."""

import json

import pytest

from pulsar.rules.loader import RulesFileError, load_rule_book
from pulsar.settings import COUNTERMEASURES_FILE, RULES_FILE
from pulsar.shared import registry


def test_real_rules_file_loads():
    book, countermeasures = load_rule_book()

    assert book.rules
    assert {rule.countermeasureId for rule in book.rules} <= {cm.id for cm in countermeasures.countermeasures}


def test_every_rule_cites_a_source_or_explains_its_assumption():
    book, _ = load_rule_book()
    sources = registry().source_ids

    for rule in book.rules:
        assert rule.source in sources or (rule.source is None and rule.assumption), rule.id


def write_variant(tmp_path, mutate):
    rules = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    mutate(rules["rules"][0])
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(rules), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("change", "complaint"),
    [
        ({"source": "made-up-2026"}, "unknown source"),
        ({"hazard": "BOREDOM"}, "not an official HRP hazard"),
        ({"hrpRisk": "SCURVY"}, "not an official HRP risk"),
        ({"bodySystems": ["SPLEEN"]}, "not a body system"),
        ({"countermeasureId": "CM-NOPE"}, "not in countermeasures.json"),
        ({"signal": "biometrics.hrv"}, "not a numeric field"),
        ({"signal": "voice.transcript"}, "not a numeric field"),
        ({"status": "GREEN"}, "status GREEN"),
    ],
)
def test_loader_rejects_untraceable_rules(tmp_path, change, complaint):
    path = write_variant(tmp_path, lambda rule: rule.update(change))

    with pytest.raises(RulesFileError, match=complaint):
        load_rule_book(rules_file=path, countermeasures_file=COUNTERMEASURES_FILE)


def test_rule_without_source_needs_an_assumption(tmp_path):
    path = write_variant(tmp_path, lambda rule: rule.update({"source": None, "assumption": " "}))

    with pytest.raises(ValueError, match="source id or an assumption"):
        load_rule_book(rules_file=path, countermeasures_file=COUNTERMEASURES_FILE)
