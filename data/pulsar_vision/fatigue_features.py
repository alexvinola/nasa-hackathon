"""Fatigue features and the model's arithmetic. THE single place for their definitions.

The browser worker (G1) ports the part marked WHAT SHIPS exactly, so that Python and JavaScript compute
the same numbers from the same MediaPipe FaceLandmarker output (blendshapes, 478 landmarks and the facial
transformation matrix; model file ``frontend/public/mediapipe/face_landmarker.task``).
Bump ``FEATURES_VERSION`` whenever a definition below changes: ``fatigue_model.json``
carries it, and a model is only valid for the version it was trained with.

==========================================================================================================
WHAT SHIPS: eye closure ``blendshape``, features used as computed (``absolute``), NO calibration step
==========================================================================================================
``SHIPPED_EYE_METHOD`` and ``SHIPPED_NORMALISATION`` below. This is a product decision of the team, not a
choice made by a score: it is what ``faceWorker.ts`` already does, it works however a session starts, and it
is the only variant whose evaluation does not depend on a calibration recording. The decision was taken
after seeing the comparison in ``out/fatigue_report.md``.

Per-frame signals (one value per processed frame; a frame with no face is MISSING = NaN, never 0)
---------------------------------------------------------------------------------------------------
``eye_blink``         mean of the ``eyeBlinkLeft`` and ``eyeBlinkRight`` blendshapes (0 open .. 1 closed).
``closed``            1 when ``eye_blink > 0.5`` (``BLENDSHAPE_CLOSED``, the worker's ``BLINK``), else 0.
``pitch_deg``         head pitch in degrees from the facial transformation matrix ``M`` (4x4, canonical face
                      to camera): ``atan2(M[2][1], M[2][2])``. JavaScript gets the matrix flattened
                      column-major, so the same value is ``atan2(m[6], m[10])`` (what ``faceWorker.ts``
                      already shows). Positive = chin towards the chest (``PITCH_DOWN_SIGN``).
``mouth_open_ratio``  ``mouth.py``, unchanged.

Window features (``FEATURE_NAMES``, in the order the model uses)
----------------------------------------------------------------
A window is every processed frame with ``start <= t < start + 60 s``; windows advance by 10 s. All seven
are pure functions of the frames inside the window, so the browser computes them from a 60 s ring buffer.

A window is USED only if it has at least ``MIN_WINDOW_FRAMES`` frames, a face in at least
``MIN_FACE_FRACTION`` of them and at least one frame whose eye state is known; otherwise it gives no
features and NO SCORE: never a score computed from zeros. Let ``valid`` be the frames
with a face, ``face_fraction = valid / frames`` and ``observed_min = face_fraction * 60 s / 60``.

Episodes are found with the same state machine as the yawn detector (``detector.open_episodes``): a series
opens on the first valid frame at or above an ``on`` level, stays open while at or above an ``off`` level,
closes on the first valid frame below it, and a face lost for more than ``MAX_GAP_S`` closes it at the last
confirming frame. An episode still open at the end of the window ends at its last confirming frame.

1. ``perclos``                    closed frames / valid frames (source ``fmcsa-1998-perclos``).
2. ``blink_rate_per_min``         closures shorter than ``LONG_CLOSURE_S``, per observed minute. A closure is an
                                  episode of the closed series (1 closed, 0 open, NaN missing; on = off = 0.5).
                                  Its duration is ``end - start + frame_dt``, where ``frame_dt`` is the median
                                  time between consecutive frames of the window: each closed frame stands for
                                  one frame period.
3. ``mean_blink_duration_s``      mean duration of those short closures; MISSING (NaN) when the window has none.
4. ``long_closure_rate_per_min``  closures of at least ``LONG_CLOSURE_S`` (0.5 s), per observed minute. The 0.5 s
                                  boundary is an assumption (no registered source); it is a count of long eye
                                  closures, not a microsleep detector.
5. ``yawns_per_min``              yawns found in the window's ``mouth_open_ratio`` series by the detector
                                  calibrated on YawDD (``out/yawn_params.json``, unchanged; ``countYawns`` in
                                  ``yawn.ts``), per window minute. Not divided by ``face_fraction``.
6. ``head_pitch_std_deg``         population standard deviation of ``pitch_deg`` over the valid frames.
7. ``nods_per_min``               head nods per observed minute. A nod is an episode of
                                  ``PITCH_DOWN_SIGN * (pitch_deg - median pitch of the window's valid frames)``
                                  with on = ``NOD_ON_DEG`` and off = ``NOD_OFF_DEG``. Both levels are assumptions.

Model arithmetic (``fatigue_model.json``)
-----------------------------------------
``z[i] = (x[i] - mean[i]) / std[i]``, and ``z[i] = 0`` when ``x[i]`` is missing (the training mean).
``logit[k] = intercept[k] + sum_i coef[k][i] * z[i]``; ``p = softmax(logit)`` over
``[alert, low_vigilance, drowsy]``. ``fatigueScore = 0.5 * p[low_vigilance] + 1.0 * p[drowsy]``, in [0, 1]:
the expected RLDD label (0, 5, 10) divided by 10.

==========================================================================================================
EVALUATED ALTERNATIVES: measured in ``make model``, NOT shipped, the browser does not port them
==========================================================================================================
They stay here because the comparison in the report is computed with them, and because they are worth
trying again on a dataset where ONE recording goes from rested to drowsy (DROZY, for example). RLDD has a
separate recording per state, so it cannot show what a calibration taken at the start of a session is worth:
with the calibration taken from the scored recording instead of the person's alert one, the EAR method lost
its advantage (``calibration_sensitivity`` in ``out/metrics.json``).

Eye closure ``ear_p80``
    ``ear`` is the eye aspect ratio (Soukupova & Cech 2016, source ``soukupova-2016-ear``), mean of both eyes::

        EAR(eye) = (|p2 - p6| + |p3 - p5|) / (2 * |p1 - p4|)

    with the six mesh landmarks of each eye in ``EAR_RIGHT_EYE`` / ``EAR_LEFT_EYE`` (p1..p6 in that order) and
    2D distances **in pixels** (``x * width``, ``y * height``), as in ``mouth.py``. NaN if either eye is
    degenerate (``|p1 - p4| == 0``). Closed when ``ear <= floor + 0.2 * (open - floor)``: the eye is at least
    80 % closed (PERCLOS P80, source ``fmcsa-1998-perclos``) relative to the person's own calibration.
    ``open`` is the median (P50) and ``floor`` the 1st percentile (P1) of ``ear`` over the valid frames of the
    calibration period; percentiles use linear interpolation at position ``q * (n - 1)`` of the sorted values.
    P50 and P1 are assumptions, and on RLDD the P1 floor was often not a closed eye. Until the calibration
    exists no eye state is known, so no window is usable.

Normalisation ``calibrated``
    The calibration period is the first ``CALIBRATION_S`` (120 s) of the session, with the person rested. Its
    reference is, per feature, the mean over the usable windows that lie entirely inside it (starts 0, 10 ..
    60 s: up to 7 windows), ignoring missing values. Every later feature becomes a DIFFERENCE to it
    (``feature - reference``, all seven; none is a ratio, because five of them are often exactly 0 while
    rested). A missing reference makes the calibrated feature missing. A calibration period with fewer than
    ``MIN_CALIBRATION_FRAMES`` frames with a face is not accepted (no EAR threshold, no reference).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from . import detector, mouth
from .detector import YawnParams

FEATURES_VERSION = 1

FEATURE_NAMES: tuple[str, ...] = (
    "perclos",
    "blink_rate_per_min",
    "mean_blink_duration_s",
    "long_closure_rate_per_min",
    "yawns_per_min",
    "head_pitch_std_deg",
    "nods_per_min",
)

# --- eye landmarks: 478-point MediaPipe face mesh, p1..p6 of Soukupova & Cech (2016) -------------------
# p1, p4: the eye corners; p2, p3: upper lid; p5, p6: lower lid (p2 is above p6, p3 above p5).
EAR_RIGHT_EYE: tuple[int, ...] = (33, 160, 158, 133, 153, 144)  # subject's right: outer corner first
EAR_LEFT_EYE: tuple[int, ...] = (362, 385, 387, 263, 373, 380)  # subject's left: inner corner first

EYE_BLINK_LEFT = "eyeBlinkLeft"
EYE_BLINK_RIGHT = "eyeBlinkRight"

BLENDSHAPE = "blendshape"
EAR_P80 = "ear_p80"
EYE_METHODS: tuple[str, ...] = (BLENDSHAPE, EAR_P80)
SHIPPED_EYE_METHOD = BLENDSHAPE  # a product decision, see the module docstring; ear_p80 is an evaluated alternative

BLENDSHAPE_CLOSED = 0.5  # mean eyeBlink blendshape above which the eyes count as closed (faceWorker.ts BLINK)
# Only the evaluated alternative ear_p80 uses these three:
P80_FRACTION = 0.2  # closed when the opening is at most 20 % of the open eye: "at least 80 % closed"
EAR_OPEN_PERCENTILE = 50.0  # assumption, see the module docstring
EAR_FLOOR_PERCENTILE = 1.0  # assumption

# --- windows --------------------------------------------------------------------------------------------
WINDOW_S = 60.0
STEP_S = 10.0
CALIBRATION_S = 120.0  # only the evaluated alternatives calibrate; what ships has no calibration step
MIN_FACE_FRACTION = 0.8  # a window with a face in fewer than 80 % of its frames is not used (our rule)
MIN_WINDOW_FRAMES = 450  # at least 7.5 processed frames per second on average (half of the 15 fps target)
MAX_GAP_S = 0.25  # as the yawn detector: bridges up to 2 frames without a face at 15 fps
MIN_CALIBRATION_FRAMES = 900  # alternatives only: frames with a face a calibration needs (half of 120 s at 15 fps)

# --- events ---------------------------------------------------------------------------------------------
LONG_CLOSURE_S = 0.5  # assumption: closures at least this long are counted apart from blinks
NOD_ON_DEG = 10.0  # assumption: the head drops this far below the window's median pitch
NOD_OFF_DEG = 5.0  # assumption: and the nod ends when it comes back within this
PITCH_DOWN_SIGN = 1.0  # atan2(M[2][1], M[2][2]) grows when the chin goes down (checked on RLDD, see the report)

# --- model ----------------------------------------------------------------------------------------------
CLASS_NAMES: tuple[str, ...] = ("alert", "low_vigilance", "drowsy")
SCORE_WEIGHTS: tuple[float, ...] = (0.0, 0.5, 1.0)  # RLDD labels 0, 5, 10 divided by 10
SCORE_FORMULA = "fatigueScore = 0.5 * P(low_vigilance) + 1.0 * P(drowsy)"

ABSOLUTE = "absolute"
CALIBRATED = "calibrated"
NORMALISATIONS: tuple[str, ...] = (ABSOLUTE, CALIBRATED)
SHIPPED_NORMALISATION = ABSOLUTE  # a product decision, see the module docstring

_EPS = 1e-9


# ------------------------------------------------------------------------------------------ per frame


def eye_aspect_ratio_from_points(eye_points: np.ndarray, width: float, height: float) -> np.ndarray:
    """EAR of one eye. ``eye_points`` has shape ``(..., 6, 2+)``: p1..p6, MediaPipe normalised x, y."""
    scale = np.array([width, height], dtype=np.float64)
    p = np.asarray(eye_points, dtype=np.float64)[..., :2] * scale
    vertical = np.linalg.norm(p[..., 1, :] - p[..., 5, :], axis=-1) + np.linalg.norm(p[..., 2, :] - p[..., 4, :], axis=-1)
    horizontal = np.linalg.norm(p[..., 0, :] - p[..., 3, :], axis=-1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(horizontal > 0.0, vertical / (2.0 * horizontal), np.nan)


def eye_aspect_ratio(right_eye_points: np.ndarray, left_eye_points: np.ndarray, width: float, height: float) -> np.ndarray:
    """The ``ear`` signal: mean of the two eyes; NaN if either is missing or degenerate."""
    right = eye_aspect_ratio_from_points(right_eye_points, width, height)
    left = eye_aspect_ratio_from_points(left_eye_points, width, height)
    return 0.5 * (right + left)


def eye_aspect_ratio_of_mesh(face_landmarks: np.ndarray, width: float, height: float) -> float:
    """``ear`` of one face given the full mesh, shape ``(478, 2+)``, indexed by landmark index."""
    mesh = np.asarray(face_landmarks, dtype=np.float64)
    return float(eye_aspect_ratio(mesh[list(EAR_RIGHT_EYE)], mesh[list(EAR_LEFT_EYE)], width, height))


def eye_blink(eye_blink_left: np.ndarray, eye_blink_right: np.ndarray) -> np.ndarray:
    """The ``eye_blink`` signal: mean of the two blendshape scores."""
    return 0.5 * (np.asarray(eye_blink_left, dtype=np.float64) + np.asarray(eye_blink_right, dtype=np.float64))


def head_angles_deg(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(pitch, yaw, roll)`` in degrees from transformation matrices of shape ``(..., 4, 4)``.

    ``matrix[r][c]`` is row ``r``, column ``c`` (as Python's MediaPipe returns it). Same formulas as
    ``faceWorker.ts``, whose flat array is column-major: ``m[6] = M[2][1]``, ``m[10] = M[2][2]``,
    ``m[2] = M[2][0]``, ``m[1] = M[1][0]``, ``m[0] = M[0][0]``.
    """
    m = np.asarray(matrix, dtype=np.float64)
    pitch = np.degrees(np.arctan2(m[..., 2, 1], m[..., 2, 2]))
    yaw = np.degrees(np.arctan2(-m[..., 2, 0], np.hypot(m[..., 2, 1], m[..., 2, 2])))
    roll = np.degrees(np.arctan2(m[..., 1, 0], m[..., 0, 0]))
    return pitch, yaw, roll


