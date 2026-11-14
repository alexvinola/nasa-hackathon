"""Time-based frame sampling and the face series cache (no video and no MediaPipe needed, except one test on a blank video)."""

from pathlib import Path

import numpy as np
import pytest

from pulsar_vision import face_series, fatigue_features as ff, landmarks, mouth


def times(fps: float, n: int = 61) -> list[float]:
    return [i * 1000.0 / fps for i in range(n)]


@pytest.mark.parametrize(
    "source_fps, expected_step",
    [(30.0, 2), (29.97, 2), (60.0, 4), (25.0, 2), (24.0, 2), (15.0, 1), (12.0, 1)],
)
def test_constant_rates_are_sampled_like_the_yawdd_frame_step(source_fps, expected_step):
    picked = face_series.sample_indices(times(source_fps))
    assert picked[:4] == [0, expected_step, 2 * expected_step, 3 * expected_step]
    assert expected_step == landmarks.frame_step(source_fps)
    assert set(np.diff(picked)) == {expected_step}


def test_timestamps_rounded_to_whole_milliseconds_still_give_every_second_frame():
    rounded = [0.0, 33.0, 66.0, 100.0, 133.0, 166.0, 200.0, 233.0, 266.0, 300.0]
    assert face_series.sample_indices(rounded) == [0, 2, 4, 6, 8]


def test_a_variable_frame_rate_is_sampled_by_time_not_by_count():
    # 30 fps for a second, then the phone drops to 10 fps: every slow frame is kept.
    stamps = times(30.0, 30) + [1000.0 + i * 100.0 for i in range(10)]
    picked = face_series.sample_indices(stamps)
    kept = np.array(stamps)[picked]
    assert np.all(np.diff(kept) >= 60.0 - 1e-6)  # never closer than 90 % of 1/15 s
    assert picked[-10:] == list(range(30, 40))


def test_the_sampler_rejects_a_missing_target_rate():
    with pytest.raises(ValueError):
        face_series.TimeSampler(0.0)


def test_the_cache_keeps_every_landmark_the_features_read():
    for index in ff.EAR_RIGHT_EYE + ff.EAR_LEFT_EYE + tuple(mouth.LANDMARKS.values()) + (face_series.NOSE_TIP, 10, 152):
        assert index in face_series.CACHED_LANDMARKS
    assert len(set(face_series.CACHED_LANDMARKS)) == len(face_series.CACHED_LANDMARKS)
    # The YawDD cache layout is a prefix: the fatigue extractor only adds points.
    assert face_series.CACHED_LANDMARKS[: len(landmarks.CACHED_LANDMARKS)] == landmarks.CACHED_LANDMARKS


def synthetic_series(n: int = 8) -> face_series.FaceSeries:
    column = face_series.LANDMARK_COLUMN
    xyz = np.zeros((n, len(face_series.CACHED_LANDMARKS), 3), dtype=np.float32)
    xyz[:, column[mouth.UPPER_INNER_LIP]] = (0.5, 0.6, 0.0)
    xyz[:, column[mouth.LOWER_INNER_LIP]] = (0.5, 0.7, 0.0)
    xyz[:, column[mouth.RIGHT_EYE_OUTER]] = (0.4, 0.4, 0.0)
    xyz[:, column[mouth.LEFT_EYE_OUTER]] = (0.6, 0.4, 0.0)
    names = ["_neutral", ff.EYE_BLINK_LEFT, ff.EYE_BLINK_RIGHT]
    blend = np.tile(np.array([0.0, 0.2, 0.6], dtype=np.float32), (n, 1))
    matrix = np.tile(np.eye(4, dtype=np.float32), (n, 1, 1))
    xyz[3] = np.nan  # a frame with no face
    blend[3] = np.nan
    matrix[3] = np.nan
    meta = {**face_series.cache_signature("abc", 1234), "width": 640, "height": 480, "blendshape_names": names}
    return face_series.FaceSeries(np.arange(n, dtype=np.int32) * 2, np.arange(n) / 15.0, xyz, blend, matrix, meta)


def test_signals_are_missing_where_no_face_was_found():
    series = synthetic_series()
    assert series.face_found.tolist() == [True, True, True, False, True, True, True, True]
    assert series.eye_blink()[0] == pytest.approx(0.4)  # mean of the two blendshapes
    pitch, yaw, roll = series.head_angles_deg()
    assert pitch[0] == 0.0 and yaw[0] == 0.0 and roll[0] == 0.0
    for signal in (series.eye_blink(), series.ear(), pitch, series.mouth_open_ratio(), series.nose_y()):
        assert np.isnan(signal[3])  # missing, never zero
    assert series.mouth_open_ratio()[0] == pytest.approx(48 / 128)


