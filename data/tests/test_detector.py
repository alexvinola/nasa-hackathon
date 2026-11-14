"""The yawn detector on synthetic series."""

import math

import numpy as np
import pytest

from pulsar_vision import calibration
from pulsar_vision.detector import (
    ABSOLUTE,
    RELATIVE,
    YawnParams,
    baseline_ratio,
    detect_yawns,
    open_episodes,
    thresholds,
)

FPS = 15.0
NAN = float("nan")


def series(*segments: tuple[float, int]) -> tuple[list[float], list[float]]:
    """Build a 15 fps series from (value, number of frames) segments."""
    values = [value for value, frames in segments for _ in range(frames)]
    times = [i / FPS for i in range(len(values))]
    return times, values


def params(**overrides) -> YawnParams:
    base = dict(variant=ABSOLUTE, threshold=0.3, min_duration_s=1.0, release_factor=1.0, max_gap_s=0.25)
    base.update(overrides)
    return YawnParams(**base)


def test_closed_mouth_has_no_yawn():
    times, ratio = series((0.02, 150))
    assert detect_yawns(times, ratio, params()) == []


def test_one_long_opening_is_one_yawn():
    times, ratio = series((0.02, 30), (0.5, 45), (0.02, 30))
    yawns = detect_yawns(times, ratio, params())
    assert len(yawns) == 1
    assert yawns[0].start_s == pytest.approx(30 / FPS)
    assert yawns[0].end_s == pytest.approx(74 / FPS)
    assert yawns[0].duration_s == pytest.approx(44 / FPS)
    assert yawns[0].peak == 0.5
    assert yawns[0].frames == 45


def test_talking_bursts_are_too_short():
    # Mouth above the threshold for 0.4 s, four times: talking, not yawning.
    times, ratio = series(*[(0.02, 10), (0.45, 7)] * 4, (0.02, 10))
    assert detect_yawns(times, ratio, params()) == []
    assert len(open_episodes(times, ratio, 0.3, 0.3, 0.25)) == 4


def test_minimum_duration_boundary():
    # 16 frames at 15 fps span exactly 1.0 s between first and last; 15 frames span 0.933 s.
    times, ratio = series((0.0, 5), (0.5, 16), (0.0, 5))
    assert len(detect_yawns(times, ratio, params(min_duration_s=1.0))) == 1
    times, ratio = series((0.0, 5), (0.5, 15), (0.0, 5))
    assert detect_yawns(times, ratio, params(min_duration_s=1.0)) == []


def test_threshold_is_inclusive():
    times, ratio = series((0.0, 5), (0.3, 20), (0.0, 5))
    assert len(detect_yawns(times, ratio, params(threshold=0.3))) == 1
    assert detect_yawns(times, ratio, params(threshold=0.31)) == []


def test_two_separate_yawns_are_counted_twice():
    times, ratio = series((0.02, 15), (0.6, 30), (0.02, 45), (0.6, 30), (0.02, 15))
    assert len(detect_yawns(times, ratio, params())) == 2


def test_yawn_still_open_at_the_end_is_counted():
    times, ratio = series((0.02, 15), (0.6, 30))
    assert len(detect_yawns(times, ratio, params())) == 1


def test_hysteresis_keeps_one_yawn_through_a_dip():
    # The ratio dips to 0.27 for two frames in the middle: below on (0.30), above off (0.24).
    times, ratio = series((0.02, 10), (0.5, 12), (0.27, 2), (0.5, 12), (0.02, 10))
    with_hysteresis = detect_yawns(times, ratio, params(release_factor=0.8))
    assert len(with_hysteresis) == 1
    assert with_hysteresis[0].frames == 26
    # Without hysteresis the dip splits it into two stretches of 0.73 s: no yawn.
    assert detect_yawns(times, ratio, params(release_factor=1.0)) == []


def test_hysteresis_does_not_open_below_the_on_threshold():
    times, ratio = series((0.02, 10), (0.27, 40), (0.02, 10))
    assert detect_yawns(times, ratio, params(release_factor=0.8)) == []


def test_short_gap_of_missing_frames_is_bridged():
    # Two frames without a face in the middle of a yawn (0.2 s between confirming frames).
    times, ratio = series((0.02, 10), (0.5, 12), (NAN, 2), (0.5, 12), (0.02, 10))
    yawns = detect_yawns(times, ratio, params())
    assert len(yawns) == 1
    assert yawns[0].frames == 24
    assert yawns[0].duration_s == pytest.approx(25 / FPS)


def test_long_gap_closes_the_episode_at_the_last_confirming_frame():
    # Four missing frames: 0.333 s between confirming frames, more than max_gap_s = 0.25.
    times, ratio = series((0.02, 10), (0.5, 12), (NAN, 4), (0.5, 12), (0.02, 10))
    episodes = open_episodes(times, ratio, 0.3, 0.3, 0.25)
    assert len(episodes) == 2
    assert episodes[0].end_s == pytest.approx(21 / FPS)
    assert episodes[1].start_s == pytest.approx(26 / FPS)
    assert detect_yawns(times, ratio, params()) == []  # two stretches of 0.73 s each


def test_gap_boundary_at_15_fps():
    for missing, expected_episodes in ((2, 1), (3, 2)):
        times, ratio = series((0.5, 5), (NAN, missing), (0.5, 5))
        assert len(open_episodes(times, ratio, 0.3, 0.3, 0.25)) == expected_episodes


