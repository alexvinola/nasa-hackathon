"""Mouth opening feature. THE single place for its landmark indices and formula.

The browser worker (G1) must port this file exactly, so that Python and JavaScript
compute the same number from the same MediaPipe FaceLandmarker output.

Formula (``FORMULA_NAME``)::

    mouth_open_ratio = dist(UPPER_INNER_LIP, LOWER_INNER_LIP) / dist(RIGHT_EYE_OUTER, LEFT_EYE_OUTER)

- Landmark indices are those of the 478-point MediaPipe face mesh returned by
  ``FaceLandmarker`` (``result.face_landmarks[0][i]`` in Python,
  ``result.faceLandmarks[0][i]`` in JavaScript).
- ``dist`` is the 2D Euclidean distance **in pixels**. MediaPipe returns ``x`` normalised
  by the image width and ``y`` by the image height, so each coordinate must be multiplied
  back (``x * width``, ``y * height``) before measuring; otherwise a 640x480 frame
  stretches horizontal distances by 4/3 relative to vertical ones. ``z`` is not used.
- The numerator is the gap between the centres of the inner lip contours: about 0 with
  the mouth closed, regardless of lip thickness.
- The denominator is the distance between the outer corners of the eyes. It is a
  face-size measure that does not change when the jaw drops (face height and mouth
  width both do), so the ratio is independent of the distance to the camera.
- The ratio is dimensionless. If the eye corners coincide (degenerate detection) the
  value is NaN, i.e. missing; a frame with no face is missing too, never 0.

Known limit: the eye-corner distance shrinks when the head turns sideways (yaw) and the
lip gap shrinks when it nods (pitch); the ratio is not corrected for head pose.
"""

from __future__ import annotations

import numpy as np

# 478-point MediaPipe face mesh indices.
UPPER_INNER_LIP = 13  # centre of the upper lip, inner contour
LOWER_INNER_LIP = 14  # centre of the lower lip, inner contour
RIGHT_EYE_OUTER = 33  # outer corner of the subject's right eye
LEFT_EYE_OUTER = 263  # outer corner of the subject's left eye

LANDMARKS: dict[str, int] = {
    "upper_inner_lip": UPPER_INNER_LIP,
    "lower_inner_lip": LOWER_INNER_LIP,
    "right_eye_outer": RIGHT_EYE_OUTER,
    "left_eye_outer": LEFT_EYE_OUTER,
}

FORMULA_NAME = "inner_lip_gap_over_outer_eye_corner_distance_2d_px"
FORMULA = (
    "dist(upper_inner_lip, lower_inner_lip) / dist(right_eye_outer, left_eye_outer), "
    "2D Euclidean distance in pixels (x * image_width, y * image_height)"
)


def mouth_open_ratio_from_points(
    upper_lip: np.ndarray,
    lower_lip: np.ndarray,
    right_eye: np.ndarray,
    left_eye: np.ndarray,
    width: float,
    height: float,
) -> np.ndarray:
    """Vectorised formula over arrays of normalised points.

    Each argument has shape ``(..., 2)`` or ``(..., 3)`` holding MediaPipe normalised
    ``x, y[, z]``; only ``x`` and ``y`` are read. NaN inputs give NaN outputs.
    """
    scale = np.array([width, height], dtype=np.float64)
    upper = np.asarray(upper_lip, dtype=np.float64)[..., :2] * scale
    lower = np.asarray(lower_lip, dtype=np.float64)[..., :2] * scale
    right = np.asarray(right_eye, dtype=np.float64)[..., :2] * scale
    left = np.asarray(left_eye, dtype=np.float64)[..., :2] * scale
    gap = np.linalg.norm(upper - lower, axis=-1)
    eye_distance = np.linalg.norm(right - left, axis=-1)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(eye_distance > 0.0, gap / eye_distance, np.nan)
    return ratio


def mouth_open_ratio(face_landmarks: np.ndarray, width: float, height: float) -> float:
    """Mouth opening ratio of one face.

    ``face_landmarks`` is the full mesh as an array of shape ``(478, 2)`` or ``(478, 3)``
    with MediaPipe normalised coordinates, indexed by landmark index.
    """
    mesh = np.asarray(face_landmarks, dtype=np.float64)
    return float(
        mouth_open_ratio_from_points(
            mesh[UPPER_INNER_LIP],
            mesh[LOWER_INNER_LIP],
            mesh[RIGHT_EYE_OUTER],
            mesh[LEFT_EYE_OUTER],
            width,
            height,
        )
    )
