"""Cuts on a camera signal and what they cost: synthetic windows only."""

import math

import numpy as np
import pytest

from pulsar_vision import fatigue_thresholds as ft


def windows(per_subject: dict[str, dict[int, list[float]]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``{subject: {class: values}}`` as the three per-window arrays."""
    rows = [(k, subject, value) for subject, states in per_subject.items() for k, values in states.items() for value in values]
    classes, groups, values = zip(*rows)
    return np.array(classes), np.array(groups), np.array(values, dtype=np.float64)


def test_the_cut_lets_at_most_the_rate_of_alert_values_through():
    alert = np.arange(100, dtype=np.float64)  # 0 .. 99
    assert ft.cut_for_rate(alert, 0.05) == 94  # 95 .. 99 are above: exactly 5 %
    assert ft.cut_for_rate(alert, 0.10) == 89
    assert ft.cut_for_rate(alert, 0.0) == 99  # nothing may fire


def test_ties_never_push_the_false_alarms_over_the_rate():
    alert = np.array([0.0] * 97 + [0.5] * 3)  # 3 % are above 0
    cut = ft.cut_for_rate(alert, 0.05)
    assert cut == 0.0 and (alert > cut).mean() == pytest.approx(0.03)
    tied = np.array([0.0] * 90 + [0.5] * 10)  # 10 % share one value: a 5 % rate cannot split them
    cut = ft.cut_for_rate(tied, 0.05)
    assert cut == 0.5 and (tied > cut).mean() == 0.0


def test_no_alert_window_gives_no_cut():
    assert math.isnan(ft.cut_for_rate(np.array([]), 0.05))


def test_an_operating_point_reports_every_subject_and_the_held_out_view():
    low, high = [0.0] * 19 + [1.0], [1.0] * 10  # one alert window in twenty is high; every drowsy window is
    classes, groups, values = windows({s: {0: low, 2: high} for s in ("a", "b", "c", "d")})
    point = ft.operating_point(classes, groups, values, [["a"], ["b"], ["c"], ["d"]], 0.05)
    assert point["cut"] == 0.0
    assert point["all_subjects"] == {"alert": pytest.approx(0.05), "low_vigilance": None, "drowsy": 1.0}
    fold = point["out_of_fold"]
    assert fold["cut_range"] == [0.0, 0.0]
    assert fold["windows"]["alert"] == pytest.approx(0.05) and fold["windows"]["drowsy"] == 1.0
    assert fold["drowsy_per_subject"] == {"subjects": 4, "median": 1.0, "min": 1.0, "max": 1.0, "subjects_with_any": 4}
    assert fold["alert_per_subject"]["subjects_with_any"] == 4


def test_the_held_out_subject_does_not_set_its_own_cut():
    # "odd" is alert at a level the others never reach: with their cut, all its alert windows fire.
    classes, groups, values = windows({"a": {0: [0.1] * 20}, "b": {0: [0.1] * 20}, "odd": {0: [0.9] * 20}})
    point = ft.operating_point(classes, groups, values, [["a"], ["b"], ["odd"]], 0.05)
    assert point["out_of_fold"]["alert_per_subject"]["max"] == 1.0
    assert point["out_of_fold"]["windows"]["alert"] == pytest.approx(1 / 3)
    assert point["all_subjects"]["alert"] <= 0.05  # the cut from everyone hides it: this is why out of fold is reported


def test_a_fixed_threshold_counts_what_the_rule_would_fire_on():
    classes, groups, values = windows({"a": {0: [0.1, 0.2], 2: [0.3, 0.8]}, "b": {0: [0.0], 2: [0.1, 0.2]}})
    at = ft.fixed_threshold(classes, groups, values, 0.3, ">=")
    assert at["windows_firing"] == 2 and at["windows"]["alert"] == 0.0 and at["windows"]["drowsy"] == 0.5
    assert at["drowsy_per_subject"]["subjects_with_any"] == 1 and at["drowsy_per_subject"]["subjects"] == 2
    assert ft.fixed_threshold(classes, groups, values, 0.3, ">")["windows_firing"] == 1
    with pytest.raises(ValueError):
        ft.fixed_threshold(classes, groups, values, 0.3, "<")


def test_only_the_camera_rules_of_the_engine_are_read():
    rules = [
        {"id": "perclos-high", "signal": "biometrics.perclos", "operator": ">=", "threshold": 0.3, "status": "AMBER", "message": "x"},
        {"id": "sleep-under-6h", "signal": "selfReport.sleepHoursLast24h", "operator": "<", "threshold": 6, "status": "AMBER"},
    ]
    assert ft.engine_rules(rules) == {"biometrics.perclos": {"id": "perclos-high", "threshold": 0.3, "operator": ">=", "status": "AMBER"}}


def test_the_block_names_every_signal_and_rule():
    classes, groups, values = windows({s: {0: [0.0] * 20, 1: [0.2] * 5, 2: [0.5] * 10} for s in ("a", "b")})
    rules = {"biometrics.perclos": {"id": "perclos-high", "threshold": 0.3, "operator": ">=", "status": "AMBER"}}
    block = ft.report(classes, groups, {"perclos": values}, [["a"], ["b"]], rules, {"biometrics.perclos": ["perclos"]})
    assert [point["false_alarm_rate"] for point in block["signals"]["perclos"]] == list(ft.FALSE_ALARM_RATES)
    fired = block["engine_rules"]["perclos-high on perclos"]
    assert fired["windows"] == {"alert": 0.0, "low_vigilance": 0.0, "drowsy": 1.0}