def test_missing_is_not_zero():
    with_missing = series((0.02, 10), (0.5, 12), (NAN, 2), (0.5, 12), (0.02, 10))
    with_zero = series((0.02, 10), (0.5, 12), (0.0, 2), (0.5, 12), (0.02, 10))
    assert len(detect_yawns(*with_missing, params())) == 1
    assert len(detect_yawns(*with_zero, params())) == 0


def test_missing_frames_never_open_the_mouth():
    times, ratio = series((NAN, 100))
    assert open_episodes(times, ratio, 0.3, 0.3, 0.25) == []
    assert detect_yawns(times, ratio, params()) == []


def test_face_lost_while_open_closes_after_max_gap():
    times, ratio = series((0.5, 20), (NAN, 60))
    episodes = open_episodes(times, ratio, 0.3, 0.3, 0.25)
    assert len(episodes) == 1
    assert episodes[0].end_s == pytest.approx(19 / FPS)  # not extended over the frames without a face


def test_empty_series():
    assert detect_yawns([], [], params()) == []


def test_accepts_numpy_arrays():
    times, ratio = series((0.02, 30), (0.5, 45), (0.02, 30))
    assert len(detect_yawns(np.array(times), np.array(ratio), params())) == 1


def test_baseline_is_the_median_of_the_first_seconds_with_a_face():
    # Two frames with no face first: the window starts at the first valid frame.
    times, ratio = series((NAN, 2), (0.10, 8), (0.20, 7), (0.9, 30))
    assert baseline_ratio(times, ratio, 1.0) == pytest.approx(0.10)  # 15 frames: 8 x 0.10, 7 x 0.20
    assert baseline_ratio(times, ratio, 2.0) == pytest.approx(0.55)  # 30 frames: middle values 0.20 and 0.9
    times, ratio = series((0.10, 1), (0.30, 1), (0.9, 30))
    assert baseline_ratio(times, ratio, 2 / FPS) == pytest.approx(0.20)  # even count: mean of the two middle values


def test_baseline_of_a_series_without_a_face_is_missing():
    times, ratio = series((NAN, 50))
    assert math.isnan(baseline_ratio(times, ratio, 2.0))
    relative = params(variant=RELATIVE, baseline_window_s=2.0)
    assert detect_yawns(times, ratio, relative) == []


def test_relative_threshold_sits_on_top_of_the_baseline():
    relative = params(variant=RELATIVE, threshold=0.3, release_factor=0.8, baseline_window_s=2.0)
    assert thresholds(relative, baseline=0.1) == pytest.approx((0.4, 0.34))
    assert thresholds(params(release_factor=0.8), baseline=0.1) == pytest.approx((0.3, 0.24))  # absolute ignores it

    # Resting mouth slightly open (0.15). An opening to 0.40 passes the absolute 0.3 but not baseline + 0.3.
    times, ratio = series((0.15, 45), (0.40, 30), (0.15, 15))
    assert len(detect_yawns(times, ratio, params())) == 1
    assert detect_yawns(times, ratio, relative) == []
    times, ratio = series((0.15, 45), (0.50, 30), (0.15, 15))
    assert len(detect_yawns(times, ratio, relative)) == 1


def test_relative_variant_misses_a_yawn_inside_the_baseline_window():
    # The video starts with the mouth already wide open: the baseline is the yawn itself.
    times, ratio = series((0.6, 45), (0.02, 30))
    assert len(detect_yawns(times, ratio, params())) == 1
    assert detect_yawns(times, ratio, params(variant=RELATIVE, baseline_window_s=2.0)) == []


def test_invalid_parameters_are_rejected():
    with pytest.raises(ValueError):
        params(variant="adaptive")
    with pytest.raises(ValueError):
        params(variant=RELATIVE)  # no baseline window
    with pytest.raises(ValueError):
        params(release_factor=1.2)
    with pytest.raises(ValueError):
        open_episodes([0.0], [0.5, 0.5], 0.3, 0.3, 0.25)
    with pytest.raises(ValueError):
        open_episodes([0.0], [0.5], 0.3, 0.4, 0.25)


@pytest.mark.parametrize("variant", [ABSOLUTE, RELATIVE])
def test_grid_counts_match_the_detector(variant):
    """The fast grid count used by the calibration is the detector, candidate by candidate."""
    rng = np.random.default_rng(11)
    n = 600
    times = np.arange(n) / 14.985
    # Wide openings every few seconds, jitter on top, and frames without a face.
    wave = np.sin(times * 0.9)
    ratio = 0.05 + 0.5 * np.where(wave > 0.6, wave, 0.0) + rng.normal(0, 0.03, n)
    ratio = np.clip(ratio, 0, None)
    ratio[rng.random(n) < 0.04] = np.nan
    ratio[200:206] = np.nan
    grid = calibration.Grid(
        thresholds=(0.1, 0.2, 0.3, 0.4, 0.6),
        min_durations_s=(0.2, 0.6, 1.0, 2.0),
        release_factors=(1.0, 0.8),
        baseline_windows_s=(1.0, 3.0),
        max_gap_s=0.25,
    )
    counts = calibration.count_yawns_grid(times, ratio, grid, variant)
    candidates = calibration.candidates(grid, variant)
    assert len(counts) == len(candidates)
    expected = [len(detect_yawns(times, ratio, candidate)) for candidate in candidates]
    assert counts.tolist() == expected
    assert max(expected) > 0 and min(expected) == 0  # the series exercises both outcomes
