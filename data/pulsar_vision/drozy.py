"""DROZY: validate the shipped fatigue model against PVT reaction times and KSS. Nothing is fitted on it.

DROZY: Massoz, Langohr, François & Verly (2016), *The ULg Multimodality Drowsiness Database (called
DROZY) and Examples of Use*, WACV 2016 (``drozy`` in shared/sources.json). 14 people, up to three
10-minute tests each, near-infrared Kinect video with a psychomotor vigilance test (PVT) and a KSS score
per test. Its role is validation on people the model never saw, never training or calibration: the video is
near-infrared with small faces (``data/probes/README.md``), not the demo's colour webcam.

File formats, from the dataset's own README.md and checked against the files:

- ``videos_i8/SUBJECT-TEST.mp4``: one 10-minute video per test. Its container plays the frames at a
  nominal rate, but frames were dropped while recording, so the container's times are not the real ones.
- ``timestamps/SUBJECT-TEST.txt``: one line per video frame (the line count equals the frame count),
  ``year month day hours minutes seconds milliseconds elapsed``; ``elapsed`` is the time since the beginning
  of the test in milliseconds. It is the frame time used here.
- ``pvt-rt/SUBJECT-TEST.csv``: first line, the beginning of the test (``yyyy-mm-dd_hh.mm.ss.mmm``); then one
  line per stimulus, ``stimulus;reaction`` in the same format. The reaction time is the difference. The
  beginning of the test is the zero of ``elapsed``, so stimuli and frames share one clock.
- ``KSS.txt``: 14 lines (subjects) by 3 columns (tests), values 1 to 9; 0 where no score was recorded
  (test 7-1 did not happen). Some tests are missing (9-1, 10-2, 12-2, 12-3, 13-3 and 7-1): 36 videos.

The features are those of the shipped model (``fatigue_features``, eye closure ``blendshape``, ``absolute``),
from the same extractor as RLDD (``face_series``, VIDEO mode, 15 fps by time) with DROZY's own frame times.

Licence: research and evaluation only, no redistribution, no image shown. The files are only read. Per-frame
series never leave the worker process that computed them and are never written anywhere, not even to a
git-ignored cache: each run extracts again. Only aggregate numbers reach ``out/``: correlations, counts and
coverage, never a recording's KSS or reaction times. Every result cites ``CITATION``.
"""

from __future__ import annotations

import re
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from . import face_series, fatigue_features as ff, fatigue_validation as fv, landmarks, rldd
from .detector import YawnParams

DATA_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = DATA_DIR / "raw" / "drozy" / "DROZY"

SOURCE_ID = "drozy"  # key in shared/sources.json
CITATION = (
    "Massoz, Langohr, François & Verly (2016), The ULg Multimodality Drowsiness Database (called DROZY) and "
    "Examples of Use, WACV 2016"
)
LICENSE_NOTE = (
    "DROZY is for research and evaluation only: no commercial use, no redistribution in full or in part, no image "
    "shown. The pipeline reads the files and writes aggregate numbers only: no frame, crop or per-frame series, and "
    "no recording's KSS or reaction times."
)
HOW_TO_GET = (
    "DROZY is not on this machine. Each person downloads it and accepts its licence agreement (`drozy` in "
    "shared/sources.json), then unpacks it so that {root} contains videos_i8/, timestamps/, pvt-rt/ and KSS.txt. "
    "The folder is git-ignored: nothing from DROZY is committed (goals/G2-fatigue-model.md)."
)
KSS_NOTE = (
    "KSS (Karolinska Sleepiness Scale; 1 to 9 in DROZY's file, higher = sleepier) is the score DROZY recorded per test. The "
    "scale itself is not registered in shared/sources.json: register it before quoting a KSS figure."
)

SUBJECTS = 14
TESTS = 3
KSS_RANGE = (1, 9)
KSS_NOT_RECORDED = 0
PVT_TIME_FORMAT = "%Y-%m-%d_%H.%M.%S.%f"
TIMESTAMP_COLUMNS = 8

