"""Loads the rules and countermeasures and checks them against `shared/` before the app serves anything.

A rule that cites an unknown source, hazard, HRP risk, body system or countermeasure stops the app at startup:
better a loud failure on the laptop than a verdict the team cannot trace.
"""

import json
from pathlib import Path

from pulsar import settings
from pulsar.rules.models import CountermeasureBook, RuleBook
from pulsar.shared import SharedRegistry, registry


class RulesFileError(ValueError):
    pass


def _problems(book: RuleBook, countermeasures: CountermeasureBook, shared: SharedRegistry) -> list[str]:
    problems: list[str] = []
    policy = book.policy

    if set(policy.levels) != set(shared.statuses) or len(policy.levels) != len(shared.statuses):
        problems.append(f"policy.levels {policy.levels} must order exactly the contract statuses {shared.statuses}")
    if set(policy.escalation) != set(policy.levels):
        problems.append("policy.escalation needs one entry per status")
    for status, escalation in policy.escalation.items():
        if escalation not in shared.escalations:
            problems.append(f"policy.escalation[{status}]: {escalation} is not a contract escalation")

    alert_levels = set(policy.levels[1:])
    countermeasure_ids = [cm.id for cm in countermeasures.countermeasures]
    if len(set(countermeasure_ids)) != len(countermeasure_ids):
        problems.append("duplicate countermeasure ids")
    for cm in countermeasures.countermeasures:
        if cm.source is not None and cm.source not in shared.source_ids:
            problems.append(f"countermeasure {cm.id}: unknown source {cm.source}")

    seen: set[str] = set()
    for rule in book.rules:
        where = f"rule {rule.id}"
        if rule.id in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(rule.id)
        if rule.status not in alert_levels:
            problems.append(f"{where}: status {rule.status} must be one of {sorted(alert_levels)}")
        if rule.source is not None and rule.source not in shared.source_ids:
            problems.append(f"{where}: unknown source {rule.source} (add it to shared/sources.json first)")
        if rule.hazard is not None and rule.hazard not in shared.hazards:
            problems.append(f"{where}: {rule.hazard} is not an official HRP hazard")
        if rule.hrpRisk is not None and rule.hrpRisk not in shared.hrp_risks:
            problems.append(f"{where}: {rule.hrpRisk} is not an official HRP risk")
        for system in rule.bodySystems:
            if system not in shared.body_systems:
                problems.append(f"{where}: {system} is not a body system in the contract")
        if rule.countermeasureId not in countermeasure_ids:
            problems.append(f"{where}: countermeasure {rule.countermeasureId} is not in countermeasures.json")
        if not _signal_in_contract(rule.signal, shared):
            problems.append(f"{where}: signal {rule.signal} is not a numeric field of the contract")
        try:
            rule.render_message(rule.threshold)
        except (KeyError, IndexError, ValueError) as error:
            problems.append(f"{where}: message template is broken ({error!r})")
    return problems


def _signal_in_contract(signal: str, shared: SharedRegistry) -> bool:
    """The signal path must reach a numeric property of the schema (through nullable objects too)."""
    node = shared.schema
    for key in signal.split("."):
        candidates = [node, *node.get("oneOf", [])]
        node = next((c["properties"][key] for c in candidates if key in c.get("properties", {})), None)
        if node is None:
            return False
    while "$ref" in node:  # local refs only, e.g. #/$defs/unit
        target = shared.schema
        for part in node["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        node = target
    types = node.get("type")
    types = types if isinstance(types, list) else [types]
    return "number" in types or "integer" in types


def load_rule_book(
    rules_file: Path | None = None,
    countermeasures_file: Path | None = None,
    shared: SharedRegistry | None = None,
    lang: str | None = None,
) -> tuple[RuleBook, CountermeasureBook]:
    rules_file = rules_file or settings.RULES_FILE
    countermeasures_file = countermeasures_file or settings.COUNTERMEASURES_FILE
    book = RuleBook.model_validate(json.loads(rules_file.read_text(encoding="utf-8")))
    countermeasures = CountermeasureBook.model_validate(json.loads(countermeasures_file.read_text(encoding="utf-8")))
    problems = _problems(book, countermeasures, shared or registry())
    if problems:
        raise RulesFileError(f"{rules_file.name} / {countermeasures_file.name}:\n  " + "\n  ".join(problems))
    return _in_language(book, countermeasures, lang)


def _in_language(book: RuleBook, countermeasures: CountermeasureBook, lang: str | None) -> tuple[RuleBook, CountermeasureBook]:
    """The files are in the default language; another one only swaps the wording (messages, titles, steps) by id."""
    lang = settings.pick_lang(lang)
    file = settings.I18N_DIR / f"{lang}.json"
    if not file.exists():
        return book, countermeasures
    text = json.loads(file.read_text(encoding="utf-8"))
    rules = tuple(rule.model_copy(update={"message": text["rules"].get(rule.id, rule.message)}) for rule in book.rules)
    cms = tuple(
        cm.model_copy(update={"title": text["countermeasures"].get(cm.id, {}).get("title", cm.title),
                              "steps": tuple(text["countermeasures"].get(cm.id, {}).get("steps", cm.steps))})
        for cm in countermeasures.countermeasures
    )
    return book.model_copy(update={"rules": rules}), countermeasures.model_copy(update={"countermeasures": cms})
