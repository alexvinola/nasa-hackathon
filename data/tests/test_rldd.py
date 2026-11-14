"""RLDD discovery, windowing and calibration bookkeeping, on names and synthetic signals (no video)."""

from pathlib import Path

import numpy as np
import pytest

from pulsar_vision import fatigue_features as ff, rldd
from pulsar_vision.detector import YawnParams

NAN = float("nan")
FPS = 15.0
YAWN = YawnParams(variant="absolute", threshold=0.26, min_duration_s=1.0, release_factor=0.8, max_gap_s=0.25)


# --------------------------------------------------------------------------- names


@pytest.mark.parametrize(
    "path, subject, label",
    [
        ("Fold1_part1/01/0.mov", "01", 0),
        ("Fold1_part1/01/10.MOV", "01", 10),
        ("Fold2_part2/20/5.MOV", "20", 5),
        ("Fold2_part2/24/10.mp4", "24", 10),
        ("Fold1_part1/7/5.mp4", "07", 5),
    ],
)
def test_label_and_subject_come_from_the_path(path, subject, label):
    video = rldd.parse_video_path(path)
    assert (video.subject, video.label) == (subject, label)
    assert video.video_id == f"{subject}_{label}"
    assert video.class_index == {0: 0, 5: 1, 10: 2}[label]
    assert video.state == {0: "alert", 5: "low_vigilance", 10: "drowsy"}[label]


@pytest.mark.parametrize("path", ["Fold1_part1/01/7.mp4", "Fold1_part1/01/notes.txt", "Fold1_part1/abc/0.mp4", "0.mp4", "Fold1_part1/01/0"])
def test_anything_else_is_not_a_dataset_video(path):
    with pytest.raises(ValueError):
        rldd.parse_video_path(path)


def fake_dataset(root: Path, names: list[str]) -> Path:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    return root


def test_discover_lists_videos_and_other_files_and_finds_incomplete_subjects(tmp_path):
    names = [f"Fold1_part1/{s}/{label}.{ext}" for s, ext in (("01", "mov"), ("02", "MOV"), ("03", "mp4")) for label in (0, 5, 10)]
    names.remove("Fold1_part1/03/5.mp4")
    root = fake_dataset(tmp_path, names + ["Fold1_part1/readme.txt"])
    videos, others = rldd.discover(root)
    assert len(videos) == 8
    assert others == ["Fold1_part1/readme.txt"]
    assert [v.video_id for v in videos][:3] == ["01_0", "01_5", "01_10"]
    assert rldd.complete_subjects(videos) == ["01", "02"]
    assert rldd.completeness_problems(videos) == ["subject 03: has videos for labels [0, 10], expected [0, 5, 10]"]
    assert {v.subject for v in rldd.apply_limit(videos, 1)} == {"01"}
    assert len(rldd.apply_limit(videos, None)) == 8


# --------------------------------------------------------------------------- synthetic signals


def signals(seconds: float, eye_blink: float = 0.1, ear: float = 0.30) -> rldd.Signals:
    n = int(round(seconds * FPS))
    return rldd.Signals(
        time_s=np.arange(n) / FPS,
        face=np.ones(n, dtype=bool),
        eye_blink=np.full(n, eye_blink),
        ear=np.full(n, ear),
        pitch_deg=np.zeros(n),
        yaw_deg=np.zeros(n),
        roll_deg=np.zeros(n),
        mouth_open_ratio=np.full(n, 0.02),
        nose_y=np.full(n, 0.5),
    )


def blink(s: rldd.Signals, at_s: float, frames: int = 3) -> None:
    start = int(round(at_s * FPS))
    s.eye_blink[start : start + frames] = 0.9
    s.ear[start : start + frames] = 0.08


def test_the_streaming_count_time_is_one_second_into_the_yawn():
    s = signals(20)
    s.mouth_open_ratio[30:60] = 0.4  # opens at 2.0 s for 2 s
    s.mouth_open_ratio[150:160] = 0.4  # 0.6 s: not a yawn
    counted = rldd.yawn_count_times(s.time_s, s.mouth_open_ratio, YAWN)
    assert counted == pytest.approx([3.0])