# ------------------------------------------------------------------------------------------ eye closure


@dataclass(frozen=True)
class EarCalibration:
    """A person's open-eye and closed-eye EAR, measured in the calibration period."""

    open: float
    floor: float
    frames: int

    @property
    def threshold(self) -> float:
        return p80_threshold(self.open, self.floor)

    def to_dict(self) -> dict:
        return {"open": self.open, "floor": self.floor, "threshold": self.threshold, "frames": self.frames}


def p80_threshold(open_ear: float, floor_ear: float) -> float:
    """EAR at or below which the eye is at least 80 % closed."""
    return floor_ear + P80_FRACTION * (open_ear - floor_ear)


def percentile(values: Sequence[float], q: float) -> float:
    """Percentile ``q`` (0..100) with linear interpolation at position ``q/100 * (n - 1)``; NaN if empty."""
    data = sorted(float(v) for v in values if v == v)
    if not data:
        return math.nan
    position = (q / 100.0) * (len(data) - 1)
    low = int(math.floor(position))
    high = min(low + 1, len(data) - 1)
    return data[low] + (position - low) * (data[high] - data[low])


def ear_calibration(ear: Sequence[float]) -> EarCalibration:
    """Calibrate from the ``ear`` values of the calibration period (missing frames are ignored)."""
    valid = [float(v) for v in ear if v == v]
    return EarCalibration(
        open=percentile(valid, EAR_OPEN_PERCENTILE),
        floor=percentile(valid, EAR_FLOOR_PERCENTILE),
        frames=len(valid),
    )


