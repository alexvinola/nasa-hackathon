"""Train and validate the fatigue model: multinomial logistic regression, subject-grouped validation.

Everything is grouped by subject: no window of a test subject is ever seen while fitting the scaler,
choosing the regularisation or fitting the weights that score that subject.

- Outer loop: subject folds (leave-one-subject-out by default). Metrics are computed on the pooled
  out-of-fold windows.
- Inner loop, on the training subjects only: ``C`` is the value with the lowest pooled multinomial
  log loss over grouped folds.
- The exported model is refit on every subject with ``C`` chosen the same way.

Windows of one video overlap (60 s windows every 10 s) and all windows of a video share one label, so
they are far from independent. Intervals here resample SUBJECTS, not windows.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

import numpy as np

from . import fatigue_features as ff, folds as folds_module

C_GRID: tuple[float, ...] = (0.001, 0.01, 0.1, 1.0, 10.0, 100.0)
DEFAULT_C = 1.0
INNER_FOLDS = 5
SEED = 2026
MAX_ITER = 1000
TOLERANCE = 1e-6
# Newton steps with an exact Hessian: with thousands of windows and seven features it converges in about
# ten iterations to the same optimum L-BFGS approaches slowly (measured: several times faster, and tighter).
SOLVER = "newton-cholesky"
BOOTSTRAP_RESAMPLES = 2000
N_CLASSES = len(ff.CLASS_NAMES)


# --------------------------------------------------------------------------- fitting


def fit_model(features: np.ndarray, classes: np.ndarray, c: float) -> dict:
    """Standardise (missing values become the mean) and fit; returns ``mean``, ``std``, ``coef``, ``intercept``."""
    from sklearn.linear_model import LogisticRegression

    x = np.asarray(features, dtype=np.float64)
    y = np.asarray(classes)
    present = sorted(set(int(v) for v in y))
    if present != list(range(N_CLASSES)):
        raise ValueError(f"training needs windows of all {N_CLASSES} classes, got {present}")
    mean = np.zeros(x.shape[1])
    std = np.ones(x.shape[1])
    for column in range(x.shape[1]):
        values = x[:, column]
        values = values[~np.isnan(values)]
        if len(values):
            mean[column] = float(values.mean())
            spread = float(values.std())
            std[column] = spread if spread > 1e-12 else 1.0  # a constant feature must not divide by zero
    z = ff.standardise(x, mean, std)
    classifier = LogisticRegression(C=c, max_iter=MAX_ITER, tol=TOLERANCE, solver=SOLVER)
    classifier.fit(z, y)
    return {
        "mean": mean.tolist(),
        "std": std.tolist(),
        "coef": classifier.coef_.tolist(),
        "intercept": classifier.intercept_.tolist(),
        "C": float(c),
    }


def subject_folds(subjects: Sequence[str], n_folds: int | None, seed: int = SEED) -> list[list[str]]:
    """Disjoint test folds of subjects; ``n_folds=None`` (or >= subjects) is leave-one-subject-out."""
    unique = sorted(set(subjects))
    count = len(unique) if n_folds is None or n_folds >= len(unique) else n_folds
    folds = folds_module.grouped_folds({s: "all" for s in unique}, count, seed)
    folds_module.assert_disjoint(folds)
    return folds


def out_of_fold_proba(features: np.ndarray, classes: np.ndarray, groups: np.ndarray, folds: list[list[str]], c: float) -> np.ndarray:
    """Probabilities of every window from a model that never saw its subject (fixed ``C``)."""
    proba = np.full((len(classes), N_CLASSES), np.nan)
    for fold in folds:
        test = np.isin(groups, fold)
        model = fit_model(features[~test], classes[~test], c)
        proba[test] = ff.predict_proba(features[test], model)
    return proba


def log_loss(classes: np.ndarray, proba: np.ndarray) -> float:
    picked = np.clip(proba[np.arange(len(classes)), classes], 1e-15, 1.0)
    return float(-np.log(picked).mean())


def binary_auc(positive: np.ndarray, score: np.ndarray) -> float:
    """AUC of ``score`` for ``positive`` (bool) against the rest; NaN when one side is empty.

    The Mann-Whitney form: the share of (positive, negative) pairs the score orders correctly, ties
    counting half. Same value as scikit-learn's ``roc_auc_score``.
    """
    from scipy.stats import rankdata

    positive = np.asarray(positive, dtype=bool)
    n_positive = int(positive.sum())
    n_negative = len(positive) - n_positive
    if not n_positive or not n_negative:
        return math.nan
    ranks = rankdata(score)  # average ranks on ties
    return float((ranks[positive].sum() - n_positive * (n_positive + 1) / 2.0) / (n_positive * n_negative))


def macro_auc(classes: np.ndarray, proba: np.ndarray) -> float:
    """Macro one-vs-rest AUC: the mean of the three class-against-the-rest AUCs; NaN when a class is absent."""
    values = [binary_auc(classes == k, proba[:, k]) for k in range(N_CLASSES)]
    return float(np.mean(values)) if all(v == v for v in values) else math.nan


def choose_c(
    features: np.ndarray,
    classes: np.ndarray,
    groups: np.ndarray,
    seed: int = SEED,
    c_grid: Sequence[float] = C_GRID,
    inner_folds: int = INNER_FOLDS,
) -> dict:
    """``C`` with the lowest pooled log loss over grouped folds of the given (training) subjects."""
    subjects = sorted(set(groups.tolist()))
    if len(subjects) < 2:
        return {"C": DEFAULT_C, "log_loss_by_C": {}, "inner_log_loss": None, "inner_auc": None, "inner_folds": 0}
    folds = subject_folds(subjects, min(inner_folds, len(subjects)), seed)
    losses: dict[float, float] = {}
    aucs: dict[float, float] = {}
    for c in c_grid:
        proba = out_of_fold_proba(features, classes, groups, folds, c)
        losses[c] = log_loss(classes, proba)
        aucs[c] = macro_auc(classes, proba)
    best = min(c_grid, key=lambda c: (losses[c], c))  # ties go to the stronger regularisation
    return {
        "C": float(best),
        "log_loss_by_C": {str(c): losses[c] for c in c_grid},
        "inner_log_loss": losses[best],
        "inner_auc": aucs[best],
        "inner_folds": len(folds),
    }


@dataclass
class CrossValidation:
    proba: np.ndarray  # [n, 3] out-of-fold probabilities
    folds: list[dict]  # per outer fold: subjects, chosen C and the inner scores
    # The same out-of-fold models applied to another version of the test rows' features (when asked for):
    alternative_proba: np.ndarray | None = None


def _outer_fold(task: tuple) -> tuple:
    """One outer fold of one feature set: choose C on the training subjects, fit, score the test subjects."""
    name, index, features, classes, groups, fold, seed, alternative = task
    test = np.isin(groups, fold)
    train = ~test
    choice = choose_c(features[train], classes[train], groups[train], seed)
    model = fit_model(features[train], classes[train], choice["C"])
    report = {
        "fold": index,
        "train_subjects": sorted(set(groups[train].tolist())),
        "test_subjects": sorted(fold),
        "C": choice["C"],
        "inner_log_loss": choice["inner_log_loss"],
        "inner_auc": choice["inner_auc"],
        "test_windows": int(test.sum()),
    }
    other = ff.predict_proba(alternative[test], model) if alternative is not None else None
    return name, index, np.flatnonzero(test), ff.predict_proba(features[test], model), other, report


def cross_validate_many(
    feature_sets: Mapping[str, np.ndarray],
    classes: np.ndarray,
    groups: np.ndarray,
    outer_folds: list[list[str]],
    seed: int = SEED,
    alternatives: Mapping[str, np.ndarray] | None = None,
) -> dict[str, CrossValidation]:
    """Nested, subject-grouped validation of several feature sets on the same folds.

    ``alternatives`` maps a feature-set name to another matrix of the same rows. The models are trained
    on the feature set as usual; each fold's model then also scores its test rows as the alternative
    matrix describes them (``alternative_proba``). Training never sees the alternative.
    """
    from threadpoolctl import threadpool_limits

    alternatives = alternatives or {}
    tasks = [
        (name, index, features, classes, groups, fold, seed, alternatives.get(name))
        for name, features in feature_sets.items()
        for index, fold in enumerate(outer_folds)
    ]
    # These fits are small (thousands of rows, seven columns): BLAS threads only get in each other's way.
    with threadpool_limits(limits=1):
        outcomes = [_outer_fold(task) for task in tasks]
    results = {
        name: CrossValidation(
            proba=np.full((len(classes), N_CLASSES), np.nan),
            folds=[None] * len(outer_folds),
            alternative_proba=np.full((len(classes), N_CLASSES), np.nan) if name in alternatives else None,
        )
        for name in feature_sets
    }
    for name, index, rows, proba, other, report in outcomes:
        results[name].proba[rows] = proba
        results[name].folds[index] = report
        if other is not None:
            results[name].alternative_proba[rows] = other
    return results


def nested_selection(cross: Mapping[str, CrossValidation], groups: np.ndarray, outer_folds: list[list[str]]) -> tuple[np.ndarray, list[str]]:
    """Out-of-fold probabilities when the feature set itself is chosen inside every fold.

    For each outer fold the feature set with the best INNER AUC (training subjects only) scores that
    fold's test subjects; ties go to the first name. Returns the probabilities and the name picked per fold.
    """
    names = list(cross)
    proba = np.full_like(cross[names[0]].proba, np.nan)
    picks: list[str] = []
    for index, fold in enumerate(outer_folds):
        pick = max(names, key=lambda name: cross[name].folds[index]["inner_auc"])
        picks.append(pick)
        test = np.isin(groups, fold)
        proba[test] = cross[pick].proba[test]
    return proba, picks


def cross_validate(
    features: np.ndarray,
    classes: np.ndarray,
    groups: np.ndarray,
    outer_folds: list[list[str]],
    seed: int = SEED,
) -> CrossValidation:
    """Nested, subject-grouped validation of one feature set."""
    return cross_validate_many({"features": features}, classes, groups, outer_folds, seed)["features"]


# --------------------------------------------------------------------------- metrics


def confusion_matrix(classes: np.ndarray, predicted: np.ndarray) -> list[list[int]]:
    matrix = [[0] * N_CLASSES for _ in range(N_CLASSES)]
    for truth, guess in zip(classes.tolist(), predicted.tolist()):
        matrix[int(truth)][int(guess)] += 1
    return matrix


def macro_f1(classes: np.ndarray, predicted: np.ndarray) -> float:
    scores = []
    for k in range(N_CLASSES):
        true_positive = int(((classes == k) & (predicted == k)).sum())
        false_positive = int(((classes != k) & (predicted == k)).sum())
        false_negative = int(((classes == k) & (predicted != k)).sum())
        denominator = 2 * true_positive + false_positive + false_negative
        scores.append(2 * true_positive / denominator if denominator else 0.0)
    return float(np.mean(scores))


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    from scipy.stats import spearmanr

    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return math.nan
    return float(spearmanr(a, b).statistic)


def classification_metrics(classes: np.ndarray, proba: np.ndarray) -> dict:
    """Three-class metrics of out-of-fold probabilities."""
    predicted = proba.argmax(axis=1)
    matrix = confusion_matrix(classes, predicted)
    return {
        "windows": int(len(classes)),
        "macro_f1": macro_f1(classes, predicted),
        "auc": macro_auc(classes, proba),
        "accuracy": float((predicted == classes).mean()),
        "log_loss": log_loss(classes, proba),
        "confusion_matrix": matrix,
        "recall": {name: (matrix[k][k] / sum(matrix[k]) if sum(matrix[k]) else None) for k, name in enumerate(ff.CLASS_NAMES)},
    }


def score_metrics(classes: np.ndarray, score: np.ndarray) -> dict:
    """How well one number in [0, 1] orders the three states. Works for any scalar score."""
    alert, drowsy = classes == 0, classes == 2
    ends = alert | drowsy
    return {
        "auc_alert_vs_drowsy": binary_auc(drowsy[ends], score[ends]),
        "auc_alert_vs_rest": binary_auc(~alert, score),
        "auc_drowsy_vs_rest": binary_auc(drowsy, score),
        "spearman_with_label": spearman(score, classes.astype(float)),
        "mean_score": {name: (float(score[classes == k].mean()) if (classes == k).any() else None) for k, name in enumerate(ff.CLASS_NAMES)},
        # Where the score actually lives: whoever puts a threshold on it needs the range, not only the order.
        "percentiles": {
            name: ({f"p{q}": float(np.percentile(score[classes == k], q)) for q in (5, 25, 50, 75, 95)} if (classes == k).any() else None)
            for k, name in enumerate(ff.CLASS_NAMES)
        },
        "min": float(score.min()),
        "max": float(score.max()),
    }


def video_predictions(classes: np.ndarray, proba: np.ndarray, video_ids: np.ndarray) -> list[dict]:
    """One prediction per video: the class most of its windows got (ties: the higher mean probability)."""
    predicted = proba.argmax(axis=1)
    rows = []
    for video in sorted(set(video_ids.tolist())):
        own = video_ids == video
        votes = np.bincount(predicted[own], minlength=N_CLASSES)
        best = np.flatnonzero(votes == votes.max())
        choice = int(best[np.argmax(proba[own][:, best].mean(axis=0))]) if len(best) > 1 else int(best[0])
        rows.append(
            {
                "video_id": video,
                "true": int(classes[own][0]),
                "predicted": choice,
                "windows": int(own.sum()),
                "votes": votes.tolist(),
                "mean_fatigue_score": float(ff.fatigue_score(proba[own]).mean()),
            }
        )
    return rows


def video_level_metrics(rows: Sequence[dict]) -> dict:
    truth = np.array([r["true"] for r in rows])
    guess = np.array([r["predicted"] for r in rows])
    return {
        "videos": len(rows),
        "correct": int((truth == guess).sum()),
        "accuracy": float((truth == guess).mean()) if len(rows) else None,
        "confusion_matrix": confusion_matrix(truth, guess),
        "rule": "a video gets the class most of its windows got; ties go to the class with the higher mean probability",
    }


def per_subject(classes: np.ndarray, proba: np.ndarray, groups: np.ndarray, video_ids: np.ndarray, baseline: np.ndarray) -> list[dict]:
    """Out-of-fold results of each subject, next to what the browser's formula does on the same windows."""
    score = ff.fatigue_score(proba)
    predicted = proba.argmax(axis=1)
    rows = []
    for subject in sorted(set(groups.tolist())):
        own = groups == subject
        y = classes[own]
        ends = (y == 0) | (y == 2)
        videos = video_predictions(y, proba[own], video_ids[own])
        mean_score = {ff.CLASS_NAMES[k]: (float(score[own][y == k].mean()) if (y == k).any() else None) for k in range(N_CLASSES)}
        mean_baseline = {ff.CLASS_NAMES[k]: (float(baseline[own][y == k].mean()) if (y == k).any() else None) for k in range(N_CLASSES)}
        rows.append(
            {
                "subject": subject,
                "windows": {ff.CLASS_NAMES[k]: int((y == k).sum()) for k in range(N_CLASSES)},
                "accuracy": float((predicted[own] == y).mean()),
                "macro_f1": macro_f1(y, predicted[own]),
                "auc": macro_auc(y, proba[own]),
                "score_auc_alert_vs_drowsy": binary_auc((y == 2)[ends], score[own][ends]),
                "baseline_auc_alert_vs_drowsy": binary_auc((y == 2)[ends], baseline[own][ends]),
                "mean_fatigue_score": mean_score,
                "mean_baseline_score": mean_baseline,
                "videos_correct": int(sum(v["true"] == v["predicted"] for v in videos)),
                "video_predictions": {ff.CLASS_NAMES[v["true"]]: ff.CLASS_NAMES[v["predicted"]] for v in videos},
            }
        )
    return rows