def test_windows_carry_bookkeeping_and_the_baseline():
    alert = rldd.parse_video_path("Fold1_part1/01/0.mp4")
    s = signals(200)
    s.eye_blink[1500:1590] = 0.9  # 6 s closed, from t = 100 s
    closed = {ff.BLENDSHAPE: ff.closed_from_blendshape(s.eye_blink)}
    rows = rldd.video_windows(alert, s, closed, YAWN)
    starts = [r["start_s"] for r in rows]
    assert starts == [float(k * 10) for k in range(15)]  # 0 .. 140: only full windows
    assert [r["in_calibration"] for r in rows] == [k <= 6 for k in range(15)]  # windows inside the first 120 s
    assert [r["overlaps_calibration"] for r in rows] == [k < 12 for k in range(15)]
    by_start = {r["start_s"]: r for r in rows}
    assert by_start[50.0]["blendshape__perclos"] == pytest.approx(90 / 900)
    assert by_start[50.0]["baseline_score"] == pytest.approx(0.6 * 0.1)  # still head, no yawns: only PERCLOS
    assert by_start[0.0]["baseline_score"] == 0.0
    assert all(r["usable"] and r["frames"] == 900 for r in rows)
    # A drowsy video has no calibration period: every window counts.
    drowsy_rows = rldd.video_windows(rldd.parse_video_path("Fold1_part1/01/10.mp4"), s, closed, YAWN)
    assert not any(r["in_calibration"] or r["overlaps_calibration"] for r in drowsy_rows)


def test_windows_without_enough_face_are_kept_as_rows_but_have_no_features():
    s = signals(70)
    s.face[:300] = False
    s.eye_blink[:300] = NAN
    rows = rldd.video_windows(rldd.parse_video_path("a/01/5.mp4"), s, {ff.BLENDSHAPE: ff.closed_from_blendshape(s.eye_blink)}, YAWN)
    assert [r["usable"] for r in rows] == [False, True]  # 300 of 900 missing, then 150 of 900
    assert np.isnan(rows[0]["blendshape__perclos"])
    assert rows[1]["face_fraction"] == pytest.approx(750 / 900)


def test_ear_calibration_uses_the_first_two_minutes_of_the_alert_video():
    s = signals(300)
    for at in range(5, 120, 4):
        blink(s, at)
    s.ear[int(130 * FPS) :] = 0.20  # later frames must not move the calibration
    calibration = rldd.subject_ear_calibration(s)
    assert calibration.frames == 1800
    assert calibration.open == pytest.approx(0.30)
    assert calibration.floor == pytest.approx(0.08)
    assert calibration.threshold == pytest.approx(0.08 + 0.2 * 0.22)
    lost = signals(300)
    lost.ear[: int(70 * FPS)] = NAN  # under 900 frames with a face in the first 120 s
    assert rldd.subject_ear_calibration(lost) is None


def test_build_windows_calibrates_each_subject_on_their_own_alert_start():
    videos = [rldd.parse_video_path(f"Fold1_part1/{s}/{label}.mp4") for s in ("01", "02") for label in (0, 5, 10)]
    by_video = {}
    for video in videos:
        s = signals(260)
        # Subject 02 blinks twice as often as subject 01 in every state; drowsy videos add long closures.
        every = 4 if video.subject == "01" else 2
        for at in range(1, 259, every):
            blink(s, at)
        if video.label == 10:
            for at in range(3, 259, 20):
                blink(s, at + 0.5, frames=12)
        by_video[video.video_id] = s
    windows, subjects = rldd.build_windows(videos, by_video, YAWN)
    assert subjects["01"]["used"] and subjects["02"]["used"]
    assert subjects["01"]["calibration_windows"] == 7
    rate = rldd.column(ff.BLENDSHAPE, "blink_rate_per_min")
    calibrated_rate = rldd.column(f"{ff.BLENDSHAPE}_{ff.CALIBRATED}", "blink_rate_per_min")
    alert_late = windows[(windows["label"] == 0) & ~windows["overlaps_calibration"]]
    # Absolute rates differ between the two people; after calibration both sit at 0 while alert.
    assert alert_late[alert_late["subject"] == "01"][rate].mean() == pytest.approx(15.0, abs=0.6)
    assert alert_late[alert_late["subject"] == "02"][rate].mean() == pytest.approx(30.0, abs=0.6)
    assert abs(alert_late[calibrated_rate]).max() < 1.1
    long_rate = rldd.column(f"{ff.EAR_P80}_{ff.CALIBRATED}", "long_closure_rate_per_min")
    assert windows[windows["label"] == 10][long_rate].mean() == pytest.approx(3.0, abs=0.3)
    assert windows[windows["label"] == 5][long_rate].abs().max() == 0.0
    # Both eye methods and both normalisations are present for every feature.
    for prefix in (ff.BLENDSHAPE, ff.EAR_P80, f"{ff.BLENDSHAPE}_{ff.CALIBRATED}", f"{ff.EAR_P80}_{ff.CALIBRATED}"):
        for name in ff.FEATURE_NAMES:
            assert rldd.column(prefix, name) in windows.columns


