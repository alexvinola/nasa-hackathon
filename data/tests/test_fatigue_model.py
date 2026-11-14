"""Model fitting, subject-grouped validation and metrics on synthetic windows."""

import json
import math

import numpy as np
import pytest

from pulsar_vision import fatigue_features as ff, fatigue_model as fm, fatigue_pipeline

NAN = float("nan")


def synthetic(subjects: int = 8, per_class: int = 30, seed: int = 0, signal: float = 1.5):
    """Windows of ``subjects`` people: feature 0 grows with the state, feature 1 is a per-person offset."""
    rng = np.random.default_rng(seed)
    features, classes, groups = [], [], []
    for s in range(subjects):
        offset = rng.normal(0, 3)
        for k in range(3):
            block = rng.normal(0, 1, size=(per_class, 3))
            block[:, 0] += signal * k
            block[:, 1] += offset
            features.append(block)
            classes += [k] * per_class
            groups += [f"{s + 1:02d}"] * per_class
    return np.vstack(features), np.array(classes), np.array(groups)


# --------------------------------------------------------------------------- folds


def test_leave_one_subject_out_folds_are_disjoint_and_cover_everyone():
    subjects = [f"{i:02d}" for i in range(1, 25)]
    folds = fm.subject_folds(subjects, None)
    assert len(folds) == 24 and all(len(f) == 1 for f in folds)
    assert sorted(s for f in folds for s in f) == subjects
    six = fm.subject_folds(subjects, 6)
    assert [len(f) for f in six] == [4] * 6
    assert sorted(s for f in six for s in f) == subjects
    assert fm.subject_folds(subjects, 6) == six  # deterministic


def test_cross_validation_never_tests_a_subject_it_trained_on():
    x, y, groups = synthetic()
    outer = fm.subject_folds(sorted(set(groups)), None)
    result = fm.cross_validate(x, y, groups, outer)
    tested = []
    for fold in result.folds:
        assert not set(fold["train_subjects"]) & set(fold["test_subjects"])
        assert sorted(fold["train_subjects"] + fold["test_subjects"]) == sorted(set(groups))
        assert fold["C"] in fm.C_GRID
        tested += fold["test_subjects"]
    assert sorted(tested) == sorted(set(groups))  # everyone tested exactly once
    assert not np.isnan(result.proba).any()
    assert result.proba.sum(axis=1) == pytest.approx(1.0)
    assert fm.classification_metrics(y, result.proba)["auc"] > 0.8


def test_no_fit_inside_an_outer_fold_ever_sees_the_test_subject(monkeypatch):
    x, y, groups = synthetic(subjects=6, per_class=10)
    x[:, 2] = np.arange(len(x))  # a row id travelling with the features: every fit can be traced
    seen: list[set[str]] = []
    real_fit = fm.fit_model

    def spy(features, classes, c):
        seen.append({groups[int(i)] for i in features[:, 2]})
        return real_fit(features, classes, c)

    monkeypatch.setattr(fm, "fit_model", spy)
    name, index, rows, proba, other, report = fm._outer_fold(("set", 0, x, y, groups, ["03"], fm.SEED, None))
    assert len(seen) == len(fm.C_GRID) * 5 + 1  # the inner grid on 5 folds, then the fold's model
    assert all("03" not in subjects for subjects in seen)  # neither the C search nor the scaler nor the weights
    assert seen[-1] == {"01", "02", "04", "05", "06"}
    assert {groups[i] for i in rows} == {"03"} and report["test_subjects"] == ["03"]
    assert "03" not in report["train_subjects"]


def test_alternative_features_are_scored_but_never_trained_on():
    x, y, groups = synthetic(subjects=5, per_class=12)
    outer = fm.subject_folds(sorted(set(groups)), None)
    shuffled = np.random.default_rng(0).permutation(x)  # the same rows described by nonsense
    plain = fm.cross_validate_many({"a": x}, y, groups, outer)["a"]
    both = fm.cross_validate_many({"a": x}, y, groups, outer, alternatives={"a": shuffled})["a"]
    np.testing.assert_allclose(both.proba, plain.proba, atol=1e-12)  # training did not change
    assert plain.alternative_proba is None
    assert fm.macro_auc(y, both.proba) > 0.8 > fm.macro_auc(y, both.alternative_proba)
    np.testing.assert_allclose(fm.cross_validate_many({"a": x}, y, groups, outer, alternatives={"a": x})["a"].alternative_proba, plain.proba, atol=1e-12)


