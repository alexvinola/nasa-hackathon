"""The whole `make model` run on a synthetic cache: no video, no MediaPipe, a few seconds.

Four invented people, three recordings each, written straight into a face-series cache. The run must
produce what `acceptance/check_model.py` asks for, keep train and test subjects apart, and write the
same bytes when it runs again.
"""

import json

import numpy as np
import pytest

from pulsar_vision import face_series, fatigue_features as ff, fatigue_pipeline, landmarks, mouth, rldd

FPS = 15.0
SECONDS = 240
LANDMARKER_BYTES = b"not a real model: only its hash is read when everything comes from the cache"


def synthetic_series(subject: int, state: int, rng: np.random.Generator, blendshapes_see_it: bool = True) -> face_series.FaceSeries:
    """A face that blinks more often and for longer the drowsier the state; each person has their own eye size.

    With ``blendshapes_see_it=False`` only the eye landmarks (EAR) show the closures: the eyeBlink blendshapes
    stay open and the head moves the same in every state, so the blendshape features carry nothing.
    """
    n = int(SECONDS * FPS)
    column = face_series.LANDMARK_COLUMN
    width, height = 640, 480
    xyz = np.zeros((n, len(face_series.CACHED_LANDMARKS), 3), dtype=np.float32)
    open_px = 10.0 + subject  # eye opening in pixels
    closed = np.zeros(n, dtype=bool)
    every = int((6 - 2 * state) * FPS)
    length = 2 + 2 * state  # 2, 4, 6 frames: blinks get longer with the state (0.13, 0.27, 0.40 s)
    for start in range(int(rng.integers(5, 40)), n - length, every):
        closed[start : start + length] = True
    opening = np.where(closed, 1.0, open_px)

    def place(indices, centre_x):
        cx, cy, half, quarter = centre_x, 200.0, 20.0, 10.0
        xs = np.array([cx - half, cx - quarter, cx + quarter, cx + half, cx + quarter, cx - quarter])
        signs = np.array([0.0, -0.5, -0.5, 0.0, 0.5, 0.5])
        for i, index in enumerate(indices):
            xyz[:, column[index], 0] = xs[i] / width
            xyz[:, column[index], 1] = (cy + signs[i] * opening) / height

    place(ff.EAR_RIGHT_EYE, 250.0)
    place(ff.EAR_LEFT_EYE, 390.0)
    xyz[:, column[mouth.UPPER_INNER_LIP]] = (0.5, 0.60, 0.0)
    xyz[:, column[mouth.LOWER_INNER_LIP]] = (0.5, 0.61, 0.0)
    xyz[:, column[face_series.NOSE_TIP], 1] = 0.5 + rng.normal(0, 0.002, n)
    names = ["_neutral", ff.EYE_BLINK_LEFT, ff.EYE_BLINK_RIGHT, "jawOpen"]
    blend = np.zeros((n, len(names)), dtype=np.float32)
    blend[:, 1] = blend[:, 2] = np.where(closed, 0.85, 0.1) if blendshapes_see_it else 0.1
    pitch = np.radians(rng.normal(0, 1.0 + (state if blendshapes_see_it else 0), n))
    matrix = np.tile(np.eye(4, dtype=np.float32), (n, 1, 1))
    matrix[:, 1, 1] = matrix[:, 2, 2] = np.cos(pitch)
    matrix[:, 2, 1] = np.sin(pitch)
    matrix[:, 1, 2] = -np.sin(pitch)
    lost = rng.choice(n, size=20, replace=False)  # a few frames without a face
    xyz[lost] = np.nan
    blend[lost] = np.nan
    matrix[lost] = np.nan
    meta = {
        **face_series.cache_signature(landmarks.sha256_of(LANDMARKER_BYTES), 1000 + subject),
        "width": width,
        "height": height,
        "source_fps": 30.0,
        "orientation_meta_deg": 0.0,
        "orientation_auto": True,
        "timestamp_fallbacks": 0,
        "processed_frames": n,
        "blendshape_names": names,
        "mediapipe_seconds": 0.01 * n,
        "total_seconds": 0.02 * n,
    }
    return face_series.FaceSeries(np.arange(n, dtype=np.int32) * 2, np.arange(n) / FPS, xyz, blend, matrix, meta)


