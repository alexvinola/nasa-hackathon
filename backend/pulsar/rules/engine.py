"""The rules engine: telemetry in, decision out. Deterministic; no model and no LLM in this path.

Each rule in `assets/rules.json` compares one contract signal with one threshold. The triggered rules
("findings") are combined by a policy that does not know about any particular scenario:

1. status      = the most severe status among the findings (policy.levels order); the first level if none.
2. escalation  = policy.escalation[status] (a team assumption, stated in the rules file).
3. affected    = union of the findings' body systems, in finding order.
4. hrpRisk     = among findings that name an official HRP risk, keep those at the highest severity; pick the
                 risk named by the most of them (the best-corroborated explanation); ties go to the rule listed
                 first in the file. Null when no finding names a risk (e.g. cabin CO2: no HRP risk covers it).
5. countermeasure = the countermeasure of the first finding (most severe, then file order).
6. factors     = every finding, most severe first, then file order. File order is therefore the priority.

A signal that is null (not measured, not entered) triggers nothing: missing data is not an alert.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pulsar.rules.models import Countermeasure, CountermeasureBook, Policy, Rule, RuleBook


@dataclass(frozen=True)
class Finding:
    rule: Rule
    value: float

    def as_factor(self) -> dict[str, Any]:
        rule = self.rule
        return {
            "signal": rule.signal,
            "value": self.value,
            "threshold": rule.threshold,
            "hazard": rule.hazard,
            "source": rule.source,
            "message": rule.render_message(self.value),
        }


def read_signal(telemetry: Mapping[str, Any], signal: str) -> float | None:
    """Value at a dotted path, or None when it is absent, null or not a number."""
    node: Any = telemetry
    for key in signal.split("."):
        if not isinstance(node, Mapping) or key not in node:
            return None
        node = node[key]
    if isinstance(node, bool) or not isinstance(node, int | float):
        return None
    return node


class RulesEngine:
    def __init__(self, book: RuleBook, countermeasures: CountermeasureBook):
        self.policy: Policy = book.policy
        self.rules: tuple[Rule, ...] = book.rules
        self.countermeasures: dict[str, Countermeasure] = {cm.id: cm for cm in countermeasures.countermeasures}
        self._severity = {level: rank for rank, level in enumerate(self.policy.levels)}
        self._order = {rule.id: index for index, rule in enumerate(self.rules)}

    def findings(self, telemetry: Mapping[str, Any]) -> list[Finding]:
        found = []
        for rule in self.rules:
            value = read_signal(telemetry, rule.signal)
            if value is not None and rule.triggers(value):
                found.append(Finding(rule, value))
        return sorted(found, key=lambda f: (-self._severity[f.rule.status], self._order[f.rule.id]))

    def evaluate(self, telemetry: Mapping[str, Any]) -> dict[str, Any]:
        """The contract's `decision` block for this telemetry. The incoming `decision` is ignored."""
        findings = self.findings(telemetry)
        status = findings[0].rule.status if findings else self.policy.levels[0]
        return {
            "status": status,
            "escalation": self.policy.escalation[status],
            "affectedSystems": self._affected_systems(findings),
            "hrpRisk": self._hrp_risk(findings),
            "factors": [finding.as_factor() for finding in findings],
            "countermeasureId": findings[0].rule.countermeasureId if findings else None,
        }

    @staticmethod
    def _affected_systems(findings: Sequence[Finding]) -> list[str]:
        systems: dict[str, None] = {}
        for finding in findings:
            systems.update(dict.fromkeys(finding.rule.bodySystems))
        return list(systems)

    def _hrp_risk(self, findings: Sequence[Finding]) -> str | None:
        named = [f for f in findings if f.rule.hrpRisk is not None]
        if not named:
            return None
        top = max(self._severity[f.rule.status] for f in named)
        # `named` is already in priority order, so Counter's insertion order breaks ties by file order.
        votes = Counter(f.rule.hrpRisk for f in named if self._severity[f.rule.status] == top)
        return max(votes, key=lambda risk: votes[risk])