def test_nested_selection_picks_by_the_inner_score_not_by_the_test_result():
    groups = np.array(["01", "01", "02", "02"])
    outer = [["01"], ["02"]]
    good = np.tile([0.9, 0.05, 0.05], (4, 1))
    bad = np.tile([0.1, 0.1, 0.8], (4, 1))
    cross = {
        # "lucky" looks better inside fold 0, "steady" inside fold 1; what they do on the test rows is irrelevant.
        "lucky": fm.CrossValidation(proba=bad, folds=[{"inner_auc": 0.9}, {"inner_auc": 0.4}]),
        "steady": fm.CrossValidation(proba=good, folds=[{"inner_auc": 0.6}, {"inner_auc": 0.7}]),
    }
    proba, picks = fm.nested_selection(cross, groups, outer)
    assert picks == ["lucky", "steady"]
    np.testing.assert_array_equal(proba[:2], bad[:2])
    np.testing.assert_array_equal(proba[2:], good[2:])
    tie = {"first": fm.CrossValidation(good, [{"inner_auc": 0.5}, {"inner_auc": 0.5}]), "second": fm.CrossValidation(bad, [{"inner_auc": 0.5}, {"inner_auc": 0.5}])}
    assert fm.nested_selection(tie, groups, outer)[1] == ["first", "first"]


def test_several_feature_sets_are_validated_on_the_same_folds():
    x, y, groups = synthetic(subjects=5, per_class=12)
    outer = fm.subject_folds(sorted(set(groups)), None)
    results = fm.cross_validate_many({"all": x, "first_only": x[:, :1]}, y, groups, outer)
    for name in ("all", "first_only"):
        assert [f["test_subjects"] for f in results[name].folds] == outer
        assert not np.isnan(results[name].proba).any()
    np.testing.assert_allclose(fm.cross_validate(x, y, groups, outer).proba, results["all"].proba, atol=1e-12)
    np.testing.assert_allclose(fm.cross_validate(x[:, :1], y, groups, outer).proba, results["first_only"].proba, atol=1e-12)


# --------------------------------------------------------------------------- the exported arithmetic


def test_exported_weights_reproduce_scikit_learn():
    from sklearn.linear_model import LogisticRegression

    x, y, _ = synthetic()
    model = fm.fit_model(x, y, 1.0)
    z = (x - np.array(model["mean"])) / np.array(model["std"])
    reference = LogisticRegression(C=1.0, max_iter=fm.MAX_ITER, tol=fm.TOLERANCE, solver=fm.SOLVER).fit(z, y)
    np.testing.assert_allclose(ff.predict_proba(x, model), reference.predict_proba(z), atol=1e-9)
    # The solver is a speed choice, not a different model: L-BFGS lands on the same probabilities.
    lbfgs = LogisticRegression(C=1.0, max_iter=5000, tol=1e-10).fit(z, y)
    np.testing.assert_allclose(ff.predict_proba(x, model), lbfgs.predict_proba(z), atol=1e-4)
    assert np.array(model["coef"]).shape == (3, 3) and len(model["intercept"]) == 3
    assert model["mean"] == pytest.approx(x.mean(axis=0).tolist())
    assert model["std"] == pytest.approx(x.std(axis=0).tolist())


def test_missing_values_are_ignored_by_the_scaler_and_a_constant_feature_keeps_a_positive_std():
    x, y, _ = synthetic()
    x[::7, 2] = NAN
    x = np.column_stack([x, np.full(len(x), 4.0)])
    model = fm.fit_model(x, y, 1.0)
    assert model["mean"][2] == pytest.approx(float(np.nanmean(x[:, 2])))
    assert model["std"][3] == 1.0 and all(s > 0 for s in model["std"])
    assert not np.isnan(ff.predict_proba(x, model)).any()


