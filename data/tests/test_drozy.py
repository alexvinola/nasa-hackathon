"""DROZY loader, windows and the validation of a model, on made-up files and synthetic signals. No DROZY data here."""

import json

import numpy as np
import pandas as pd
import pytest

from drozy_layout import KSS_LINES, fake_drozy, synthetic_pvt, synthetic_signals, synthetic_tests
from pulsar_vision import drozy, fatigue_features as ff, fatigue_pipeline, fatigue_validation as fv, landmarks


# --------------------------------------------------------------------------- files


@pytest.mark.parametrize("stem, expected", [("1-1", (1, 1)), ("7-2", (7, 2)), ("14-3", (14, 3)), ("10-1", (10, 1))])
def test_parse_name(stem, expected):
    assert drozy.parse_name(stem) == expected


@pytest.mark.parametrize("stem", ["15-1", "0-1", "3-4", "3-0", "1-1-s2", "1_1", "a-1", "1-", "101-1", ""])
def test_parse_name_rejects_what_is_not_a_test(stem):
    with pytest.raises(ValueError):
        drozy.parse_name(stem)


def test_kss_is_one_line_per_subject_and_one_column_per_test(tmp_path):
    scores = drozy.load_kss(fake_drozy(tmp_path, []) / "KSS.txt")
    assert len(scores) == 14 * 3
    assert (scores[(1, 1)], scores[(1, 2)], scores[(1, 3)]) == (1.0, 5.0, 9.0)
    assert scores[(4, 3)] == 8.0
    assert scores[(7, 1)] is None  # 0 means no score was recorded: missing, not "extremely alert"


@pytest.mark.parametrize("lines", [KSS_LINES[:13], ["3 6"] + KSS_LINES[1:], ["3 6 10"] + KSS_LINES[1:]])
def test_kss_file_of_another_shape_or_range_is_refused(tmp_path, lines):
    path = tmp_path / "KSS.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(drozy.DatasetMissing):
        drozy.load_kss(path)


def test_pvt_reaction_time_is_reaction_minus_stimulus(tmp_path):
    root = fake_drozy(tmp_path, ["2-1"])
    stimulus_s, rt_ms = drozy.load_pvt(root / "pvt-rt" / "2-1.csv")
    assert stimulus_s == pytest.approx([5.5, 62.0])  # seconds since the first line of the file
    assert rt_ms == pytest.approx([312.0, 1250.0])


@pytest.mark.parametrize("content", ["", "not a date\n", "2020-01-02_10.00.00.000\n2020-01-02_10.00.05.500\n"])
def test_pvt_file_of_another_format_is_refused(tmp_path, content):
    path = tmp_path / "1-1.csv"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(drozy.DatasetMissing):
        drozy.load_pvt(path)


def test_frame_times_are_the_elapsed_column_in_milliseconds(tmp_path):
    root = fake_drozy(tmp_path, ["2-1"])
    assert drozy.load_frame_times_ms(root / "timestamps" / "2-1.txt") == pytest.approx([20.0, 53.0, 120.0])


@pytest.mark.parametrize("content", ["1 2 3\n4 5 6\n", "2020 1 2 10 0 0 53 53\n2020 1 2 10 0 0 20 20\n"])
def test_frame_times_of_another_format_are_refused(tmp_path, content):
    path = tmp_path / "1-1.txt"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(drozy.DatasetMissing):
        drozy.load_frame_times_ms(path)


def test_load_gives_one_test_per_video_in_subject_and_test_order(tmp_path):
    root = fake_drozy(tmp_path, ["10-1", "2-3", "2-1", "7-2"])
    tests = drozy.load(root)
    assert [t.name for t in tests] == ["2-1", "2-3", "7-2", "10-1"]
    assert [t.subject for t in tests] == ["2", "2", "7", "10"]
    assert [t.kss for t in tests] == [2.0, 6.0, 8.0, 5.0]
    assert tests[0].video == root / "videos_i8" / "2-1.mp4"
    assert tests[0].timestamps == root / "timestamps" / "2-1.txt" and tests[0].pvt == root / "pvt-rt" / "2-1.csv"


def test_load_stops_on_a_video_without_its_pvt_or_timestamps(tmp_path):
    root = fake_drozy(tmp_path, ["1-1", "1-2"])
    (root / "pvt-rt" / "1-2.csv").unlink()
    with pytest.raises(drozy.DatasetMissing, match="1-2.*pvt-rt"):
        drozy.load(root)


def test_load_stops_on_a_video_name_it_does_not_know(tmp_path):
    root = fake_drozy(tmp_path, ["1-1"])
    (root / "videos_i8" / "1-1-copy.mp4").touch()
    with pytest.raises(drozy.DatasetMissing, match="1-1-copy"):
        drozy.load(root)


def test_a_missing_dataset_says_how_to_get_it(tmp_path):
    assert not drozy.available(tmp_path / "drozy" / "DROZY")
    with pytest.raises(drozy.DatasetMissing) as error:
        drozy.load(tmp_path / "drozy" / "DROZY")
    message = str(error.value)
    assert "downloads" in message and "licence" in message and "git-ignored" in message
    assert str(tmp_path / "drozy" / "DROZY") in message


