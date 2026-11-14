"""The fatigue features on synthetic series: every definition in fatigue_features.py, one at a time."""

import math

import numpy as np
import pytest

from pulsar_vision import fatigue_features as ff
from pulsar_vision.detector import YawnParams

NAN = float("nan")
FPS = 15.0
YAWN = YawnParams(variant="absolute", threshold=0.26, min_duration_s=1.0, release_factor=0.8, max_gap_s=0.25)


def window(seconds: float = 60.0, fps: float = FPS):
    """An alert, still face for ``seconds``: eyes open, mouth closed, level head."""
    n = int(round(seconds * fps))
    time_s = np.arange(n) / fps
    return {
        "time_s": time_s,
        "face": np.ones(n, dtype=bool),
        "closed": np.zeros(n),
        "pitch_deg": np.zeros(n),
        "mouth_open_ratio": np.full(n, 0.02),
    }


def features(w) -> dict:
    result = ff.window_features(w["time_s"], w["face"], w["closed"], w["pitch_deg"], w["mouth_open_ratio"], YAWN)
    assert result is not None
    return result


def close(w, start_frame: int, frames: int) -> None:
    w["closed"][start_frame : start_frame + frames] = 1.0


# --------------------------------------------------------------------------- names and order


def test_feature_names_are_the_model_order():
    assert ff.FEATURE_NAMES == (
        "perclos",
        "blink_rate_per_min",
        "mean_blink_duration_s",
        "long_closure_rate_per_min",
        "yawns_per_min",
        "head_pitch_std_deg",
        "nods_per_min",
    )
    assert list(features(window())) == list(ff.FEATURE_NAMES)


def test_a_still_alert_window_is_all_zero_and_has_no_blink_duration():
    f = features(window())
    assert f["perclos"] == 0.0
    assert f["blink_rate_per_min"] == 0.0
    assert math.isnan(f["mean_blink_duration_s"])  # no blink: missing, not 0
    assert f["long_closure_rate_per_min"] == 0.0
    assert f["yawns_per_min"] == 0.0
    assert f["head_pitch_std_deg"] == 0.0
    assert f["nods_per_min"] == 0.0


# --------------------------------------------------------------------------- EAR


def eye(width_px: float, opening_px: float, centre=(320.0, 240.0), image=(640.0, 480.0)) -> np.ndarray:
    """Six points p1..p6 of an eye ``width_px`` wide and ``opening_px`` tall, in normalised coordinates."""
    cx, cy = centre
    half, quarter, up = width_px / 2, width_px / 4, opening_px / 2
    pixels = np.array(
        [
            (cx - half, cy),  # p1 corner
            (cx - quarter, cy - up),  # p2 upper lid
            (cx + quarter, cy - up),  # p3 upper lid
            (cx + half, cy),  # p4 corner
            (cx + quarter, cy + up),  # p5 lower lid
            (cx - quarter, cy + up),  # p6 lower lid
        ]
    )
    return pixels / np.array(image)


def test_ear_is_opening_over_width_in_pixels():
    # |p2-p6| = |p3-p5| = 12 px, |p1-p4| = 40 px -> (12 + 12) / (2 * 40) = 0.3, although the image is not square
    assert ff.eye_aspect_ratio_from_points(eye(40, 12), 640, 480) == pytest.approx(0.3)
    assert ff.eye_aspect_ratio_from_points(eye(40, 0), 640, 480) == pytest.approx(0.0)


def test_ear_would_be_wrong_without_scaling_back_to_pixels():
    points = eye(40, 12)
    assert ff.eye_aspect_ratio_from_points(points, 1, 1) == pytest.approx(0.3 * (640 / 480))