def test_training_needs_all_three_states():
    x, y, _ = synthetic()
    with pytest.raises(ValueError):
        fm.fit_model(x[y != 1], y[y != 1], 1.0)


def test_c_is_chosen_on_grouped_folds_and_falls_back_with_one_subject():
    x, y, groups = synthetic()
    choice = fm.choose_c(x, y, groups)
    assert choice["C"] in fm.C_GRID and choice["inner_folds"] == 5
    assert choice["inner_log_loss"] == min(choice["log_loss_by_C"].values())
    one = fm.choose_c(x[groups == "01"], y[groups == "01"], groups[groups == "01"])
    assert one["C"] == fm.DEFAULT_C and one["inner_folds"] == 0


# --------------------------------------------------------------------------- metrics


def test_confusion_matrix_and_macro_f1():
    truth = np.array([0, 0, 0, 1, 1, 1, 2, 2, 2])
    guess = np.array([0, 0, 1, 1, 1, 2, 2, 2, 2])
    assert fm.confusion_matrix(truth, guess) == [[2, 1, 0], [0, 2, 1], [0, 0, 3]]
    f1 = [2 * 2 / (2 * 2 + 0 + 1), 2 * 2 / (2 * 2 + 1 + 1), 2 * 3 / (2 * 3 + 1 + 0)]
    assert fm.macro_f1(truth, guess) == pytest.approx(np.mean(f1))
    assert fm.macro_f1(truth, np.zeros(9, dtype=int)) == pytest.approx((2 * 3 / (2 * 3 + 6)) / 3)


def test_classification_metrics_of_a_perfect_and_a_useless_model():
    y = np.array([0, 1, 2] * 10)
    perfect = np.eye(3)[y]
    m = fm.classification_metrics(y, perfect)
    assert (m["macro_f1"], m["auc"], m["accuracy"]) == (1.0, 1.0, 1.0)
    assert m["confusion_matrix"] == [[10, 0, 0], [0, 10, 0], [0, 0, 10]]
    assert all(isinstance(c, int) for row in m["confusion_matrix"] for c in row)
    uniform = np.full((30, 3), 1 / 3)
    assert fm.classification_metrics(y, uniform)["auc"] == pytest.approx(0.5)
    assert fm.classification_metrics(y, uniform)["log_loss"] == pytest.approx(math.log(3))
    assert math.isnan(fm.macro_auc(np.array([0, 0, 1]), np.full((3, 3), 1 / 3)))


def test_auc_matches_scikit_learn_with_ties_and_three_classes():
    from sklearn.metrics import roc_auc_score

    rng = np.random.default_rng(5)
    y = rng.integers(0, 3, size=400)
    score = np.round(rng.normal(size=400) + 0.5 * y, 1)  # rounded: plenty of ties
    assert fm.binary_auc(y == 2, score) == pytest.approx(roc_auc_score(y == 2, score))
    proba = rng.dirichlet([1, 1, 1], size=400)
    proba[np.arange(400), y] += 0.3
    proba /= proba.sum(axis=1, keepdims=True)
    assert fm.macro_auc(y, proba) == pytest.approx(roc_auc_score(y, proba, multi_class="ovr", average="macro"))
    assert math.isnan(fm.binary_auc(np.zeros(5, dtype=bool), np.arange(5.0)))


def test_score_metrics_order_the_three_states():
    y = np.array([0] * 5 + [1] * 5 + [2] * 5)
    rising = np.concatenate([np.linspace(0, 0.2, 5), np.linspace(0.4, 0.6, 5), np.linspace(0.8, 1, 5)])
    m = fm.score_metrics(y, rising)
    assert m["auc_alert_vs_drowsy"] == 1.0 and m["auc_alert_vs_rest"] == 1.0 and m["auc_drowsy_vs_rest"] == 1.0
    assert m["spearman_with_label"] > 0.9
    assert fm.score_metrics(y, -rising)["auc_alert_vs_drowsy"] == 0.0
    assert math.isnan(fm.score_metrics(y, np.zeros(15))["spearman_with_label"])


