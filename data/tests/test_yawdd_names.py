"""The YawDD file-name parser on every name pattern found in the download.

``yawdd_file_names.txt`` is the listing of the 349 .avi files of the dataset as
downloaded (paths relative to its root). Only names are stored, no video content.
"""

from collections import Counter
from pathlib import Path

import pytest

from pulsar_vision import yawdd_names
from pulsar_vision.yawdd_names import VideoName, name_irregularities, parse_video_name

REAL_NAMES = (Path(__file__).parent / "yawdd_file_names.txt").read_text(encoding="utf-8").splitlines()
DATASET_ROOT = Path(__file__).resolve().parents[1] / "raw" / "yawdd" / "YawDD dataset"


def expect(path, camera, sex, number, eyewear, facial_hair, condition):
    return (path, VideoName(camera, sex, number, eyewear, facial_hair, condition, path))


PATTERNS = [
    # Mirror, the regular pattern, each condition and each sex
    expect("Mirror/Female_mirror/1-FemaleNoGlasses-Normal.avi", "mirror", "F", 1, "none", "none", "normal"),
    expect("Mirror/Female_mirror/1-FemaleNoGlasses-Talking.avi", "mirror", "F", 1, "none", "none", "talking"),
    expect("Mirror/Female_mirror/1-FemaleNoGlasses-Yawning.avi", "mirror", "F", 1, "none", "none", "yawning"),
    expect("Mirror/Male_mirror Avi Videos/10-MaleNoGlasses-Normal.avi", "mirror", "M", 10, "none", "none", "normal"),
    # eyewear variants
    expect("Mirror/Female_mirror/15-FemaleGlasses-Talking.avi", "mirror", "F", 15, "glasses", "none", "talking"),
    expect("Mirror/Female_mirror/15-FemaleSunGlasses-Yawning.avi", "mirror", "F", 15, "sunglasses", "none", "yawning"),
    expect("Mirror/Male_mirror Avi Videos/1-MaleSunGlasses-Normal.avi", "mirror", "M", 1, "sunglasses", "none", "normal"),
    expect("Mirror/Male_mirror Avi Videos/11-MaleGlasses-Yawning.avi", "mirror", "M", 11, "glasses", "none", "yawning"),
    # facial hair glued to the eyewear
    expect("Mirror/Male_mirror Avi Videos/19-MaleGlassesmoustache-Talking.avi", "mirror", "M", 19, "glasses", "moustache", "talking"),
    expect("Mirror/Male_mirror Avi Videos/8-MaleGlassesBeard-Yawning.avi", "mirror", "M", 8, "glasses", "beard", "yawning"),
    # talking and yawning in one video, in its two spellings
    expect("Mirror/Female_mirror/19-FemaleNoGlasses-Talking&Yawning.avi", "mirror", "F", 19, "none", "none", "talking_yawning"),
    expect("Mirror/Male_mirror Avi Videos/23-MaleGlassesBeard-Talking&Yawning.avi", "mirror", "M", 23, "glasses", "beard", "talking_yawning"),
    expect("Mirror/Male_mirror Avi Videos/20-MaleGlasses-Talking&yawning.avi", "mirror", "M", 20, "glasses", "none", "talking_yawning"),
    # Dash: no condition, doubled extension, space before the extension
    expect("Dash/Female/1-FemaleNoGlasses.avi", "dash", "F", 1, "none", "none", "mixed"),
    expect("Dash/Female/11-FemaleGlasses.avi.avi", "dash", "F", 11, "glasses", "none", "mixed"),
    expect("Dash/Male/13-MaleNoGlasses .avi", "dash", "M", 13, "none", "none", "mixed"),
    expect("Dash/Male/1-MaleGlasses.avi", "dash", "M", 1, "glasses", "none", "mixed"),
]


@pytest.mark.parametrize("path, expected", PATTERNS, ids=[p for p, _ in PATTERNS])
def test_name_patterns(path, expected):
    assert parse_video_name(path) == expected


def test_windows_separators_are_accepted():
    parsed = parse_video_name("Mirror\\Female_mirror\\1-FemaleNoGlasses-Normal.avi")
    assert parsed.relative_path == "Mirror/Female_mirror/1-FemaleNoGlasses-Normal.avi"


def test_every_real_name_parses():
    parsed = [parse_video_name(name) for name in REAL_NAMES]
    assert len(parsed) == 349
    assert Counter(v.camera for v in parsed) == {"mirror": 320, "dash": 29}
    assert Counter((v.camera, v.sex) for v in parsed) == {
        ("mirror", "F"): 156,
        ("mirror", "M"): 164,
        ("dash", "F"): 13,
        ("dash", "M"): 16,
    }
    # Every Mirror video has exactly one of the four conditions; every Dash video is "mixed".
    assert {v.condition for v in parsed if v.camera == "dash"} == {"mixed"}
    mirror_conditions = Counter(v.condition for v in parsed if v.camera == "mirror")
    assert set(mirror_conditions) == {"normal", "talking", "yawning", "talking_yawning"}
    assert mirror_conditions["talking_yawning"] == 13
    assert sum(mirror_conditions.values()) == 320