def test_ear_is_the_mean_of_both_eyes_and_missing_stays_missing():
    assert ff.eye_aspect_ratio(eye(40, 12), eye(40, 4), 640, 480) == pytest.approx((0.3 + 0.1) / 2)
    missing = np.full((6, 2), NAN)
    assert math.isnan(float(ff.eye_aspect_ratio(eye(40, 12), missing, 640, 480)))
    degenerate = np.tile(np.array([[0.5, 0.5]]), (6, 1))
    assert math.isnan(float(ff.eye_aspect_ratio_from_points(degenerate, 640, 480)))


def test_ear_reads_the_documented_indices_of_the_full_mesh():
    mesh = np.zeros((478, 3))
    mesh[list(ff.EAR_RIGHT_EYE), :2] = eye(40, 12, centre=(250, 200))
    mesh[list(ff.EAR_LEFT_EYE), :2] = eye(40, 8, centre=(390, 200))
    assert ff.eye_aspect_ratio_of_mesh(mesh, 640, 480) == pytest.approx((0.3 + 0.2) / 2)
    assert ff.EAR_RIGHT_EYE == (33, 160, 158, 133, 153, 144)
    assert ff.EAR_LEFT_EYE == (362, 385, 387, 263, 373, 380)


def test_ear_indices_belong_to_the_mediapipe_eye_contours():
    connections = pytest.importorskip("mediapipe.tasks.python.vision").FaceLandmarksConnections
    right = {i for c in connections.FACE_LANDMARKS_RIGHT_EYE for i in (c.start, c.end)}
    left = {i for c in connections.FACE_LANDMARKS_LEFT_EYE for i in (c.start, c.end)}
    assert set(ff.EAR_RIGHT_EYE) <= right
    assert set(ff.EAR_LEFT_EYE) <= left


# --------------------------------------------------------------------------- eye closure


def test_percentile_interpolates_linearly_and_ignores_missing():
    assert ff.percentile([1, 2, 3, 4, 5], 50) == 3
    assert ff.percentile([1, 2, 3, 4], 50) == pytest.approx(2.5)
    assert ff.percentile([0, 10], 1) == pytest.approx(0.1)
    assert ff.percentile([4, NAN, 2], 100) == 4
    assert math.isnan(ff.percentile([NAN], 50))
    values = np.random.default_rng(0).normal(size=501)
    assert ff.percentile(values, 1) == pytest.approx(float(np.percentile(values, 1)))


def test_p80_threshold_is_a_fifth_of_the_way_up_from_the_floor():
    assert ff.p80_threshold(0.30, 0.10) == pytest.approx(0.14)
    calibration = ff.ear_calibration([0.30] * 97 + [0.10] * 3 + [NAN] * 10)
    assert calibration.frames == 100
    assert calibration.open == pytest.approx(0.30)
    assert calibration.floor == pytest.approx(0.10)
    assert calibration.threshold == pytest.approx(0.14)


def test_closed_series_keep_missing_frames_missing():
    blend = ff.closed_from_blendshape(np.array([0.1, 0.5, 0.51, NAN]))
    assert blend[:3].tolist() == [0.0, 0.0, 1.0]  # strictly above 0.5, as the browser
    assert math.isnan(blend[3])
    ear = ff.closed_from_ear(np.array([0.30, 0.14, 0.13, NAN]), 0.14)
    assert ear[:3].tolist() == [0.0, 1.0, 1.0]  # at or below the threshold
    assert math.isnan(ear[3])
    assert np.isnan(ff.closed_from_ear(np.array([0.3, 0.1]), NAN)).all()  # no calibration: nothing is known


# --------------------------------------------------------------------------- PERCLOS and closures


def test_perclos_is_the_share_of_frames_with_a_face_that_are_closed():
    w = window()
    close(w, 100, 90)  # 90 of 900 frames
    assert features(w)["perclos"] == pytest.approx(0.1)
    # Losing the face on 100 open frames changes the denominator, not the count: missing is not open.
    w["face"][400:500] = False
    w["closed"][400:500] = NAN
    assert features(w)["perclos"] == pytest.approx(90 / 800)