def test_a_video_gets_the_state_most_of_its_windows_got():
    proba = np.array([[0.8, 0.1, 0.1], [0.6, 0.3, 0.1], [0.1, 0.2, 0.7], [0.2, 0.2, 0.6], [0.5, 0.4, 0.1], [0.1, 0.3, 0.6]])
    y = np.array([0, 0, 0, 2, 2, 2])
    videos = np.array(["01_0", "01_0", "01_0", "01_10", "01_10", "01_10"])
    rows = fm.video_predictions(y, proba, videos)
    assert [(r["video_id"], r["true"], r["predicted"], r["votes"]) for r in rows] == [("01_0", 0, 0, [2, 0, 1]), ("01_10", 2, 2, [1, 0, 2])]
    level = fm.video_level_metrics(rows)
    assert level["correct"] == 2 and level["accuracy"] == 1.0
    tie = fm.video_predictions(np.array([1, 1]), np.array([[0.9, 0.05, 0.05], [0.3, 0.3, 0.4]]), np.array(["02_5", "02_5"]))
    assert tie[0]["predicted"] == 0  # one vote each: the higher mean probability wins


def test_per_subject_rows_and_the_ordering_count():
    x, y, groups = synthetic(subjects=4)
    videos = np.array([f"{g}_{(0, 5, 10)[k]}" for g, k in zip(groups, y)])
    proba = fm.cross_validate(x, y, groups, fm.subject_folds(sorted(set(groups)), None)).proba
    rows = fm.per_subject(y, proba, groups, videos, baseline=np.zeros(len(y)))
    assert [r["subject"] for r in rows] == ["01", "02", "03", "04"]
    assert all(r["windows"] == {"alert": 30, "low_vigilance": 30, "drowsy": 30} for r in rows)
    assert all(math.isnan(r["baseline_auc_alert_vs_drowsy"]) or r["baseline_auc_alert_vs_drowsy"] == 0.5 for r in rows)
    ordering = fm.ordering_counts(rows, "mean_fatigue_score")
    assert ordering["drowsy_above_alert"] == {"subjects": 4, "of": 4}
    assert fm.ordering_counts(rows, "mean_baseline_score")["drowsy_above_alert"] == {"subjects": 0, "of": 4}


def test_the_bootstrap_resamples_subjects_not_windows():
    groups = np.array(["a"] * 50 + ["b"] * 50 + ["c"] * 50)
    values = np.array([0.0] * 50 + [1.0] * 50 + [2.0] * 50)
    seen = []

    def statistics(index):
        seen.append(len(index))
        return {"mean": float(values[index].mean())}

    intervals = fm.subject_bootstrap(groups, statistics, resamples=300, seed=1)
    assert set(seen) == {150}  # whole subjects: always 3 x 50 windows
    low, high = intervals["mean"]
    # With 3 subjects the mean ranges over whole-subject combinations (0 .. 2), far wider than a window bootstrap would give.
    assert low <= 1 / 3 and high >= 5 / 3


# --------------------------------------------------------------------------- output plumbing


def test_json_cleaning_turns_nan_into_null_and_rounds():
    cleaned = fatigue_pipeline.clean({"a": np.float64(0.123456789), "b": NAN, "c": np.int64(3), "d": [np.bool_(True), np.array([1.5, NAN])], 5: "x"})
    assert cleaned == {"a": 0.123457, "b": None, "c": 3, "d": [True, [1.5, None]], "5": "x"}
    json.dumps(cleaned, allow_nan=False)


def test_feature_columns_follow_the_model_order():
    assert fatigue_pipeline.feature_columns(ff.BLENDSHAPE, ff.ABSOLUTE) == [f"blendshape__{n}" for n in ff.FEATURE_NAMES]
    assert fatigue_pipeline.feature_columns(ff.EAR_P80, ff.CALIBRATED) == [f"ear_p80_calibrated__{n}" for n in ff.FEATURE_NAMES]
    assert set(fatigue_pipeline.FEATURE_DEFINITIONS) == set(ff.FEATURE_NAMES)