def closed_from_blendshape(eye_blink_signal: np.ndarray) -> np.ndarray:
    """Closed series (1 closed, 0 open, NaN missing) with the ``blendshape`` method."""
    signal = np.asarray(eye_blink_signal, dtype=np.float64)
    return np.where(np.isnan(signal), np.nan, (signal > BLENDSHAPE_CLOSED).astype(np.float64))


def closed_from_ear(ear: np.ndarray, threshold: float) -> np.ndarray:
    """Closed series with the ``ear_p80`` method; all missing when there is no threshold."""
    signal = np.asarray(ear, dtype=np.float64)
    if threshold != threshold:
        return np.full(signal.shape, np.nan)
    return np.where(np.isnan(signal), np.nan, (signal <= threshold).astype(np.float64))


# ------------------------------------------------------------------------------------------ windows


def window_starts(first_time_s: float, end_time_s: float, window_s: float = WINDOW_S, step_s: float = STEP_S) -> list[float]:
    """Starts of every full window of a recording: ``first + k * step`` while the window ends by ``end_time_s``.

    ``end_time_s`` is the end of the recording: the time of its last frame plus one frame period.
    """
    starts: list[float] = []
    k = 0
    while first_time_s + k * step_s + window_s <= end_time_s + _EPS:
        starts.append(first_time_s + k * step_s)
        k += 1
    return starts


