"""The fatigue model, end to end: ``make model`` (``cd data && uv run python pipeline.py``).

    uv run python pipeline.py              # full run: writes fatigue_model.json, out/metrics.json, out/fatigue_report.md
    uv run python pipeline.py --limit 6    # smoke run on the first 6 subjects: writes everything under out/smoke/
    uv run python pipeline.py --no-drozy   # the same without the DROZY validation

Steps: find the RLDD videos, extract the face series with MediaPipe (cached per video in
``features/rldd/``; a second run reads the cache and never runs MediaPipe again), compute the window
features of ``fatigue_features.py``, validate the SHIPPED configuration (``SHIPPED`` below: a fixed setting,
not a choice made by any score) with subject-grouped folds, compare it with the browser's current formula,
refit it on every subject and write the outputs.

Then, when DROZY is on this machine (``data/raw/drozy/DROZY``), the refit model is applied unchanged to
DROZY's 14 people and its score is correlated with their PVT reaction times and KSS (``drozy.py``): that is
``pvt_correlation`` and ``drozy_validation`` in ``metrics.json``. Nothing is fitted on DROZY, and nothing
from it is cached: every run extracts it again (about 6 minutes with 5 processes on a 10-CPU laptop).

Without RLDD (no raw videos and no cache) there is nothing to train. If the shipped model and its metrics
are present and DROZY is here, the run validates THAT model on DROZY and merges the result into the
existing ``metrics.json`` and report, leaving ``fatigue_model.json`` and every RLDD number as they are.
With neither dataset it stops with an error and writes nothing.

Secondary analyses, kept because they are the evidence behind that setting: the same validation for the
three alternative combinations of eye method x normalisation, what a fold-internal choice among the four
would have scored, and what the EAR calibration is worth when it is not taken rested.

The written files hold no timestamps and no per-run timings, so running it again on the same cache
leaves them byte-identical.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from . import drozy, fatigue_features as ff, fatigue_model as fm, fatigue_report, landmarks, rldd
from .detector import YawnParams

DATA_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = DATA_DIR.parent
DEFAULT_ROOT = DATA_DIR / "raw" / "rldd"
DEFAULT_CACHE = DATA_DIR / "features" / "rldd"
DEFAULT_OUT = DATA_DIR / "out"
DEFAULT_MODEL_FILE = DATA_DIR / "fatigue_model.json"
DEFAULT_LANDMARKER = REPO_DIR / "frontend" / "public" / "mediapipe" / "face_landmarker.task"
YAWN_PARAMS_FILE = DATA_DIR / "out" / "yawn_params.json"

SOURCE_ID = "uta-rldd"  # key in shared/sources.json
BASELINE = "browser_formula"
OTHER = "auc_minus_other::"
MIN_SUBJECTS = 3

# The configuration that ships. FIXED: nothing in this pipeline chooses it, and no result can change it.
SHIPPED: tuple[str, str] = (ff.SHIPPED_EYE_METHOD, ff.SHIPPED_NORMALISATION)
DECISION = (
    "Product decision of the team, taken after seeing the four-way comparison, the fold-internal selection and the "
    "calibration sensitivity reported here: ship eye closure `blendshape` with `absolute` features, which is what "
    "faceWorker.ts already computes and needs no calibration. Reasons: it does not depend on how a session starts, and it "
    "is the only variant whose evaluation does not depend on a calibration recording. It is a fixed setting of the "
    "pipeline, not a selection on test folds."
)

# Every combination that is validated; all but SHIPPED are secondary analyses.
CONFIGURATIONS: tuple[tuple[str, str], ...] = (
    (ff.BLENDSHAPE, ff.ABSOLUTE),
    (ff.BLENDSHAPE, ff.CALIBRATED),
    (ff.EAR_P80, ff.ABSOLUTE),
    (ff.EAR_P80, ff.CALIBRATED),
)
# Constants only the evaluated alternatives use: they do not travel in the shipped model's `constants`.
ALTERNATIVE_CONSTANTS = ("p80_fraction", "ear_open_percentile", "ear_floor_percentile")

FEATURE_DEFINITIONS: dict[str, str] = {
    "perclos": "closed frames / frames with a face, in the window",
    "blink_rate_per_min": "eye closures shorter than 0.5 s, per observed minute",
    "mean_blink_duration_s": "mean duration of those short closures (last closed frame - first + one frame period); missing when there is none",
    "long_closure_rate_per_min": "eye closures of 0.5 s or more, per observed minute (assumption: the 0.5 s boundary)",
    "yawns_per_min": "yawns found in the window by the YawDD-calibrated detector (yawn_params.json), per window minute",
    "head_pitch_std_deg": "population standard deviation of the head pitch (degrees) over the frames with a face",
    "nods_per_min": "drops of the head at least 10 degrees below the window's median pitch (ending within 5), per observed minute (assumption: both levels)",
}


def log(message: str) -> None:
    print(message, flush=True)


def key(method: str, normalisation: str) -> str:
    return f"{method}/{normalisation}"


def clean(value):
    """JSON-ready copy: numpy types to Python, NaN to null, floats rounded so re-runs write the same bytes."""
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return None if not math.isfinite(number) else round(number, 6)
    return value


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(payload), indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def load_yawn_params(path: Path) -> tuple[YawnParams, dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    params = YawnParams(
        variant=raw["variant"],
        threshold=raw["threshold"],
        min_duration_s=raw["min_duration_s"],
        release_factor=raw["release_factor"],
        max_gap_s=raw["max_gap_s"],
        baseline_window_s=raw.get("baseline_window_s"),
    )
    return params, raw


# --------------------------------------------------------------------------- datasets


def feature_columns(method: str, normalisation: str) -> list[str]:
    prefix = method if normalisation == ff.ABSOLUTE else f"{method}_{ff.CALIBRATED}"
    return [rldd.column(prefix, name) for name in ff.FEATURE_NAMES]


def evaluation_rows(windows: pd.DataFrame, subjects: dict[str, dict]) -> pd.DataFrame:
    """The windows every configuration is trained and scored on.

    Usable windows of the subjects that could be calibrated, minus every window of the alert video that
    touches its first 120 s: those seconds are the calibration, so no configuration may be scored on them.
    """
    used = {s for s, info in subjects.items() if info["used"]}
    keep = windows["usable"] & ~windows["overlaps_calibration"] & windows["subject"].isin(used)
    return windows[keep].reset_index(drop=True)


def window_accounting(windows: pd.DataFrame, evaluated: pd.DataFrame) -> dict:
    by_state = {}
    for label, name in rldd.LABELS.items():
        own = windows[windows["label"] == label]
        by_state[name] = {
            "windows": int(len(own)),
            "dropped_low_face_or_few_frames": int((~own["usable"]).sum()),
            "calibration_period": int((own["usable"] & own["overlaps_calibration"]).sum()),
            "evaluated": int((evaluated["label"] == label).sum()),
        }
    return {
        "windows": int(len(windows)),
        "dropped_low_face_or_few_frames": int((~windows["usable"]).sum()),
        "calibration_period": int((windows["usable"] & windows["overlaps_calibration"]).sum()),
        "evaluated": int(len(evaluated)),
        "by_state": by_state,
    }


def feature_evidence(evaluated: pd.DataFrame, columns: list[str], resamples: int) -> dict:
    """What each feature shows on its own, with how sure that is: nothing is fitted, so nothing can leak.

    Per feature: the alert-vs-drowsy AUC of its raw value with a 95 % interval from resampling subjects,
    and in how many people the mean over the drowsy video is above the mean over the alert video.
    """
    classes = evaluated["class_index"].to_numpy()
    groups = evaluated["subject"].to_numpy()
    values = {name: evaluated[col].to_numpy(dtype=np.float64) for name, col in zip(ff.FEATURE_NAMES, columns)}

    def auc(name: str, index: np.ndarray) -> float:
        x, y = values[name][index], classes[index]
        ends = ~np.isnan(x) & (y != 1)
        return fm.binary_auc(y[ends] == 2, x[ends])

    everything = np.arange(len(classes))
    intervals = fm.subject_bootstrap(groups, lambda index: {name: auc(name, index) for name in values}, resamples)
    result = {}
    for name, x in values.items():
        higher = of = 0
        for subject in sorted(set(groups.tolist())):
            own = groups == subject
            alert, drowsy = x[own & (classes == 0)], x[own & (classes == 2)]
            if np.isnan(alert).all() or np.isnan(drowsy).all():
                continue
            of += 1
            higher += int(np.nanmean(drowsy) > np.nanmean(alert))
        result[name] = {
            "auc_alert_vs_drowsy": auc(name, everything),
            "ci95_subject_bootstrap": intervals.get(name),
            "subjects_higher_in_drowsy_video": {"subjects": higher, "of": of},
        }
    return result


def feature_statistics(evaluated: pd.DataFrame, columns: list[str]) -> dict:
    """Per feature: mean by state and how well it separates alert from drowsy windows on its own.

    Nothing is fitted here: an AUC of a raw feature needs no training, so there is no leakage. An AUC
    below 0.5 means the feature is LOWER in drowsy windows. Missing values are left out.
    """
    classes = evaluated["class_index"].to_numpy()
    result = {}
    for name, col in zip(ff.FEATURE_NAMES, columns):
        values = evaluated[col].to_numpy(dtype=np.float64)
        present = ~np.isnan(values)
        ends = present & (classes != 1)
        result[name] = {
            "mean": {
                state: (float(values[present & (classes == k)].mean()) if (present & (classes == k)).any() else None)
                for k, state in enumerate(ff.CLASS_NAMES)
            },
            "missing_share": float((~present).mean()),
            "auc_alert_vs_drowsy": fm.binary_auc(classes[ends] == 2, values[ends]),
            "spearman_with_label": fm.spearman(values[present], classes[present].astype(float)),
        }
    return result


# --------------------------------------------------------------------------- the run


def run(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    smoke = args.limit is not None
    out_dir = Path(args.out) if args.out else (DEFAULT_OUT / "smoke" if smoke else DEFAULT_OUT)
    model_file = out_dir / "fatigue_model.json" if smoke or args.out else DEFAULT_MODEL_FILE
    root, cache_dir, landmarker = Path(args.root), Path(args.cache), Path(args.landmarker)

    if not YAWN_PARAMS_FILE.is_file():
        log(f"MISSING: {YAWN_PARAMS_FILE} (run `make yawns` first: the yawn feature uses its calibration)")
        return 1
    if not landmarker.is_file():
        log(f"MISSING: {landmarker} (run `make prefetch`)")
        return 1
    yawn_params, yawn_raw = load_yawn_params(YAWN_PARAMS_FILE)

    # --- videos
    videos, others = rldd.discover(root) if root.is_dir() else ([], [])
    origin = f"{len(videos)} videos under {root}" if root.is_dir() else f"the raw folder {root} is not here"
    videos, cache_only = rldd.with_cached(videos, cache_dir)
    if cache_only:
        origin += f"; {len(cache_only)} more only in the cache {cache_dir}"
    if not videos:
        log(f"MISSING: no RLDD video under {root} and no cache in {cache_dir}. Download UTA-RLDD (docs/PREP.md) into data/raw/rldd/.")
        if smoke or not use_drozy(args):
            return 1
        return validate_existing(args, model_file, out_dir, landmarker, yawn_params, yawn_raw)
    log(f"RLDD: {origin}")
    if others:
        log(f"  ignored files that are not dataset videos: {others[:10]}{' ...' if len(others) > 10 else ''}")
    problems = rldd.completeness_problems(videos)
    for problem in problems:
        log(f"  INCOMPLETE {problem}")
    videos = [v for v in videos if v.subject in set(rldd.complete_subjects(videos))]
    videos = rldd.apply_limit(videos, args.limit)
    if smoke:
        log(f"  smoke run: the first {args.limit} subjects, {len(videos)} videos; outputs go to {out_dir}")

    # --- extraction (cached)
    series, failed, timing = rldd.extract_all(videos, root, landmarker, cache_dir, args.workers, args.force_extract)
    for failure in failed:
        log(f"  FAILED {failure['video']}: {failure['error']}")

    # --- per-frame signals and windows
    tick = time.perf_counter()
    signals = {video_id: rldd.signals_of(s) for video_id, s in series.items()}
    by_id = {v.video_id: v for v in videos}
    summaries = [rldd.video_summary(by_id[i], series[i], signals[i]) for i in sorted(series)]
    ear_checks = [rldd.ear_landmark_check(series[i]) for i in sorted(series)]
    windows, subjects = rldd.build_windows(videos, signals, yawn_params)
    if windows.empty:
        log("FAIL: no subject has its three videos extracted")
        return 1
    evaluated = evaluation_rows(windows, subjects)
    used_subjects = sorted(evaluated["subject"].unique())
    log(
        f"windows: {len(windows)} of 60 s every 10 s; {len(evaluated)} evaluated from {len(used_subjects)} subjects "
        f"({time.perf_counter() - tick:.0f} s)"
    )
    if len(used_subjects) < MIN_SUBJECTS:
        log(f"FAIL: {len(used_subjects)} usable subjects; subject-grouped validation needs at least {MIN_SUBJECTS}")
        return 1
    for row in summaries:
        own = windows[windows["video_id"] == f"{row['subject']}_{row['label']}"]
        row["windows"] = int(len(own))
        row["windows_dropped"] = int((~own["usable"]).sum())
        row["windows_evaluated"] = int((evaluated["video_id"] == f"{row['subject']}_{row['label']}").sum())

    classes = evaluated["class_index"].to_numpy()
    groups = evaluated["subject"].to_numpy()
    video_ids = evaluated["video_id"].to_numpy()
    baseline_score = evaluated["baseline_score"].to_numpy(dtype=np.float64)

    # --- validation: the shipped configuration, and the three alternatives as secondary analyses
    tick = time.perf_counter()
    outer = fm.subject_folds(used_subjects, args.folds)
    scheme = "leave-one-subject-out" if len(outer) == len(used_subjects) else f"{len(outer)} subject-grouped folds"
    log(f"validation: {scheme}, {len(outer)} folds; C from {list(fm.C_GRID)} by inner grouped folds on the training subjects")
    feature_sets = {
        key(method, normalisation): evaluated[feature_columns(method, normalisation)].to_numpy(dtype=np.float64)
        for method, normalisation in CONFIGURATIONS
    }
    # The browser's current formula goes through the same folds as a one-feature model (see `baseline` below).
    # The same ear_p80 models also score each test subject with the eye threshold taken from the scored video itself.
    own_features = evaluated[[rldd.column(rldd.OWN_VIDEO, name) for name in ff.FEATURE_NAMES]].to_numpy(dtype=np.float64)
    ear_absolute = key(ff.EAR_P80, ff.ABSOLUTE)
    blend_calibrated = key(ff.BLENDSHAPE, ff.CALIBRATED)
    own_reference = evaluated[[rldd.column(rldd.OWN_REFERENCE, name) for name in ff.FEATURE_NAMES]].to_numpy(dtype=np.float64)
    cross = fm.cross_validate_many(
        {**feature_sets, BASELINE: baseline_score[:, None]}, classes, groups, outer, alternatives={ear_absolute: own_features, blend_calibrated: own_reference}
    )
    baseline_cv = cross.pop(BASELINE)
    configurations: dict[str, dict] = {}
    for method, normalisation in CONFIGURATIONS:
        name = key(method, normalisation)
        metrics = fm.classification_metrics(classes, cross[name].proba)
        metrics["score"] = fm.score_metrics(classes, ff.fatigue_score(cross[name].proba))
        metrics["eye_method"], metrics["normalisation"] = method, normalisation
        metrics["C_by_fold"] = [fold["C"] for fold in cross[name].folds]
        metrics["folds_at_smallest_C"] = int(sum(fold["C"] == min(fm.C_GRID) for fold in cross[name].folds))
        configurations[name] = metrics
        log(
            f"  {name:24s} AUC {metrics['auc']:.3f}  macro F1 {metrics['macro_f1']:.3f}  accuracy {metrics['accuracy']:.3f}  "
            f"log loss {metrics['log_loss']:.3f}  alert-vs-drowsy AUC {metrics['score']['auc_alert_vs_drowsy']:.3f}"
        )
    chosen = key(*SHIPPED)  # fixed: no number above takes part in this
    method, normalisation = SHIPPED
    proba = cross[chosen].proba
    score = ff.fatigue_score(proba)
    ranking = sorted(configurations, key=lambda n: -configurations[n]["auc"])
    log(f"shipped (fixed setting, not selected): {chosen}")

    # --- secondary: what choosing among the four inside each fold, on the training subjects only, would score
    nested_proba, nested_picks = fm.nested_selection(cross, groups, outer)
    nested = fm.classification_metrics(classes, nested_proba)
    nested["score"] = fm.score_metrics(classes, ff.fatigue_score(nested_proba))
    nested["picked"] = {name: nested_picks.count(name) for name in configurations}
    nested["note"] = (
        "Secondary analysis, not the shipped model. If the configuration were chosen by a score, the honest way is "
        "inside every fold from the training subjects alone (inner AUC); this is what that procedure scores."
    )

    # --- what the alert-video calibration is worth: the eye threshold taken from the scored video instead
    after_start = ~evaluated["touches_first_120s"].to_numpy()
    later = after_start & ~np.isnan(own_features[:, 0]) & ~np.isnan(own_reference[:, 0])
    own_proba = cross[ear_absolute].alternative_proba
    own_reference_proba = cross[blend_calibrated].alternative_proba

    def brief(probabilities: np.ndarray) -> dict:
        metrics = fm.classification_metrics(classes[later], probabilities[later])
        scores = fm.score_metrics(classes[later], ff.fatigue_score(probabilities[later]))
        return {
            "auc": metrics["auc"],
            "macro_f1": metrics["macro_f1"],
            "accuracy": metrics["accuracy"],
            "score_auc_alert_vs_drowsy": scores["auc_alert_vs_drowsy"],
            "mean_score": scores["mean_score"],
        }

    def perclos_by_state(prefix: str) -> dict:
        values = evaluated[rldd.column(prefix, "perclos")].to_numpy(dtype=np.float64)
        return {state: float(values[later & (classes == k)].mean()) for k, state in enumerate(ff.CLASS_NAMES)}

    def sensitivity_statistics(index: np.ndarray) -> dict[str, float]:
        index = index[later[index]]
        y = classes[index]
        ends = y != 1
        usual = fm.binary_auc(y[ends] == 2, ff.fatigue_score(cross[ear_absolute].proba[index])[ends])
        own = fm.binary_auc(y[ends] == 2, ff.fatigue_score(own_proba[index])[ends])
        reference_usual = fm.binary_auc(y[ends] == 2, ff.fatigue_score(cross[blend_calibrated].proba[index])[ends])
        reference_own = fm.binary_auc(y[ends] == 2, ff.fatigue_score(own_reference_proba[index])[ends])
        return {
            "score_auc_alert_vs_drowsy_alert_video_minus_own_video": usual - own,
            "auc_alert_video_minus_own_video": fm.macro_auc(y, cross[ear_absolute].proba[index]) - fm.macro_auc(y, own_proba[index]),
            "calibrated_features_score_auc_alert_vs_drowsy_alert_video_minus_own_video": reference_usual - reference_own,
            "calibrated_features_auc_alert_video_minus_own_video": fm.macro_auc(y, cross[blend_calibrated].proba[index])
            - fm.macro_auc(y, own_reference_proba[index]),
        }

    ends_later = later & (classes != 1)
    sensitivity = {
        "question": (
            "ear_p80 takes its eye threshold from the first 120 s of the person's ALERT video. What if it comes from the first "
            "120 s of the video being scored, whatever state the person is in?"
        ),
        "how": (
            f"The out-of-fold `{ear_absolute}` models, unchanged (trained with the alert-video threshold); only the test subject's "
            "windows are recomputed with a threshold from each video's own first 120 s. Both versions are scored on the same "
            "windows: those that touch the first 120 s of no video."
        ),
        "windows": {state: int((later & (classes == k)).sum()) for k, state in enumerate(ff.CLASS_NAMES)},
        "windows_without_own_calibration": int((after_start & ~later).sum()),
        "calibrated_features": {
            "what": (
                f"The same question for the `calibrated` features: the out-of-fold `{blend_calibrated}` models, unchanged, with the "
                "test subject's reference taken from the first 120 s of each video instead of the alert video."
            ),
            "reference_from_alert_video": brief(cross[blend_calibrated].proba),
            "reference_from_scored_video": brief(own_reference_proba),
        },
        "threshold_from_alert_video": {**brief(cross[ear_absolute].proba), "perclos": perclos_by_state(ff.EAR_P80)},
        "threshold_from_scored_video": {**brief(own_proba), "perclos": perclos_by_state(rldd.OWN_VIDEO)},
        "blendshape_absolute_same_windows": {**brief(cross[key(ff.BLENDSHAPE, ff.ABSOLUTE)].proba), "perclos": perclos_by_state(ff.BLENDSHAPE)},
        "browser_formula_same_windows": {"score_auc_alert_vs_drowsy": fm.binary_auc(classes[ends_later] == 2, baseline_score[ends_later])},
        "ci95_subject_bootstrap": fm.subject_bootstrap(groups, sensitivity_statistics, args.bootstrap),
        "reading": (
            "RLDD has no recording that starts rested and then turns drowsy, so neither version is the product's case. "
            "The alert-video threshold assumes the calibration was taken rested; the scored-video threshold is what happens "
            "when the session starts with the person already in the state being measured."
        ),
    }

    # --- the browser's current formula on the same windows
    baseline = {
        "formula": ff.BROWSER_BASELINE_FORMULA,
        "what": "faceWorker.ts today: blendshape PERCLOS of the last minute, streaming yawn count, spread of the nose height over the last 90 frames",
        "score": fm.score_metrics(classes, baseline_score),
        "as_three_class_model": {
            **fm.classification_metrics(classes, baseline_cv.proba),
            "how": "the formula's number as the only feature of the same logistic regression, in the same folds: the best three-way split that number allows",
        },
        "share_of_windows_at_zero": float((baseline_score == 0).mean()),
    }
    model_score = fm.score_metrics(classes, score)

    def statistics(index: np.ndarray) -> dict[str, float]:
        y, p = classes[index], proba[index]
        ends = y != 1
        model_auc = fm.binary_auc(y[ends] == 2, score[index][ends])
        formula_auc = fm.binary_auc(y[ends] == 2, baseline_score[index][ends])
        three_class = fm.macro_auc(y, p)
        formula_three_class = fm.macro_auc(y, baseline_cv.proba[index])
        result = {
            "auc": three_class,
            "macro_f1": fm.macro_f1(y, p.argmax(axis=1)),
            "accuracy": float((p.argmax(axis=1) == y).mean()),
            "score_auc_alert_vs_drowsy": model_auc,
            "baseline_auc_alert_vs_drowsy": formula_auc,
            "score_minus_baseline_auc_alert_vs_drowsy": model_auc - formula_auc,
            "baseline_as_model_auc": formula_three_class,
            "auc_minus_baseline_as_model_auc": three_class - formula_three_class,
        }
        for other in others_than_chosen:
            result[OTHER + other] = three_class - fm.macro_auc(y, cross[other].proba[index])
        return result

    others_than_chosen = [name for name in configurations if name != chosen]
    intervals = fm.subject_bootstrap(groups, statistics, args.bootstrap)
    # How far the shipped configuration is from each alternative: its AUC minus theirs, resampling subjects.
    against_others = {
        other: {
            "auc_difference": configurations[chosen]["auc"] - configurations[other]["auc"],
            "ci95_subject_bootstrap": intervals.pop(OTHER + other),
        }
        for other in others_than_chosen
    }
    subject_rows = fm.per_subject(classes, proba, groups, video_ids, baseline_score)
    video_rows = fm.video_predictions(classes, proba, video_ids)
    baseline_video_rows = fm.video_predictions(classes, baseline_cv.proba, video_ids)
    log(f"validation done ({time.perf_counter() - tick:.0f} s)")

    # --- the model the browser gets: every subject, same settings
    final_features = feature_sets[chosen]
    with threadpool_limits(limits=1):
        final_choice = fm.choose_c(final_features, classes, groups)
        final = fm.fit_model(final_features, classes, final_choice["C"])

    counts = {name: int((classes == k).sum()) for k, name in enumerate(ff.CLASS_NAMES)}
    parts = sorted({v.part for v in videos if v.part})
    trained_on = (
        f"UTA-RLDD ({', '.join(parts)}): {len(evaluated)} windows of 60 s every 10 s from {len(video_rows)} videos of "
        f"{len(used_subjects)} subjects ({counts['alert']} alert, {counts['low_vigilance']} low vigilance, {counts['drowsy']} drowsy; "
        f"self-reported labels)"
    )
    chosen_metrics = configurations[chosen]
    face_landmarker = {
        "model_file_name": landmarker.name,
        "model_sha256": timing["model_sha256"],
        "running_mode": "VIDEO",
        "num_faces": landmarks.NUM_FACES,
        "min_face_detection_confidence": landmarks.MIN_FACE_DETECTION_CONFIDENCE,
        "min_face_presence_confidence": landmarks.MIN_FACE_PRESENCE_CONFIDENCE,
        "min_tracking_confidence": landmarks.MIN_TRACKING_CONFIDENCE,
        "output_face_blendshapes": True,
        "output_facial_transformation_matrixes": True,
        "target_fps": landmarks.TARGET_FPS,
    }
    eye_rules = {
        ff.BLENDSHAPE: f"closed when (eyeBlinkLeft + eyeBlinkRight) / 2 > {ff.BLENDSHAPE_CLOSED}",
        ff.EAR_P80: (
            f"closed when ear <= floor + {ff.P80_FRACTION} * (open - floor); open = P{ff.EAR_OPEN_PERCENTILE:g} and floor = "
            f"P{ff.EAR_FLOOR_PERCENTILE:g} of ear over the frames with a face in the first {ff.CALIBRATION_S:g} s"
        ),
    }
    normalisation_rules = {
        ff.ABSOLUTE: "features are used as computed",
        ff.CALIBRATED: (
            f"feature - reference, for every feature; reference = mean of the feature over the usable windows inside the "
            f"first {ff.CALIBRATION_S:g} s of the session (person rested), ignoring missing values"
        ),
    }
    needs_calibration = method == ff.EAR_P80 or normalisation == ff.CALIBRATED
    eye_closure = {
        "method": method,
        "rule": eye_rules[method],
        "needs_calibration": method == ff.EAR_P80,
        "same_as": "faceWorker.ts (BLINK = 0.5)" if method == ff.BLENDSHAPE else None,
    }
    normalisation_block = {
        "variant": normalisation,
        "rule": normalisation_rules[normalisation],
        "needs_calibration": normalisation == ff.CALIBRATED,
    }
    # Measured here, not shipped: kept in the file so nobody has to guess what was tried.
    evaluated_alternatives = {
        "status": "evaluated on RLDD, NOT shipped; the browser does not port them",
        "why_not": (
            "RLDD has one recording per state, so it cannot show what a calibration taken at the start of a session is worth. "
            "To be tried again on a dataset where one recording goes from rested to drowsy (DROZY, for example)."
        ),
        "eye_closure": {
            "method": ff.EAR_P80 if method == ff.BLENDSHAPE else ff.BLENDSHAPE,
            "rule": eye_rules[ff.EAR_P80 if method == ff.BLENDSHAPE else ff.BLENDSHAPE],
            "ear_landmarks": {"right_eye_p1_to_p6": list(ff.EAR_RIGHT_EYE), "left_eye_p1_to_p6": list(ff.EAR_LEFT_EYE)},
            "constants": {"p80_fraction": ff.P80_FRACTION, "ear_open_percentile": ff.EAR_OPEN_PERCENTILE, "ear_floor_percentile": ff.EAR_FLOOR_PERCENTILE},
        },
        "normalisation": {
            "variant": ff.CALIBRATED if normalisation == ff.ABSOLUTE else ff.ABSOLUTE,
            "rule": normalisation_rules[ff.CALIBRATED if normalisation == ff.ABSOLUTE else ff.ABSOLUTE],
        },
        "calibration_s": ff.CALIBRATION_S,
        "min_calibration_frames": ff.MIN_CALIBRATION_FRAMES,
        "results": "data/out/metrics.json: configurations, nested_selection, calibration_sensitivity",
    }
    constants = {
        "window_s": ff.WINDOW_S,
        "step_s": ff.STEP_S,
        "min_face_fraction": ff.MIN_FACE_FRACTION,
        "min_window_frames": ff.MIN_WINDOW_FRAMES,
        "max_gap_s": ff.MAX_GAP_S,
        "long_closure_s": ff.LONG_CLOSURE_S,
        "nod_on_deg": ff.NOD_ON_DEG,
        "nod_off_deg": ff.NOD_OFF_DEG,
        "pitch_down_sign": ff.PITCH_DOWN_SIGN,
        "blendshape_closed": ff.BLENDSHAPE_CLOSED,
        "p80_fraction": ff.P80_FRACTION,
        "ear_open_percentile": ff.EAR_OPEN_PERCENTILE,
        "ear_floor_percentile": ff.EAR_FLOOR_PERCENTILE,
        "assumptions": [
            "long_closure_s", "nod_on_deg", "nod_off_deg", "min_face_fraction", "min_window_frames",
            "ear_open_percentile", "ear_floor_percentile", "min_calibration_frames",
        ],
    }
    model_payload = {
        "schema": "pulsar.fatigue_model/1",
        "limit": args.limit,
        "features": list(ff.FEATURE_NAMES),
        "mean": final["mean"],
        "std": final["std"],
        "coef": final["coef"],
        "intercept": final["intercept"],
        "classes": list(ff.CLASS_NAMES),
        "trainedOn": trained_on,
        "score": {
            "name": "fatigueScore",
            "formula": ff.SCORE_FORMULA,
            "weights": dict(zip(ff.CLASS_NAMES, ff.SCORE_WEIGHTS)),
            "range": [0, 1],
            "meaning": "expected RLDD label (0 alert, 5 low vigilance, 10 drowsy) divided by 10",
        },
        "configuration": {"shipped": chosen, "decision": DECISION, "selected_on_test_folds": False},
        "calibration": {
            "required": needs_calibration,
            "note": (
                "None. The score is available from the first usable 60 s window." if not needs_calibration
                else f"The first {ff.CALIBRATION_S:g} s of the session, with the person rested; no score before it."
            ),
        },
        "inference": (
            f"Per processed frame: eye {eye_rules[method]}. Per usable 60 s window: the seven features ({normalisation_rules[normalisation]}); "
            "z = (x - mean) / std, with z = 0 for a missing feature; p = softmax(intercept + coef . z)."
            + (" No calibration step." if not needs_calibration else "")
        ),
        "features_version": ff.FEATURES_VERSION,
        "feature_definitions": FEATURE_DEFINITIONS,
        "feature_module": "data/pulsar_vision/fatigue_features.py",
        "eye_closure": eye_closure,
        "normalisation": normalisation_block,
        "constants": {
            k: (v if k != "assumptions" else [a for a in v if a not in ALTERNATIVE_CONSTANTS and a != "min_calibration_frames"])
            for k, v in constants.items()
            if needs_calibration or k not in ALTERNATIVE_CONSTANTS
        },
        "evaluated_alternatives": evaluated_alternatives,
        "yawn_detector": {
            "params_file": "data/out/yawn_params.json",
            "variant": yawn_raw["variant"],
            "threshold": yawn_raw["threshold"],
            "min_duration_s": yawn_raw["min_duration_s"],
            "release_factor": yawn_raw["release_factor"],
            "max_gap_s": yawn_raw["max_gap_s"],
        },
        "face_landmarker": face_landmarker,
        "regularisation": {"C": final["C"], "chosen_by": "lowest pooled log loss over 5 subject-grouped folds of all subjects", "grid": list(fm.C_GRID)},
        "validated": {
            "scheme": scheme,
            "subjects": len(used_subjects),
            "windows": int(len(evaluated)),
            "macro_f1": chosen_metrics["macro_f1"],
            "auc": chosen_metrics["auc"],
            "accuracy": chosen_metrics["accuracy"],
            "score_auc_alert_vs_drowsy": model_score["auc_alert_vs_drowsy"],
            "ci95_subject_bootstrap": {k: intervals[k] for k in ("auc", "macro_f1", "score_auc_alert_vs_drowsy")},
            "note": "out-of-fold numbers of this configuration; the weights above are a refit on every subject",
        },
        "not_a_medical_device": "It estimates signs consistent with drowsiness from self-reported labels. The rules engine decides.",
        "source": SOURCE_ID,
    }

    no_face = np.array([row["no_face_rate"] for row in summaries], dtype=np.float64)
    frames_total = int(sum(row["processed_frames"] for row in summaries))
    dataset = {
        "source": SOURCE_ID,
        "parts": parts,
        "videos": len(summaries),
        "subjects_found": len({v.subject for v in videos}),
        "subjects_used": len(used_subjects),
        "subjects_not_used": {s: info["reason"] for s, info in subjects.items() if not info["used"]},
        "incomplete_subjects": problems,
        "failed_videos": failed,
        "ignored_files": others,
        "hours_of_video": sum(row["duration_s"] for row in summaries) / 3600.0,
        "portrait_videos": int(sum(row["height"] > row["width"] for row in summaries)),
        "timestamp_fallback_frames": int(sum(row["timestamp_fallbacks"] for row in summaries)),
        "processed_frames": frames_total,
        "no_face": {
            "frames": int(sum(row["no_face_frames"] for row in summaries)),
            "rate_overall": float(sum(row["no_face_frames"] for row in summaries) / frames_total),
            "rate_per_video": {"median": float(np.median(no_face)), "max": float(no_face.max())},
            "videos_above_5_percent": [row["video"] for row in summaries if row["no_face_rate"] > 0.05],
        },
        "orientation": {
            "videos_with_rotation_flag": int(sum(row["orientation_meta_deg"] != 0 for row in summaries)),
            "max_abs_median_roll_deg": float(max(abs(row["roll_median_deg"]) for row in summaries if row["roll_median_deg"] is not None)),
            "videos_sideways": [row["video"] for row in summaries if row["roll_median_deg"] is not None and abs(row["roll_median_deg"]) > 45],
        },
        "processed_fps": {
            "min": float(min(row["processed_fps"] for row in summaries)),
            "median": float(np.median([row["processed_fps"] for row in summaries])),
            "max": float(max(row["processed_fps"] for row in summaries)),
            "videos_under_12": [row["video"] for row in summaries if row["processed_fps"] < 12.0],
            "videos_under_13": [row["video"] for row in summaries if row["processed_fps"] < 13.0],
        },
        "windows": window_accounting(windows, evaluated),
        "window_rule": (
            f"60 s windows every 10 s from the first frame; used when they hold at least {ff.MIN_WINDOW_FRAMES} frames and a face "
            f"in at least {ff.MIN_FACE_FRACTION:.0%} of them. Every window of the alert video that touches its first "
            f"{ff.CALIBRATION_S:g} s is left out, for training and for scoring: the calibrated alternatives use those seconds, "
            "and all four configurations are measured on the same windows. The shipped configuration does not use them for anything."
        ),
    }

    def pooled_check(name: str, field: str) -> float:
        total = sum(check[name]["frames"] for check in ear_checks if check[name])
        return float(sum(check[name][field] * check[name]["frames"] for check in ear_checks if check[name]) / total)

    layout = [rldd.matrix_layout_check(series[i]) for i in sorted(series)]
    pitch_checks = [row["pitch_vs_nose_position_correlation"] for row in summaries if row["pitch_vs_nose_position_correlation"] is not None]
    checks = {
        "ear_landmarks": {
            eye: {field: pooled_check(eye, field) for field in ("lid_points_between_corners", "upper_and_lower_lids_on_opposite_sides", "p2_faces_p6_and_p3_faces_p5", "upper_lid_above_lower_lid_in_image")}
            for eye in ("right", "left")
        },
        "ear_landmarks_note": "share of the frames with a face where the six points of each eye sit where the EAR formula assumes; lids can cross on a fully closed eye",
        "transformation_matrix": {
            "frames": int(sum(c["frames"] for c in layout)),
            "last_row_is_0_0_0_1": int(sum(c["last_row_is_0_0_0_1"] for c in layout)),
            "rotation_columns_share_one_scale": int(sum(c["rotation_columns_share_one_scale"] for c in layout)),
            "note": "row-major in Python with the translation in the last column; the browser's flat array is its transpose, so M[2][1] here is m[6] there",
        },
        "pitch_sign": {
            "videos": len(pitch_checks),
            "videos_with_positive_correlation": int(sum(c > 0 for c in pitch_checks)),
            "median_correlation": float(np.median(pitch_checks)) if pitch_checks else None,
            "note": "correlation between pitch_deg and how far down the nose tip sits between forehead and chin; positive supports PITCH_DOWN_SIGN = +1",
        },
    }

    calibrations = [info["ear_calibration"] for info in subjects.values() if info.get("ear_calibration")]
    eye_methods = {
        "perclos_by_state": {
            m: {state: float(evaluated.loc[evaluated["class_index"] == k, rldd.column(m, "perclos")].mean()) for k, state in enumerate(ff.CLASS_NAMES)}
            for m in ff.EYE_METHODS
        },
        "ear_calibration": {
            "open_median": float(np.median([c["open"] for c in calibrations])),
            "floor_median": float(np.median([c["floor"] for c in calibrations])),
            "threshold_range": [float(min(c["threshold"] for c in calibrations)), float(max(c["threshold"] for c in calibrations))],
            "floor_over_open_range": [float(min(c["floor"] / c["open"] for c in calibrations)), float(max(c["floor"] / c["open"] for c in calibrations))],
            "subjects_with_floor_above_half_open": int(sum(c["floor"] > 0.5 * c["open"] for c in calibrations)),
            "subjects": len(calibrations),
            "by_subject": {s: info["ear_calibration"] for s, info in sorted(subjects.items())},
        },
        "caveat": (
            "RLDD records the three states of a person as three separate videos, often on another day, device or camera angle. "
            "The EAR threshold and the calibration reference come from the alert video and are applied to the other two. The product "
            "calibrates at the start of the session it then monitors, a case RLDD does not contain; `calibration_sensitivity` measures "
            "what changes when the threshold comes from the scored recording itself."
        ),
    }

    metrics_payload = {
        "schema": "pulsar.fatigue_metrics/1",
        "limit": args.limit,
        # --- what goals/G2 asks for: the SHIPPED configuration, out of fold. No selection step produced these.
        "macro_f1": chosen_metrics["macro_f1"],
        "auc": chosen_metrics["auc"],
        "labels": list(ff.CLASS_NAMES),
        "confusion_matrix": chosen_metrics["confusion_matrix"],
        "confusion_matrix_note": "rows: true state, columns: predicted state, in the order of `labels`; counts of 60 s windows",
        "pvt_correlation": None,
        "pvt_correlation_note": "DROZY (video with PVT reaction times) is not downloaded, so the score has not been compared with any reaction time.",
        "folds": [
            {"fold": f["fold"], "train_subjects": f["train_subjects"], "test_subjects": f["test_subjects"], "C": f["C"], "test_windows": f["test_windows"]}
            for f in cross[chosen].folds
        ],
        # --- everything else
        "auc_definition": "macro average of the three one-vs-rest AUCs, on pooled out-of-fold windows",
        "validation": {
            "scheme": scheme,
            "folds": len(outer),
            "inner": f"C from {list(fm.C_GRID)} by lowest pooled log loss over {fm.INNER_FOLDS} subject-grouped folds of the training subjects",
            "seed": fm.SEED,
            "correlated_windows": (
                "Windows of a video overlap by 50 s and share one label: the window counts overstate the evidence. "
                "Intervals resample the subjects, not the windows."
            ),
        },
        "chosen": {
            "configuration": chosen,
            "eye_method": method,
            "normalisation": normalisation,
            "how": DECISION,
            "selected_on_test_folds": False,
            "rank_among_the_four_by_auc": ranking.index(chosen) + 1,
            **{k: chosen_metrics[k] for k in ("windows", "accuracy", "log_loss", "recall")},
            "score": model_score,
            "ci95_subject_bootstrap": intervals,
            "bootstrap_resamples": args.bootstrap,
            "auc_minus_other_configurations": against_others,
        },
        "feature_evidence": feature_evidence(evaluated, feature_columns(method, normalisation), args.bootstrap),
        # --- secondary analyses: the evidence the decision was taken on, not the shipped model
        "secondary_analyses": (
            "`configurations` (the shipped one and three alternatives on the same windows), `nested_selection` and "
            "`calibration_sensitivity` are secondary. The decision in `chosen.how` was taken after seeing them."
        ),
        "configurations": configurations,
        "nested_selection": nested,
        "calibration_sensitivity": sensitivity,
        "baseline": baseline,
        "video_level": {
            "model": fm.video_level_metrics(video_rows),
            "baseline_as_three_class_model": fm.video_level_metrics(baseline_video_rows),
            "videos": [{**row, "true": ff.CLASS_NAMES[row["true"]], "predicted": ff.CLASS_NAMES[row["predicted"]]} for row in video_rows],
        },
        "per_subject": subject_rows,
        "subject_ordering": {
            "model_mean_fatigue_score": fm.ordering_counts(subject_rows, "mean_fatigue_score"),
            "baseline_mean_score": fm.ordering_counts(subject_rows, "mean_baseline_score"),
        },
        "feature_statistics": {
            name: feature_statistics(evaluated, feature_columns(*name.split("/"))) for name in configurations
        },
        "final_model": {
            "file": "data/fatigue_model.json" if model_file == DEFAULT_MODEL_FILE else str(model_file),
            "C": final["C"],
            "log_loss_by_C": final_choice["log_loss_by_C"],
            "coef_standardised": {state: dict(zip(ff.FEATURE_NAMES, row)) for state, row in zip(ff.CLASS_NAMES, final["coef"])},
            "note": "refit on every subject; the metrics in this file are out of fold, not of this refit",
        },
        "features": {"version": ff.FEATURES_VERSION, "names": list(ff.FEATURE_NAMES), "definitions": FEATURE_DEFINITIONS, "constants": constants},
        "eye_methods": eye_methods,
        "checks": checks,
        "dataset": dataset,
        "subjects": {s: {k: v for k, v in info.items() if k != "ear_calibration"} for s, info in sorted(subjects.items())},
        "videos": summaries,
        "extraction": {
            "face_landmarker": face_landmarker,
            "mediapipe_ms_per_frame_mean": timing["mediapipe_ms_per_frame_mean"],
            "decode_plus_mediapipe_seconds_per_video": timing["decode_plus_mediapipe_seconds_per_video"],
            "decode_plus_mediapipe_seconds_sum": timing["decode_plus_mediapipe_seconds_sum"],
            "runs": timing["extraction_runs"],
            "note": timing["note"],
        },
    }

    # --- DROZY: the refit model, unchanged, against reaction times and KSS of people it never saw
    block = None
    if smoke or args.no_drozy:
        log("DROZY validation skipped (" + ("smoke run" if smoke else "--no-drozy") + ")")
    else:
        block = drozy_block(args, clean(model_payload), landmarker, yawn_params, yawn_raw)
    metrics_payload = drozy.merge(metrics_payload, block)

    write_json(model_file, model_payload)
    write_json(out_dir / "metrics.json", metrics_payload)
    report = fatigue_report.render(clean(metrics_payload), clean(model_payload))
    (out_dir / "fatigue_report.md").write_text(report, encoding="utf-8")

    interval = intervals["auc"]
    log(
        f"out of fold ({chosen}, the shipped setting): macro F1 {chosen_metrics['macro_f1']:.3f}, AUC {chosen_metrics['auc']:.3f}"
        + (f" (95 % subject bootstrap {interval[0]:.3f} to {interval[1]:.3f})" if interval else "")
        + f"; alert-vs-drowsy AUC {model_score['auc_alert_vs_drowsy']:.3f} vs {baseline['score']['auc_alert_vs_drowsy']:.3f} for the browser's formula"
    )
    log(f"wrote {model_file}, {out_dir / 'metrics.json'}, {out_dir / 'fatigue_report.md'}  (total {time.perf_counter() - started:.0f} s)")
    return 0


# --------------------------------------------------------------------------- DROZY


def use_drozy(args: argparse.Namespace) -> bool:
    return not args.no_drozy and drozy.available(Path(args.drozy_root))


def drozy_block(args: argparse.Namespace, model: dict, landmarker: Path, yawn_params: YawnParams, yawn_raw: dict) -> dict | None:
    """The ``drozy_validation`` block, or ``None`` when DROZY is not here (``pvt_correlation`` stays null)."""
    root = Path(args.drozy_root)
    try:
        return clean(drozy.validate_model(model, yawn_params, yawn_raw, root, landmarker, args.workers, log))
    except drozy.DatasetMissing as missing:
        log(f"DROZY validation skipped: {missing}")
        return None


def validate_existing(args: argparse.Namespace, model_file: Path, out_dir: Path, landmarker: Path, yawn_params: YawnParams, yawn_raw: dict) -> int:
    """No RLDD here: validate the model already in ``model_file`` on DROZY and merge into the existing outputs.

    ``fatigue_model.json`` is only read. ``metrics.json`` keeps every RLDD number and gets ``pvt_correlation`` and
    ``drozy_validation``; the report is rendered again from it. Refuses smoke outputs and a metrics file that does
    not describe that model.
    """
    metrics_file = out_dir / "metrics.json"
    if not (model_file.is_file() and metrics_file.is_file()):
        log(f"MISSING: no {model_file} and {metrics_file} to validate either; nothing to train and nothing to validate.")
        return 1
    model = json.loads(model_file.read_text(encoding="utf-8"))
    metrics = json.loads(metrics_file.read_text(encoding="utf-8"))
    if model.get("limit") is not None or metrics.get("limit") is not None:
        log(f"FAIL: {model_file} or {metrics_file} comes from a smoke run (--limit): not validated")
        return 1
    if model.get("validated", {}).get("auc") != metrics.get("auc") or model.get("regularisation", {}).get("C") != metrics.get("final_model", {}).get("C"):
        log(f"FAIL: {metrics_file} does not describe {model_file} (AUC or C differ): run `make model` where RLDD is")
        return 1
    log(f"RLDD is not here: training skipped. The existing {model_file.name} is validated on DROZY and left unchanged.")
    try:
        block = drozy_block(args, model, landmarker, yawn_params, yawn_raw)
    except ValueError as mismatch:
        log(f"FAIL: {mismatch}")
        return 1
    if block is None:
        return 1
    merged = drozy.merge(metrics, block)
    write_json(metrics_file, merged)
    (out_dir / "fatigue_report.md").write_text(fatigue_report.render(clean(merged), clean(model)), encoding="utf-8")
    log(
        f"DROZY ({drozy.CITATION}): pvt_correlation = {num(merged['pvt_correlation'])} (Spearman, {block['headline']['n_recordings']} tests); "
        f"wrote {metrics_file} and {out_dir / 'fatigue_report.md'}; {model_file} unchanged"
    )
    return 0


def num(value) -> str:
    return "n/a" if value is None else f"{value:+.3f}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train and validate the PULSAR fatigue model on UTA-RLDD.")
    parser.add_argument("--limit", type=int, default=None, help="smoke run on the first N subjects; writes under out/smoke/")
    parser.add_argument("--workers", type=int, default=rldd.default_workers(), help="MediaPipe worker processes")
    parser.add_argument("--folds", type=int, default=None, help="subject folds (default: leave-one-subject-out)")
    parser.add_argument("--bootstrap", type=int, default=fm.BOOTSTRAP_RESAMPLES, help="subject bootstrap resamples")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="RLDD folder")
    parser.add_argument("--cache", default=str(DEFAULT_CACHE), help="face series cache (git-ignored)")
    parser.add_argument("--landmarker", default=str(DEFAULT_LANDMARKER), help="face_landmarker.task")
    parser.add_argument("--out", default=None, help="output folder (default: out/, or out/smoke/ with --limit)")
    parser.add_argument("--force-extract", action="store_true", help="ignore the cache and run MediaPipe again")
    parser.add_argument("--drozy-root", default=str(drozy.DEFAULT_ROOT), help="DROZY folder (validation only, never cached)")
    parser.add_argument("--no-drozy", action="store_true", help="skip the DROZY validation")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < MIN_SUBJECTS:
        parser.error(f"--limit needs at least {MIN_SUBJECTS} subjects")
    return args


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
