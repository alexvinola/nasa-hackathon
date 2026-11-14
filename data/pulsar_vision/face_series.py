"""Per-frame face series for the fatigue features: landmarks, blendshapes and the transformation matrix.

Same FaceLandmarker model, running mode and confidences as ``landmarks.py`` (the YawDD extractor) and
as the browser worker; it only keeps more of the output, because the fatigue features need the eyes,
the eyeBlink blendshapes and the head pose as well as the mouth. It has its own cache signature, so the
YawDD cache is untouched.

Frames are sampled BY TIME, from the container's own timestamps: a frame is processed when at least one
target period (1/15 s, minus a 10 % tolerance for timestamp jitter) has passed since the last processed
one. A constant 30 fps video gives every second frame, as the YawDD extractor does; phone videos with a
variable frame rate, or slower than 15 fps, keep their real times. Every later computation uses those
times, never a frame count. A dataset that measured its own frame times (DROZY) passes them in
(``frame_times_ms``, ``DatasetClock``) and they replace the container's.

Phone videos carry a rotation flag. OpenCV applies it while decoding (``CAP_PROP_ORIENTATION_AUTO``); the
flag and the head roll measured on the result are kept in ``meta`` so a sideways video shows up in the
report instead of silently losing the face.

A frame where no face is found is MISSING (NaN), never zero. Nothing here writes pixels anywhere: the
cache holds coordinates and scores only and is git-ignored.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

import numpy as np

from . import fatigue_features, landmarks, mouth

# Bump when the extraction changes in a way that invalidates cached series.
EXTRACTOR_VERSION = 1

SAMPLING_TOLERANCE = 0.10  # share of the target period forgiven to timestamp jitter

# Landmarks kept in the cache: everything the features read, plus a few points that let alternative
# formulas be compared without re-running MediaPipe.
CACHED_LANDMARKS: tuple[int, ...] = tuple(
    dict.fromkeys(
        landmarks.CACHED_LANDMARKS
        + fatigue_features.EAR_RIGHT_EYE
        + fatigue_features.EAR_LEFT_EYE
        + (159, 145, 386, 374)  # centres of the upper and lower lids, right then left eye
        + (468, 473)  # iris centres
    )
)
LANDMARK_COLUMN = {index: column for column, index in enumerate(CACHED_LANDMARKS)}
NOSE_TIP = 1


@dataclass
class FaceSeries:
    """Per-frame series of one video at the processed frame rate."""

    frame_index: np.ndarray  # int32 [n]: index of the frame in the source video
    time_s: np.ndarray  # float64 [n]: presentation time of the frame, from the container
    xyz: np.ndarray  # float32 [n, len(CACHED_LANDMARKS), 3]: normalised x, y, z; NaN when no face
    blendshapes: np.ndarray  # float32 [n, len(meta["blendshape_names"])]; NaN when no face
    matrix: np.ndarray  # float32 [n, 4, 4]: facial transformation matrix, row-major; NaN when no face
    meta: dict

    @property
    def face_found(self) -> np.ndarray:
        return ~np.isnan(self.xyz[:, 0, 0])

    def points(self, landmark_index: int) -> np.ndarray:
        return self.xyz[:, LANDMARK_COLUMN[landmark_index], :]

    def eye_points(self, indices: tuple[int, ...]) -> np.ndarray:
        return self.xyz[:, [LANDMARK_COLUMN[i] for i in indices], :]

    def blendshape(self, name: str) -> np.ndarray:
        return self.blendshapes[:, self.meta["blendshape_names"].index(name)].astype(np.float64)

    # --- the per-frame signals of fatigue_features.py ---

    def eye_blink(self) -> np.ndarray:
        return fatigue_features.eye_blink(
            self.blendshape(fatigue_features.EYE_BLINK_LEFT), self.blendshape(fatigue_features.EYE_BLINK_RIGHT)
        )

    def ear(self) -> np.ndarray:
        return fatigue_features.eye_aspect_ratio(
            self.eye_points(fatigue_features.EAR_RIGHT_EYE),
            self.eye_points(fatigue_features.EAR_LEFT_EYE),
            self.meta["width"],
            self.meta["height"],
        )

    def head_angles_deg(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        return fatigue_features.head_angles_deg(self.matrix)

    def mouth_open_ratio(self) -> np.ndarray:
        return mouth.mouth_open_ratio_from_points(
            self.points(mouth.UPPER_INNER_LIP),
            self.points(mouth.LOWER_INNER_LIP),
            self.points(mouth.RIGHT_EYE_OUTER),
            self.points(mouth.LEFT_EYE_OUTER),
            self.meta["width"],
            self.meta["height"],
        )

    def nose_y(self) -> np.ndarray:
        return self.points(NOSE_TIP)[:, 1].astype(np.float64)


class TimeSampler:
    """Decides, frame by frame, which frames to process so that they are about ``target_fps`` apart."""

    def __init__(self, target_fps: float = landmarks.TARGET_FPS, tolerance: float = SAMPLING_TOLERANCE) -> None:
        if not target_fps or target_fps <= 0:
            raise ValueError(f"invalid target frame rate: {target_fps!r}")
        self.min_interval_ms = (1000.0 / target_fps) * (1.0 - tolerance)
        self.last_ms: float | None = None

    def take(self, time_ms: float) -> bool:
        if self.last_ms is None or time_ms - self.last_ms >= self.min_interval_ms - 1e-6:
            self.last_ms = time_ms
            return True
        return False


class FrameClock:
    """Presentation time of each decoded frame in milliseconds, strictly increasing.

    It is the container's own timestamp. Where that does not advance (a file without usable
    timestamps, or a repeated one), the frame is placed one nominal frame period after the previous
    one, and ``fallbacks`` counts how often that happened.
    """

    def __init__(self, source_fps: float) -> None:
        self.step_ms = 1000.0 / source_fps if source_fps and source_fps > 0 else 1000.0 / 30.0
        self.previous_ms: float | None = None
        self.fallbacks = 0

    def time_ms(self, container_ms: float) -> float:
        if self.previous_ms is None:
            time_ms = container_ms if math.isfinite(container_ms) else 0.0
        elif container_ms > self.previous_ms:
            time_ms = container_ms
        else:
            time_ms = self.previous_ms + self.step_ms
            self.fallbacks += 1
        self.previous_ms = time_ms
        return time_ms


class DatasetClock:
    """Frame times measured by the dataset itself, one per decoded frame, in milliseconds.

    For recordings whose container timestamps are not the real ones (DROZY dropped frames while
    recording, so its mp4 plays them at a nominal rate). Same interface as ``FrameClock``: frame ``i``
    of the decode gets ``times_ms[i]``. A video with more frames than times, or times that do not
    increase, is an error, never a guess; ``check_complete`` catches a video with fewer frames.
    """

    fallbacks = 0  # never: every time is the dataset's

    def __init__(self, times_ms) -> None:
        self.times_ms = np.asarray(times_ms, dtype=np.float64)
        if self.times_ms.ndim != 1 or not len(self.times_ms):
            raise ValueError("no frame times")
        if not np.all(np.isfinite(self.times_ms)) or np.any(np.diff(self.times_ms) <= 0):
            raise ValueError("frame times must be finite and strictly increasing")
        self.used = 0

    def time_ms(self, container_ms: float) -> float:
        if self.used >= len(self.times_ms):
            raise OSError(f"the video has more frames than the {len(self.times_ms)} frame times given")
        time_ms = float(self.times_ms[self.used])
        self.used += 1
        return time_ms

    def check_complete(self) -> None:
        if self.used != len(self.times_ms):
            raise OSError(f"the video has {self.used} frames but {len(self.times_ms)} frame times were given")


def installed_version(package: str) -> str | None:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return None


def sample_indices(times_ms, target_fps: float = landmarks.TARGET_FPS) -> list[int]:
    """Indices of the frames ``TimeSampler`` processes, given every frame's time."""
    sampler = TimeSampler(target_fps)
    return [index for index, time_ms in enumerate(times_ms) if sampler.take(float(time_ms))]


