"""Where a threshold on a camera signal would sit, and what it would cost, measured on the RLDD windows.

The rules engine decides with thresholds on ``biometrics.perclos`` and ``biometrics.fatigueScore``
(``backend/assets/rules.json``); both are team placeholders. This module does not choose them. It reports,
for each signal, the cut that keeps the share of ALERT windows above it at a given rate (the false alarms),
and the share of low-vigilance and drowsy windows above that cut (what it catches), so that whoever writes
the rule knows the trade.

A window "fires" when its value is ABOVE the cut. The cut for a rate is the smallest observed alert value
with at most that share of alert windows above it, so ties (many windows at exactly 0) never push the false
alarms over the rate.

Two sets of numbers per rate:

- ``cut``: from the alert windows of every subject. This is the number a rule would use.
- ``out_of_fold``: every subject is scored with the cut taken from the OTHER subjects' alert windows (the
  folds of the validation), which is what a new person should expect. Shares are over windows, and per
  subject (the share of that person's alert, and drowsy, windows that fire).

``FALSE_ALARM_RATES`` is a team assumption: which rates are worth looking at, not a recommendation.
RLDD's labels are self-reported and each video has one label, so "drowsy windows that fire" means windows of
a video its subject called drowsy, not moments of drowsiness.
"""

from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np

from . import fatigue_features as ff

FALSE_ALARM_RATES: tuple[float, ...] = (0.05, 0.10)  # assumption: the rates reported


def cut_for_rate(alert_values: np.ndarray, rate: float) -> float:
    """Smallest observed alert value with at most ``rate`` of the alert values above it; NaN without values."""
    values = np.sort(np.asarray(alert_values, dtype=np.float64))
    if not len(values):
        return float("nan")
    allowed = int(np.floor(rate * len(values) + 1e-9))  # how many alert windows may fire
    candidate = values[len(values) - allowed - 1] if allowed < len(values) else values[0]
    return float(candidate)  # values above it: at most `allowed`, fewer when the candidate is tied with larger ranks


def fire_shares(classes: np.ndarray, fires: np.ndarray) -> dict:
    """Share of the windows of each state that fire; None for a state with no window."""
    return {name: (float(fires[classes == k].mean()) if (classes == k).any() else None) for k, name in enumerate(ff.CLASS_NAMES)}


def per_subject_shares(classes: np.ndarray, groups: np.ndarray, fires: np.ndarray, state: int) -> dict:
    """The share of each subject's windows of one state that fire: median, range and how many subjects fire at all."""
    shares = [float(fires[(groups == subject) & (classes == state)].mean()) for subject in sorted(set(groups)) if ((groups == subject) & (classes == state)).any()]
    if not shares:
        return {"subjects": 0, "median": None, "min": None, "max": None, "subjects_with_any": 0}
    return {
        "subjects": len(shares),
        "median": float(np.median(shares)),
        "min": float(min(shares)),
        "max": float(max(shares)),
        "subjects_with_any": int(sum(share > 0 for share in shares)),
    }


def operating_point(classes: np.ndarray, groups: np.ndarray, values: np.ndarray, folds: Sequence[Sequence[str]], rate: float) -> dict:
    """The cut for one false-alarm rate and what it does, on every subject and out of fold."""
    alert = classes == 0
    cut = cut_for_rate(values[alert], rate)
    fires = np.zeros(len(values), dtype=bool)
    fold_cuts = []
    for test_subjects in folds:
        test = np.isin(groups, list(test_subjects))
        fold_cut = cut_for_rate(values[alert & ~test], rate)
        fold_cuts.append(fold_cut)
        fires[test] = values[test] > fold_cut  # NaN cut (no alert window to learn from): nothing fires
    return {
        "false_alarm_rate": rate,
        "cut": cut,
        "fires_when": "value > cut",
        "all_subjects": fire_shares(classes, values > cut),
        "out_of_fold": {
            "cut_range": [float(np.nanmin(fold_cuts)), float(np.nanmax(fold_cuts))] if np.isfinite(fold_cuts).any() else None,
            "windows": fire_shares(classes, fires),
            "alert_per_subject": per_subject_shares(classes, groups, fires, 0),
            "drowsy_per_subject": per_subject_shares(classes, groups, fires, 2),
        },
    }


def fixed_threshold(classes: np.ndarray, groups: np.ndarray, values: np.ndarray, threshold: float, operator: str) -> dict:
    """What an existing rule (``value <operator> threshold``) does on these windows."""
    if operator not in (">=", ">"):
        raise ValueError(f"unsupported operator for a camera threshold: {operator!r}")
    fires = values >= threshold if operator == ">=" else values > threshold
    return {
        "threshold": threshold,
        "operator": operator,
        "windows": fire_shares(classes, fires),
        "windows_firing": int(fires.sum()),
        "alert_per_subject": per_subject_shares(classes, groups, fires, 0),
        "drowsy_per_subject": per_subject_shares(classes, groups, fires, 2),
    }


def engine_rules(rules: Sequence[Mapping]) -> dict[str, dict]:
    """The engine's rules on the two camera signals, by signal: ``{signal: {id, threshold, operator, status}}``."""
    wanted = ("biometrics.perclos", "biometrics.fatigueScore")
    return {
        rule["signal"]: {key: rule[key] for key in ("id", "threshold", "operator", "status")}
        for rule in rules
        if rule.get("signal") in wanted
    }


def report(
    classes: np.ndarray,
    groups: np.ndarray,
    signals: Mapping[str, np.ndarray],
    folds: Sequence[Sequence[str]],
    rules: Mapping[str, Mapping] | None = None,
    rule_signals: Mapping[str, Sequence[str]] | None = None,
) -> dict:
    """The ``thresholds`` block of ``metrics.json``.

    ``signals`` maps a name to one value per window. ``rules`` is ``engine_rules(...)`` and ``rule_signals``
    says which of the signals each engine signal is compared with (``biometrics.fatigueScore`` is the
    browser's formula today, and would be the model's score if the model replaced it).
    """
    block = {
        "false_alarm_rates": list(FALSE_ALARM_RATES),
        "how": (
            "A window fires when its value is above the cut. The cut for a rate is the smallest alert value with at most that share of "
            "alert windows above it. `out_of_fold` scores every subject with the cut from the other subjects' alert windows."
        ),
        "signals": {
            name: [operating_point(classes, groups, np.asarray(values, dtype=np.float64), folds, rate) for rate in FALSE_ALARM_RATES]
            for name, values in signals.items()
        },
        "engine_rules": {},
        "limits": [
            "RLDD labels are self-reported, one per video: a drowsy window is a window of a video its subject called drowsy.",
            "The rates looked at (5 % and 10 % of alert windows) are a team assumption, not a recommendation.",
            "Windows of one video overlap by 50 s, so the shares are not counts of independent events; an alarm that fires on a window fires on its neighbours too.",
            "The browser's fatigueScore is also raised by eyes held closed for seconds (vision-hud/sleep.ts); that part is not in these numbers.",
        ],
    }
    for engine_signal, rule in (rules or {}).items():
        for name in (rule_signals or {}).get(engine_signal, ()):
            block["engine_rules"][f"{rule['id']} on {name}"] = {
                "rule": dict(rule),
                "signal": name,
                **fixed_threshold(classes, groups, np.asarray(signals[name], dtype=np.float64), float(rule["threshold"]), rule["operator"]),
            }
    return block