# The three signals compared, all on the same windows; none is fitted on DROZY.
SCORE = "fatigue_score"
PERCLOS = "perclos"
BROWSER = "browser_formula"
SIGNALS: tuple[str, ...] = (SCORE, PERCLOS, BROWSER)
SIGNAL_DEFINITIONS: dict[str, str] = {
    SCORE: "the shipped model's fatigueScore (data/fatigue_model.json, trained on UTA-RLDD), unchanged",
    PERCLOS: "the model's first feature alone: closed frames / frames with a face, eye closed when mean eyeBlink > 0.5",
    BROWSER: f"faceWorker.ts's fixed formula before the model: {ff.BROWSER_BASELINE_FORMULA}",
}
# The headline: decided before looking at any DROZY result of this model, see HEADLINE_WHY.
HEADLINE = {"view": "per_recording", "signal": SCORE, "target": fv.PVT_MEAN_RT, "statistic": "spearman"}
HEADLINE_WHY = (
    "Per recording, because the 36 tests are the only units that do not overlap: windows share 50 of their 60 s and a "
    "person's windows share the person, so window counts overstate the evidence. Spearman rather than Pearson, decided "
    "before seeing this model's numbers: a test's mean reaction time is pulled up by a few very slow responses, and with 36 "
    "points Pearson can be carried by two or three extreme tests (the earlier 3-feature score showed Pearson well above "
    "Spearman for that reason). Pearson is reported next to it."
)

_NAME = re.compile(r"^(\d{1,2})-(\d)$")


class DatasetMissing(Exception):
    """DROZY is not here, or not laid out as this loader expects. The message says what to do."""


@dataclass(frozen=True)
class DrozyTest:
    subject: str  # "1" .. "14"
    test: int  # 1, 2 or 3
    video: Path
    timestamps: Path
    pvt: Path
    kss: float | None  # None where DROZY recorded none

    @property
    def name(self) -> str:
        return f"{self.subject}-{self.test}"


# --------------------------------------------------------------------------- files


def parse_name(stem: str) -> tuple[int, int]:
    """``"7-2"`` -> subject 7, test 2. Raises ``ValueError`` on any other name."""
    match = _NAME.match(stem)
    if not match:
        raise ValueError(f"not a DROZY test name (SUBJECT-TEST): {stem!r}")
    subject, test = int(match.group(1)), int(match.group(2))
    if not (1 <= subject <= SUBJECTS and 1 <= test <= TESTS):
        raise ValueError(f"DROZY has subjects 1-{SUBJECTS} and tests 1-{TESTS}: {stem!r}")
    return subject, test