def test_a_subject_without_three_videos_or_without_calibration_is_reported_not_used():
    videos = [rldd.parse_video_path(f"a/{s}/{label}.mp4") for s, labels in (("01", (0, 5)), ("02", (0, 5, 10))) for label in labels]
    by_video = {v.video_id: signals(200) for v in videos}
    by_video["02_0"].face[:] = False
    by_video["02_0"].ear[:] = NAN
    by_video["02_0"].eye_blink[:] = NAN
    _, subjects = rldd.build_windows(videos, by_video, YAWN)
    assert not subjects["01"]["used"] and "labels [0, 5] only" in subjects["01"]["reason"]
    assert not subjects["02"]["used"] and "too little face" in subjects["02"]["reason"]


def test_longest_missing_run():
    time_s = np.arange(10) / FPS
    face = np.array([1, 1, 0, 0, 0, 1, 0, 1, 1, 1], dtype=bool)
    assert rldd.longest_missing_run_s(time_s, face) == pytest.approx(3 / FPS)
    assert rldd.longest_missing_run_s(time_s, np.ones(10, dtype=bool)) == 0.0


def test_the_baseline_uses_the_last_90_nose_heights_and_the_yawns_counted_in_the_window():
    s = signals(140)
    s.nose_y[:] = 0.5
    s.nose_y[int(58 * FPS) : int(59 * FPS)] = 0.6  # the head moves at 58 s: inside the last 90 frames (6 s) of window 0
    s.mouth_open_ratio[int(65 * FPS) : int(68 * FPS)] = 0.4  # a yawn opening at 65 s is counted at 66 s
    rows = rldd.video_windows(rldd.parse_video_path("a/01/5.mp4"), s, {ff.BLENDSHAPE: ff.closed_from_blendshape(s.eye_blink)}, YAWN)
    by_start = {r["start_s"]: r for r in rows}
    nose = np.array([0.5] * 75 + [0.6] * 15)  # the last 90 frames of window 0: 54 s to 60 s
    expected = 0.15 * min(1.0, 12 * float(nose.std()))
    assert by_start[0.0]["baseline_score"] == pytest.approx(expected) and expected > 0.05
    assert by_start[0.0]["baseline_yawns"] == 0  # not yet counted when window 0 ends
    # Window 10 (10 s to 70 s): the nose moved 11 s before its end, outside the last 90 frames; the yawn is inside.
    assert by_start[10.0]["baseline_yawns"] == 1
    assert by_start[10.0]["baseline_score"] == pytest.approx(0.25 * 1 / 4)
    assert by_start[70.0]["baseline_yawns"] == 0 and by_start[70.0]["baseline_score"] == 0.0
    assert [r["touches_first_120s"] for r in rows] == [r["start_s"] < 120 for r in rows]


def test_the_own_video_threshold_absorbs_a_state_the_alert_threshold_sees():
    videos = [rldd.parse_video_path(f"a/01/{label}.mp4") for label in (0, 5, 10)]
    by_video = {}
    for video in videos:
        s = signals(260)
        for at in range(1, 259, 3):
            blink(s, at)
        if video.label == 10:
            s.ear[s.ear > 0.2] = 0.12  # eyes half shut for the whole drowsy recording, blinks still reach 0.08
        by_video[video.video_id] = s
    windows, _ = rldd.build_windows(videos, by_video, YAWN)
    drowsy = windows[windows["label"] == 10]
    alert_threshold = drowsy[rldd.column(ff.EAR_P80, "perclos")].mean()
    own_threshold = drowsy[rldd.column(rldd.OWN_VIDEO, "perclos")].mean()
    assert alert_threshold == pytest.approx(1.0)  # against the rested eye, a half-shut eye is closed
    assert own_threshold < 0.1  # calibrated on itself, only the blinks are
    alert = windows[windows["label"] == 0]
    np.testing.assert_allclose(alert[rldd.column(rldd.OWN_VIDEO, "perclos")], alert[rldd.column(ff.EAR_P80, "perclos")])