def window_slice(time_s: np.ndarray, start_s: float, window_s: float = WINDOW_S) -> slice:
    """Frames with ``start <= t < start + window`` (``time_s`` is sorted)."""
    low = int(np.searchsorted(time_s, start_s - _EPS, side="left"))
    high = int(np.searchsorted(time_s, start_s + window_s - _EPS, side="left"))
    return slice(low, high)


def frame_period(time_s: np.ndarray) -> float:
    """Median time between consecutive frames; NaN with fewer than two frames."""
    if len(time_s) < 2:
        return math.nan
    return float(np.median(np.diff(np.asarray(time_s, dtype=np.float64))))


def closure_durations(time_s: Sequence[float], closed: Sequence[float]) -> list[float]:
    """Duration of every eye closure in a window, in order (see the module docstring)."""
    times = [float(t) for t in time_s]
    episodes = detector.open_episodes(times, [float(c) for c in closed], 0.5, 0.5, MAX_GAP_S)
    period = frame_period(np.asarray(times))
    return [e.duration_s + period for e in episodes]


def nod_count(time_s: Sequence[float], pitch_deg: Sequence[float]) -> int:
    """Head nods in a window: drops of at least ``NOD_ON_DEG`` below the window's median pitch."""
    pitch = np.asarray(pitch_deg, dtype=np.float64)
    valid = pitch[~np.isnan(pitch)]
    if not len(valid):
        return 0
    drop = PITCH_DOWN_SIGN * (pitch - float(np.median(valid)))
    episodes = detector.open_episodes([float(t) for t in time_s], [float(d) for d in drop], NOD_ON_DEG, NOD_OFF_DEG, MAX_GAP_S)
    return len(episodes)