def test_every_result_cites_the_dataset():
    assert all(word in drozy.CITATION for word in ("Massoz", "Langohr", "Verly", "2016", "WACV"))
    assert "not registered" in drozy.KSS_NOTE


# --------------------------------------------------------------------------- windows


@pytest.fixture(scope="module")
def yawn_params():
    params, _ = fatigue_pipeline.load_yawn_params(fatigue_pipeline.YAWN_PARAMS_FILE)
    return params


def a_test(name: str = "3-2", kss: float | None = 6.0) -> drozy.DrozyTest:
    subject, test = name.split("-")
    return drozy.DrozyTest(subject, int(test), None, None, None, kss)


def test_windows_use_the_shipped_features_and_the_pvt_of_the_same_seconds(yawn_params):
    rng = np.random.default_rng(1)
    signals = synthetic_signals(0.5, 180.0, rng)
    stimulus_s = float(signals.time_s[0]) + np.array([5.0, 30.0, 59.99, 60.0, 75.0, 170.0])  # seconds after the first frame
    rt_ms = np.array([300.0, 500.0, 700.0, 900.0, 1100.0, 400.0])
    rows = drozy.recording_windows(a_test(), signals, yawn_params, stimulus_s, rt_ms)
    assert len(rows) == len(ff.window_starts(float(signals.time_s[0]), float(signals.time_s[-1]) + ff.frame_period(signals.time_s)))
    first = rows[0]
    assert first["start_s"] == pytest.approx(0.02, abs=0.005)  # on the test's clock: the first frame's time
    # The same functions as RLDD: the shipped features of the window's frames.
    frames = ff.window_slice(signals.time_s, first["start_s"])
    expected = ff.window_features(
        signals.time_s[frames], signals.face[frames], ff.closed_from_blendshape(signals.eye_blink)[frames],
        signals.pitch_deg[frames], signals.mouth_open_ratio[frames], yawn_params,
    )
    assert {name: first[name] for name in ff.FEATURE_NAMES} == pytest.approx(expected, nan_ok=True)
    # Stimuli in [start, start + 60 s): 59.99 s after the start is in the first window, 60.0 s belongs to the next ones.
    assert first[fv.PVT_STIMULI] == 3 and first[fv.PVT_MEAN_RT] == pytest.approx(500.0)
    assert first[fv.RECORDING_MEAN_RT] == pytest.approx(rt_ms.mean())
    assert first[fv.KSS] == 6.0 and first["usable"] and first["subject"] == "3" and first["recording"] == "3-2"
    assert 0.0 <= first["baseline_score"] <= 1.0
    assert first["perclos"] == pytest.approx(first["baseline_perclos"])  # the same eye rule as the browser


def test_a_window_without_enough_face_has_no_features_and_no_kss_is_missing(yawn_params):
    rng = np.random.default_rng(2)
    signals = synthetic_signals(0.2, 130.0, rng, lost=slice(0, int(30 * 15)))  # no face in the first 30 s
    rows = drozy.recording_windows(a_test(kss=None), signals, yawn_params, *synthetic_pvt(0.2, 130.0, rng))
    assert not rows[0]["usable"] and np.isnan(rows[0]["perclos"])  # a lost face is not a drowsy face
    assert rows[-1]["usable"]
    assert all(np.isnan(row[fv.KSS]) for row in rows)


# --------------------------------------------------------------------------- the model on DROZY


def shipped_model() -> dict:
    return json.loads((fatigue_pipeline.DEFAULT_MODEL_FILE).read_text(encoding="utf-8"))


def yawn_raw() -> dict:
    return json.loads(fatigue_pipeline.YAWN_PARAMS_FILE.read_text(encoding="utf-8"))


def test_the_model_is_refused_when_it_does_not_fit_the_features():
    model = shipped_model()
    sha = model["face_landmarker"]["model_sha256"]
    drozy.check_model(model, yawn_raw(), sha)  # the shipped model fits
    for change, match in (
        (lambda m: m.update(features=list(reversed(m["features"]))), "features"),
        (lambda m: m.update(features_version=99), "features_version"),
        (lambda m: m["configuration"].update(shipped="ear_p80/absolute"), "shipped configuration"),
        (lambda m: m["yawn_detector"].update(threshold=0.9), "yawn detector"),
    ):
        broken = json.loads(json.dumps(model))
        change(broken)
        with pytest.raises(ValueError, match=match):
            drozy.check_model(broken, yawn_raw(), sha)
    with pytest.raises(ValueError, match="face_landmarker"):
        drozy.check_model(model, yawn_raw(), "another model")


def test_the_score_is_the_shipped_model_applied_as_it_is(tmp_path):
    _, windows, _ = synthetic_tests(tmp_path, {"1-1": 0.1, "1-2": 0.9})
    model = shipped_model()
    scored = drozy.score_windows(windows, model)
    assert len(scored) == int(windows["usable"].sum()) > 0
    row = scored.iloc[0]
    expected = ff.fatigue_score(ff.predict_proba(np.array([row[name] for name in ff.FEATURE_NAMES]), model))[0]
    assert row[drozy.SCORE] == pytest.approx(expected)
    assert (scored[drozy.BROWSER] == scored["baseline_score"]).all()
    assert json.loads(json.dumps(model)) == shipped_model()  # nothing in the model was touched


