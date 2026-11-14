"""The mouth opening formula on synthetic landmarks."""

import math

import numpy as np
import pytest

from pulsar_vision import mouth


def mesh(upper, lower, right_eye, left_eye) -> np.ndarray:
    """A 478-point mesh with only the four landmarks of the formula set; the rest are NaN,
    so the test fails if the formula reads any other landmark."""
    points = np.full((478, 3), np.nan)
    points[mouth.UPPER_INNER_LIP, :2] = upper
    points[mouth.LOWER_INNER_LIP, :2] = lower
    points[mouth.RIGHT_EYE_OUTER, :2] = right_eye
    points[mouth.LEFT_EYE_OUTER, :2] = left_eye
    points[:, 2] = 123.0  # z must be ignored
    return points


def test_indices_are_the_documented_ones():
    # The JS worker hard-codes the same indices: a change here must be a deliberate one.
    assert mouth.LANDMARKS == {
        "upper_inner_lip": 13,
        "lower_inner_lip": 14,
        "right_eye_outer": 33,
        "left_eye_outer": 263,
    }
    assert mouth.FORMULA_NAME == "inner_lip_gap_over_outer_eye_corner_distance_2d_px"


def test_known_geometry_in_pixels():
    # 640x480: eyes 0.2 * 640 = 128 px apart, lips 0.1 * 480 = 48 px apart.
    face = mesh(upper=(0.5, 0.6), lower=(0.5, 0.7), right_eye=(0.4, 0.4), left_eye=(0.6, 0.4))
    assert mouth.mouth_open_ratio(face, 640, 480) == pytest.approx(48 / 128)


def test_closed_mouth_is_zero():
    face = mesh(upper=(0.5, 0.6), lower=(0.5, 0.6), right_eye=(0.4, 0.4), left_eye=(0.6, 0.4))
    assert mouth.mouth_open_ratio(face, 640, 480) == 0.0


def test_coordinates_are_converted_to_pixels_before_measuring():
    # The same normalised points on a portrait frame give another ratio: x and y scale differently.
    face = mesh(upper=(0.5, 0.6), lower=(0.5, 0.7), right_eye=(0.4, 0.4), left_eye=(0.6, 0.4))
    assert mouth.mouth_open_ratio(face, 480, 640) == pytest.approx(64 / 96)
    assert mouth.mouth_open_ratio(face, 100, 100) == pytest.approx(0.5)


def test_independent_of_distance_to_the_camera():
    near = mesh(upper=(0.5, 0.6), lower=(0.5, 0.7), right_eye=(0.4, 0.4), left_eye=(0.6, 0.4))
    centre = np.array([0.5, 0.5])
    far = near.copy()
    far[:, :2] = centre + 0.37 * (near[:, :2] - centre)  # the same face, 0.37 times the size
    shifted = near.copy()
    shifted[:, :2] += np.array([0.1, -0.2])
    reference = mouth.mouth_open_ratio(near, 640, 480)
    assert mouth.mouth_open_ratio(far, 640, 480) == pytest.approx(reference)
    assert mouth.mouth_open_ratio(shifted, 640, 480) == pytest.approx(reference)


def test_uses_euclidean_distance_not_only_the_vertical_gap():
    # Head tilted: lips displaced 30 px in x and 40 px in y -> 50 px; eyes 60 px in x and 80 px in y -> 100 px.
    face = mesh(upper=(0.5, 0.5), lower=(0.53, 0.54), right_eye=(0.2, 0.2), left_eye=(0.26, 0.28))
    assert mouth.mouth_open_ratio(face, 1000, 1000) == pytest.approx(0.5)


def test_missing_face_stays_missing():
    face = np.full((478, 3), np.nan)
    assert math.isnan(mouth.mouth_open_ratio(face, 640, 480))


def test_degenerate_eye_distance_is_missing_not_infinite():
    face = mesh(upper=(0.5, 0.6), lower=(0.5, 0.7), right_eye=(0.4, 0.4), left_eye=(0.4, 0.4))
    assert math.isnan(mouth.mouth_open_ratio(face, 640, 480))


def test_vectorised_form_matches_the_scalar_one():
    rng = np.random.default_rng(7)
    frames = rng.uniform(0.1, 0.9, size=(25, 4, 3))
    frames[3] = np.nan  # a frame with no face
    series = mouth.mouth_open_ratio_from_points(frames[:, 0], frames[:, 1], frames[:, 2], frames[:, 3], 640, 480)
    assert series.shape == (25,)
    assert math.isnan(series[3])
    for i in (0, 1, 10, 24):
        face = mesh(frames[i, 0, :2], frames[i, 1, :2], frames[i, 2, :2], frames[i, 3, :2])
        assert series[i] == pytest.approx(mouth.mouth_open_ratio(face, 640, 480))


def test_accepts_xy_only_meshes():
    face = mesh(upper=(0.5, 0.6), lower=(0.5, 0.7), right_eye=(0.4, 0.4), left_eye=(0.6, 0.4))
    assert mouth.mouth_open_ratio(face[:, :2], 640, 480) == pytest.approx(0.375)