def load_kss(path: Path) -> dict[tuple[int, int], float | None]:
    """(subject, test) -> KSS score, ``None`` where the file holds 0 (no score recorded)."""
    rows = [line.split() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != SUBJECTS or any(len(row) != TESTS for row in rows):
        raise DatasetMissing(f"{path}: expected {SUBJECTS} lines of {TESTS} scores")
    scores: dict[tuple[int, int], float | None] = {}
    for subject, row in enumerate(rows, start=1):
        for test, text in enumerate(row, start=1):
            value = int(text)
            if value != KSS_NOT_RECORDED and not KSS_RANGE[0] <= value <= KSS_RANGE[1]:
                raise DatasetMissing(f"{path}: {value} is not a KSS score (subject {subject}, test {test})")
            scores[(subject, test)] = None if value == KSS_NOT_RECORDED else float(value)
    return scores


def load_pvt(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Stimulus times in seconds since the beginning of the test, and reaction times in milliseconds."""
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    try:
        started = datetime.strptime(lines[0], PVT_TIME_FORMAT)
        stimulus_s: list[float] = []
        rt_ms: list[float] = []
        for line in lines[1:]:
            stimulus, reaction = (datetime.strptime(text, PVT_TIME_FORMAT) for text in line.split(";"))
            stimulus_s.append((stimulus - started).total_seconds())
            rt_ms.append((reaction - stimulus).total_seconds() * 1000.0)
    except (IndexError, ValueError) as error:
        raise DatasetMissing(f"{path}: not a DROZY pvt-rt file ({error})") from error
    return np.asarray(stimulus_s, dtype=np.float64), np.asarray(rt_ms, dtype=np.float64)


def load_frame_times_ms(path: Path) -> np.ndarray:
    """Milliseconds since the beginning of the test for every frame of the video (the last column)."""
    try:
        table = np.loadtxt(path, dtype=np.float64, ndmin=2)
    except ValueError as error:
        raise DatasetMissing(f"{path}: not a DROZY timestamps file ({error})") from error
    if table.shape[1] != TIMESTAMP_COLUMNS:
        raise DatasetMissing(f"{path}: expected {TIMESTAMP_COLUMNS} columns per frame, found {table.shape[1]}")
    times = table[:, -1]
    if (np.diff(times) <= 0).any():
        raise DatasetMissing(f"{path}: elapsed times do not increase")
    return times


def available(root: Path) -> bool:
    return (root / "videos_i8").is_dir() and (root / "KSS.txt").is_file()


def load(root: Path = DEFAULT_ROOT) -> list[DrozyTest]:
    """One ``DrozyTest`` per video, ordered by subject and test. Checks that each has its timestamps and PVT."""
    if not available(root):
        raise DatasetMissing(HOW_TO_GET.format(root=root))
    videos_dir = root / "videos_i8"
    try:
        names = sorted(parse_name(path.stem) for path in videos_dir.glob("*.mp4"))
    except ValueError as error:
        raise DatasetMissing(f"{videos_dir}: {error}") from error
    if not names:
        raise DatasetMissing(HOW_TO_GET.format(root=root))
    kss = load_kss(root / "KSS.txt")
    tests: list[DrozyTest] = []
    for subject, test in names:
        stem = f"{subject}-{test}"
        timestamps, pvt = root / "timestamps" / f"{stem}.txt", root / "pvt-rt" / f"{stem}.csv"
        for needed in (timestamps, pvt):
            if not needed.is_file():
                raise DatasetMissing(f"DROZY test {stem} has a video but no {needed.parent.name}/{needed.name}")
        tests.append(DrozyTest(str(subject), test, videos_dir / f"{stem}.mp4", timestamps, pvt, kss[(subject, test)]))
    return tests


# --------------------------------------------------------------------------- windows


def recording_windows(test: DrozyTest, signals: rldd.Signals, yawn_params: YawnParams, stimulus_s: np.ndarray, rt_ms: np.ndarray) -> list[dict]:
    """One row per 60 s window of a test: the shipped features, the browser's formula and the PVT of the window.

    Same window rule as RLDD (``fatigue_features``): windows every 10 s from the first frame, used only when
    they hold enough frames with a face. ``start_s`` is on the test's clock (the PVT's zero).
    """
    time_s = signals.time_s
    rows: list[dict] = []
    if len(time_s) < 2:
        return rows
    counted_yawns = np.asarray(rldd.yawn_count_times(time_s, signals.mouth_open_ratio, yawn_params))
    closed = ff.closed_from_blendshape(signals.eye_blink)
    starts = ff.window_starts(float(time_s[0]), float(time_s[-1]) + ff.frame_period(time_s))
    pvt_mean, pvt_count = fv.window_pvt(stimulus_s, rt_ms, np.asarray(starts), np.asarray(starts) + ff.WINDOW_S)
    recording_rt = float(np.mean(rt_ms)) if len(rt_ms) else float("nan")
    for k, start in enumerate(starts):
        frames = ff.window_slice(time_s, start)
        face = signals.face[frames]
        features = ff.window_features(
            time_s[frames], face, closed[frames], signals.pitch_deg[frames], signals.mouth_open_ratio[frames], yawn_params
        )
        row = {
            "subject": test.subject,
            "recording": test.name,
            "start_s": round(start, 3),
            "frames": int(frames.stop - frames.start),
            "face_fraction": float(face.mean()) if len(face) else 0.0,
            "usable": features is not None,
            **{name: (features[name] if features is not None else np.nan) for name in ff.FEATURE_NAMES},
            **rldd.browser_baseline(signals, frames, start, counted_yawns, closed),
            fv.PVT_MEAN_RT: float(pvt_mean[k]),
            fv.PVT_STIMULI: int(pvt_count[k]),
            fv.RECORDING_MEAN_RT: recording_rt,
            fv.KSS: np.nan if test.kss is None else test.kss,
        }
        rows.append(row)
    return rows


def coverage(test: DrozyTest, series: face_series.FaceSeries, signals: rldd.Signals, rows: Sequence[dict]) -> dict:
    """What a test gave, as counts: nothing here is a reaction time or a KSS score."""
    n = len(signals.time_s)
    duration = float(signals.time_s[-1] - signals.time_s[0]) if n > 1 else 0.0
    usable = sum(row["usable"] for row in rows)
    return {
        "recording": test.name,
        "subject": test.subject,
        "test": test.test,
        "video_frames": int(series.meta["frames_read"]),
        "processed_frames": n,
        "processed_fps": round((n - 1) / duration, 3) if duration > 0 else None,
        "face_found": round(float(signals.face.mean()), 5) if n else None,
        "longest_no_face_s": round(rldd.longest_missing_run_s(signals.time_s, signals.face), 2),
        "windows": len(rows),
        "windows_rejected": len(rows) - usable,
        "kss_recorded": test.kss is not None,
    }


# --------------------------------------------------------------------------- extraction (no cache)

_YAWN_PARAMS: YawnParams | None = None


def _init_worker(model_path: str, yawn_params: YawnParams, quiet: bool) -> None:
    global _YAWN_PARAMS
    rldd._init_worker(model_path, quiet)  # model bytes and a silenced MediaPipe stderr, as for RLDD
    _YAWN_PARAMS = yawn_params


def _test_task(test: DrozyTest) -> dict:
    """Extract one test and return its window rows. The per-frame series is dropped when this returns."""
    try:
        times_ms = load_frame_times_ms(test.timestamps)
        stimulus_s, rt_ms = load_pvt(test.pvt)
        series = face_series.extract_face_series(test.video, rldd._MODEL_BYTES, frame_times_ms=times_ms)
        if series.meta["processed_frames"] == 0:
            return {"ok": False, "error": "no frame could be decoded"}
        signals = rldd.signals_of(series)
        rows = recording_windows(test, signals, _YAWN_PARAMS, stimulus_s, rt_ms)
        return {
            "ok": True,
            "rows": rows,
            "coverage": coverage(test, series, signals, rows),
            "seconds": series.meta["total_seconds"],
            "mediapipe_seconds": series.meta["mediapipe_seconds"],
        }
    except Exception as error:  # a bad file must not stop the other tests
        return {"ok": False, "error": f"{type(error).__name__}: {error}"}


def extract_windows(tests: Sequence[DrozyTest], landmarker: Path, yawn_params: YawnParams, workers: int, log=print) -> tuple[pd.DataFrame, list[dict], list[dict], dict]:
    """Window table of every test, coverage per test, failures, and timings (for the log only)."""
    rows: list[dict] = []
    covered: list[dict] = []
    failed: list[dict] = []
    started = time.perf_counter()
    mediapipe_seconds = 0.0
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker, initargs=(str(landmarker), yawn_params, True)) as pool:
        ordered = sorted(tests, key=lambda t: -t.video.stat().st_size)  # longest first
        futures = {pool.submit(_test_task, test): test for test in ordered}
        for done, future in enumerate(as_completed(futures), start=1):
            test = futures[future]
            outcome = future.result()
            elapsed = time.perf_counter() - started
            if outcome["ok"]:
                rows += outcome["rows"]
                covered.append(outcome["coverage"])
                mediapipe_seconds += outcome["mediapipe_seconds"]
                c = outcome["coverage"]
                log(
                    f"  [{done:2d}/{len(tests)}] DROZY {test.name}  frames={c['processed_frames']}  face={c['face_found']:.3f}  "
                    f"windows={c['windows'] - c['windows_rejected']}/{c['windows']}  {outcome['seconds']:.0f}s  elapsed={elapsed:.0f}s"
                )
            else:
                log(f"  [{done:2d}/{len(tests)}] DROZY {test.name} FAILED: {outcome['error']}")
                failed.append({"recording": test.name, "error": outcome["error"]})
    order = {t.name: (int(t.subject), t.test) for t in tests}
    covered.sort(key=lambda c: order[c["recording"]])
    table = pd.DataFrame(rows)
    if not table.empty:
        table["_order"] = table["recording"].map(order)
        table = table.sort_values(["_order", "start_s"], kind="stable").drop(columns="_order").reset_index(drop=True)
    timing = {"wall_seconds": time.perf_counter() - started, "mediapipe_seconds": mediapipe_seconds, "workers": workers}
    return table, covered, failed, timing


# --------------------------------------------------------------------------- the model on DROZY


def check_model(model: Mapping, yawn_raw: Mapping, landmarker_sha256: str) -> None:
    """Refuse a model these features do not fit: another feature list, version, configuration, yawn detector or MediaPipe model."""
    problems = []
    if list(model.get("features", [])) != list(ff.FEATURE_NAMES):
        problems.append(f"features {model.get('features')} are not {list(ff.FEATURE_NAMES)}")
    if model.get("features_version") != ff.FEATURES_VERSION:
        problems.append(f"features_version {model.get('features_version')} is not {ff.FEATURES_VERSION}")
    shipped = f"{ff.SHIPPED_EYE_METHOD}/{ff.SHIPPED_NORMALISATION}"
    if model.get("configuration", {}).get("shipped") != shipped:
        problems.append(f"the model is not the shipped configuration {shipped}")
    for field in ("variant", "threshold", "min_duration_s", "release_factor", "max_gap_s"):
        if model.get("yawn_detector", {}).get(field) != yawn_raw.get(field):
            problems.append(f"yawn detector `{field}` differs from out/yawn_params.json")
    if model.get("face_landmarker", {}).get("model_sha256") != landmarker_sha256:
        problems.append("the model was trained on features from another face_landmarker.task")
    if problems:
        raise ValueError("the fatigue model does not match this feature extractor: " + "; ".join(problems))


def score_windows(windows: pd.DataFrame, model: Mapping) -> pd.DataFrame:
    """The usable windows with the three signals; the model is applied as shipped, nothing is refitted."""
    scored = windows[windows["usable"]].copy()
    features = scored[list(ff.FEATURE_NAMES)].to_numpy(dtype=np.float64)
    scored[SCORE] = ff.fatigue_score(ff.predict_proba(features, model)) if len(scored) else np.array([])
    scored[BROWSER] = scored["baseline_score"]
    return scored  # PERCLOS is already a column: the model's first feature


def distribution(values: np.ndarray) -> dict:
    values = values[np.isfinite(values)]
    if not len(values):
        return {}
    p = np.percentile(values, [0, 25, 50, 75, 100])
    return {"min": p[0], "p25": p[1], "median": p[2], "p75": p[3], "max": p[4]}


def summary(windows: pd.DataFrame, scored: pd.DataFrame, covered: Sequence[dict], failed: Sequence[dict], tests: Sequence[DrozyTest], model: Mapping) -> dict:
    """The ``drozy_validation`` block of ``metrics.json``. Aggregate numbers only."""
    results = fv.validate(scored, SIGNALS)
    headline = results[HEADLINE["view"]][HEADLINE["signal"]][HEADLINE["target"]]
    faces = np.array([c["face_found"] for c in covered], dtype=np.float64)
    fps = np.array([c["processed_fps"] for c in covered if c["processed_fps"]], dtype=np.float64)
    recordings_scored = int(scored["recording"].nunique()) if len(scored) else 0
    return {
        "source": SOURCE_ID,
        "citation": CITATION,
        "licence": LICENSE_NOTE,
        "what": (
            "The shipped data/fatigue_model.json applied unchanged to DROZY, whose 14 people the model never saw: nothing is "
            "fitted, scaled or chosen on DROZY. Its fatigueScore, PERCLOS alone and the browser's former fixed formula are "
            "compared with the mean PVT reaction time and with KSS, on the same windows."
        ),
        "model": {"trainedOn": model["trainedOn"], "configuration": model["configuration"]["shipped"], "refit_on_drozy": False},
        "headline": {
            **HEADLINE,
            "value": headline[HEADLINE["statistic"]],
            "pearson_r": headline["r"],
            "n_recordings": headline["n"],
            "why": HEADLINE_WHY,
        },
        "signals": SIGNAL_DEFINITIONS,
        "targets": {
            fv.PVT_MEAN_RT: (
                "per window: mean reaction time of the PVT stimuli shown in it (start <= stimulus < start + 60 s); per recording: "
                "mean of every reaction time of the test. Reaction time = response time - stimulus time, from pvt-rt/; no stimulus "
                "is dropped or capped"
            ),
            fv.KSS: KSS_NOTE,
        },
        "dataset": {
            "tests_found": len(tests),
            "subjects_found": len({t.subject for t in tests}),
            "tests_extracted": len(covered),
            "tests_failed": list(failed),
            "tests_scored": recordings_scored,
            "subjects_scored": int(scored["subject"].nunique()) if len(scored) else 0,
            "tests_without_kss": sorted((t.name for t in tests if t.kss is None), key=lambda n: tuple(map(int, n.split("-")))),
            "frame_times": "DROZY's timestamps/ (elapsed ms), one per decoded frame; frames processed at 15 per second by those times",
            "processed_frames": int(sum(c["processed_frames"] for c in covered)),
            "processed_fps": {"min": float(fps.min()), "median": float(np.median(fps)), "max": float(fps.max())} if len(fps) else {},
            "face_found": {
                "overall": float(sum(c["face_found"] * c["processed_frames"] for c in covered) / max(1, sum(c["processed_frames"] for c in covered))),
                "min_per_test": float(faces.min()) if len(faces) else None,
                "median_per_test": float(np.median(faces)) if len(faces) else None,
            },
            "windows": int(len(windows)),
            "windows_rejected": int((~windows["usable"]).sum()) if len(windows) else 0,
            "windows_scored": int(len(scored)),
            "windows_scored_without_stimulus": int(scored[fv.PVT_MEAN_RT].isna().sum()) if len(scored) else 0,
            "window_rule": (
                f"60 s windows every 10 s from the first frame, as on RLDD; a window needs at least {ff.MIN_WINDOW_FRAMES} frames "
                f"and a face in {ff.MIN_FACE_FRACTION:.0%} of them, otherwise it has no score. No window is left out for calibration: "
                "the shipped model has none."
            ),
        },
        "score_distribution": {signal: distribution(scored[signal].to_numpy(dtype=np.float64)) for signal in SIGNALS},
        "results": results,
        "recordings": list(covered),
        "limits": [
            "Near-infrared Kinect video, 512x424, faces about 65 px wide: not the demo's colour webcam. The numbers do not transfer to it.",
            "14 people and 36 tests: one person can move a per-recording correlation a lot. No interval or p-value is computed.",
            "Windows overlap by 50 s: a window count is not a sample size.",
            "Per recording, the points mix differences between people with changes within a person.",
            "Within one person there are at most 3 distinct KSS values (one per test), and some people have only one or two tests.",
            "The PVT is a reaction test (a mouse click per visual stimulus) taken by people kept awake 28-30 h (`drozy` in shared/sources.json); it is not an astronaut's workload.",
            KSS_NOTE,
        ],
    }


def validate_model(
    model: Mapping,
    yawn_params: YawnParams,
    yawn_raw: Mapping,
    root: Path,
    landmarker: Path,
    workers: int,
    log=print,
) -> dict:
    """Run the shipped model on every DROZY test and return the ``drozy_validation`` block.

    Raises ``DatasetMissing`` when DROZY is not here and ``ValueError`` when the model does not fit these features.
    """
    check_model(model, yawn_raw, landmarks.sha256_of(landmarker.read_bytes()))
    tests = load(root)
    log(f"DROZY: {len(tests)} tests of {len({t.subject for t in tests})} subjects under {root}; validation only, nothing is fitted")
    log(f"  extraction with {workers} worker(s); per-frame series are not written anywhere, so every run extracts again")
    windows, covered, failed, timing = extract_windows(tests, landmarker, yawn_params, workers, log)
    if windows.empty:
        raise DatasetMissing("no DROZY test could be extracted: " + "; ".join(f"{f['recording']}: {f['error']}" for f in failed))
    scored = score_windows(windows, model)
    block = summary(windows, scored, covered, failed, tests, model)
    log(
        f"  DROZY extraction: {len(covered)} tests in {timing['wall_seconds'] / 60:.1f} min with {workers} processes "
        f"(MediaPipe {1000 * timing['mediapipe_seconds'] / max(1, block['dataset']['processed_frames']):.1f} ms per frame, this CPU)"
    )
    return block


def pvt_fields(block: Mapping | None) -> dict:
    """``pvt_correlation`` and its note for metrics.json, from the block or from its absence."""
    if block is None:
        return {
            "pvt_correlation": None,
            "pvt_correlation_note": "DROZY (video with PVT reaction times) is not downloaded, so the score has not been compared with any reaction time.",
        }
    h = block["headline"]
    return {
        "pvt_correlation": h["value"],
        "pvt_correlation_note": (
            f"Spearman correlation, over the {h['n_recordings']} DROZY tests (one point per test), between the shipped model's mean "
            "fatigueScore and the test's mean PVT reaction time; positive = the score rises as reactions slow down. Nothing is "
            f"fitted on DROZY. Details and baselines in `drozy_validation`. DROZY: {CITATION}."
        ),
    }


def merge(metrics: Mapping, block: Mapping | None) -> dict:
    """``metrics`` with the DROZY fields set: the same function for a full run and for a DROZY-only run, so both write the same keys in the same order."""
    merged = {key: value for key, value in metrics.items() if key != "drozy_validation"}
    merged.update(pvt_fields(block))
    if block is not None:
        merged["drozy_validation"] = dict(block)
    return merged