def test_real_names_give_the_expected_subjects():
    parsed = [parse_video_name(name) for name in REAL_NAMES]
    mirror_subjects = {v.subject_id for v in parsed if v.camera == "mirror"}
    dash_subjects = {v.subject_id for v in parsed if v.camera == "dash"}
    assert len({s for s in mirror_subjects if s.startswith("mirror-F")}) == 43
    assert len({s for s in mirror_subjects if s.startswith("mirror-M")}) == 47
    assert len(dash_subjects) == 29  # one video per Dash participant
    assert not mirror_subjects & dash_subjects


def test_subject_is_sex_and_number_not_the_stem():
    beard = parse_video_name("Mirror/Male_mirror Avi Videos/23-MaleGlassesBeard-Normal.avi")
    plain = parse_video_name("Mirror/Male_mirror Avi Videos/23-MaleNoGlasses-Normal.avi")
    woman = parse_video_name("Mirror/Female_mirror/23-FemaleNoGlasses-Normal.avi")
    dash = parse_video_name("Dash/Male/1-MaleGlasses.avi")
    mirror = parse_video_name("Mirror/Male_mirror Avi Videos/1-MaleNoGlasses-Talking.avi")
    assert beard.subject_id == plain.subject_id == "mirror-M23"
    assert woman.subject_id == "mirror-F23"
    assert dash.subject_id == "dash-M01" != mirror.subject_id  # numbering restarts in each camera set


def test_video_ids_are_unique_and_file_system_safe():
    ids = [parse_video_name(name).video_id for name in REAL_NAMES]
    assert len(set(ids)) == len(ids)
    for video_id in ids:
        assert all(ch.isalnum() or ch in "._-" for ch in video_id), video_id


def test_irregular_names_are_reported():
    assert name_irregularities("Mirror/Female_mirror/1-FemaleNoGlasses-Normal.avi") == []
    assert name_irregularities("Dash/Female/11-FemaleGlasses.avi.avi") == ["doubled .avi extension"]
    assert name_irregularities("Dash/Male/13-MaleNoGlasses .avi") == ["whitespace in the file name"]
    assert name_irregularities("Mirror/Male_mirror Avi Videos/20-MaleGlasses-Talking&yawning.avi") == [
        "condition not capitalised as in the rest of the dataset"
    ]
    irregular = [name for name in REAL_NAMES if name_irregularities(name)]
    assert len(irregular) == 6  # four doubled extensions, one space, one lower-case condition


@pytest.mark.parametrize(
    "path",
    [
        "Mirror/Female_mirror/1-FemaleNoGlasses-Singing.avi",  # unknown condition
        "Mirror/Female_mirror/1-FemaleNoGlasses.avi",  # Mirror needs a condition
        "Dash/Female/1-FemaleNoGlasses-Yawning.avi",  # Dash has none
        "Mirror/Female_mirror/1-MaleNoGlasses-Normal.avi",  # sex disagrees with the folder
        "Mirror/Unknown/1-FemaleNoGlasses-Normal.avi",  # unknown folder
        "Side/Female/1-FemaleNoGlasses.avi",  # unknown camera
        "Mirror/Female_mirror/1-FemaleNoGlasses-Normal.mp4",  # not an .avi
        "Mirror/Female_mirror/FemaleNoGlasses-Normal.avi",  # no participant number
        "Mirror/Female_mirror/1-FemaleMonocle-Normal.avi",  # unknown eyewear
        "1-FemaleNoGlasses-Normal.avi",  # not inside the dataset folders
        "Readme_YawDD.pdf",
    ],
)
def test_unexpected_names_are_rejected(path):
    with pytest.raises(ValueError):
        parse_video_name(path)


def test_main_conditions_exclude_the_mixed_videos():
    assert yawdd_names.MAIN_CONDITIONS == ("normal", "talking", "yawning")


@pytest.mark.skipif(not DATASET_ROOT.is_dir(), reason="YawDD is not downloaded (git-ignored)")
def test_listing_matches_the_dataset_on_disk():
    on_disk = sorted(
        p.relative_to(DATASET_ROOT).as_posix() for p in DATASET_ROOT.rglob("*") if p.is_file() and ".avi" in p.name.lower()
    )
    assert on_disk == sorted(REAL_NAMES)
