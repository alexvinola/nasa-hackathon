"""Reaction times per window, and correlations that are missing rather than made up."""

import numpy as np
import pandas as pd
import pytest

from pulsar_vision import fatigue_validation as fv

NAN = float("nan")


def test_window_pvt_averages_the_stimuli_shown_during_the_window():
    stimulus_s = np.array([5.0, 20.0, 65.0, 70.0, 130.0])
    rt_ms = np.array([300.0, 500.0, 200.0, 400.0, 900.0])
    start = np.array([0.0, 10.0, 60.0, 70.0, 200.0])
    mean, count = fv.window_pvt(stimulus_s, rt_ms, start, start + 60.0)
    assert count.tolist() == [2, 2, 2, 1, 0]  # 70 s ends the second window and starts the fourth; 130 s ends the fourth
    assert mean[:4] == pytest.approx([400.0, 350.0, 300.0, 400.0])
    assert np.isnan(mean[4])  # no stimulus: missing, not 0


def test_window_pvt_uses_the_same_half_open_interval_as_the_frames():
    # A window holds the frames with start <= t < start + 60 s; a stimulus at exactly start + 60 s is in the next one.
    mean, count = fv.window_pvt(np.array([0.0, 60.0]), np.array([100.0, 900.0]), np.array([0.0, 10.0]), np.array([60.0, 70.0]))
    assert count.tolist() == [1, 1] and mean.tolist() == [100.0, 900.0]


def test_window_pvt_does_not_need_sorted_stimuli():
    mean, count = fv.window_pvt(np.array([50.0, 10.0]), np.array([100.0, 300.0]), np.array([0.0]), np.array([20.0]))
    assert count.tolist() == [1] and mean.tolist() == [300.0]


def test_correlation():
    a = np.array([1.0, 2.0, 3.0, 4.0])
    assert fv.correlation(a, 2 * a + 1) == {"r": pytest.approx(1.0), "spearman": pytest.approx(1.0), "n": 4}
    assert fv.correlation(a, -a)["r"] == pytest.approx(-1.0)
    monotone = fv.correlation(a, a**3)
    assert monotone["spearman"] == pytest.approx(1.0) and monotone["r"] < 1.0


def test_correlation_skips_missing_pairs():
    result = fv.correlation([1.0, 2.0, NAN, 4.0, 5.0], [2.0, 4.0, 9.0, NAN, 10.0])
    assert result["n"] == 3 and result["r"] == pytest.approx(1.0)


@pytest.mark.parametrize(
    "a, b",
    [
        ([1.0, 2.0], [1.0, 2.0]),  # two points always correlate perfectly: not reported
        ([1.0, 1.0, 1.0, 1.0], [1.0, 2.0, 3.0, 4.0]),  # a constant signal
        ([1.0, 2.0, 3.0, 4.0], [7.0, 7.0, 7.0, 7.0]),  # a constant target (KSS within one test)
        ([], []),
    ],
)
def test_correlation_is_missing_when_it_cannot_be_measured(a, b):
    result = fv.correlation(a, b)
    assert result["r"] is None and result["spearman"] is None and result["n"] == len(a)


def windows() -> pd.DataFrame:
    """Two made-up people with two recordings each. In "a" the signal follows reaction time; in "b" it goes against it."""
    rows = []
    for subject, sign in (("a", 1.0), ("b", -1.0)):
        for recording, kss, level in ((1, 3.0, 300.0), (2, 8.0, 400.0)):
            for k in range(5):
                rt = level + 10.0 * k
                rows.append(
                    {
                        "subject": subject,
                        "recording": f"{subject}-{recording}",
                        "signal": sign * rt,
                        "flat": 0.0,
                        fv.PVT_MEAN_RT: rt,
                        fv.RECORDING_MEAN_RT: level + 20.0,
                        fv.KSS: kss,
                    }
                )
    return pd.DataFrame(rows)


def test_validation_is_reported_per_subject():
    report = fv.validate(windows(), ("signal", "flat"))
    assert (report["subjects"], report["recordings"], report["windows"]) == (2, 4, 20)
    a, b = report["per_subject"]["a"], report["per_subject"]["b"]
    assert (a["recordings"], a["windows"]) == (2, 10)
    assert a["signal"][fv.PVT_MEAN_RT]["r"] == pytest.approx(1.0)
    assert b["signal"][fv.PVT_MEAN_RT]["r"] == pytest.approx(-1.0)
    assert a["signal"][fv.KSS]["r"] > 0.9 and b["signal"][fv.KSS]["r"] < -0.9
    assert a["flat"][fv.PVT_MEAN_RT] == {"r": None, "spearman": None, "n": 10}


def test_the_within_subject_summary_does_not_hide_the_people_who_disagree():
    report = fv.validate(windows(), ("signal", "flat"))
    within = report["within_subject"]["signal"][fv.PVT_MEAN_RT]["r"]
    assert within == {"subjects": 2, "positive": 1, "median": pytest.approx(0.0), "min": pytest.approx(-1.0), "max": pytest.approx(1.0)}
    assert report["within_subject"]["signal"][fv.PVT_MEAN_RT]["spearman"]["positive"] == 1
    flat = report["within_subject"]["flat"][fv.PVT_MEAN_RT]["r"]
    assert flat["subjects"] == 0 and flat["median"] is None
    assert report["pooled_windows"]["signal"][fv.PVT_MEAN_RT]["n"] == 20
    assert abs(report["pooled_windows"]["signal"][fv.PVT_MEAN_RT]["r"]) < 0.1  # the two people cancel out


def test_per_recording_is_one_point_per_recording_against_its_whole_test_mean():
    report = fv.validate(windows(), ("signal",))
    per_recording = report["per_recording"]["signal"]
    assert per_recording[fv.PVT_MEAN_RT]["n"] == 4 and per_recording[fv.KSS]["n"] == 4
    table = fv.recording_table(windows(), ("signal",))
    assert table.loc["a-1", fv.PVT_MEAN_RT] == 320.0  # the recording's own mean, not the windows' mean
    assert table.loc["a-1", "signal"] == pytest.approx(320.0)


def test_a_recording_without_kss_is_left_out_of_the_kss_figures_only():
    data = windows()
    data.loc[data["recording"] == "a-1", fv.KSS] = NAN
    report = fv.validate(data, ("signal",))
    assert report["per_recording"]["signal"][fv.KSS]["n"] == 3
    assert report["per_recording"]["signal"][fv.PVT_MEAN_RT]["n"] == 4
