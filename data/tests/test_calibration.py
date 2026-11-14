"""Scores, tie-breaking and video-level metrics of the calibration."""

import numpy as np
import pytest

from pulsar_vision import calibration
from pulsar_vision.detector import ABSOLUTE, RELATIVE


def test_default_grid_is_what_the_report_says():
    grid = calibration.DEFAULT_GRID
    assert grid.thresholds[0] == 0.10 and grid.thresholds[-1] == 0.70 and len(grid.thresholds) == 31
    assert grid.min_durations_s[0] == 0.4 and grid.min_durations_s[-1] == 4.0 and len(grid.min_durations_s) == 19
    assert len(calibration.candidates(grid, ABSOLUTE)) == 31 * 19 * 2
    assert len(calibration.candidates(grid, RELATIVE)) == 31 * 19 * 2 * 3
    assert all(c.baseline_window_s is None for c in calibration.candidates(grid, ABSOLUTE))
    assert all(c.max_gap_s == calibration.MAX_GAP_S for c in calibration.candidates(grid, RELATIVE))


def test_wilson_interval():
    assert calibration.wilson_interval(0, 0) is None
    low, high = calibration.wilson_interval(0, 10)
    assert low == 0.0 and high == pytest.approx(0.2775, abs=1e-3)
    low, high = calibration.wilson_interval(5, 10)
    assert (low, high) == pytest.approx((0.2366, 0.7634), abs=1e-3)
    low, high = calibration.wilson_interval(10, 10)
    assert low == pytest.approx(0.7225, abs=1e-3) and high == pytest.approx(1.0)


def test_proportion_of_nothing_has_no_rate():
    assert calibration.proportion(0, 0) == {"count": 0, "of": 0, "rate": None, "ci95_wilson": None}
    assert calibration.proportion(3, 4)["rate"] == 0.75


def test_candidate_scores_use_only_the_selected_videos():
    conditions = np.array(["yawning", "yawning", "talking", "talking", "normal", "normal"])
    counts = np.array(
        [
            [1, 2, 0, 0, 0, 0],  # perfect
            [1, 0, 1, 0, 0, 0],  # half the yawns, half the talking videos flagged
            [3, 3, 4, 1, 1, 1],  # fires everywhere
        ]
    )
    everything = np.ones(6, dtype=bool)
    assert calibration.candidate_scores(counts, conditions, everything).tolist() == pytest.approx([1.0, 0.25, 0.0])
    # Only the first video of each condition: the second candidate now flags every talking video.
    subset = np.array([True, False, True, False, True, False])
    assert calibration.candidate_scores(counts, conditions, subset).tolist() == pytest.approx([1.0, 0.5, 0.0])


def test_score_needs_the_three_conditions():
    conditions = np.array(["yawning", "talking"])
    with pytest.raises(ValueError):
        calibration.candidate_scores(np.array([[1, 0]]), conditions, np.ones(2, dtype=bool))


def test_tie_goes_to_the_centre_of_the_tied_region():
    grid = calibration.Grid(
        thresholds=(0.1, 0.2, 0.3, 0.4, 0.5),
        min_durations_s=(0.5, 1.0, 1.5),
        release_factors=(1.0,),
        baseline_windows_s=(),
        max_gap_s=0.25,
    )
    params = calibration.candidates(grid, ABSOLUTE)
    scores = np.array([0.9 if 0.2 <= p.threshold <= 0.4 else 0.1 for p in params])
    best = params[calibration.select_candidate(scores, params, grid)]
    assert (best.threshold, best.min_duration_s) == (0.3, 1.0)

    # A single winner is taken as it is.
    scores[0] = 1.0
    assert calibration.select_candidate(scores, params, grid) == 0


def test_video_metrics():
    conditions = np.array(["yawning"] * 4 + ["talking"] * 2 + ["normal"] * 2)
    yawns = np.array([1, 2, 0, 1, 3, 0, 0, 0])
    minutes = np.array([0.5] * 4 + [1.0, 0.5] + [0.25, 0.25])
    metrics = calibration.video_metrics(yawns, conditions, minutes)
    assert metrics["videos"] == {"yawning": 4, "talking": 2, "normal": 2}
    assert (metrics["yawning_recall"]["count"], metrics["yawning_recall"]["of"]) == (3, 4)
    assert (metrics["talking_false_alarm"]["count"], metrics["talking_false_alarm"]["of"]) == (1, 2)
    assert (metrics["normal_false_alarm"]["count"], metrics["normal_false_alarm"]["of"]) == (0, 2)
    assert metrics["yawns_per_minute"] == {"yawning": 2.0, "talking": 2.0, "normal": 0.0}
    assert metrics["score"] == pytest.approx(0.75 - 0.5 * (0.5 + 0.0))
    assert metrics["yawns_per_yawning_video"] == {"mean": 1.0, "median": 1.0, "max": 2}


def test_video_metrics_without_a_condition_have_no_score():
    metrics = calibration.video_metrics(np.array([1]), np.array(["yawning"]), np.array([0.5]))
    assert metrics["score"] is None
    assert metrics["talking_false_alarm"]["rate"] is None