def test_the_summary_holds_aggregates_only_and_the_headline_is_per_recording_spearman(tmp_path):
    levels = {"1-1": 0.0, "1-2": 0.5, "1-3": 1.0, "2-1": 0.2, "2-2": 0.8, "3-1": 0.3, "3-3": 0.6}
    tests, windows, covered = synthetic_tests(tmp_path, levels)
    model = shipped_model()
    scored = drozy.score_windows(windows, model)
    block = drozy.summary(windows, scored, covered, [], tests, model)
    headline = block["headline"]
    per_test = block["results"]["per_recording"][drozy.SCORE][fv.PVT_MEAN_RT]
    assert (headline["view"], headline["statistic"], headline["signal"]) == ("per_recording", "spearman", drozy.SCORE)
    assert headline["value"] == per_test["spearman"] and headline["pearson_r"] == per_test["r"] and headline["n_recordings"] == 7
    assert set(block["results"]["per_recording"]) == set(drozy.SIGNALS)
    # PERCLOS is built to follow sleepiness here, and the reaction times too: the sign must come out positive.
    assert block["results"]["per_recording"][drozy.PERCLOS][fv.PVT_MEAN_RT]["spearman"] > 0.5
    assert block["dataset"]["tests_scored"] == 7 and block["dataset"]["subjects_scored"] == 3
    assert block["model"]["refit_on_drozy"] is False and "Massoz" in block["citation"]
    # The licence: no recording's KSS or reaction times in the output, only counts and correlations.
    for recording in block["recordings"]:
        assert not {"kss", "mean_rt_ms", fv.PVT_MEAN_RT, fv.RECORDING_MEAN_RT} & set(recording)
    text = json.dumps(fatigue_pipeline.clean(block))
    assert '"rt_ms"' not in text and '"stimulus_s"' not in text


def test_pvt_correlation_is_a_number_with_drozy_and_null_without():
    assert drozy.pvt_fields(None)["pvt_correlation"] is None
    block = {"headline": {"value": 0.25, "n_recordings": 36}}
    fields = drozy.pvt_fields(block)
    assert fields["pvt_correlation"] == 0.25 and "Massoz" in fields["pvt_correlation_note"]
    metrics = {"macro_f1": 0.4, "pvt_correlation": None, "pvt_correlation_note": "old", "folds": [], "drozy_validation": {"stale": True}}
    merged = drozy.merge(metrics, block)
    assert list(merged) == ["macro_f1", "pvt_correlation", "pvt_correlation_note", "folds", "drozy_validation"]
    assert merged["drozy_validation"] == block
    assert "drozy_validation" not in drozy.merge(metrics, None)  # a stale block never survives a run without DROZY


def test_validate_model_extracts_through_the_worker_pool_and_writes_nothing(tmp_path, monkeypatch):
    levels = {"1-1": 0.1, "1-2": 0.9, "2-1": 0.4}
    tests, windows, covered = synthetic_tests(tmp_path / "DROZY", levels)
    landmarker = tmp_path / "face_landmarker.task"
    landmarker.write_bytes(b"made up")
    model = shipped_model()
    model["face_landmarker"]["model_sha256"] = landmarks.sha256_of(b"made up")
    seen = {}

    def fake_extract(found, path, params, workers, log):
        seen["tests"] = [t.name for t in found]
        return windows, covered, [], {"wall_seconds": 1.0, "mediapipe_seconds": 0.5, "workers": workers}

    monkeypatch.setattr(drozy, "extract_windows", fake_extract)
    before = sorted(p for p in tmp_path.rglob("*"))
    block = drozy.validate_model(model, fatigue_pipeline.load_yawn_params(fatigue_pipeline.YAWN_PARAMS_FILE)[0], yawn_raw(), tmp_path / "DROZY", landmarker, 2, lambda m: None)
    assert seen["tests"] == ["1-1", "1-2", "2-1"]
    assert block["dataset"]["tests_scored"] == 3
    assert sorted(p for p in tmp_path.rglob("*")) == before  # no cache, no file of any kind


def test_validation_of_a_missing_dataset_raises_so_the_pipeline_can_report_it(tmp_path):
    model = shipped_model()
    landmarker = fatigue_pipeline.DEFAULT_LANDMARKER
    if not landmarker.is_file():
        pytest.skip("face_landmarker.task is not downloaded (make prefetch)")
    with pytest.raises(drozy.DatasetMissing):
        drozy.validate_model(model, None, yawn_raw(), tmp_path / "none", landmarker, 1, lambda m: None)


def test_windows_table_has_one_row_per_window(tmp_path):
    _, windows, covered = synthetic_tests(tmp_path, {"4-1": 0.3})
    assert isinstance(windows, pd.DataFrame) and len(windows) == covered[0]["windows"]
    assert covered[0]["windows_rejected"] == int((~windows["usable"]).sum())