def test_blinks_are_counted_with_their_duration():
    w = window()
    for start in (30, 200, 400, 600):
        close(w, start, 3)  # 3 frames closed = 0.2 s
    f = features(w)
    assert f["blink_rate_per_min"] == pytest.approx(4.0)
    assert f["mean_blink_duration_s"] == pytest.approx(3 / FPS)
    assert f["long_closure_rate_per_min"] == 0.0
    assert ff.closure_durations(w["time_s"], w["closed"]) == pytest.approx([0.2] * 4)


def test_a_single_closed_frame_lasts_one_frame_period():
    w = window()
    close(w, 50, 1)
    assert ff.closure_durations(w["time_s"], w["closed"]) == pytest.approx([1 / FPS])


def test_closures_of_half_a_second_or_more_are_long_closures_not_blinks():
    w = window()
    close(w, 100, 7)  # 7 frames: 0.467 s -> still a blink
    close(w, 300, 8)  # 8 frames: 0.533 s -> long closure
    close(w, 500, 45)  # 3 s
    f = features(w)
    assert f["blink_rate_per_min"] == pytest.approx(1.0)
    assert f["mean_blink_duration_s"] == pytest.approx(7 / FPS)
    assert f["long_closure_rate_per_min"] == pytest.approx(2.0)


def test_a_short_face_loss_does_not_split_a_closure_but_a_long_one_does():
    w = window()
    close(w, 100, 10)
    w["closed"][104:106] = NAN  # 2 frames lost: the next closed frame is 0.2 s after the last one
    w["face"][104:106] = False
    assert len(ff.closure_durations(w["time_s"], w["closed"])) == 1
    close(w, 300, 12)
    w["closed"][304:308] = NAN  # 4 frames lost: 0.333 s > MAX_GAP_S
    w["face"][304:308] = False
    assert len(ff.closure_durations(w["time_s"], w["closed"])) == 3


def test_rates_are_per_observed_minute():
    w = window()
    for start in (30, 200, 400, 600):
        close(w, start, 3)
    w["face"][700:850] = False  # 150 of 900 frames without a face: 5/6 of the minute was observed
    w["closed"][700:850] = NAN
    assert features(w)["blink_rate_per_min"] == pytest.approx(4.0 / (750 / 900))


def test_durations_follow_the_real_frame_times():
    w = window(fps=12.0)  # a 12 fps phone video: each closed frame stands for 1/12 s
    close(w, 100, 3)
    assert ff.closure_durations(w["time_s"], w["closed"]) == pytest.approx([3 / 12.0])


# --------------------------------------------------------------------------- yawns


def test_yawns_use_the_calibrated_detector_on_the_window():
    w = window()
    w["mouth_open_ratio"][100:130] = 0.4  # 2 s wide open: a yawn
    w["mouth_open_ratio"][300:310] = 0.4  # 0.6 s: too short (talking)
    w["mouth_open_ratio"][500:520] = 0.25  # long but below the threshold
    assert features(w)["yawns_per_min"] == pytest.approx(1.0)


# --------------------------------------------------------------------------- head


