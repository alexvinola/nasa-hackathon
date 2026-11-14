"""File-name parser for the YawDD dataset.

Labels in YawDD live in the file names and folders, one label per video:

- ``Mirror/Female_mirror/<n>-Female<Eyewear>-<Condition>.avi``
- ``Mirror/Male_mirror Avi Videos/<n>-Male<Eyewear>[moustache|Beard]-<Condition>.avi``
- ``Dash/Female/<n>-Female<Eyewear>.avi`` and ``Dash/Male/<n>-Male<Eyewear>.avi``

Irregular names found in the download and handled here on purpose:

- doubled extension: ``11-FemaleGlasses.avi.avi`` (Dash)
- a space before the extension: ``13-MaleNoGlasses .avi`` (Dash)
- lower-case condition: ``20-MaleGlasses-Talking&yawning.avi``
- facial hair glued to the eyewear: ``19-MaleGlassesmoustache-...``, ``23-MaleGlassesBeard-...``

The participant number restarts for each sex and for each camera set, and the same
participant can appear with several eyewear variants (``23-MaleGlassesBeard`` and
``23-MaleNoGlasses``). The subject id is therefore set + sex + number, never the stem.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePath

MIRROR = "mirror"
DASH = "dash"

NORMAL = "normal"
TALKING = "talking"
YAWNING = "yawning"
TALKING_YAWNING = "talking_yawning"
MIXED = "mixed"  # Dash: one video mixes normal, talking and yawning, with no time marks

MAIN_CONDITIONS = (NORMAL, TALKING, YAWNING)

_EYEWEAR = {"noglasses": "none", "glasses": "glasses", "sunglasses": "sunglasses"}
_FACIAL_HAIR = {"": "none", "moustache": "moustache", "beard": "beard"}
_CONDITION = {
    "normal": NORMAL,
    "talking": TALKING,
    "yawning": YAWNING,
    "talking&yawning": TALKING_YAWNING,
}

_STEM = re.compile(
    r"""^(?P<number>\d+)-
        (?P<sex>Female|Male)
        (?P<eyewear>NoGlasses|SunGlasses|Glasses)
        (?P<hair>moustache|Beard)?
        (?:-(?P<condition>Normal|Talking|Yawning|Talking&Yawning))?$""",
    re.IGNORECASE | re.VERBOSE,
)
_EXTENSIONS = re.compile(r"(\s*\.avi)+\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class VideoName:
    camera: str  # "mirror" | "dash"
    sex: str  # "F" | "M"
    number: int
    eyewear: str  # "none" | "glasses" | "sunglasses"
    facial_hair: str  # "none" | "moustache" | "beard" (only what the name says)
    condition: str  # "normal" | "talking" | "yawning" | "talking_yawning" | "mixed"
    relative_path: str  # POSIX path relative to the dataset root

    @property
    def subject_id(self) -> str:
        return f"{self.camera}-{self.sex}{self.number:02d}"

    @property
    def video_id(self) -> str:
        """Stable id safe for cache file names."""
        return re.sub(r"[^A-Za-z0-9._-]+", "_", _EXTENSIONS.sub("", self.relative_path).replace("/", "__"))


def parse_video_name(relative_path: str) -> VideoName:
    """Parse a path relative to the dataset root. Raises ``ValueError`` on anything unexpected."""
    path = PurePath(relative_path.replace("\\", "/"))
    parts = path.parts
    if len(parts) != 3:
        raise ValueError(f"unexpected folder depth: {relative_path!r}")
    top, folder, file_name = parts

    if top == "Mirror":
        camera = MIRROR
        folder_sex = {"Female_mirror": "F", "Male_mirror Avi Videos": "M"}.get(folder)
    elif top == "Dash":
        camera = DASH
        folder_sex = {"Female": "F", "Male": "M"}.get(folder)
    else:
        raise ValueError(f"unknown camera folder: {relative_path!r}")
    if folder_sex is None:
        raise ValueError(f"unknown sex folder: {relative_path!r}")

    stem, replaced = _EXTENSIONS.subn("", file_name)
    if not replaced:
        raise ValueError(f"not an .avi file: {relative_path!r}")
    match = _STEM.match(stem)
    if match is None:
        raise ValueError(f"unrecognised file name: {relative_path!r}")

    sex = "F" if match["sex"].lower() == "female" else "M"
    if sex != folder_sex:
        raise ValueError(f"sex in the name and in the folder disagree: {relative_path!r}")

    raw_condition = match["condition"]
    if camera == MIRROR:
        if raw_condition is None:
            raise ValueError(f"Mirror video without a condition: {relative_path!r}")
        condition = _CONDITION[raw_condition.lower()]
    else:
        if raw_condition is not None:
            raise ValueError(f"Dash video with a condition: {relative_path!r}")
        condition = MIXED

    return VideoName(
        camera=camera,
        sex=sex,
        number=int(match["number"]),
        eyewear=_EYEWEAR[match["eyewear"].lower()],
        facial_hair=_FACIAL_HAIR[(match["hair"] or "").lower()],
        condition=condition,
        relative_path=path.as_posix(),
    )


def name_irregularities(relative_path: str) -> list[str]:
    """What had to be tolerated to parse this name (empty for a regular name)."""
    file_name = PurePath(relative_path.replace("\\", "/")).name
    found: list[str] = []
    if len(re.findall(r"\.avi", file_name, re.IGNORECASE)) > 1:
        found.append("doubled .avi extension")
    if re.search(r"\s", file_name):
        found.append("whitespace in the file name")
    stem = _EXTENSIONS.sub("", file_name)
    match = _STEM.match(stem)
    if match is not None and match["condition"] and match["condition"] not in (
        "Normal",
        "Talking",
        "Yawning",
        "Talking&Yawning",
    ):
        found.append("condition not capitalised as in the rest of the dataset")
    return found