def ordering_counts(subject_rows: Sequence[dict], key: str) -> dict:
    """In how many subjects the drowsy video scores higher on average than the alert one, and so on."""
    pairs = {"drowsy_above_alert": ("drowsy", "alert"), "low_vigilance_above_alert": ("low_vigilance", "alert"), "drowsy_above_low_vigilance": ("drowsy", "low_vigilance")}
    result = {}
    for name, (high, low) in pairs.items():
        usable = [r for r in subject_rows if r[key][high] is not None and r[key][low] is not None]
        result[name] = {"subjects": int(sum(r[key][high] > r[key][low] for r in usable)), "of": len(usable)}
    return result


def subject_bootstrap(
    groups: np.ndarray,
    statistics: Callable[[np.ndarray], dict[str, float]],
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = SEED,
) -> dict[str, list[float] | None]:
    """95 % percentile intervals from resampling subjects with replacement.

    ``statistics`` receives the row indices of a resample and returns named numbers. Resampling whole
    subjects respects that the windows of a person (and of a video) are correlated.
    """
    subjects = sorted(set(groups.tolist()))
    rows_of = {s: np.flatnonzero(groups == s) for s in subjects}
    rng = np.random.default_rng(seed)
    collected: dict[str, list[float]] = {}
    for _ in range(resamples):
        drawn = rng.choice(len(subjects), size=len(subjects), replace=True)
        index = np.concatenate([rows_of[subjects[i]] for i in drawn])
        for name, value in statistics(index).items():
            collected.setdefault(name, []).append(value)
    intervals: dict[str, list[float] | None] = {}
    for name, values in collected.items():
        finite = np.array([v for v in values if v == v])
        intervals[name] = [float(np.percentile(finite, 2.5)), float(np.percentile(finite, 97.5))] if len(finite) >= 0.9 * resamples else None
    return intervals