def window_usable(frames: int, face_frames: int) -> bool:
    """The rule that decides whether a window gives features at all."""
    return frames >= MIN_WINDOW_FRAMES and face_frames >= MIN_FACE_FRACTION * frames - _EPS


def window_features(
    time_s: np.ndarray,
    face: np.ndarray,
    closed: np.ndarray,
    pitch_deg: np.ndarray,
    mouth_open_ratio: np.ndarray,
    yawn_params: YawnParams,
    window_s: float = WINDOW_S,
) -> dict[str, float] | None:
    """The seven features of one window, or ``None`` when the window is not usable.

    Every array holds the frames of the window only, in time order: ``face`` is True where a face was
    found, ``closed`` is the closed series of the chosen eye method, the other two are per-frame signals.
    """
    frames = len(time_s)
    face_frames = int(np.count_nonzero(face))
    if not window_usable(frames, face_frames):
        return None
    closed = np.asarray(closed, dtype=np.float64)
    seen = ~np.isnan(closed)
    if not seen.any():
        return None  # no eye state at all (ear_p80 before its calibration exists): no features, no score
    observed_min = (face_frames / frames) * (window_s / 60.0)

    durations = closure_durations(time_s, closed)
    blinks = [d for d in durations if d < LONG_CLOSURE_S - _EPS]
    long_closures = len(durations) - len(blinks)
    pitch = np.asarray(pitch_deg, dtype=np.float64)
    pitch_valid = pitch[~np.isnan(pitch)]
    yawns = detector.detect_yawns([float(t) for t in time_s], [float(r) for r in mouth_open_ratio], yawn_params)

    return {
        "perclos": float(np.count_nonzero(closed[seen] > 0.5) / seen.sum()),
        "blink_rate_per_min": len(blinks) / observed_min,
        "mean_blink_duration_s": float(np.mean(blinks)) if blinks else math.nan,
        "long_closure_rate_per_min": long_closures / observed_min,
        "yawns_per_min": len(yawns) / (window_s / 60.0),
        "head_pitch_std_deg": float(np.std(pitch_valid)) if len(pitch_valid) else math.nan,
        "nods_per_min": nod_count(time_s, pitch) / observed_min,
    }


