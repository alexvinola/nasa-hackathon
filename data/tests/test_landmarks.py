"""Frame-rate handling, the series cache, and "no face is missing, not zero"."""

import numpy as np
import pytest

from pulsar_vision import landmarks, mouth, yawdd


def synthetic_series(n: int = 6) -> landmarks.VideoSeries:
    xyz = np.zeros((n, len(landmarks.CACHED_LANDMARKS), 3), dtype=np.float32)
    column = landmarks.LANDMARK_COLUMN
    xyz[:, column[mouth.UPPER_INNER_LIP]] = (0.5, 0.6, 0.0)
    xyz[:, column[mouth.LOWER_INNER_LIP]] = (0.5, 0.7, 0.0)
    xyz[:, column[mouth.RIGHT_EYE_OUTER]] = (0.4, 0.4, 0.0)
    xyz[:, column[mouth.LEFT_EYE_OUTER]] = (0.6, 0.4, 0.0)
    xyz[2] = np.nan  # a frame with no face
    frame_index = np.arange(n, dtype=np.int32) * 2
    meta = {**landmarks.cache_signature("abc"), "width": 640, "height": 480, "source_fps": 30.0}
    jaw = np.where(np.arange(n) == 2, np.nan, 0.3).astype(np.float32)
    return landmarks.VideoSeries(frame_index, frame_index / 30.0, xyz, jaw, meta)


@pytest.mark.parametrize("source_fps, step", [(30.0, 2), (29.97, 2), (15.0, 1), (25.0, 2), (60.0, 4), (10.0, 1)])
def test_frame_step(source_fps, step):
    assert landmarks.frame_step(source_fps) == step


def test_frame_step_rejects_a_missing_frame_rate():
    with pytest.raises(ValueError):
        landmarks.frame_step(0.0)


def test_the_product_landmarks_are_cached():
    for index in mouth.LANDMARKS.values():
        assert index in landmarks.CACHED_LANDMARKS
    assert len(set(landmarks.CACHED_LANDMARKS)) == len(landmarks.CACHED_LANDMARKS)


def test_series_ratio_is_missing_where_no_face_was_found():
    series = synthetic_series()
    ratio = series.mouth_open_ratio()
    assert series.face_found.tolist() == [True, True, False, True, True, True]
    assert np.isnan(ratio[2])
    assert ratio[[0, 1, 3, 4, 5]] == pytest.approx(48 / 128)


def test_cache_round_trip(tmp_path):
    series = synthetic_series()
    path = tmp_path / "nested" / "video.npz"
    landmarks.save_series(series, path)
    loaded = landmarks.load_series(path, landmarks.cache_signature("abc"))
    assert loaded is not None
    np.testing.assert_array_equal(loaded.frame_index, series.frame_index)
    np.testing.assert_array_equal(loaded.xyz, series.xyz)  # NaN rows included
    np.testing.assert_array_equal(loaded.jaw_open, series.jaw_open)
    assert loaded.meta == series.meta
    assert not list(tmp_path.rglob("*.part"))


def test_cache_from_another_setup_is_not_reused(tmp_path):
    path = tmp_path / "video.npz"
    landmarks.save_series(synthetic_series(), path)
    assert landmarks.load_series(path, landmarks.cache_signature("another model")) is None
    assert landmarks.load_series(path, landmarks.cache_signature("abc", target_fps=30.0)) is None
    assert landmarks.load_series(tmp_path / "absent.npz", landmarks.cache_signature("abc")) is None
    broken = tmp_path / "broken.npz"
    broken.write_bytes(b"not an archive")
    assert landmarks.load_series(broken, landmarks.cache_signature("abc")) is None


@pytest.mark.skipif(not yawdd.DEFAULT_MODEL.is_file(), reason="face_landmarker.task is not downloaded (make prefetch)")
def test_video_without_a_face_is_all_missing(tmp_path):
    """End to end with the real model on a synthetic grey video: no face, so every frame is missing."""
    import cv2

    path = tmp_path / "grey.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 30.0, (320, 240))
    assert writer.isOpened()
    for _ in range(21):
        writer.write(np.full((240, 320, 3), 128, dtype=np.uint8))
    writer.release()

    series = landmarks.extract_video(path, yawdd.DEFAULT_MODEL.read_bytes())
    assert series.meta["frame_step"] == 2
    assert series.meta["processed_fps"] == pytest.approx(15.0)
    assert series.frame_index.tolist() == list(range(0, 21, 2))  # every second frame
    assert series.time_s == pytest.approx(np.arange(0, 21, 2) / 30.0)
    assert not series.face_found.any()
    assert np.isnan(series.xyz).all() and np.isnan(series.jaw_open).all()
    assert np.isnan(series.mouth_open_ratio()).all()  # missing, never zero
