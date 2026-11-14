"""UTA-RLDD: find the videos, extract the face series (cached) and build the table of 60 s windows.

Layout (source ``uta-rldd``): ``<root>/FoldX_partY/<subject>/<label>.<ext>``, one video per subject and
label, where the label is the file name: ``0`` alert, ``5`` low vigilance, ``10`` drowsy. The labels are
the participants' own rating of the whole recording, not a per-minute measurement.

The download is untrusted data: videos are only decoded, nothing in the folder is executed. No frame,
crop or image is written anywhere; the cache (``features/rldd/``) holds coordinates and scores only and
is git-ignored.
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from . import detector, face_series, fatigue_features as ff, landmarks
from .detector import YawnParams
from .face_series import FaceSeries

LABELS: dict[int, str] = {0: "alert", 5: "low_vigilance", 10: "drowsy"}
CLASS_INDEX: dict[int, int] = {0: 0, 5: 1, 10: 2}
ALERT = 0
VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".m4v")

# The ear_p80 closed series with its threshold taken from the first 120 s of the SAME video, whatever the
# person's state in it. Not a product method: it measures what the alert-video calibration is worth.
OWN_VIDEO = "ear_p80_own_video"
# The same idea for the `calibrated` features: blendshape features minus a reference taken from the first
# 120 s of the SAME video instead of the person's alert video.
OWN_REFERENCE = "blendshape_calibrated_own_video"

INDEX_FILE = "_index.json"  # in the cache folder: the videos it holds, so a run without raw/ still works
EXTRACTION_RUNS_FILE = "_extraction_runs.json"  # when and how long MediaPipe ran


def log(message: str) -> None:
    print(message, flush=True)


# --------------------------------------------------------------------------- discovery


@dataclass(frozen=True)
class RlddVideo:
    subject: str  # "01" .. "60", unique across folds
    label: int  # 0, 5 or 10
    part: str  # "Fold1_part1"
    relative_path: str  # posix, relative to the dataset root

    @property
    def video_id(self) -> str:
        return f"{self.subject}_{self.label}"

    @property
    def class_index(self) -> int:
        return CLASS_INDEX[self.label]

    @property
    def state(self) -> str:
        return LABELS[self.label]


def parse_video_path(relative_path: str) -> RlddVideo:
    """``Fold1_part1/01/10.MOV`` -> subject ``01``, label 10. Raises ``ValueError`` on anything else."""
    parts = Path(relative_path).as_posix().split("/")
    if len(parts) < 2:
        raise ValueError(f"{relative_path}: expected <part>/<subject>/<label>.<ext>")
    name = parts[-1]
    stem, dot, extension = name.rpartition(".")
    if not dot or f".{extension.lower()}" not in VIDEO_EXTENSIONS:
        raise ValueError(f"{relative_path}: not a video file")
    subject = parts[-2]
    if not subject.isdigit():
        raise ValueError(f"{relative_path}: the subject folder must be a number, got {subject!r}")
    if not stem.isdigit() or int(stem) not in LABELS:
        raise ValueError(f"{relative_path}: the label must be 0, 5 or 10, got {stem!r}")
    return RlddVideo(
        subject=f"{int(subject):02d}",
        label=int(stem),
        part=parts[-3] if len(parts) >= 3 else "",
        relative_path="/".join(parts),
    )


def discover(root: Path) -> tuple[list[RlddVideo], list[str]]:
    """Every video under ``root`` and the files that are not videos of the dataset."""
    videos: list[RlddVideo] = []
    others: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        try:
            videos.append(parse_video_path(relative))
        except ValueError:
            others.append(relative)
    videos.sort(key=lambda v: (v.subject, v.label))
    return videos, others


def completeness_problems(videos: Sequence[RlddVideo]) -> list[str]:
    """What stops a subject from being used: a missing or duplicated label."""
    problems: list[str] = []
    by_subject: dict[str, list[int]] = {}
    for video in videos:
        by_subject.setdefault(video.subject, []).append(video.label)
    for subject in sorted(by_subject):
        labels = sorted(by_subject[subject])
        if labels != sorted(LABELS):
            problems.append(f"subject {subject}: has videos for labels {labels}, expected {sorted(LABELS)}")
    return problems


def complete_subjects(videos: Sequence[RlddVideo]) -> list[str]:
    by_subject: dict[str, list[int]] = {}
    for video in videos:
        by_subject.setdefault(video.subject, []).append(video.label)
    return sorted(s for s, labels in by_subject.items() if sorted(labels) == sorted(LABELS))


def apply_limit(videos: Sequence[RlddVideo], limit: int | None) -> list[RlddVideo]:
    """Smoke subset: every video of the first ``limit`` subjects."""
    if limit is None:
        return list(videos)
    keep = set(sorted({v.subject for v in videos})[:limit])
    return [v for v in videos if v.subject in keep]


# --------------------------------------------------------------------------- extraction

_MODEL_BYTES: bytes | None = None


def _init_worker(model_path: str, quiet: bool) -> None:
    global _MODEL_BYTES
    if quiet:
        # MediaPipe's C++ side prints warning lines per FaceLandmarker straight to stderr. Worker errors
        # do not travel through stderr: a failing video is caught in _extract_task and reported.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 2)
        os.close(devnull)
    _MODEL_BYTES = Path(model_path).read_bytes()


def _extract_task(task: tuple[str, str]) -> dict:
    video_path, cache_path = task
    try:
        series = face_series.extract_face_series(Path(video_path), _MODEL_BYTES)
        if series.meta["processed_frames"] == 0:
            return {"ok": False, "error": "no frame could be decoded"}
        face_series.save_series(series, Path(cache_path))
        return {
            "ok": True,
            "seconds": series.meta["total_seconds"],
            "mediapipe_seconds": series.meta["mediapipe_seconds"],
            "frames": series.meta["processed_frames"],
            "faces": int(series.face_found.sum()),
        }
    except Exception as error:  # a bad file must not stop the other videos
        return {"ok": False, "error": f"{type(error).__name__}: {error}"}


def default_workers() -> int:
    """Half of the logical CPUs, at most 12: leaves headroom for whatever else the laptop runs."""
    return max(1, min(12, (os.cpu_count() or 2) // 2))


def cached_videos(cache_dir: Path) -> list[RlddVideo]:
    """The videos a cache folder says it holds (the index is kept up to date by ``extract_all``)."""
    path = cache_dir / INDEX_FILE
    if not path.is_file():
        return []
    return [parse_video_path(relative) for relative in json.loads(path.read_text(encoding="utf-8"))["videos"]]


def with_cached(videos: Sequence[RlddVideo], cache_dir: Path) -> tuple[list[RlddVideo], list[RlddVideo]]:
    """The videos on disk plus the ones only the cache has; returns ``(all, cache_only)``.

    A raw folder that is missing, empty or partial must not silently shrink the dataset when the
    extracted series are still in the cache.
    """
    on_disk = {v.video_id for v in videos}
    cache_only = [v for v in cached_videos(cache_dir) if v.video_id not in on_disk]
    return sorted([*videos, *cache_only], key=lambda v: (v.subject, v.label)), cache_only


def extract_all(
    videos: Sequence[RlddVideo],
    root: Path,
    model_path: Path,
    cache_dir: Path,
    workers: int,
    force: bool = False,
) -> tuple[dict[str, FaceSeries], list[dict], dict]:
    """Face series of every video, from the cache when it matches the current setup.

    A video whose file is not on disk is read from the cache alone (same model and settings); a video
    on disk must also match the size the cache was built from.
    """
    model_sha256 = landmarks.sha256_of(model_path.read_bytes())
    cache_path = {v.video_id: cache_dir / f"{v.video_id}.npz" for v in videos}

    series: dict[str, FaceSeries] = {}
    todo: list[RlddVideo] = []
    failed: list[dict] = []
    signatures: dict[str, dict] = {}
    for video in videos:
        source = root / video.relative_path
        size = source.stat().st_size if source.is_file() else None
        signatures[video.video_id] = face_series.cache_signature(model_sha256, size)
        cached = None if force and size is not None else face_series.load_series(cache_path[video.video_id], signatures[video.video_id])
        if cached is not None:
            series[video.video_id] = cached
        elif size is None:
            failed.append({"video": video.relative_path, "error": "not on disk and not in the cache"})
        else:
            todo.append(video)
    log(f"extraction: {len(series)} videos from cache, {len(todo)} to process with {workers} worker(s)")

    started = time.perf_counter()
    done_frames = 0
    extracted = 0
    if todo:
        # Largest first, so the pool does not end with one worker on a long video.
        todo.sort(key=lambda v: -(root / v.relative_path).stat().st_size)
        with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker, initargs=(str(model_path), True)) as executor:
            futures = {
                executor.submit(_extract_task, (str(root / v.relative_path), str(cache_path[v.video_id]))): v for v in todo
            }
            for done, future in enumerate(as_completed(futures), start=1):
                video = futures[future]
                outcome = future.result()
                elapsed = time.perf_counter() - started
                eta = elapsed / done * (len(todo) - done)
                if outcome["ok"]:
                    done_frames += outcome["frames"]
                    log(
                        f"[{done:3d}/{len(todo)}] {video.relative_path}  frames={outcome['frames']}  "
                        f"face={outcome['faces'] / outcome['frames']:.3f}  {outcome['seconds']:.0f}s "
                        f"(mediapipe {outcome['mediapipe_seconds']:.0f}s)  elapsed={elapsed:.0f}s  eta~{eta:.0f}s"
                    )
                    loaded = face_series.load_series(cache_path[video.video_id], signatures[video.video_id])
                    if loaded is None:
                        failed.append({"video": video.relative_path, "error": "cache could not be read back"})
                    else:
                        series[video.video_id] = loaded
                        extracted += 1
                else:
                    log(f"[{done:3d}/{len(todo)}] FAILED {video.relative_path}: {outcome['error']}")
                    failed.append({"video": video.relative_path, "error": outcome["error"]})
    wall = time.perf_counter() - started

    cache_dir.mkdir(parents=True, exist_ok=True)
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
                "videos": extracted,
                "frames": done_frames,
                "wall_seconds": round(wall, 1),
                "workers": workers,
            }
        )
        runs_path.write_text(json.dumps(extraction_runs, indent=2) + "\n", encoding="utf-8")
    # The index lists what the cache holds, so a laptop without the raw videos can still run from it.
    already = {v.relative_path for v in cached_videos(cache_dir)}
    known = already | {v.relative_path for v in videos if v.video_id in series}
    if known != already:
        (cache_dir / INDEX_FILE).write_text(json.dumps({"videos": sorted(known)}, indent=2) + "\n", encoding="utf-8")

    metas = [s.meta for s in series.values()]
    frames = sum(m["processed_frames"] for m in metas)
    mediapipe_seconds = sum(m["mediapipe_seconds"] for m in metas)
    per_video = sorted(m["total_seconds"] for m in metas)
    timing = {
        "model_sha256": model_sha256,
        "videos_from_cache_this_run": len(series) - extracted,
        "videos_extracted_this_run": extracted,
        "extraction_wall_seconds_this_run": wall if todo else 0.0,
        "extraction_runs": extraction_runs,
        "workers": workers,
        "processed_frames": frames,
        # Measured when each video was extracted (kept in its cache file):
        "mediapipe_seconds_sum": mediapipe_seconds,
        "decode_plus_mediapipe_seconds_sum": sum(per_video),
        "decode_plus_mediapipe_seconds_per_video": {
            "min": per_video[0] if per_video else None,
            "median": float(np.median(per_video)) if per_video else None,
            "max": per_video[-1] if per_video else None,
        },
        "mediapipe_ms_per_frame_mean": (1000.0 * mediapipe_seconds / frames) if frames else None,
        "note": (
            "Per-frame time is FaceLandmarker.detect_for_video in Python on this machine's CPU, measured while "
            "several worker processes ran at once. It is not a browser measurement."
        ),
    }
    return series, failed, timing


# --------------------------------------------------------------------------- per-frame signals


@dataclass
class Signals:
    """The per-frame signals of ``fatigue_features.py`` for one video."""

    time_s: np.ndarray
    face: np.ndarray
    eye_blink: np.ndarray
    ear: np.ndarray
    pitch_deg: np.ndarray
    yaw_deg: np.ndarray
    roll_deg: np.ndarray
    mouth_open_ratio: np.ndarray
    nose_y: np.ndarray


def signals_of(series: FaceSeries) -> Signals:
    pitch, yaw, roll = series.head_angles_deg()
    return Signals(
        time_s=series.time_s,
        face=series.face_found,
        eye_blink=series.eye_blink(),
        ear=series.ear(),
        pitch_deg=pitch,
        yaw_deg=yaw,
        roll_deg=roll,
        mouth_open_ratio=series.mouth_open_ratio(),
        nose_y=series.nose_y(),
    )


def longest_missing_run_s(time_s: np.ndarray, face: np.ndarray) -> float:
    """Longest stretch of consecutive frames without a face, in seconds (first to last missing frame + one period)."""
    longest = 0.0
    start: float | None = None
    period = ff.frame_period(time_s)
    for t, found in zip(time_s, face):
        if not found:
            if start is None:
                start = t
            longest = max(longest, t - start + (period if period == period else 0.0))
        else:
            start = None
    return float(longest)


def ear_landmark_check(series: FaceSeries) -> dict:
    """How often the six EAR points of each eye sit where the formula assumes, on the detected faces.

    With the image's y growing downwards: p2 and p3 (upper lid) above p6 and p5 (lower lid), and p2, p3,
    p5, p6 between the corners p1 and p4 along the eye's own axis. A wrong index would fail most frames.
    """
    result = {}
    scale = np.array([series.meta["width"], series.meta["height"]], dtype=np.float64)
    found = series.face_found
    for name, indices in (("right", ff.EAR_RIGHT_EYE), ("left", ff.EAR_LEFT_EYE)):
        p = series.eye_points(indices)[found][..., :2].astype(np.float64) * scale
        if not len(p):
            result[name] = None
            continue
        axis = p[:, 3] - p[:, 0]
        length = np.linalg.norm(axis, axis=1, keepdims=True)
        axis = axis / np.where(length > 0, length, 1.0)
        along = np.einsum("nij,nj->ni", p - p[:, :1], axis) / np.where(length > 0, length, 1.0)
        between = np.all((along[:, [1, 2, 4, 5]] > 0.0) & (along[:, [1, 2, 4, 5]] < 1.0), axis=1)
        # "Above" in the head's frame: the side the upper lid is on must be the same for both pairs and
        # p2/p6, p3/p5 must face each other (similar position along the eye axis).
        normal = np.stack([-axis[:, 1], axis[:, 0]], axis=1)
        across = np.einsum("nij,nj->ni", p - p[:, :1], normal)
        opposite = (np.sign(across[:, 1]) == np.sign(across[:, 2])) & (np.sign(across[:, 4]) == np.sign(across[:, 5])) & (
            np.sign(across[:, 1]) != np.sign(across[:, 5])
        )
        paired = (np.abs(along[:, 1] - along[:, 5]) < 0.25) & (np.abs(along[:, 2] - along[:, 4]) < 0.25)
        upper_above = (p[:, 1, 1] < p[:, 5, 1]) & (p[:, 2, 1] < p[:, 4, 1])
        result[name] = {
            "frames": int(len(p)),
            "lid_points_between_corners": float(between.mean()),
            "upper_and_lower_lids_on_opposite_sides": float(opposite.mean()),
            "p2_faces_p6_and_p3_faces_p5": float(paired.mean()),
            "upper_lid_above_lower_lid_in_image": float(upper_above.mean()),
        }
    return result


def pitch_sign_check(series: FaceSeries, signals: Signals) -> float | None:
    """Correlation between ``pitch_deg`` and how low the nose tip sits between forehead and chin.

    When the head tips down, the nose tip moves towards the chin in the image, so a positive value
    supports ``PITCH_DOWN_SIGN = +1``. Uses landmarks 10 (forehead), 152 (chin) and 1 (nose tip).
    """
    found = signals.face
    if found.sum() < 30:
        return None
    scale = np.array([series.meta["width"], series.meta["height"]], dtype=np.float64)
    top = series.points(10)[found][:, :2] * scale
    chin = series.points(152)[found][:, :2] * scale
    nose = series.points(face_series.NOSE_TIP)[found][:, :2] * scale
    axis = chin - top
    length_sq = (axis**2).sum(axis=1)
    position = ((nose - top) * axis).sum(axis=1) / np.where(length_sq > 0, length_sq, np.nan)
    pitch = signals.pitch_deg[found]
    ok = ~np.isnan(position) & ~np.isnan(pitch)
    if ok.sum() < 30 or np.std(position[ok]) == 0 or np.std(pitch[ok]) == 0:
        return None
    return float(np.corrcoef(pitch[ok], position[ok])[0, 1])


def matrix_layout_check(series: FaceSeries) -> dict:
    """On the frames with a face: is the transformation matrix laid out as ``head_angles_deg`` assumes?

    Row-major 4x4 with the rotation in the upper-left 3x3, the translation in the last COLUMN and
    ``[0, 0, 0, 1]`` as the last row. JavaScript's flat array is the transpose (column-major), which is
    why ``M[2][1]`` here is ``m[6]`` there.
    """
    matrices = series.matrix[series.face_found].astype(np.float64)
    if not len(matrices):
        return {"frames": 0, "last_row_is_0_0_0_1": 0, "rotation_columns_share_one_scale": 0}
    last_row = np.all(np.abs(matrices[:, 3, :] - np.array([0.0, 0.0, 0.0, 1.0])) < 1e-4, axis=1)
    lengths = np.linalg.norm(matrices[:, :3, :3], axis=1)
    unit = np.all(np.abs(lengths - lengths[:, :1]) < 1e-2 * lengths[:, :1], axis=1)  # one common scale
    return {"frames": int(len(matrices)), "last_row_is_0_0_0_1": int(last_row.sum()), "rotation_columns_share_one_scale": int(unit.sum())}


def video_summary(video: RlddVideo, series: FaceSeries, signals: Signals) -> dict:
    n = len(signals.time_s)
    duration = float(signals.time_s[-1] - signals.time_s[0]) if n > 1 else 0.0
    faces = int(signals.face.sum())
    roll = signals.roll_deg[signals.face]
    meta = series.meta
    return {
        "video": video.relative_path,
        "subject": video.subject,
        "label": video.label,
        "width": meta["width"],
        "height": meta["height"],
        "source_fps": round(meta["source_fps"], 3),
        "orientation_meta_deg": meta["orientation_meta_deg"],
        "orientation_auto": meta["orientation_auto"],
        "timestamp_fallbacks": meta["timestamp_fallbacks"],
        "duration_s": round(duration, 1),
        "processed_frames": n,
        "processed_fps": round((n - 1) / duration, 3) if duration > 0 else None,
        "frame_period_median_s": round(ff.frame_period(signals.time_s), 4) if n > 1 else None,
        "no_face_frames": n - faces,
        "no_face_rate": round(1.0 - faces / n, 5) if n else None,
        "longest_no_face_s": round(longest_missing_run_s(signals.time_s, signals.face), 2),
        "roll_median_deg": round(float(np.median(roll)), 1) if len(roll) else None,
        "pitch_vs_nose_position_correlation": pitch_sign_check(series, signals),
        "mediapipe_ms_per_frame": round(1000.0 * meta["mediapipe_seconds"] / n, 2) if n else None,
        "extraction_seconds": round(meta["total_seconds"], 1),
    }


# --------------------------------------------------------------------------- windows


def yawn_count_times(time_s: Sequence[float], ratio: Sequence[float], params: YawnParams) -> list[float]:
    """When the streaming detector (``YawnDetector.push`` in ``yawn.ts``) counts each yawn.

    That is the first frame of an open episode at least ``min_duration_s`` after its start. Used only to
    reproduce what the browser's ``yawnsPerMin`` holds today, for the baseline.
    """
    times = [float(t) for t in time_s]
    values = [float(r) for r in ratio]
    on, off = detector.thresholds(params, 0.0)
    episodes = detector.open_episodes(times, values, on, off, params.max_gap_s)
    counted: list[float] = []
    cursor = 0
    for episode in detector.yawns_from_episodes(episodes, params.min_duration_s):
        while times[cursor] < episode.start_s:
            cursor += 1
        index = cursor
        while index < len(times) and times[index] <= episode.end_s:
            if values[index] == values[index] and times[index] - episode.start_s >= params.min_duration_s - 1e-9:
                counted.append(times[index])
                break
            index += 1
    return counted


def column(method: str, feature: str) -> str:
    return f"{method}__{feature}"


def video_windows(video: RlddVideo, signals: Signals, closed_by_method: Mapping[str, np.ndarray], yawn_params: YawnParams) -> list[dict]:
    """One row per 60 s window of a video: bookkeeping, the features of each eye method and the baseline."""
    rows: list[dict] = []
    time_s = signals.time_s
    if len(time_s) < 2:
        return rows
    first = float(time_s[0])
    calibration_end = first + ff.CALIBRATION_S
    counted_yawns = np.asarray(yawn_count_times(time_s, signals.mouth_open_ratio, yawn_params))
    blendshape_closed = ff.closed_from_blendshape(signals.eye_blink)
    for start in ff.window_starts(first, float(time_s[-1]) + ff.frame_period(time_s)):
        frames = ff.window_slice(time_s, start)
        times = time_s[frames]
        face = signals.face[frames]
        n = len(times)
        face_frames = int(face.sum())
        end = start + ff.WINDOW_S
        row: dict = {
            "subject": video.subject,
            "label": video.label,
            "class_index": video.class_index,
            "video_id": video.video_id,
            "start_s": round(start - first, 3),
            "frames": n,
            "face_fraction": face_frames / n if n else 0.0,
            "usable": ff.window_usable(n, face_frames),
            # Only an alert video has a calibration period (the product calibrates rested, at session start).
            "in_calibration": video.label == ALERT and end <= calibration_end + 1e-9,
            "overlaps_calibration": video.label == ALERT and start < calibration_end - 1e-9,
            # In any video: does the window touch the recording's first 120 s?
            "touches_first_120s": start < calibration_end - 1e-9,
            "inside_first_120s": end <= calibration_end + 1e-9,
        }
        for method, closed in closed_by_method.items():
            features = ff.window_features(
                times, face, closed[frames], signals.pitch_deg[frames], signals.mouth_open_ratio[frames], yawn_params
            )
            for name in ff.FEATURE_NAMES:
                row[column(method, name)] = features[name] if features is not None else np.nan

        row.update(browser_baseline(signals, frames, start, counted_yawns, blendshape_closed))
        rows.append(row)
    return rows


def browser_baseline(signals: Signals, frames: slice, start: float, counted_yawns: np.ndarray, blendshape_closed: np.ndarray) -> dict:
    """What the browser shows today at the last frame of the window ``frames`` (which starts at ``start``).

    ``counted_yawns`` are the times ``yawn_count_times`` gives for the whole recording and
    ``blendshape_closed`` its closed series; both are computed once per recording.
    """
    window_closed = blendshape_closed[frames]
    seen = ~np.isnan(window_closed)
    perclos = float((window_closed[seen] > 0.5).mean()) if seen.any() else float("nan")
    yawns_last_minute = int(((counted_yawns >= start) & (counted_yawns < start + ff.WINDOW_S)).sum())
    nose = signals.nose_y[: frames.stop]
    nose = nose[~np.isnan(nose)][-ff.BROWSER_NOSE_SAMPLES :]
    return {
        "baseline_perclos": perclos,
        "baseline_yawns": yawns_last_minute,
        "baseline_score": ff.browser_baseline_score(perclos, yawns_last_minute, nose),
    }


def subject_ear_calibration(alert_signals: Signals) -> ff.EarCalibration | None:
    """EAR calibration from the first ``CALIBRATION_S`` of a subject's alert video; ``None`` if too little face."""
    time_s = alert_signals.time_s
    if not len(time_s):
        return None
    period = time_s < time_s[0] + ff.CALIBRATION_S
    calibration = ff.ear_calibration(alert_signals.ear[period])
    if calibration.frames < ff.MIN_CALIBRATION_FRAMES:
        return None
    return calibration