def series_file(cache: Path, video_id: str, model_sha: str, size: int | None) -> None:
    from pulsar_vision import face_series

    n = 4
    meta = {**face_series.cache_signature(model_sha, size), "width": 4, "height": 4, "blendshape_names": [], "processed_frames": n, "mediapipe_seconds": 0.0, "total_seconds": 0.0}
    series = face_series.FaceSeries(
        np.arange(n, dtype=np.int32), np.arange(n) / FPS, np.zeros((n, len(face_series.CACHED_LANDMARKS), 3), dtype=np.float32),
        np.zeros((n, 0), dtype=np.float32), np.tile(np.eye(4, dtype=np.float32), (n, 1, 1)), meta,
    )
    face_series.save_series(series, cache / f"{video_id}.npz")


def test_the_cache_stands_in_for_videos_that_are_not_on_disk(tmp_path):
    from pulsar_vision import landmarks

    model = tmp_path / "model.task"
    model.write_bytes(b"model")
    sha = landmarks.sha256_of(b"model")
    cache = tmp_path / "cache"
    root = fake_dataset(tmp_path / "raw", ["p/01/0.mp4"])  # one (empty) video on disk, size 0
    series_file(cache, "01_0", sha, 0)
    series_file(cache, "01_5", sha, 999)  # extracted on another laptop: only the cache has it
    (cache / rldd.INDEX_FILE).write_text('{"videos": ["p/01/0.mp4", "p/01/5.mp4"]}', encoding="utf-8")
    on_disk, _ = rldd.discover(root)
    videos, cache_only = rldd.with_cached(on_disk, cache)
    assert [v.video_id for v in videos] == ["01_0", "01_5"] and [v.video_id for v in cache_only] == ["01_5"]
    missing = rldd.parse_video_path("p/01/10.mp4")  # neither on disk nor in the cache
    series, failed, timing = rldd.extract_all([*videos, missing], root, model, cache, workers=1)
    assert sorted(series) == ["01_0", "01_5"]
    assert failed == [{"video": "p/01/10.mp4", "error": "not on disk and not in the cache"}]
    assert timing["videos_extracted_this_run"] == 0 and timing["videos_from_cache_this_run"] == 2
    # A cache built with another model is not reused, and a video whose size changed is not either.
    other = tmp_path / "other.task"
    other.write_bytes(b"another model")
    assert rldd.extract_all(cache_only, root, other, cache, workers=1)[0] == {}
    (root / "p/01/0.mp4").write_bytes(b"x")  # now 1 byte: the cached series came from another file
    assert face_series_miss(cache, sha, 1)


def face_series_miss(cache: Path, sha: str, size: int) -> bool:
    from pulsar_vision import face_series

    return face_series.load_series(cache / "01_0.npz", face_series.cache_signature(sha, size)) is None


def test_the_index_is_written_when_the_cache_learns_a_video(tmp_path):
    from pulsar_vision import landmarks

    model = tmp_path / "model.task"
    model.write_bytes(b"model")
    cache = tmp_path / "cache"
    series_file(cache, "02_5", landmarks.sha256_of(b"model"), None)
    assert rldd.cached_videos(cache) == []
    video = rldd.parse_video_path("p/02/5.mp4")
    rldd.extract_all([video], tmp_path / "no-raw", model, cache, workers=1)
    assert [v.relative_path for v in rldd.cached_videos(cache)] == ["p/02/5.mp4"]


def test_matrix_layout_check_counts_frames_laid_out_as_the_angles_assume():
    from pulsar_vision import face_series

    n = 5
    matrix = np.tile(np.eye(4, dtype=np.float32), (n, 1, 1))
    matrix[:, :3, 3] = (1.0, 2.0, -40.0)  # translation in the last column
    matrix[4] = matrix[4].T  # one frame transposed: translation in the last row
    xyz = np.zeros((n, len(face_series.CACHED_LANDMARKS), 3), dtype=np.float32)
    series = face_series.FaceSeries(np.arange(n, dtype=np.int32), np.arange(n) / FPS, xyz, np.zeros((n, 0), dtype=np.float32), matrix, {})
    check = rldd.matrix_layout_check(series)
    assert check["frames"] == 5 and check["last_row_is_0_0_0_1"] == 4
