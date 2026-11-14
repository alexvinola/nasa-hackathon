"""Pieces of the YawDD pipeline that need no video: discovery, the smoke subset, no-face runs."""

from pathlib import Path

import numpy as np
import pytest

from pulsar_vision import yawdd

REAL_NAMES = (Path(__file__).parent / "yawdd_file_names.txt").read_text(encoding="utf-8").splitlines()
NAN = float("nan")


def fake_dataset(root: Path, names: list[str]) -> Path:
    """Empty files with the dataset's names: enough for discovery, no video content."""
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    return root


def test_discover_finds_every_video_and_lists_the_other_files(tmp_path):
    root = fake_dataset(tmp_path, REAL_NAMES + ["Readme_YawDD.pdf", "Table1.pdf"])
    videos, others = yawdd.discover(root)
    assert len(videos) == 349
    assert sorted(v.relative_path for v in videos) == sorted(REAL_NAMES)
    assert others == ["Readme_YawDD.pdf", "Table1.pdf"]


def test_discover_stops_on_a_name_it_does_not_know(tmp_path):
    root = fake_dataset(tmp_path, REAL_NAMES[:5] + ["Mirror/Female_mirror/1-FemaleNoGlasses-Singing.avi"])
    with pytest.raises(SystemExit) as error:
        yawdd.discover(root)
    assert "Singing" in str(error.value)


def test_limit_keeps_whole_subjects_of_both_sexes(tmp_path):
    videos, _ = yawdd.discover(fake_dataset(tmp_path, REAL_NAMES))
    subset = yawdd.apply_limit(videos, 10)
    mirror = [v for v in subset if v.camera == "mirror"]
    dash = [v for v in subset if v.camera == "dash"]
    kept = {v.subject_id for v in mirror}
    assert len(kept) == 10
    assert {v.sex for v in mirror} == {"F", "M"}
    assert len(dash) == 2
    # Every video of a kept subject is kept: the smoke run cannot split a person across the limit.
    assert len(mirror) == sum(v.subject_id in kept for v in videos)
    assert {v.condition for v in mirror} >= {"normal", "talking", "yawning"}


def test_runs_of_frames_without_a_face():
    conditions = np.array(["yawning", "talking"])
    ratios = [
        # face lost for 3 frames in the middle of a wide opening, and for 1 frame with the mouth closed
        np.array([0.0, 0.5, NAN, NAN, NAN, 0.5, 0.0, NAN, 0.0]),
        # starts and ends without a face; mouth closed around both runs
        np.array([NAN, NAN, 0.1, 0.1, NAN]),
    ]
    result = yawdd.no_face_gaps(ratios, conditions, open_threshold=0.3)
    assert result["by_condition"]["yawning"] == {"runs": 2, "runs_beside_open_mouth": 1, "longest_run_frames": 3}
    assert result["by_condition"]["talking"] == {"runs": 2, "runs_beside_open_mouth": 0, "longest_run_frames": 2}
    assert result["run_length_frames"]["max"] == 3.0


def test_json_cleaning_turns_nan_into_null_and_numpy_into_python():
    cleaned = yawdd.clean({"a": np.float64(0.1234567891), "b": NAN, "c": np.int64(3), "d": [np.float32(0.5), None], 5: "x"})
    assert cleaned == {"a": 0.123457, "b": None, "c": 3, "d": [0.5, None], "5": "x"}