def run_pipeline(root, blendshapes_see_it: bool = True) -> dict:
    cache = root / "cache"
    rng = np.random.default_rng(7)
    names = []
    for subject in range(1, 5):
        for state, label in enumerate((0, 5, 10)):
            face_series.save_series(synthetic_series(subject, state, rng, blendshapes_see_it), cache / f"{subject:02d}_{label}.npz")
            names.append(f"Fold1_part1/{subject:02d}/{label}.mp4")
    (cache / rldd.INDEX_FILE).write_text(json.dumps({"videos": names}), encoding="utf-8")
    landmarker = root / "face_landmarker.task"
    landmarker.write_bytes(LANDMARKER_BYTES)
    out = root / "out"
    argv = ["--root", str(root / "no-raw-videos-here"), "--cache", str(cache), "--landmarker", str(landmarker), "--out", str(out), "--bootstrap", "40"]
    assert fatigue_pipeline.main(argv) == 0
    return {"out": out, "argv": argv}


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    return run_pipeline(tmp_path_factory.mktemp("fatigue"))


def load(run, name):
    return json.loads((run["out"] / name).read_text(encoding="utf-8"))


def test_metrics_have_what_the_goal_asks_for(run):
    metrics = load(run, "metrics.json")
    assert 0 <= metrics["macro_f1"] <= 1 and 0.5 < metrics["auc"] <= 1
    assert metrics["labels"] == ["alert", "low_vigilance", "drowsy"]
    matrix = metrics["confusion_matrix"]
    assert len(matrix) == 3 and all(len(row) == 3 and all(isinstance(c, int) for c in row) for row in matrix)
    assert sum(map(sum, matrix)) == metrics["dataset"]["windows"]["evaluated"] > 0
    assert metrics["pvt_correlation"] is None
    assert set(metrics["configurations"]) == {"blendshape/absolute", "blendshape/calibrated", "ear_p80/absolute", "ear_p80/calibrated"}
    assert metrics["chosen"]["configuration"] == "blendshape/absolute" and metrics["chosen"]["selected_on_test_folds"] is False
    shipped = metrics["configurations"]["blendshape/absolute"]
    assert (metrics["auc"], metrics["macro_f1"], metrics["confusion_matrix"]) == (shipped["auc"], shipped["macro_f1"], shipped["confusion_matrix"])
    assert set(metrics["feature_evidence"]) == set(ff.FEATURE_NAMES)
    assert metrics["baseline"]["score"]["auc_alert_vs_drowsy"] is not None
    assert metrics["video_level"]["model"]["videos"] == 12
    assert len(metrics["per_subject"]) == 4 and len(metrics["videos"]) == 12


def test_no_subject_is_in_both_train_and_test(run):
    folds = load(run, "metrics.json")["folds"]
    assert len(folds) == 4
    tested = []
    for fold in folds:
        assert fold["train_subjects"] and fold["test_subjects"]
        assert not set(fold["train_subjects"]) & set(fold["test_subjects"])
        tested += fold["test_subjects"]
    assert sorted(tested) == ["01", "02", "03", "04"]


def test_the_calibration_minutes_are_never_scored(run):
    windows = load(run, "metrics.json")["dataset"]["windows"]["by_state"]
    # 240 s -> 19 windows per video; in the alert video the 12 that touch the first 120 s are calibration.
    assert windows["alert"]["windows"] == 4 * 19 and windows["alert"]["calibration_period"] == 4 * 12
    assert windows["alert"]["evaluated"] == 4 * 7
    assert windows["drowsy"]["evaluated"] == 4 * 19 and windows["drowsy"]["calibration_period"] == 0


def test_the_model_file_is_what_the_browser_needs(run):
    model = load(run, "fatigue_model.json")
    n = len(model["features"])
    assert model["features"] == list(ff.FEATURE_NAMES)
    assert len(model["mean"]) == n and len(model["std"]) == n and all(s > 0 for s in model["std"])
    assert len(model["coef"]) == 3 and all(len(row) == n for row in model["coef"]) and len(model["intercept"]) == 3
    assert model["classes"] == ["alert", "low_vigilance", "drowsy"]
    assert model["trainedOn"].startswith("UTA-RLDD")
    assert model["score"]["formula"] == ff.SCORE_FORMULA
    assert model["score"]["weights"] == {"alert": 0.0, "low_vigilance": 0.5, "drowsy": 1.0}
    assert model["features_version"] == ff.FEATURES_VERSION
    # What ships needs neither EAR nor a calibration; both are documented as evaluated alternatives only.
    assert model["eye_closure"] == {"method": "blendshape", "rule": "closed when (eyeBlinkLeft + eyeBlinkRight) / 2 > 0.5", "needs_calibration": False, "same_as": "faceWorker.ts (BLINK = 0.5)"}
    assert model["normalisation"]["variant"] == "absolute" and model["normalisation"]["needs_calibration"] is False
    assert model["calibration"]["required"] is False and "No calibration step" in model["inference"]
    assert model["configuration"]["shipped"] == "blendshape/absolute" and model["configuration"]["selected_on_test_folds"] is False
    assert model["evaluated_alternatives"]["eye_closure"]["method"] == "ear_p80"
    assert not {"p80_fraction", "ear_open_percentile", "ear_floor_percentile"} & set(model["constants"])
    # The file alone is enough to score a window.
    proba = ff.predict_proba(np.array(model["mean"]), model)[0]
    assert proba.sum() == pytest.approx(1.0)
    assert 0.0 <= float(ff.fatigue_score(proba)) <= 1.0


