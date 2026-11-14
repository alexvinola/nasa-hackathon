"""Rules engine: the only component of PULSAR that decides.

Vision measures, the fatigue classifier estimates, this engine decides, and the LLM only phrases the verdict.
Rules and the aggregation policy live in `assets/rules.json`; countermeasures in `assets/countermeasures.json`.
"""

from pulsar.rules.engine import RulesEngine
from pulsar.rules.loader import RulesFileError, load_rule_book

__all__ = ["RulesEngine", "RulesFileError", "load_rule_book", "build_engine"]


def build_engine() -> RulesEngine:
    """Engine built from the configured rules and countermeasures, checked against shared/."""
    return RulesEngine(*load_rule_book())
