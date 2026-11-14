"""Calibrate and evaluate yawn detection on the YawDD dataset, end to end.

    cd data && uv run python -m pulsar_vision.yawdd            # full run
    cd data && uv run python -m pulsar_vision.yawdd --limit 10 # smoke run, writes to out/smoke/

Steps: find and parse the videos, extract landmarks with MediaPipe (cached per video in
``features/yawdd/``), compute the mouth opening series, search threshold x minimum
duration on train folds with subject-grouped validation, measure on test folds, and write
``out/yawn_metrics.json``, ``out/yawn_params.json``, ``out/yawn_report.md`` and
``out/yawn_videos.csv``.

YawDD labels are per video, not per frame. Mirror is the labelled set; Dash has no time
annotations and is only described (yawns per minute), never scored.

Licence: YawDD is for non-commercial research only. This pipeline writes no frame, crop
or image anywhere; the cache holds landmark coordinates only and is git-ignored.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import calibration, detector, folds as folds_module, landmarks, mouth, yawdd_names
from .calibration import DEFAULT_GRID, Grid
from .detector import ABSOLUTE, RELATIVE, YawnParams
from .yawdd_names import DASH, MAIN_CONDITIONS, MIRROR, MIXED, NORMAL, TALKING, TALKING_YAWNING, YAWNING

DATA_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = DATA_DIR.parent
DEFAULT_ROOT = DATA_DIR / "raw" / "yawdd" / "YawDD dataset"
DEFAULT_MODEL = REPO_DIR / "frontend" / "public" / "mediapipe" / "face_landmarker.task"
DEFAULT_CACHE = DATA_DIR / "features" / "yawdd"
DEFAULT_OUT = DATA_DIR / "out"

SOURCE_ID = "yawdd"  # key in shared/sources.json
CITATION = (
    'S. Abtahi, M. Omidyeganeh, S. Shirmohammadi, and B. Hariri, "YawDD: A Yawning Detection Dataset", '
    "Proc. ACM Multimedia Systems, Singapore, March 19-21 2014."
)
LICENSE_NOTE = (
    "YawDD videos are for non-commercial and research purposes only. Screenshots are allowed only for the "
    "videos whose row in the dataset tables says so; this pipeline writes no frames, crops or images."
)

EXTRACTION_RUNS_FILE = "_extraction_runs.json"  # in the cache folder: when and how long MediaPipe ran

VARIANTS = (ABSOLUTE, RELATIVE)
DEFAULT_FOLDS = 5
DEFAULT_SEED = 2026

# Alternative mouth-opening measures, compared with the same procedure for information only.
# The product formula is the one in mouth.py; these are NOT used by the detector parameters.
ALTERNATIVE_GRIDS: dict[str, tuple[float, ...]] = {
    "inner_lip_gap_over_inner_mouth_width_2d_px": calibration._arange(0.10, 1.50, 0.05),
    "inner_lip_gap_over_outer_eye_corner_distance_3d": DEFAULT_GRID.thresholds,
    "jaw_open_blendshape": calibration._arange(0.10, 0.90, 0.025),
}


def log(message: str) -> None:
    print(message, flush=True)


# --------------------------------------------------------------------------- discovery


def discover(root: Path) -> tuple[list[yawdd_names.VideoName], list[str]]:
    """Parse every .avi under ``root``. Returns the videos and the non-video files found."""
    videos: list[yawdd_names.VideoName] = []
    others: list[str] = []
    unparsed: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if ".avi" not in path.name.lower():
            others.append(relative)
            continue
        try:
            videos.append(yawdd_names.parse_video_name(relative))
        except ValueError as error:
            unparsed.append(str(error))
    if unparsed:
        raise SystemExit("File names the parser does not know (handle them explicitly):\n  " + "\n  ".join(unparsed))
    videos.sort(key=lambda v: (v.camera, v.sex, v.number, v.relative_path))
    return videos, others


def apply_limit(videos: list[yawdd_names.VideoName], limit: int) -> list[yawdd_names.VideoName]:
    """Smoke subset: the first ``limit`` Mirror subjects (sexes alternating, all their videos)
    plus the first ``max(1, limit // 5)`` Dash videos."""
    mirror_subjects: list[str] = []
    by_sex = {
        sex: sorted({(v.number, v.subject_id) for v in videos if v.camera == MIRROR and v.sex == sex})
        for sex in ("F", "M")
    }
    for pair in zip(by_sex["F"], by_sex["M"]):
        mirror_subjects.extend(subject for _, subject in pair)
    keep = set(mirror_subjects[:limit])
    dash = [v for v in videos if v.camera == DASH][: max(1, limit // 5)]
    return [v for v in videos if v.subject_id in keep] + dash


# --------------------------------------------------------------------------- extraction

_MODEL_BYTES: bytes | None = None


def _init_worker(model_path: str, quiet: bool) -> None:
    global _MODEL_BYTES
    if quiet:
        # MediaPipe's C++ side prints three warning lines per FaceLandmarker straight to stderr
        # (over a thousand in a full run). Worker errors do not travel through stderr: a failing
        # video is caught in _extract_task and reported by the main process.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 2)
        os.close(devnull)
    _MODEL_BYTES = Path(model_path).read_bytes()


def _extract_task(task: tuple[str, str]) -> dict:
    video_path, cache_path = task
    try:
        series = landmarks.extract_video(Path(video_path), _MODEL_BYTES)
        if series.meta["processed_frames"] == 0:
            return {"ok": False, "error": "no frame could be decoded"}
        landmarks.save_series(series, Path(cache_path))
        return {"ok": True, "seconds": series.meta["total_seconds"], "frames": series.meta["processed_frames"]}
    except Exception as error:  # a bad file must not stop the other videos
        return {"ok": False, "error": f"{type(error).__name__}: {error}"}


def extract_all(
    videos: list[yawdd_names.VideoName],
    root: Path,
    model_path: Path,
    cache_dir: Path,
    workers: int,
    force: bool,
    executor: ProcessPoolExecutor,
) -> tuple[dict[str, landmarks.VideoSeries], list[dict], dict]:
    """Landmark series of every video, from the cache when it matches the current setup."""
    model_sha256 = landmarks.sha256_of(model_path.read_bytes())
    signature = landmarks.cache_signature(model_sha256)
    cache_path = {v.relative_path: cache_dir / f"{v.video_id}.npz" for v in videos}

    series: dict[str, landmarks.VideoSeries] = {}
    todo: list[yawdd_names.VideoName] = []
    for video in videos:
        cached = None if force else landmarks.load_series(cache_path[video.relative_path], signature)
        if cached is not None:
            series[video.relative_path] = cached
        else:
            todo.append(video)
    log(f"extraction: {len(series)} videos from cache, {len(todo)} to process with {workers} worker(s)")

    failed: list[dict] = []
    started = time.perf_counter()
    if todo:
        # Longest first, so the pool does not end with one worker on a long video.
        todo.sort(key=lambda v: -(root / v.relative_path).stat().st_size)
        futures = {
            executor.submit(_extract_task, (str(root / v.relative_path), str(cache_path[v.relative_path]))): v
            for v in todo
        }
        done_frames = 0
        for done, future in enumerate(as_completed(futures), start=1):
            video = futures[future]
            outcome = future.result()
            elapsed = time.perf_counter() - started
            eta = elapsed / done * (len(todo) - done)
            if outcome["ok"]:
                done_frames += outcome["frames"]
                log(
                    f"[{done:3d}/{len(todo)}] {video.relative_path}  frames={outcome['frames']}  "
                    f"{outcome['seconds']:.1f}s  elapsed={elapsed:.0f}s  eta~{eta:.0f}s"
                )
                loaded = landmarks.load_series(cache_path[video.relative_path], signature)
                if loaded is None:
                    failed.append({"video": video.relative_path, "error": "cache could not be read back"})
                else:
                    series[video.relative_path] = loaded
            else:
                log(f"[{done:3d}/{len(todo)}] FAILED {video.relative_path}: {outcome['error']}")
                failed.append({"video": video.relative_path, "error": outcome["error"]})
    wall = time.perf_counter() - started

    # The wall time of an extraction is only known when it happens: keep it next to the cache,
    # so a later run that reads everything from the cache can still report it.
    runs_path = cache_dir / EXTRACTION_RUNS_FILE
    extraction_runs: list[dict] = []
    if runs_path.is_file():
        try:
            extraction_runs = json.loads(runs_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            extraction_runs = []
    if todo:
        extraction_runs.append(
            {
                "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "videos": len(todo) - len(failed),
                "frames": done_frames,
                "wall_seconds": round(wall, 1),
                "workers": workers,
            }
        )
        cache_dir.mkdir(parents=True, exist_ok=True)
        runs_path.write_text(json.dumps(extraction_runs, indent=2) + "\n", encoding="utf-8")

    metas = [s.meta for s in series.values()]
    frames = sum(m["processed_frames"] for m in metas)
    mediapipe_seconds = sum(m["mediapipe_seconds"] for m in metas)
    timing = {
        "videos_from_cache_this_run": len(videos) - len(todo),
        "videos_extracted_this_run": len(todo) - len(failed),
        "extraction_wall_seconds_this_run": wall if todo else 0.0,
        "extraction_runs": extraction_runs,
        "workers": workers,
        "processed_frames": frames,
        # Measured when each video was extracted (kept in its cache file), summed over videos:
        "mediapipe_seconds_sum": mediapipe_seconds,
        "decode_plus_mediapipe_seconds_sum": sum(m["total_seconds"] for m in metas),
        "mediapipe_ms_per_frame_mean": (1000.0 * mediapipe_seconds / frames) if frames else None,
        "note": (
            "Per-frame time is FaceLandmarker.detect_for_video in Python on this machine's CPU, "
            "measured while several worker processes ran at once. It is not a browser measurement."
        ),
    }
    return series, failed, {"model_sha256": model_sha256, **timing}


# --------------------------------------------------------------------------- features


def alternative_feature(name: str, series: landmarks.VideoSeries) -> np.ndarray:
    """Other mouth-opening measures, for the information-only comparison."""
    width, height = series.meta["width"], series.meta["height"]
    upper = series.points(mouth.UPPER_INNER_LIP).astype(np.float64)
    lower = series.points(mouth.LOWER_INNER_LIP).astype(np.float64)
    if name == "inner_lip_gap_over_inner_mouth_width_2d_px":
        return mouth.mouth_open_ratio_from_points(upper, lower, series.points(78), series.points(308), width, height)
    if name == "inner_lip_gap_over_outer_eye_corner_distance_3d":
        # MediaPipe's z uses roughly the same scale as x, so all three axes go to pixels with the width for z.
        scale = np.array([width, height, width], dtype=np.float64)
        right = series.points(mouth.RIGHT_EYE_OUTER).astype(np.float64)
        left = series.points(mouth.LEFT_EYE_OUTER).astype(np.float64)
        gap = np.linalg.norm((upper - lower) * scale, axis=-1)
        eyes = np.linalg.norm((right - left) * scale, axis=-1)
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(eyes > 0, gap / eyes, np.nan)
    if name == "jaw_open_blendshape":
        return series.jaw_open.astype(np.float64)
    raise KeyError(name)


def _count_task(task: tuple[np.ndarray, dict[str, np.ndarray], dict[str, Grid], Grid]) -> dict[str, np.ndarray]:
    """Yawn counts of one video for every candidate: both variants on the product feature,
    the absolute variant on each alternative feature."""
    times, features, alternative_grids, grid = task
    counts = {
        ABSOLUTE: calibration.count_yawns_grid(times, features["product"], grid, ABSOLUTE),
        RELATIVE: calibration.count_yawns_grid(times, features["product"], grid, RELATIVE),
    }
    for name, alternative_grid in alternative_grids.items():
        counts[name] = calibration.count_yawns_grid(times, features[name], alternative_grid, ABSOLUTE)
    return counts


# --------------------------------------------------------------------------- validation


def cross_validate(
    count_matrix: np.ndarray,
    params: list[YawnParams],
    grid: Grid,
    conditions: np.ndarray,
    minutes: np.ndarray,
    fold_of_video: np.ndarray,
    main: np.ndarray,
    n_folds: int,
) -> tuple[np.ndarray, list[dict]]:
    """Search the grid on the train folds, count yawns on the test fold with the winner.

    Returns the out-of-fold yawn count of every Mirror video (-1 where a video is in no fold)
    and one report per fold.
    """
    out_of_fold = np.full(count_matrix.shape[1], -1, dtype=np.int64)
    reports: list[dict] = []
    for fold in range(n_folds):
        train = main & (fold_of_video >= 0) & (fold_of_video != fold)
        test = fold_of_video == fold
        scores = calibration.candidate_scores(count_matrix, conditions, train)
        best = calibration.select_candidate(scores, params, grid)
        out_of_fold[test] = count_matrix[best, test]
        test_main = test & main
        reports.append(
            {
                "fold": fold,
                "params": params[best].to_dict(),
                "train_score": float(scores[best]),
                "candidates_tied_on_train": int((scores >= scores[best] - 1e-12).sum()),
                "test": calibration.video_metrics(count_matrix[best, test_main], conditions[test_main], minutes[test_main]),
            }
        )
    return out_of_fold, reports


def breakdown(table: pd.DataFrame, column: str, yawns: np.ndarray) -> dict:
    result = {}
    for value in sorted(table[column].unique()):
        rows = (table[column] == value).to_numpy()
        result[value] = calibration.video_metrics(yawns[rows], table["condition"].to_numpy()[rows], table["minutes"].to_numpy()[rows])
    return result


def evaluate_out_of_fold(table: pd.DataFrame, yawns: np.ndarray) -> dict:
    """Metrics from out-of-fold counts. ``table`` and ``yawns`` cover the Mirror videos."""
    conditions = table["condition"].to_numpy()
    minutes = table["minutes"].to_numpy()
    main = np.isin(conditions, MAIN_CONDITIONS)
    mixed = conditions == TALKING_YAWNING
    main_table = table[main]
    result = {
        "overall": calibration.video_metrics(yawns[main], conditions[main], minutes[main]),
        "by_eyewear": breakdown(main_table, "eyewear", yawns[main]),
        "by_facial_hair": breakdown(main_table, "facial_hair", yawns[main]),
        "by_sex": breakdown(main_table, "sex", yawns[main]),
        "talking_and_yawning_videos": {
            "note": "Reported apart; never used to choose parameters. Each should contain at least one yawn.",
            "with_detected_yawn": calibration.proportion(int((yawns[mixed] > 0).sum()), int(mixed.sum())),
            "detected_yawns": int(yawns[mixed].sum()),
            "yawns_per_minute": (float(yawns[mixed].sum() / minutes[mixed].sum()) if mixed.any() else None),
        },
    }
    return result


def no_face_rates(table: pd.DataFrame) -> dict:
    def rate(rows: pd.DataFrame) -> dict:
        frames = int(rows["processed_frames"].sum())
        missing = int(rows["no_face_frames"].sum())
        return {
            "videos": int(len(rows)),
            "frames": frames,
            "no_face_frames": missing,
            "rate": (missing / frames) if frames else None,
            "videos_with_any_no_face_frame": int((rows["no_face_frames"] > 0).sum()),
        }

    result: dict = {"by_camera_and_condition": {}, "by_camera_and_eyewear": {}}
    for (camera, condition), rows in table.groupby(["camera", "condition"]):
        result["by_camera_and_condition"][f"{camera}/{condition}"] = rate(rows)
    for (camera, eyewear), rows in table.groupby(["camera", "eyewear"]):
        result["by_camera_and_eyewear"][f"{camera}/{eyewear}"] = rate(rows)
    worst = table.assign(rate=table["no_face_frames"] / table["processed_frames"])
    worst = worst[worst["rate"] > 0.05].sort_values("rate", ascending=False)
    result["videos_over_5_percent"] = [
        {"video": row.relative_path, "rate": float(row.rate), "frames": int(row.processed_frames)}
        for row in worst.itertuples()
    ]
    return result


def no_face_gaps(ratios: list[np.ndarray], conditions: np.ndarray, open_threshold: float) -> dict:
    """Runs of consecutive frames without a face, and how many sit next to an open mouth.

    A run is "next to an open mouth" when the valid frame just before or just after it has
    a ratio at or above ``open_threshold``: the face was lost while the mouth was open.
    """
    result: dict = {"open_threshold": open_threshold, "by_condition": {}}
    lengths_all: list[int] = []
    for condition in sorted(set(conditions.tolist())):
        runs = 0
        beside_open = 0
        longest = 0
        for ratio in (r for r, c in zip(ratios, conditions) if c == condition):
            missing = np.isnan(ratio)
            i = 0
            while i < len(ratio):
                if not missing[i]:
                    i += 1
                    continue
                j = i
                while j < len(ratio) and missing[j]:
                    j += 1
                before = ratio[i - 1] if i > 0 else np.nan
                after = ratio[j] if j < len(ratio) else np.nan
                runs += 1
                longest = max(longest, j - i)
                lengths_all.append(j - i)
                if (before >= open_threshold) or (after >= open_threshold):
                    beside_open += 1
                i = j
        result["by_condition"][condition] = {"runs": runs, "runs_beside_open_mouth": beside_open, "longest_run_frames": longest}
    result["run_length_frames"] = quantiles(np.array(lengths_all, dtype=np.float64))
    return result


def error_videos(mirror_table: pd.DataFrame, column: str, fold_params: list[dict] | None) -> dict:
    """The Mirror videos a variant gets wrong out of fold, by name, with the mouth opening they reach."""

    def describe(row) -> dict:
        item = {
            "video": row.relative_path,
            "fold": int(row.fold),
            "detected_yawns": int(getattr(row, column)),
            "max_ratio": float(row.max_ratio),
            "no_face_rate": float(row.no_face_frames / row.processed_frames),
        }
        if fold_params is not None:  # absolute variant: was the fold's threshold ever reached?
            item["fold_threshold"] = fold_params[int(row.fold)]["threshold"]
            item["reaches_fold_threshold"] = bool(row.max_ratio >= item["fold_threshold"])
        return item

    yawns = mirror_table[column]
    missed = mirror_table[(mirror_table["condition"] == YAWNING) & (yawns == 0)]
    false_alarms = mirror_table[mirror_table["condition"].isin([TALKING, NORMAL]) & (yawns > 0)]
    result = {
        "missed_yawning_videos": [describe(row) for row in missed.itertuples()],
        "false_alarm_videos": [describe(row) for row in false_alarms.itertuples()],
    }
    if fold_params is not None:
        result["missed_never_reaching_fold_threshold"] = sum(
            not item["reaches_fold_threshold"] for item in result["missed_yawning_videos"]
        )
    return result


def quantiles(values: np.ndarray) -> dict | None:
    values = values[~np.isnan(values)]
    if not len(values):
        return None
    q = np.percentile(values, [0, 10, 25, 50, 75, 90, 100])
    return dict(zip(("min", "p10", "p25", "p50", "p75", "p90", "max"), (float(x) for x in q)))


# --------------------------------------------------------------------------- main


def run(args: argparse.Namespace) -> int:
    run_started = time.perf_counter()
    root: Path = args.data_root
    model_path: Path = args.model
    if not root.is_dir():
        raise SystemExit(f"YawDD not found at {root} (download it by hand, see docs/PREP.md; the folder is git-ignored)")
    if not model_path.is_file():
        raise SystemExit(f"FaceLandmarker model not found at {model_path} (run `make prefetch`)")

    videos, other_files = discover(root)
    found = len(videos)
    if args.limit:
        videos = apply_limit(videos, args.limit)
    out_dir: Path = args.out_dir / "smoke" if args.limit else args.out_dir
    cache_dir: Path = args.cache_dir
    log(f"YawDD: {found} videos found, {len(videos)} used" + (f" (--limit {args.limit})" if args.limit else ""))

    grid = DEFAULT_GRID
    initargs = (str(model_path), not args.mediapipe_log)
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker, initargs=initargs) as pool:
        series, failed, extraction = extract_all(videos, root, model_path, cache_dir, args.workers, args.force, pool)
        videos = [v for v in videos if v.relative_path in series]

        # ---- per-video series and table
        rows = []
        times: list[np.ndarray] = []
        features: list[dict[str, np.ndarray]] = []
        for video in videos:
            s = series[video.relative_path]
            ratio = s.mouth_open_ratio()
            times.append(s.time_s)
            features.append(
                {"product": ratio, **{name: alternative_feature(name, s) for name in ALTERNATIVE_GRIDS}}
            )
            rows.append(
                {
                    "relative_path": video.relative_path,
                    "camera": video.camera,
                    "subject_id": video.subject_id,
                    "sex": video.sex,
                    "eyewear": video.eyewear,
                    "facial_hair": video.facial_hair,
                    "condition": video.condition,
                    "source_fps": s.meta["source_fps"],
                    "processed_fps": s.meta["processed_fps"],
                    "frames_read": s.meta["frames_read"],
                    "reported_frames": s.meta["reported_frames"],
                    "processed_frames": s.meta["processed_frames"],
                    "no_face_frames": int((~s.face_found).sum()),
                    "minutes": s.meta["frames_read"] / s.meta["source_fps"] / 60.0,
                    "max_ratio": float(np.nanmax(ratio)) if np.isfinite(ratio).any() else np.nan,
                    "median_ratio": float(np.nanmedian(ratio)) if np.isfinite(ratio).any() else np.nan,
                }
            )
        table = pd.DataFrame(rows)

        # ---- yawn counts of every candidate on every video (computed once, folds only add up)
        calibration_started = time.perf_counter()
        alternative_grids = {
            name: Grid(thresholds, grid.min_durations_s, grid.release_factors, (), grid.max_gap_s)
            for name, thresholds in ALTERNATIVE_GRIDS.items()
        }
        tasks = [(times[i], features[i], alternative_grids, grid) for i in range(len(videos))]
        per_video = list(pool.map(_count_task, tasks, chunksize=4))
    count_matrices = {key: np.stack([c[key] for c in per_video], axis=1) for key in per_video[0]}
    candidate_lists = {
        ABSOLUTE: calibration.candidates(grid, ABSOLUTE),
        RELATIVE: calibration.candidates(grid, RELATIVE),
        **{name: calibration.candidates(g, ABSOLUTE) for name, g in alternative_grids.items()},
    }
    grids = {ABSOLUTE: grid, RELATIVE: grid, **alternative_grids}
    log(f"grid: {len(candidate_lists[ABSOLUTE])} absolute and {len(candidate_lists[RELATIVE])} relative candidates")

    # ---- folds (Mirror subjects only)
    conditions = table["condition"].to_numpy()
    minutes = table["minutes"].to_numpy()
    is_mirror = (table["camera"] == MIRROR).to_numpy()
    main = is_mirror & np.isin(conditions, MAIN_CONDITIONS)
    strata = {row.subject_id: row.sex for row in table[is_mirror].itertuples()}
    n_folds = min(args.folds, len(strata))
    fold_subjects = folds_module.grouped_folds(strata, n_folds, args.seed)
    folds_module.assert_disjoint(fold_subjects)
    fold_of_subject = {subject: k for k, fold in enumerate(fold_subjects) for subject in fold}
    fold_of_video = np.array([fold_of_subject.get(s, -1) for s in table["subject_id"]], dtype=np.int64)
    table["fold"] = fold_of_video

    # ---- validation, per variant
    mirror_table = table[is_mirror].reset_index(drop=True)
    results: dict = {}
    out_of_fold: dict[str, np.ndarray] = {}
    fold_reports: dict[str, list[dict]] = {}
    for variant in VARIANTS:
        out_of_fold[variant], fold_reports[variant] = cross_validate(
            count_matrices[variant], candidate_lists[variant], grid, conditions, minutes, fold_of_video, main, n_folds
        )
        results[variant] = {
            **evaluate_out_of_fold(mirror_table, out_of_fold[variant][is_mirror]),
            "per_fold": fold_reports[variant],
        }
        table[f"yawns_out_of_fold_{variant}"] = out_of_fold[variant]
        results[variant]["errors"] = error_videos(
            table[is_mirror],
            f"yawns_out_of_fold_{variant}",
            [r["params"] for r in fold_reports[variant]] if variant == ABSOLUTE else None,
        )

    # Unbiased estimate of the whole procedure: the variant is also chosen on the train folds.
    nested = np.full(len(table), -1, dtype=np.int64)
    nested_choice = []
    for fold in range(n_folds):
        chosen = max(VARIANTS, key=lambda v: (fold_reports[v][fold]["train_score"], v == ABSOLUTE))
        nested_choice.append(chosen)
        test = fold_of_video == fold
        nested[test] = out_of_fold[chosen][test]
    results["variant_chosen_on_train_folds"] = {
        "note": "Per fold, the variant with the higher train score (absolute on a tie) is applied to the test fold.",
        "variant_per_fold": nested_choice,
        **evaluate_out_of_fold(mirror_table, nested[is_mirror]),
    }

    scores = {variant: results[variant]["overall"]["score"] for variant in VARIANTS}
    chosen_variant = RELATIVE if scores[RELATIVE] > scores[ABSOLUTE] + 1e-12 else ABSOLUTE
    results["chosen_variant"] = chosen_variant
    results["chosen_by"] = (
        "Higher out-of-fold selection score (recall on Yawning minus the mean false-alarm rate on Talking and "
        "Normal); absolute on a tie because it needs no baseline. Choosing between two variants on the "
        "out-of-fold score is slightly optimistic; see variant_chosen_on_train_folds for the estimate without it."
    )
    results["out_of_fold_score"] = scores

    # ---- final parameters: the same search on every labelled Mirror video
    final: dict = {}
    final_params: dict[str, YawnParams] = {}
    for variant in VARIANTS:
        all_scores = calibration.candidate_scores(count_matrices[variant], conditions, main)
        best = calibration.select_candidate(all_scores, candidate_lists[variant], grid)
        final_params[variant] = candidate_lists[variant][best]
        table[f"yawns_final_{variant}"] = count_matrices[variant][best]
        final[variant] = {
            "params": final_params[variant].to_dict(),
            "candidates_tied": int((all_scores >= all_scores[best] - 1e-12).sum()),
            "in_sample_metrics": {
                "note": "Same videos used to choose the parameters: optimistic, not a validation result.",
                **calibration.video_metrics(count_matrices[variant][best, main], conditions[main], minutes[main]),
            },
        }

    # ---- how long the mouth stays open at the final threshold, per condition
    params = final_params[chosen_variant]
    longest = []
    baselines = {window: [] for window in grid.baseline_windows_s}
    first_open_start = []
    for i in range(len(videos)):
        ratio = features[i]["product"]
        baseline = (
            detector.baseline_ratio(times[i], ratio, params.baseline_window_s) if params.variant == RELATIVE else 0.0
        )
        on, off = detector.thresholds(params, baseline)
        episodes = detector.open_episodes(times[i], ratio, on, off, params.max_gap_s)
        longest.append(max((e.duration_s for e in episodes), default=0.0))
        # Where the first yawn starts is always measured with the absolute detector: it does not
        # depend on the baseline whose calmness is being checked.
        yawns = detector.detect_yawns(times[i], ratio, final_params[ABSOLUTE])
        first_valid = times[i][np.isfinite(ratio)]
        first_open_start.append(yawns[0].start_s - first_valid[0] if yawns and len(first_valid) else np.nan)
        for window in baselines:
            baselines[window].append(detector.baseline_ratio(times[i], ratio, window))
    table["longest_open_s_final"] = longest
    longest_array = np.array(longest)
    longest_by_condition = {
        condition: quantiles(longest_array[is_mirror & (conditions == condition)])
        for condition in (*MAIN_CONDITIONS, TALKING_YAWNING)
    }

    # ---- is the start of a video calm? (what the relative variant assumes)
    baseline_check: dict = {
        "note": (
            "The relative variant takes the median ratio of the first seconds as the person's resting mouth. "
            "YawDD does not guarantee a calm start: the numbers below measure it."
        ),
        "baseline_by_window_and_condition": {},
        "yawning_videos_first_yawn_inside_window": {},
    }
    starts = np.array(first_open_start)
    yawning_rows = is_mirror & (conditions == YAWNING)
    for window, values in baselines.items():
        values_array = np.array(values)
        table[f"baseline_{window:g}s"] = values_array
        baseline_check["baseline_by_window_and_condition"][f"{window:g}s"] = {
            condition: quantiles(values_array[is_mirror & (conditions == condition)]) for condition in MAIN_CONDITIONS
        }
        with np.errstate(invalid="ignore"):
            inside = int((starts[yawning_rows] < window).sum())
        baseline_check["yawning_videos_first_yawn_inside_window"][f"{window:g}s"] = calibration.proportion(
            inside, int(np.isfinite(starts[yawning_rows]).sum())
        )
    baseline_check["first_yawn_measured_with"] = "final absolute parameters; Yawning videos with a detected yawn only"

    # ---- Dash: descriptive only
    dash_rows = table[table["camera"] == DASH]
    dash: dict = {
        "note": (
            "Dash videos mix normal, talking and yawning with no time annotations. These are counts of what the "
            "detector fires on, with the final parameters; they are not an accuracy measurement."
        ),
        "videos": int(len(dash_rows)),
    }
    for variant in VARIANTS:
        counts = dash_rows[f"yawns_final_{variant}"].to_numpy()
        per_minute = counts / dash_rows["minutes"].to_numpy() if len(dash_rows) else np.array([])
        dash[variant] = {
            "total_yawns": int(counts.sum()),
            "total_minutes": float(dash_rows["minutes"].sum()),
            "yawns_per_minute_pooled": (float(counts.sum() / dash_rows["minutes"].sum()) if len(dash_rows) else None),
            "yawns_per_minute_per_video": quantiles(per_minute.astype(np.float64)),
            "videos_with_detected_yawn": int((counts > 0).sum()),
            "per_video": [
                {
                    "video": row.relative_path,
                    "minutes": round(float(row.minutes), 3),
                    "yawns": int(getattr(row, f"yawns_final_{variant}")),
                    "yawns_per_minute": round(float(getattr(row, f"yawns_final_{variant}") / row.minutes), 3),
                }
                for row in dash_rows.itertuples()
            ],
        }

    # ---- max_gap_s is fixed, not searched: measure how much the result depends on it
    mirror_index = np.flatnonzero(is_mirror)
    gap_sensitivity: dict = {
        "note": (
            "Out-of-fold result of the absolute variant if max_gap_s had another value (same folds, same search). "
            "max_gap_s must exceed the time between two processed frames, or no stretch can ever last."
        ),
        "values": {},
    }
    for max_gap in (0.25, 0.5, 1.0):
        gap_grid = Grid(grid.thresholds, grid.min_durations_s, grid.release_factors, grid.baseline_windows_s, max_gap)
        gap_candidates = calibration.candidates(gap_grid, ABSOLUTE)
        gap_counts = np.zeros((len(gap_candidates), len(videos)), dtype=np.int32)
        for i in mirror_index:
            gap_counts[:, i] = calibration.count_yawns_grid(times[i], features[i]["product"], gap_grid, ABSOLUTE)
        counts, _ = cross_validate(gap_counts, gap_candidates, gap_grid, conditions, minutes, fold_of_video, main, n_folds)
        overall = calibration.video_metrics(counts[main], conditions[main], minutes[main])
        gap_sensitivity["values"][f"{max_gap:g}"] = {
            k: overall[k] for k in ("yawning_recall", "talking_false_alarm", "normal_false_alarm", "score")
        }

    no_face = no_face_rates(table)
    no_face["runs_of_frames_without_a_face"] = {
        "note": "Mirror videos. A run next to an open mouth means the face was lost while the mouth was open.",
        **no_face_gaps(
            [features[i]["product"] for i in mirror_index],
            conditions[mirror_index],
            final_params[ABSOLUTE].threshold,
        ),
    }

    # ---- alternative features, information only
    alternatives: dict = {
        "note": (
            "Same folds, same search, absolute thresholds. For information only: the detector parameters use the "
            "product formula. Each row is the out-of-fold result if that measure replaced it."
        ),
        "product_formula_absolute": {k: results[ABSOLUTE]["overall"][k] for k in ("yawning_recall", "talking_false_alarm", "normal_false_alarm", "score")},
    }
    for name in ALTERNATIVE_GRIDS:
        counts, reports = cross_validate(
            count_matrices[name], candidate_lists[name], grids[name], conditions, minutes, fold_of_video, main, n_folds
        )
        overall = calibration.video_metrics(counts[main], conditions[main], minutes[main])
        alternatives[name] = {
            **{k: overall[k] for k in ("yawning_recall", "talking_false_alarm", "normal_false_alarm", "score")},
            "params_per_fold": [
                {k: r["params"][k] for k in ("threshold", "min_duration_s", "release_factor")} for r in reports
            ],
        }
    calibration_seconds = time.perf_counter() - calibration_started

    # ---- outputs
    per_condition: dict = {}
    for (camera, condition), group in table.groupby(["camera", "condition"]):
        per_condition.setdefault(camera, {})[condition] = int(len(group))
    truncated = table[table["frames_read"] < table["reported_frames"]]
    metrics = {
        "schema": "pulsar.yawn_metrics/1",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "command": "cd data && uv run python -m pulsar_vision.yawdd" + (f" --limit {args.limit}" if args.limit else ""),
        "limit": args.limit or None,
        "dataset": {
            "name": "YawDD",
            "source": SOURCE_ID,
            "citation": CITATION,
            "license": LICENSE_NOTE,
            "labels": "One label per video, from the file name. No per-frame labels.",
            "videos_found": found,
            "videos_used": int(len(table)),
            "videos_failed": failed,
            "videos_per_condition": per_condition,
            "subjects": {camera: int(group["subject_id"].nunique()) for camera, group in table.groupby("camera")},
            "minutes": {camera: float(group["minutes"].sum()) for camera, group in table.groupby("camera")},
            "other_files": other_files,
            "irregular_names": {
                v.relative_path: yawdd_names.name_irregularities(v.relative_path)
                for v in videos
                if yawdd_names.name_irregularities(v.relative_path)
            },
            "videos_shorter_than_reported": [
                {"video": row.relative_path, "frames_read": int(row.frames_read), "reported_frames": int(row.reported_frames)}
                for row in truncated.itertuples()
            ],
        },
        "extraction": {
            "model_file": model_path.resolve().relative_to(REPO_DIR).as_posix() if model_path.resolve().is_relative_to(REPO_DIR) else model_path.name,
            "model_file_name": model_path.name,
            "model_sha256": extraction["model_sha256"],
            "mediapipe_version": sorted({s.meta["mediapipe_version"] for s in series.values()}),
            "task": "FaceLandmarker",
            "running_mode": "VIDEO",
            "num_faces": landmarks.NUM_FACES,
            "min_face_detection_confidence": landmarks.MIN_FACE_DETECTION_CONFIDENCE,
            "min_face_presence_confidence": landmarks.MIN_FACE_PRESENCE_CONFIDENCE,
            "min_tracking_confidence": landmarks.MIN_TRACKING_CONFIDENCE,
            "target_fps": landmarks.TARGET_FPS,
            "frame_step": sorted({int(x) for x in table["source_fps"].map(landmarks.frame_step)}),
            "source_fps": sorted({round(float(x), 3) for x in table["source_fps"]}),
            "processed_fps": sorted({round(float(x), 3) for x in table["processed_fps"]}),
            "processed_frames": int(table["processed_frames"].sum()),
            "frame_size": sorted({f"{s.meta['width']}x{s.meta['height']}" for s in series.values()}),
        },
        "feature": {"name": mouth.FORMULA_NAME, "formula": mouth.FORMULA, "landmarks": mouth.LANDMARKS},
        "detector": {
            "rule": "mouth_open_ratio >= on threshold, kept while >= off threshold, for at least min_duration_s",
            "grid": grid.to_dict(),
            "max_gap_s_is_searched": False,
            "selection_score": "recall_yawning - 0.5 * (false_alarm_talking + false_alarm_normal), on videos",
            "tie_break": "candidate closest to the centre of the tied region of the grid",
        },
        "validation": {
            "scheme": f"{n_folds} folds grouped by subject (camera + sex + participant number), stratified by sex",
            "seed": args.seed,
            "subjects_in_train_and_test": 0,
            "folds": [
                {
                    "fold": k,
                    "test_subjects": fold_subjects[k],
                    "train_subjects": folds_module.train_subjects(fold_subjects, k),
                }
                for k in range(n_folds)
            ],
        },
        "results": results,
        "final_params": final,
        "longest_open_episode_s_at_final_threshold": {
            "note": f"Longest stretch above the final {chosen_variant} threshold, per Mirror video, by condition.",
            **longest_by_condition,
        },
        "baseline_check": baseline_check,
        "no_face": no_face,
        "max_gap_sensitivity": gap_sensitivity,
        "dash_descriptive": dash,
        "alternative_features": alternatives,
        "timing": {
            **{k: v for k, v in extraction.items() if k != "model_sha256"},
            "calibration_seconds": calibration_seconds,
            "run_seconds": time.perf_counter() - run_started,
            "cpu_count": os.cpu_count(),
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
    }

    chosen = final_params[chosen_variant]
    other = final_params[RELATIVE if chosen_variant == ABSOLUTE else ABSOLUTE]
    yawn_params = {
        "schema": "pulsar.yawn_params/1",
        "generated_at": metrics["generated_at"],
        "limit": args.limit or None,
        **chosen.to_dict(),
        "threshold_meaning": (
            "mouth_open_ratio must reach this value"
            if chosen_variant == ABSOLUTE
            else "mouth_open_ratio must reach baseline + this value; baseline = median ratio of the valid frames "
            "in the first baseline_window_s seconds after the first frame with a face"
        ),
        "release_threshold": (None if chosen_variant == RELATIVE else chosen.release_factor * chosen.threshold),
        "rule": (
            "Open when ratio >= on. Stay open while ratio >= off (off = baseline + release_factor * threshold; "
            "baseline = 0 for the absolute variant). Frames without a face are skipped; if more than max_gap_s "
            "passes since the last frame that kept it open, close at that frame. A yawn is an open stretch whose "
            "last frame is at least min_duration_s after its first."
        ),
        "feature": {"name": mouth.FORMULA_NAME, "formula": mouth.FORMULA, "landmarks": mouth.LANDMARKS},
        "calibrated_at_fps": metrics["extraction"]["processed_fps"],
        "face_landmarker": {
            "model_file_name": model_path.name,
            "model_sha256": extraction["model_sha256"],
            "running_mode": "VIDEO",
            "num_faces": landmarks.NUM_FACES,
            "min_face_detection_confidence": landmarks.MIN_FACE_DETECTION_CONFIDENCE,
            "min_face_presence_confidence": landmarks.MIN_FACE_PRESENCE_CONFIDENCE,
            "min_tracking_confidence": landmarks.MIN_TRACKING_CONFIDENCE,
        },
        "other_variant": other.to_dict(),
        "trainedOn": f"YawDD Mirror, {int(main.sum())} videos of {len(strata)} subjects (Normal, Talking, Yawning)",
        "validated": {
            k: results[chosen_variant]["overall"][k] for k in ("yawning_recall", "talking_false_alarm", "normal_false_alarm")
        },
        "source": SOURCE_ID,
        "citation": CITATION,
    }

    from . import yawdd_report

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "yawn_metrics.json").write_text(json.dumps(clean(metrics), indent=2) + "\n", encoding="utf-8")
    (out_dir / "yawn_params.json").write_text(json.dumps(clean(yawn_params), indent=2) + "\n", encoding="utf-8")
    (out_dir / "yawn_report.md").write_text(yawdd_report.render(clean(metrics), clean(yawn_params)), encoding="utf-8", newline="\n")
    table.round(5).to_csv(out_dir / "yawn_videos.csv", index=False, lineterminator="\n")

    overall = results[chosen_variant]["overall"]
    log(
        f"chosen: {chosen_variant}  threshold={chosen.threshold}  min_duration_s={chosen.min_duration_s}  "
        f"release_factor={chosen.release_factor}"
    )
    log(
        "out-of-fold: recall on Yawning {yawning_recall[count]}/{yawning_recall[of]}, false alarms on Talking "
        "{talking_false_alarm[count]}/{talking_false_alarm[of]}, on Normal "
        "{normal_false_alarm[count]}/{normal_false_alarm[of]}".format(**overall)
    )
    log(f"wrote {out_dir.relative_to(DATA_DIR).as_posix()}/yawn_metrics.json, yawn_params.json, yawn_report.md, yawn_videos.csv")
    log(f"run time: {time.perf_counter() - run_started:.1f}s")
    return 0


def clean(value):
    """JSON-ready copy: numpy scalars to Python, floats rounded to 6 decimals, NaN to null."""
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return None if number != number else round(number, 6)
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    return value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--limit", type=int, default=0, help="smoke run: first N Mirror subjects and N // 5 Dash videos; writes to out/smoke/")
    parser.add_argument("--workers", type=int, default=max(1, min(8, (os.cpu_count() or 2) // 2)), help="worker processes (one FaceLandmarker each)")
    parser.add_argument("--folds", type=int, default=DEFAULT_FOLDS, help="number of subject-grouped folds")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="seed of the fold split")
    parser.add_argument("--force", action="store_true", help="ignore the cache and run MediaPipe again")
    parser.add_argument("--mediapipe-log", action="store_true", help="keep MediaPipe's own stderr lines from the workers")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_ROOT, help="YawDD dataset folder")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="face_landmarker.task (the file the browser loads)")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE, help="git-ignored folder for per-video series")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT, help="where the metrics, parameters and report go")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(run(parse_args()))
