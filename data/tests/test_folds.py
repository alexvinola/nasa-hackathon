"""Subject-grouped folds: no subject on both sides, and the search never sees the test fold."""

from pathlib import Path

import numpy as np
import pytest

from pulsar_vision import calibration, folds, yawdd
from pulsar_vision.detector import ABSOLUTE
from pulsar_vision.yawdd_names import MAIN_CONDITIONS, parse_video_name

REAL_NAMES = (Path(__file__).parent / "yawdd_file_names.txt").read_text(encoding="utf-8").splitlines()


def real_strata() -> dict[str, str]:
    videos = [parse_video_name(name) for name in REAL_NAMES]
    return {v.subject_id: v.sex for v in videos if v.camera == "mirror"}


def test_folds_are_disjoint_and_cover_every_subject():
    strata = real_strata()
    split = folds.grouped_folds(strata, yawdd.DEFAULT_FOLDS, yawdd.DEFAULT_SEED)
    assert len(split) == yawdd.DEFAULT_FOLDS
    everyone = [subject for fold in split for subject in fold]
    assert len(everyone) == len(set(everyone)) == len(strata) == 90
    assert set(everyone) == set(strata)
    folds.assert_disjoint(split)


def test_no_subject_in_train_and_test():
    strata = real_strata()
    split = folds.grouped_folds(strata, yawdd.DEFAULT_FOLDS, yawdd.DEFAULT_SEED)
    for k, test in enumerate(split):
        train = folds.train_subjects(split, k)
        assert not set(train) & set(test)
        assert set(train) | set(test) == set(strata)


def test_no_video_of_a_test_subject_is_in_train():
    # The same participant appears under several file stems (eyewear variants): all of them follow the subject.
    videos = [parse_video_name(name) for name in REAL_NAMES if name.startswith("Mirror/")]
    split = folds.grouped_folds(real_strata(), yawdd.DEFAULT_FOLDS, yawdd.DEFAULT_SEED)
    for k, test in enumerate(split):
        train = set(folds.train_subjects(split, k))
        test_videos = [v for v in videos if v.subject_id in set(test)]
        train_videos = [v for v in videos if v.subject_id in train]
        assert len(test_videos) + len(train_videos) == len(videos)
        assert not {(v.sex, v.number) for v in test_videos} & {(v.sex, v.number) for v in train_videos}


def test_folds_are_balanced_by_sex_and_size():
    strata = real_strata()
    split = folds.grouped_folds(strata, 5, yawdd.DEFAULT_SEED)
    sizes = [len(fold) for fold in split]
    assert max(sizes) - min(sizes) <= 1
    women = [sum(strata[s] == "F" for s in fold) for fold in split]
    assert max(women) - min(women) <= 1


def test_every_train_side_has_the_three_conditions():
    videos = [parse_video_name(name) for name in REAL_NAMES if name.startswith("Mirror/")]
    split = folds.grouped_folds(real_strata(), yawdd.DEFAULT_FOLDS, yawdd.DEFAULT_SEED)
    for k in range(len(split)):
        for side in (set(split[k]), set(folds.train_subjects(split, k))):
            assert {v.condition for v in videos if v.subject_id in side} >= set(MAIN_CONDITIONS)


def test_split_is_deterministic_and_depends_on_the_seed():
    strata = real_strata()
    assert folds.grouped_folds(strata, 5, 1) == folds.grouped_folds(dict(reversed(list(strata.items()))), 5, 1)
    assert folds.grouped_folds(strata, 5, 1) != folds.grouped_folds(strata, 5, 2)


def test_invalid_splits_are_rejected():
    with pytest.raises(ValueError):
        folds.grouped_folds({"a": "F", "b": "M"}, 1, 0)
    with pytest.raises(ValueError):
        folds.grouped_folds({"a": "F", "b": "M"}, 3, 0)
    with pytest.raises(AssertionError):
        folds.assert_disjoint([["a", "b"], ["b", "c"]])


def test_cross_validation_chooses_on_train_only():
    """A candidate that is perfect on the test fold but wrong on train must not be picked."""
    grid = calibration.Grid(thresholds=(0.2, 0.4), min_durations_s=(1.0,), release_factors=(1.0,), baseline_windows_s=(), max_gap_s=0.25)
    candidates = calibration.candidates(grid, ABSOLUTE)
    assert len(candidates) == 2
    # Six videos: fold 0 holds videos 0-2, fold 1 holds videos 3-5; one video per condition in each.
    conditions = np.array(["yawning", "talking", "normal"] * 2)
    fold_of_video = np.array([0, 0, 0, 1, 1, 1])
    minutes = np.full(6, 0.5)
    main = np.ones(6, dtype=bool)
    count_matrix = np.array(
        [
            # candidate 0: perfect on fold 0, fires on talking in fold 1
            [1, 0, 0, 1, 1, 0],
            # candidate 1: misses the yawn in fold 0, perfect on fold 1
            [0, 0, 0, 1, 0, 0],
        ]
    )
    out_of_fold, reports = yawdd.cross_validate(count_matrix, candidates, grid, conditions, minutes, fold_of_video, main, 2)
    # Fold 0 is tested with the candidate that wins on fold 1 (candidate 1), and the other way round.
    assert reports[0]["params"]["threshold"] == 0.4
    assert reports[1]["params"]["threshold"] == 0.2
    assert out_of_fold.tolist() == [0, 0, 0, 1, 1, 0]
    assert reports[0]["test"]["yawning_recall"]["count"] == 0
    assert reports[1]["test"]["talking_false_alarm"]["count"] == 1


def test_videos_outside_the_main_conditions_never_steer_the_search():
    grid = calibration.Grid(thresholds=(0.2, 0.4), min_durations_s=(1.0,), release_factors=(1.0,), baseline_windows_s=(), max_gap_s=0.25)
    candidates = calibration.candidates(grid, ABSOLUTE)
    conditions = np.array(["yawning", "talking", "normal", "talking_yawning"] * 2)
    fold_of_video = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    main = conditions != "talking_yawning"
    count_matrix = np.array(
        [
            [1, 0, 0, 0, 1, 0, 0, 0],  # candidate 0: perfect on the main videos, silent on the mixed ones
            [0, 0, 0, 5, 0, 0, 0, 5],  # candidate 1: only fires on the mixed ones
        ]
    )
    out_of_fold, reports = yawdd.cross_validate(count_matrix, candidates, grid, conditions, np.full(8, 0.5), fold_of_video, main, 2)
    assert [r["params"]["threshold"] for r in reports] == [0.2, 0.2]
    assert out_of_fold.tolist() == [1, 0, 0, 0, 1, 0, 0, 0]  # mixed videos still get an out-of-fold count