def feature_vector(features: Mapping[str, float]) -> np.ndarray:
    """A features mapping as a vector in ``FEATURE_NAMES`` order."""
    return np.array([features[name] for name in FEATURE_NAMES], dtype=np.float64)


# ------------------------------------------------------------------------------------------ calibration


def calibration_reference(calibration_windows: np.ndarray) -> np.ndarray:
    """Per-feature mean over the calibration windows (rows), ignoring missing values.

    A feature that is missing in every window (or no window at all) has a missing reference.
    """
    rows = np.asarray(calibration_windows, dtype=np.float64).reshape(-1, len(FEATURE_NAMES))
    reference = np.full(len(FEATURE_NAMES), np.nan)
    for column in range(len(FEATURE_NAMES)):
        values = rows[:, column]
        values = values[~np.isnan(values)]
        if len(values):
            reference[column] = float(values.mean())
    return reference


def calibrate(features: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """The ``calibrated`` variant: ``feature - reference`` for every feature."""
    return np.asarray(features, dtype=np.float64) - np.asarray(reference, dtype=np.float64)


# ------------------------------------------------------------------------------------------ model


def standardise(features: np.ndarray, mean: Sequence[float], std: Sequence[float]) -> np.ndarray:
    """``(x - mean) / std``; a missing feature becomes 0, i.e. the training mean."""
    z = (np.asarray(features, dtype=np.float64) - np.asarray(mean, dtype=np.float64)) / np.asarray(std, dtype=np.float64)
    return np.where(np.isnan(z), 0.0, z)


def predict_proba(features: np.ndarray, model: Mapping) -> np.ndarray:
    """Class probabilities ``[alert, low_vigilance, drowsy]`` for rows of features, from a model dict."""
    z = standardise(np.atleast_2d(features), model["mean"], model["std"])
    logits = z @ np.asarray(model["coef"], dtype=np.float64).T + np.asarray(model["intercept"], dtype=np.float64)
    logits -= logits.max(axis=1, keepdims=True)
    exp = np.exp(logits)
    return exp / exp.sum(axis=1, keepdims=True)


def fatigue_score(proba: np.ndarray) -> np.ndarray:
    """``0.5 * P(low_vigilance) + 1.0 * P(drowsy)``: the expected label divided by 10, in [0, 1]."""
    return np.asarray(proba, dtype=np.float64) @ np.asarray(SCORE_WEIGHTS)


# ------------------------------------------------------------------------------------------ what ships today

BROWSER_NOSE_SAMPLES = 90  # faceWorker.ts keeps the last 90 nose heights
BROWSER_BASELINE_FORMULA = "clamp01(0.6 * perclos + 0.25 * min(1, yawnsPerMin / 4) + 0.15 * clamp01(12 * std(noseY)))"


def browser_baseline_score(perclos: float, yawns_last_minute: float, nose_y: Sequence[float]) -> float:
    """The fixed formula ``faceWorker.ts`` ships today, reproduced only to compare the model against it.

    ``perclos`` is the ``blendshape`` PERCLOS of the last minute, ``yawns_last_minute`` the yawns the
    streaming detector counted in it, and ``nose_y`` the normalised height of the nose tip (landmark 1)
    in the last ``BROWSER_NOSE_SAMPLES`` frames with a face. Missing PERCLOS counts as 0, as in the worker.
    """
    values = np.asarray(nose_y, dtype=np.float64)
    spread = float(np.std(values)) if len(values) else 0.0
    instability = min(1.0, max(0.0, spread * 12.0))
    closed_share = 0.0 if perclos != perclos else perclos
    return min(1.0, max(0.0, 0.6 * closed_share + 0.25 * min(1.0, yawns_last_minute / 4.0) + 0.15 * instability))


__all__ = [name for name in dir() if not name.startswith("_")]
