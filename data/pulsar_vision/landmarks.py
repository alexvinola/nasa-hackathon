"""Landmark extraction with MediaPipe Tasks ``FaceLandmarker`` in VIDEO running mode.

It loads the same model file the browser loads
(``frontend/public/mediapipe/face_landmarker.task``) and processes every ``step``-th
frame so that the series has G1's minimum frame rate (15 fps): Python and the browser
see the same temporal resolution.

A frame where no face is found is recorded as **missing** (NaN), never as zero.

Nothing here writes pixels anywhere: only landmark coordinates of a handful of points
are kept, and the cache they go to is git-ignored (YawDD licence: no frames or crops).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import mouth

TARGET_FPS = 15.0

# Bump when the extraction changes in a way that invalidates cached series.
EXTRACTOR_VERSION = 1

# FaceLandmarker options. The browser worker must use the same values
# (numFaces, minFaceDetectionConfidence, minFacePresenceConfidence, minTrackingConfidence).
NUM_FACES = 1
MIN_FACE_DETECTION_CONFIDENCE = 0.5
MIN_FACE_PRESENCE_CONFIDENCE = 0.5
MIN_TRACKING_CONFIDENCE = 0.5

# Landmarks kept in the cache. The first four are the product formula (``mouth.py``);
# the rest only allow alternative formulas to be compared without re-running MediaPipe.
CACHED_LANDMARKS: tuple[int, ...] = (
    mouth.UPPER_INNER_LIP,  # 13
    mouth.LOWER_INNER_LIP,  # 14
    mouth.RIGHT_EYE_OUTER,  # 33
    mouth.LEFT_EYE_OUTER,  # 263
    78,  # inner mouth corner, subject's right
    308,  # inner mouth corner, subject's left
    61,  # outer mouth corner, subject's right
    291,  # outer mouth corner, subject's left
    0,  # upper lip, outer contour centre
    17,  # lower lip, outer contour centre
    133,  # inner corner of the right eye
    362,  # inner corner of the left eye
    10,  # top of the forehead
    152,  # chin
    1,  # nose tip
)
LANDMARK_COLUMN = {index: column for column, index in enumerate(CACHED_LANDMARKS)}

JAW_OPEN_BLENDSHAPE = "jawOpen"


@dataclass
class VideoSeries:
    """Per-frame series of one video at the processed frame rate."""

    frame_index: np.ndarray  # int32 [n]: index of the frame in the source video
    time_s: np.ndarray  # float64 [n]: frame_index / source_fps
    xyz: np.ndarray  # float32 [n, len(CACHED_LANDMARKS), 3]: normalised x, y, z; NaN when no face
    jaw_open: np.ndarray  # float32 [n]: MediaPipe "jawOpen" blendshape; NaN when no face
    meta: dict

    @property
    def face_found(self) -> np.ndarray:
        return ~np.isnan(self.xyz[:, 0, 0])

    def points(self, landmark_index: int) -> np.ndarray:
        return self.xyz[:, LANDMARK_COLUMN[landmark_index], :]

    def mouth_open_ratio(self) -> np.ndarray:
        """The product feature (``mouth.py``) for every processed frame; NaN when no face."""
        return mouth.mouth_open_ratio_from_points(
            self.points(mouth.UPPER_INNER_LIP),
            self.points(mouth.LOWER_INNER_LIP),
            self.points(mouth.RIGHT_EYE_OUTER),
            self.points(mouth.LEFT_EYE_OUTER),
            self.meta["width"],
            self.meta["height"],
        )


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def frame_step(source_fps: float, target_fps: float = TARGET_FPS) -> int:
    """How many source frames to advance per processed frame (30 fps -> 2 for 15 fps)."""
    if not source_fps or source_fps <= 0:
        raise ValueError(f"invalid source frame rate: {source_fps!r}")
    return max(1, int(round(source_fps / target_fps)))


def cache_signature(model_sha256: str, target_fps: float = TARGET_FPS) -> dict:
    """What a cached series must match to be reused."""
    return {
        "extractor_version": EXTRACTOR_VERSION,
        "model_sha256": model_sha256,
        "target_fps": target_fps,
        "cached_landmarks": list(CACHED_LANDMARKS),
        "num_faces": NUM_FACES,
        "min_face_detection_confidence": MIN_FACE_DETECTION_CONFIDENCE,
        "min_face_presence_confidence": MIN_FACE_PRESENCE_CONFIDENCE,
        "min_tracking_confidence": MIN_TRACKING_CONFIDENCE,
    }


def extract_video(video_path: Path, model_bytes: bytes, target_fps: float = TARGET_FPS) -> VideoSeries:
    """Run FaceLandmarker over one video and return its per-frame series."""
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    started = time.perf_counter()
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise OSError(f"cannot open video: {video_path}")
    try:
        source_fps = float(capture.get(cv2.CAP_PROP_FPS))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        reported_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        step = frame_step(source_fps, target_fps)

        options = vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_buffer=model_bytes),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=NUM_FACES,
            min_face_detection_confidence=MIN_FACE_DETECTION_CONFIDENCE,
            min_face_presence_confidence=MIN_FACE_PRESENCE_CONFIDENCE,
            min_tracking_confidence=MIN_TRACKING_CONFIDENCE,
            output_face_blendshapes=True,
        )
        frame_indices: list[int] = []
        rows: list[np.ndarray] = []
        jaw: list[float] = []
        missing_row = np.full((len(CACHED_LANDMARKS), 3), np.nan, dtype=np.float32)
        mediapipe_seconds = 0.0
        frames_read = 0
        last_timestamp_ms = -1

        # One landmarker per video: VIDEO mode tracks across frames and needs increasing timestamps.
        with vision.FaceLandmarker.create_from_options(options) as landmarker:
            index = 0
            while capture.grab():
                frames_read += 1
                if index % step == 0:
                    ok, frame_bgr = capture.retrieve()
                    if not ok:
                        break
                    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
                    timestamp_ms = max(int(round(index * 1000.0 / source_fps)), last_timestamp_ms + 1)
                    last_timestamp_ms = timestamp_ms
                    tick = time.perf_counter()
                    result = landmarker.detect_for_video(image, timestamp_ms)
                    mediapipe_seconds += time.perf_counter() - tick

                    frame_indices.append(index)
                    if result.face_landmarks:
                        face = result.face_landmarks[0]
                        rows.append(
                            np.array([(face[i].x, face[i].y, face[i].z) for i in CACHED_LANDMARKS], dtype=np.float32)
                        )
                        jaw.append(_jaw_open(result))
                    else:
                        rows.append(missing_row)
                        jaw.append(np.nan)
                index += 1
    finally:
        capture.release()

    frame_index = np.asarray(frame_indices, dtype=np.int32)
    xyz = np.stack(rows) if rows else np.empty((0, len(CACHED_LANDMARKS), 3), dtype=np.float32)
    meta = {
        **cache_signature(sha256_of(model_bytes), target_fps),
        "source_fps": source_fps,
        "width": width,
        "height": height,
        "reported_frames": reported_frames,
        "frames_read": frames_read,
        "frame_step": step,
        "processed_fps": source_fps / step,
        "processed_frames": int(len(frame_index)),
        "mediapipe_seconds": mediapipe_seconds,
        "total_seconds": time.perf_counter() - started,
        "mediapipe_version": mp.__version__,
    }
    return VideoSeries(
        frame_index=frame_index,
        time_s=frame_index.astype(np.float64) / source_fps,
        xyz=xyz,
        jaw_open=np.asarray(jaw, dtype=np.float32),
        meta=meta,
    )


def _jaw_open(result) -> float:
    if not result.face_blendshapes:
        return float("nan")
    for category in result.face_blendshapes[0]:
        if category.category_name == JAW_OPEN_BLENDSHAPE:
            return float(category.score)
    return float("nan")


def save_series(series: VideoSeries, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    with open(temporary, "wb") as handle:
        np.savez_compressed(
            handle,
            frame_index=series.frame_index,
            time_s=series.time_s,
            xyz=series.xyz,
            jaw_open=series.jaw_open,
            meta=np.array(json.dumps(series.meta)),
        )
    temporary.replace(path)


def load_series(path: Path, signature: dict) -> VideoSeries | None:
    """Load a cached series, or ``None`` if it is absent, unreadable or from another setup."""
    if not path.is_file():
        return None
    try:
        with np.load(path, allow_pickle=False) as data:
            meta = json.loads(str(data["meta"]))
            if any(meta.get(key) != value for key, value in signature.items()):
                return None
            return VideoSeries(
                frame_index=data["frame_index"],
                time_s=data["time_s"],
                xyz=data["xyz"],
                jaw_open=data["jaw_open"],
                meta=meta,
            )
    except (OSError, ValueError, KeyError):
        return None