def build_windows(
    videos: Sequence[RlddVideo],
    signals_by_video: Mapping[str, Signals],
    yawn_params: YawnParams,
) -> tuple[pd.DataFrame, dict[str, dict]]:
    """The window table of every subject with its three videos, and each subject's calibration."""
    rows: list[dict] = []
    subjects: dict[str, dict] = {}
    by_subject: dict[str, dict[int, RlddVideo]] = {}
    for video in videos:
        if video.video_id in signals_by_video:
            by_subject.setdefault(video.subject, {})[video.label] = video
    for subject in sorted(by_subject):
        own = by_subject[subject]
        if sorted(own) != sorted(LABELS):
            subjects[subject] = {"used": False, "reason": f"videos available for labels {sorted(own)} only"}
            continue
        calibration = subject_ear_calibration(signals_by_video[own[ALERT].video_id])
        threshold = calibration.threshold if calibration is not None else float("nan")
        subject_rows: list[dict] = []
        for label in sorted(own):
            signals = signals_by_video[own[label].video_id]
            own_calibration = subject_ear_calibration(signals)
            closed = {
                ff.BLENDSHAPE: ff.closed_from_blendshape(signals.eye_blink),
                ff.EAR_P80: ff.closed_from_ear(signals.ear, threshold),
                OWN_VIDEO: ff.closed_from_ear(signals.ear, own_calibration.threshold if own_calibration is not None else float("nan")),
            }
            subject_rows += video_windows(own[label], signals, closed, yawn_params)
        if not subject_rows:
            subjects[subject] = {"used": False, "reason": "no video is long enough for one 60 s window"}
            continue
        table = pd.DataFrame(subject_rows)
        calibration_rows = table[table["in_calibration"] & table["usable"]]
        references = {
            method: ff.calibration_reference(calibration_rows[[column(method, n) for n in ff.FEATURE_NAMES]].to_numpy())
            for method in ff.EYE_METHODS
        }
        for method in ff.EYE_METHODS:
            calibrated = ff.calibrate(table[[column(method, n) for n in ff.FEATURE_NAMES]].to_numpy(), references[method])
            for i, name in enumerate(ff.FEATURE_NAMES):
                table[column(f"{method}_{ff.CALIBRATED}", name)] = calibrated[:, i]
        blendshape_columns = [column(ff.BLENDSHAPE, n) for n in ff.FEATURE_NAMES]
        for i, name in enumerate(ff.FEATURE_NAMES):
            table[column(OWN_REFERENCE, name)] = np.nan
        for video_id in table["video_id"].unique():
            own_rows = table["video_id"] == video_id
            start_rows = table[own_rows & table["inside_first_120s"] & table["usable"]]
            reference = ff.calibration_reference(start_rows[blendshape_columns].to_numpy())
            calibrated = ff.calibrate(table.loc[own_rows, blendshape_columns].to_numpy(), reference)
            for i, name in enumerate(ff.FEATURE_NAMES):
                table.loc[own_rows, column(OWN_REFERENCE, name)] = calibrated[:, i]
        usable_calibration = calibration is not None and len(calibration_rows) > 0
        subjects[subject] = {
            "used": bool(usable_calibration),
            "reason": None if usable_calibration else "the first 120 s of the alert video have too little face to calibrate",
            "ear_calibration": calibration.to_dict() if calibration is not None else None,
            "calibration_windows": int(len(calibration_rows)),
            "calibration_reference": {
                method: {n: (None if v != v else float(v)) for n, v in zip(ff.FEATURE_NAMES, references[method])}
                for method in ff.EYE_METHODS
            },
        }
        rows.append(table)
    windows = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    return windows, subjects