def cache_signature(model_sha256: str, source_size_bytes: int | None = None, target_fps: float = landmarks.TARGET_FPS) -> dict:
    """What a cached series must match to be reused."""
    signature = {
        "face_series_version": EXTRACTOR_VERSION,
        "mediapipe_version": installed_version("mediapipe"),  # another MediaPipe may place landmarks differently
        "model_sha256": model_sha256,
        "target_fps": target_fps,
        "sampling_tolerance": SAMPLING_TOLERANCE,
        "cached_landmarks": list(CACHED_LANDMARKS),
        "num_faces": landmarks.NUM_FACES,
        "min_face_detection_confidence": landmarks.MIN_FACE_DETECTION_CONFIDENCE,
        "min_face_presence_confidence": landmarks.MIN_FACE_PRESENCE_CONFIDENCE,
        "min_tracking_confidence": landmarks.MIN_TRACKING_CONFIDENCE,
    }
    if source_size_bytes is not None:
        signature["source_size_bytes"] = int(source_size_bytes)
    return signature


def extract_face_series(
    video_path: Path, model_bytes: bytes, target_fps: float = landmarks.TARGET_FPS, frame_times_ms=None
) -> FaceSeries:
    """Run FaceLandmarker over one video and return its per-frame series.

    ``frame_times_ms``: the real time of every frame of the video when the dataset measured it
    (``DatasetClock``); sampling, MediaPipe's timestamps and every later computation then use those
    times instead of the container's. ``None`` (RLDD, YawDD): the container's own timestamps.
    """
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    started = time.perf_counter()
    source_size = video_path.stat().st_size
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise OSError(f"cannot open video: {video_path}")
    try:
        source_fps = float(capture.get(cv2.CAP_PROP_FPS))
        reported_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        orientation_meta = float(capture.get(cv2.CAP_PROP_ORIENTATION_META))
        orientation_auto = bool(capture.get(cv2.CAP_PROP_ORIENTATION_AUTO))
        clock = FrameClock(source_fps) if frame_times_ms is None else DatasetClock(frame_times_ms)

        options = vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_buffer=model_bytes),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=landmarks.NUM_FACES,
            min_face_detection_confidence=landmarks.MIN_FACE_DETECTION_CONFIDENCE,
            min_face_presence_confidence=landmarks.MIN_FACE_PRESENCE_CONFIDENCE,
            min_tracking_confidence=landmarks.MIN_TRACKING_CONFIDENCE,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
        )
        sampler = TimeSampler(target_fps)
        frame_indices: list[int] = []
        times_ms: list[float] = []
        rows: list[np.ndarray] = []
        shapes: list[np.ndarray] = []
        matrices: list[np.ndarray] = []
        blendshape_names: list[str] | None = None
        missing_row = np.full((len(CACHED_LANDMARKS), 3), np.nan, dtype=np.float32)
        missing_matrix = np.full((4, 4), np.nan, dtype=np.float32)
        mediapipe_seconds = 0.0
        frames_read = 0
        width = height = 0
        last_timestamp_ms = -1

        # One landmarker per video: VIDEO mode tracks across frames and needs increasing timestamps.
        with vision.FaceLandmarker.create_from_options(options) as landmarker:
            index = 0
            while capture.grab():
                frames_read += 1
                time_ms = clock.time_ms(float(capture.get(cv2.CAP_PROP_POS_MSEC)))
                if sampler.take(time_ms):
                    ok, frame_bgr = capture.retrieve()
                    if not ok:
                        # A truncated series must not be cached as if it were the whole video.
                        raise OSError(f"frame {index} of {video_path.name} could not be decoded")
                    height, width = frame_bgr.shape[:2]
                    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
                    timestamp_ms = max(int(round(time_ms)), last_timestamp_ms + 1)
                    last_timestamp_ms = timestamp_ms
                    tick = time.perf_counter()
                    result = landmarker.detect_for_video(image, timestamp_ms)
                    mediapipe_seconds += time.perf_counter() - tick

                    frame_indices.append(index)
                    times_ms.append(time_ms)
                    found = bool(result.face_landmarks) and bool(result.face_blendshapes) and bool(result.facial_transformation_matrixes)
                    if found:
                        face = result.face_landmarks[0]
                        categories = result.face_blendshapes[0]
                        if blendshape_names is None:
                            blendshape_names = [c.category_name for c in categories]
                        rows.append(np.array([(face[i].x, face[i].y, face[i].z) for i in CACHED_LANDMARKS], dtype=np.float32))
                        shapes.append(np.array([c.score for c in categories], dtype=np.float32))
                        matrices.append(np.asarray(result.facial_transformation_matrixes[0], dtype=np.float32).reshape(4, 4))
                    else:
                        rows.append(missing_row)
                        shapes.append(None)
                        matrices.append(missing_matrix)
                index += 1
        if isinstance(clock, DatasetClock):
            clock.check_complete()
    finally:
        capture.release()

    names = blendshape_names or []
    missing_shapes = np.full(len(names), np.nan, dtype=np.float32)
    blend = [missing_shapes if s is None else s for s in shapes]
    n = len(frame_indices)
    meta = {
        **cache_signature(landmarks.sha256_of(model_bytes), source_size, target_fps),
        "source_fps": source_fps,
        "width": width,  # of the decoded frame, i.e. after OpenCV applied the rotation flag
        "height": height,
        "orientation_meta_deg": orientation_meta,
        "orientation_auto": orientation_auto,
        "reported_frames": reported_frames,
        "frames_read": frames_read,
        "timestamp_fallbacks": clock.fallbacks,
        "frame_times": "container" if frame_times_ms is None else "dataset",
        "processed_frames": n,
        "blendshape_names": names,
        "mediapipe_seconds": mediapipe_seconds,
        "total_seconds": time.perf_counter() - started,
        "mediapipe_version": mp.__version__,
        "opencv_version": cv2.__version__,
    }
    return FaceSeries(
        frame_index=np.asarray(frame_indices, dtype=np.int32),
        time_s=np.asarray(times_ms, dtype=np.float64) / 1000.0,
        xyz=np.stack(rows) if rows else np.empty((0, len(CACHED_LANDMARKS), 3), dtype=np.float32),
        blendshapes=np.stack(blend) if blend else np.empty((0, len(names)), dtype=np.float32),
        matrix=np.stack(matrices) if matrices else np.empty((0, 4, 4), dtype=np.float32),
        meta=meta,
    )


def save_series(series: FaceSeries, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    with open(temporary, "wb") as handle:
        np.savez_compressed(
            handle,
            frame_index=series.frame_index,
            time_s=series.time_s,
            xyz=series.xyz,
            blendshapes=series.blendshapes,
            matrix=series.matrix,
            meta=np.array(json.dumps(series.meta)),
        )
    temporary.replace(path)


def load_series(path: Path, signature: dict) -> FaceSeries | None:
    """Load a cached series, or ``None`` if it is absent, unreadable or from another setup."""
    if not path.is_file():
        return None
    try:
        with np.load(path, allow_pickle=False) as data:
            meta = json.loads(str(data["meta"]))
            if any(meta.get(key) != value for key, value in signature.items()):
                return None
            return FaceSeries(
                frame_index=data["frame_index"],
                time_s=data["time_s"],
                xyz=data["xyz"],
                blendshapes=data["blendshapes"],
                matrix=data["matrix"],
                meta=meta,
            )
    except (OSError, ValueError, KeyError):
        return None
