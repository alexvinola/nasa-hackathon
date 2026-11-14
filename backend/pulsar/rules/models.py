"""Typed shape of the rules file (`assets/rules.json`) and the countermeasures file.

Pydantic checks the structure; `pulsar.rules.loader` then checks every id against `shared/`.
"""

import operator
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Operator = Literal["<", "<=", ">", ">="]

OPERATORS: dict[str, Callable[[float, float], bool]] = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Rule(_Strict):
    """One threshold on one contract signal. Triggered when `value <operator> threshold`."""

    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    signal: str = Field(description="Dotted path of the field in the contract, e.g. biometrics.perclos")
    operator: Operator
    threshold: float
    unit: str = Field(description="Unit shown in messages; empty when the signal has none")
    display: Literal["number", "percent"] = "number"
    status: str = Field(description="Status this rule raises when triggered (AMBER or RED)")
    hazard: str | None = Field(description="Official HRP hazard id (shared/hrp.json), or null")
    hrpRisk: str | None = Field(description="Official HRP risk id (shared/hrp.json), or null when none applies")
    bodySystems: tuple[str, ...] = Field(description="Body-twin zones this rule lights up")
    countermeasureId: str
    source: str | None = Field(description="Id in shared/sources.json behind the threshold")
    assumption: str | None = Field(description="Why the threshold is what it is, when no source backs it")
    message: str = Field(description="Template; {value}, {threshold} and {unit} are filled in")

    @model_validator(mode="after")
    def _traceable(self) -> "Rule":
        if self.source is None and not (self.assumption or "").strip():
            raise ValueError(f"rule {self.id}: a threshold needs a source id or an assumption explaining it")
        return self

    def triggers(self, value: float) -> bool:
        return OPERATORS[self.operator](value, self.threshold)

    def format(self, number: float) -> str:
        if self.display == "percent":
            return f"{round(number * 100)}%"
        return f"{number:g}"

    def render_message(self, value: float) -> str:
        return self.message.format(value=self.format(value), threshold=self.format(self.threshold), unit=self.unit)


class Policy(_Strict):
    """How triggered rules combine into one decision. See pulsar.rules.engine for the algorithm."""

    levels: tuple[str, ...] = Field(description="Statuses from least to most severe; the first one means no alert")
    escalation: dict[str, str] = Field(description="Escalation for each status")
    assumption: str
    description: tuple[str, ...] = Field(description="Plain-English statement of the policy, shown by GET /rules/policy")


class RuleBook(_Strict):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    comment: str | None = Field(default=None, alias="$comment")
    policy: Policy
    rules: tuple[Rule, ...]


class Countermeasure(_Strict):
    """Short steps the astronaut can follow, one at a time ("next step" by voice later)."""

    id: str
    title: str
    steps: tuple[str, ...] = Field(min_length=1)
    source: str | None = None
    note: str


class CountermeasureBook(_Strict):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    comment: str | None = Field(default=None, alias="$comment")
    countermeasures: tuple[Countermeasure, ...]