def test_head_angles_match_the_browser_formulas():
    angle = math.radians(20.0)
    c, s = math.cos(angle), math.sin(angle)
    pitched = np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]], dtype=float)
    pitch, yaw, roll = ff.head_angles_deg(pitched)
    assert (float(pitch), float(yaw), float(roll)) == pytest.approx((20.0, 0.0, 0.0))
    # faceWorker.ts reads the column-major flat array: m[6], m[10], m[2], m[1], m[0]
    m = pitched.T.reshape(-1)
    assert math.degrees(math.atan2(m[6], m[10])) == pytest.approx(float(pitch))
    assert math.degrees(math.atan2(-m[2], math.hypot(m[6], m[10]))) == pytest.approx(float(yaw))
    assert math.degrees(math.atan2(m[1], m[0])) == pytest.approx(float(roll))
    rolled = np.array([[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=float)
    assert float(ff.head_angles_deg(rolled)[2]) == pytest.approx(20.0)
    assert np.isnan(ff.head_angles_deg(np.full((4, 4), NAN))[0])


def test_pitch_variability_is_the_population_standard_deviation():
    w = window()
    w["pitch_deg"][:450] = -2.0
    w["pitch_deg"][450:] = 2.0
    assert features(w)["head_pitch_std_deg"] == pytest.approx(2.0)
    w["pitch_deg"][0:90] = NAN  # missing frames are left out
    assert features({**w, "face": ~np.isnan(w["pitch_deg"])})["head_pitch_std_deg"] == pytest.approx(float(np.nanstd(w["pitch_deg"])))


def test_nods_are_drops_below_the_window_median():
    w = window()
    w["pitch_deg"][:] = 5.0  # the person's usual posture is not zero: the median takes it out
    w["pitch_deg"][100:115] = 5.0 + 12.0  # down 12 degrees for 1 s: a nod
    w["pitch_deg"][300:310] = 5.0 + 8.0  # down 8 degrees: not enough
    w["pitch_deg"][500:510] = 5.0 - 15.0  # head up: not a nod
    assert ff.nod_count(w["time_s"], w["pitch_deg"]) == 1
    assert features(w)["nods_per_min"] == pytest.approx(1.0)


def test_a_nod_ends_only_when_the_head_comes_back():
    w = window()
    w["pitch_deg"][100:110] = 12.0
    w["pitch_deg"][110:120] = 7.0  # still more than NOD_OFF_DEG below: the same nod
    w["pitch_deg"][120:130] = 12.0
    assert ff.nod_count(w["time_s"], w["pitch_deg"]) == 1
    w["pitch_deg"][110:120] = 2.0  # back up in between: two nods
    assert ff.nod_count(w["time_s"], w["pitch_deg"]) == 2


# --------------------------------------------------------------------------- windows


def test_windows_are_60_s_every_10_s_and_only_full_ones():
    assert ff.window_starts(0.0, 59.9) == []
    assert ff.window_starts(0.0, 60.0) == [0.0]
    assert ff.window_starts(2.0, 95.0) == [2.0, 12.0, 22.0, 32.0]
    time_s = np.arange(0, 100, 1 / FPS)
    frames = ff.window_slice(time_s, 10.0)
    assert time_s[frames][0] == pytest.approx(10.0)
    assert time_s[frames][-1] < 70.0
    assert len(time_s[frames]) == 900


def test_a_window_with_too_little_face_or_too_few_frames_gives_no_features():
    w = window()
    w["face"][:181] = False  # 181 of 900 without a face: under 80 %
    w["closed"][:181] = NAN
    assert ff.window_features(w["time_s"], w["face"], w["closed"], w["pitch_deg"], w["mouth_open_ratio"], YAWN) is None
    w = window()
    w["face"][:180] = False  # exactly 80 %: still used
    w["closed"][:180] = NAN
    assert features(w) is not None
    sparse = window(fps=7.0)  # 420 frames in the minute
    assert ff.window_features(sparse["time_s"], sparse["face"], sparse["closed"], sparse["pitch_deg"], sparse["mouth_open_ratio"], YAWN) is None
    assert ff.window_usable(450, 360) and not ff.window_usable(449, 449)


# --------------------------------------------------------------------------- calibration


def test_calibration_reference_is_the_mean_of_the_calibration_windows_ignoring_missing():
    rows = np.array(
        [
            [0.02, 10.0, 0.20, 0.0, 0.0, 1.0, 0.0],
            [0.04, 14.0, NAN, 0.0, 0.0, 3.0, 0.0],
        ]
    )
    reference = ff.calibration_reference(rows)
    assert reference == pytest.approx([0.03, 12.0, 0.20, 0.0, 0.0, 2.0, 0.0])
    assert np.isnan(ff.calibration_reference(np.empty((0, 7)))).all()
    assert math.isnan(ff.calibration_reference(np.array([[0.0, 0.0, NAN, 0, 0, 0, 0]]))[2])


def test_calibrated_features_are_differences():
    reference = np.array([0.03, 12.0, 0.20, 0.0, 0.0, 2.0, 0.0])
    now = np.array([0.13, 20.0, 0.35, 2.0, 1.0, 5.0, 3.0])
    assert ff.calibrate(now, reference) == pytest.approx([0.10, 8.0, 0.15, 2.0, 1.0, 3.0, 3.0])
    assert math.isnan(ff.calibrate(now, np.array([0.03, 12.0, NAN, 0, 0, 2, 0]))[2])


# --------------------------------------------------------------------------- model arithmetic and score


MODEL = {
    "mean": [0.1, 10.0],
    "std": [0.05, 5.0],
    "coef": [[-1.0, -0.5], [0.0, 0.0], [1.0, 0.5]],
    "intercept": [0.2, 0.0, -0.2],
}


def test_standardise_puts_a_missing_feature_at_the_training_mean():
    z = ff.standardise(np.array([0.2, NAN]), MODEL["mean"], MODEL["std"])
    assert z.tolist() == pytest.approx([2.0, 0.0])


def test_predict_proba_is_a_softmax_of_the_linear_scores():
    proba = ff.predict_proba(np.array([0.2, 15.0]), MODEL)[0]
    logits = np.array([0.2 - 2.0 - 0.5, 0.0, -0.2 + 2.0 + 0.5])
    expected = np.exp(logits) / np.exp(logits).sum()
    assert proba == pytest.approx(expected)
    assert proba.sum() == pytest.approx(1.0)
    at_the_mean = ff.predict_proba(np.array([[0.1, NAN]]), MODEL)[0]
    assert at_the_mean == pytest.approx(np.exp([0.2, 0.0, -0.2]) / np.exp([0.2, 0.0, -0.2]).sum())


def test_fatigue_score_is_the_expected_label_over_ten():
    assert ff.SCORE_WEIGHTS == (0.0, 0.5, 1.0)
    assert ff.fatigue_score(np.array([1.0, 0.0, 0.0])) == 0.0
    assert ff.fatigue_score(np.array([0.0, 1.0, 0.0])) == 0.5
    assert ff.fatigue_score(np.array([0.0, 0.0, 1.0])) == 1.0
    assert ff.fatigue_score(np.array([0.2, 0.5, 0.3])) == pytest.approx(0.5 * 0.5 + 0.3)
    scores = ff.fatigue_score(np.random.default_rng(1).dirichlet([1, 1, 1], size=200))
    assert scores.min() >= 0.0 and scores.max() <= 1.0


# --------------------------------------------------------------------------- the browser's current formula


def test_browser_baseline_reproduces_the_worker_formula():
    still = [0.5] * 90
    assert ff.browser_baseline_score(0.0, 0, still) == 0.0
    assert ff.browser_baseline_score(0.5, 0, still) == pytest.approx(0.30)
    assert ff.browser_baseline_score(0.0, 2, still) == pytest.approx(0.125)
    assert ff.browser_baseline_score(0.0, 9, still) == pytest.approx(0.25)  # 4 yawns a minute saturate
    moving = [0.4, 0.6] * 45  # std 0.1 -> instability min(1, 1.2) = 1
    assert ff.browser_baseline_score(0.0, 0, moving) == pytest.approx(0.15)
    assert ff.browser_baseline_score(1.0, 4, moving) == 1.0
    assert ff.browser_baseline_score(NAN, 0, []) == 0.0


def test_no_eye_state_means_no_features_not_zeros():
    # ear_p80 before its calibration exists: the closed series is all missing. A score must not come out of that.
    w = window()
    w["closed"] = ff.closed_from_ear(np.full(len(w["time_s"]), 0.3), NAN)
    assert ff.window_features(w["time_s"], w["face"], w["closed"], w["pitch_deg"], w["mouth_open_ratio"], YAWN) is None