def test_cache_round_trip_and_signature(tmp_path):
    series = synthetic_series()
    path = tmp_path / "01_0.npz"
    face_series.save_series(series, path)
    loaded = face_series.load_series(path, face_series.cache_signature("abc", 1234))
    assert loaded is not None
    np.testing.assert_array_equal(loaded.xyz, series.xyz)
    np.testing.assert_array_equal(loaded.blendshapes, series.blendshapes)
    np.testing.assert_array_equal(loaded.matrix, series.matrix)
    assert loaded.meta["blendshape_names"] == series.meta["blendshape_names"]
    # Without the raw video only the model and settings are checked; another model or another file is a miss.
    assert face_series.load_series(path, face_series.cache_signature("abc")) is not None
    assert face_series.load_series(path, face_series.cache_signature("other-model", 1234)) is None
    assert face_series.load_series(path, face_series.cache_signature("abc", 999)) is None
    assert face_series.load_series(tmp_path / "missing.npz", face_series.cache_signature("abc")) is None
    assert not list(tmp_path.glob("*.part"))


def test_the_fatigue_cache_signature_does_not_touch_the_yawdd_one():
    yawdd = landmarks.cache_signature("abc")
    assert "face_series_version" not in yawdd
    assert yawdd["cached_landmarks"] == list(landmarks.CACHED_LANDMARKS)
    assert len(landmarks.CACHED_LANDMARKS) == 15


def test_the_frame_clock_follows_the_container_and_falls_back_when_it_stalls():
    clock = face_series.FrameClock(source_fps=25.0)
    stamps = [0.0, 40.0, 80.0, 80.0, 70.0, 200.0]  # a repeated and a backwards timestamp
    assert [clock.time_ms(t) for t in stamps] == pytest.approx([0.0, 40.0, 80.0, 120.0, 160.0, 200.0])
    assert clock.fallbacks == 2
    no_stamps = face_series.FrameClock(source_fps=30.0)  # a container that always answers 0
    times = [no_stamps.time_ms(0.0) for _ in range(4)]
    assert times == pytest.approx([0.0, 1000 / 30, 2000 / 30, 3000 / 30])
    assert no_stamps.fallbacks == 3
    assert face_series.FrameClock(source_fps=0.0).step_ms == pytest.approx(1000 / 30)
    assert face_series.FrameClock(30.0).time_ms(float("nan")) == 0.0


def test_a_cache_from_another_mediapipe_is_not_reused(tmp_path, monkeypatch):
    series = synthetic_series()
    path = tmp_path / "01_0.npz"
    face_series.save_series(series, path)
    assert face_series.load_series(path, face_series.cache_signature("abc", 1234)) is not None
    monkeypatch.setattr(face_series, "installed_version", lambda package: "9.9.9")
    assert face_series.load_series(path, face_series.cache_signature("abc", 1234)) is None


def test_a_dataset_clock_gives_each_frame_its_measured_time():
    clock = face_series.DatasetClock([23.0, 57.0, 140.0])
    assert [clock.time_ms(0.0) for _ in range(3)] == [23.0, 57.0, 140.0]  # the container's time is ignored
    assert clock.fallbacks == 0
    clock.check_complete()
    with pytest.raises(OSError, match="more frames"):
        clock.time_ms(0.0)


def test_a_dataset_clock_refuses_times_that_do_not_match_the_video():
    short = face_series.DatasetClock([0.0, 40.0, 80.0])
    short.time_ms(0.0)
    with pytest.raises(OSError, match="1 frames but 3"):
        short.check_complete()
    for bad in ([], [0.0, 40.0, 40.0], [0.0, float("nan")]):
        with pytest.raises(ValueError):
            face_series.DatasetClock(bad)


def test_dropped_frames_keep_their_real_times_when_sampled():
    # 30 fps with a dropped stretch, as DROZY's timestamps show: sampling goes by those times, not by frame count.
    stamps = [i * 1000.0 / 30 for i in range(10)] + [600.0 + i * 1000.0 / 30 for i in range(10)]
    clock = face_series.DatasetClock(stamps)
    picked = face_series.sample_indices([clock.time_ms(0.0) for _ in stamps])
    assert picked == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]
    assert np.array(stamps)[picked][5] == pytest.approx(600.0)


LANDMARKER = Path(__file__).resolve().parents[2] / "frontend" / "public" / "mediapipe" / "face_landmarker.task"


@pytest.mark.skipif(not LANDMARKER.is_file(), reason="face_landmarker.task is not downloaded (make prefetch)")
def test_the_extractor_uses_the_dataset_times_and_checks_the_frame_count(tmp_path):
    import cv2

    model = LANDMARKER.read_bytes()
    video = tmp_path / "blank.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 30.0, (64, 48))
    for _ in range(6):
        writer.write(np.zeros((48, 64, 3), dtype=np.uint8))  # no face: only the times are under test
    writer.release()
    times = [10.0, 43.0, 200.0, 233.0, 266.0, 400.0]
    series = face_series.extract_face_series(video, model, frame_times_ms=times)
    assert series.meta["frame_times"] == "dataset" and series.meta["frames_read"] == 6
    assert series.frame_index.tolist() == [0, 2, 4, 5]  # 43 ms is too close to 10 ms; 233 too close to 200
    assert series.time_s == pytest.approx([0.010, 0.200, 0.266, 0.400])
    assert not series.face_found.any()
    with pytest.raises(OSError, match="frame times"):
        face_series.extract_face_series(video, model, frame_times_ms=times[:5])
    with pytest.raises(OSError, match="frame times"):
        face_series.extract_face_series(video, model, frame_times_ms=times + [500.0])