def test_the_synthetic_states_are_told_apart_and_the_report_says_so(run):
    metrics = load(run, "metrics.json")
    assert metrics["auc"] > 0.9  # the invented states differ on purpose: a broken pipeline would not see it
    report = (run["out"] / "fatigue_report.md").read_text(encoding="utf-8")
    assert f"{metrics['auc']:.3f}" in report and f"{metrics['macro_f1']:.3f}" in report
    for heading in ("## What can be said", "## The decision", "## Against what the browser ships today", "## Secondary analyses: the evidence behind the decision", "## Limits", "## Every video"):
        assert heading in report
    assert "Eye closure and blink duration predict drowsiness on 4 people the model never saw." in report


def test_running_again_writes_the_same_bytes(run):
    before = {name: (run["out"] / name).read_bytes() for name in ("metrics.json", "fatigue_model.json", "fatigue_report.md")}
    assert fatigue_pipeline.main(run["argv"]) == 0
    for name, content in before.items():
        assert (run["out"] / name).read_bytes() == content


def test_a_missing_dataset_is_an_error_not_an_empty_model(tmp_path):
    landmarker = tmp_path / "face_landmarker.task"
    landmarker.write_bytes(LANDMARKER_BYTES)
    argv = ["--root", str(tmp_path / "nothing"), "--cache", str(tmp_path / "empty"), "--landmarker", str(landmarker), "--out", str(tmp_path / "out")]
    assert fatigue_pipeline.main(argv) == 1
    assert not (tmp_path / "out").exists()


def test_the_calibration_sensitivity_is_measured_on_windows_outside_every_first_two_minutes(run):
    sensitivity = load(run, "metrics.json")["calibration_sensitivity"]
    # 240 s -> 19 windows per video, 12 of them touch the first 120 s: 7 left per video, in all three states.
    assert sensitivity["windows"] == {"alert": 4 * 7, "low_vigilance": 4 * 7, "drowsy": 4 * 7}
    for version in ("threshold_from_alert_video", "threshold_from_scored_video", "blendshape_absolute_same_windows"):
        assert 0 <= sensitivity[version]["auc"] <= 1 and set(sensitivity[version]["perclos"]) == {"alert", "low_vigilance", "drowsy"}
    report = (run["out"] / "fatigue_report.md").read_text(encoding="utf-8")
    assert "### What a rested calibration is worth" in report
    assert set(sensitivity["calibrated_features"]) >= {"reference_from_alert_video", "reference_from_scored_video"}


def test_the_shipped_configuration_is_a_setting_not_the_best_score(tmp_path):
    """EAR sees the drowsy eyes here and the blendshapes do not: a selection by score would switch to EAR."""
    assert fatigue_pipeline.SHIPPED == ("blendshape", "absolute") == (ff.SHIPPED_EYE_METHOD, ff.SHIPPED_NORMALISATION)
    blind = run_pipeline(tmp_path, blendshapes_see_it=False)
    metrics, model = load(blind, "metrics.json"), load(blind, "fatigue_model.json")
    configurations = metrics["configurations"]
    assert configurations["ear_p80/absolute"]["auc"] > 0.9 > 0.7 > configurations["blendshape/absolute"]["auc"]
    assert metrics["chosen"]["configuration"] == "blendshape/absolute" and metrics["chosen"]["rank_among_the_four_by_auc"] > 1
    assert metrics["auc"] == configurations["blendshape/absolute"]["auc"]  # the headline is the shipped one, however it scores
    assert model["eye_closure"]["method"] == "blendshape" and model["calibration"]["required"] is False
    report = (blind["out"] / "fatigue_report.md").read_text(encoding="utf-8")
    # The wording follows the numbers: with nothing demonstrated, the pitch sentence moves to "may not be said".
    may, may_not = report.split("May not be said:")[0], report.split("May not be said:")[1]
    assert "predict drowsiness" not in may.split("May be said:")[1] and "not supported by this run" in may_not
