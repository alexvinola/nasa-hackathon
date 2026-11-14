"""Yawn detector: a pure function over the per-frame mouth opening series.

The browser worker (G1) ports ``open_episodes`` as a streaming state machine; it reads
one ``(time, ratio)`` pair per processed frame and keeps four values of state
(``open``, ``start``, ``last``, ``peak``).

Rules
-----
- The mouth becomes *open* on the first frame whose ratio is ``>= on_threshold``.
- It stays open while the ratio is ``>= off_threshold`` (hysteresis: ``off <= on``),
  and closes on the first valid frame below it.
- A frame with no face has a missing ratio (NaN). Missing frames neither open nor close
  the mouth, but if more than ``max_gap_s`` passes since the last frame that confirmed
  the mouth open, the episode is closed at that last frame.
- An episode's duration is ``end - start``: the time between its first and last
  confirming frames. One confirming frame alone has duration 0.
- A **yawn** is an open episode whose duration is ``>= min_duration_s``.

Thresholds come in two variants (``variant`` in ``YawnParams``):

- ``absolute``: ``on = threshold``.
- ``relative``: ``on = baseline + threshold``, where ``baseline`` is the median ratio of
  the valid frames in the first ``baseline_window_s`` seconds after the first valid frame.

In both, ``off = baseline + release_factor * (on - baseline)`` with ``baseline = 0`` for
the absolute variant.

``detect_yawns`` measures the baseline first and then scans the whole series, baseline
window included. A live session cannot do that: it has no baseline until the window has
passed, so it calibrates first and only then starts counting. On a recorded video the two
differ only for a yawn that starts inside the window.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Sequence

ABSOLUTE = "absolute"
RELATIVE = "relative"

# Comparisons on durations tolerate float rounding of frame times (index / fps).
_EPS = 1e-9


@dataclass(frozen=True)
class Episode:
    """A stretch of frames with the mouth open."""

    start_s: float
    end_s: float
    peak: float
    frames: int

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


@dataclass(frozen=True)
class YawnParams:
    """Everything the detector needs; this is what ``yawn_params.json`` carries."""

    variant: str
    threshold: float
    min_duration_s: float
    release_factor: float
    max_gap_s: float
    baseline_window_s: float | None = None

    def __post_init__(self) -> None:
        if self.variant not in (ABSOLUTE, RELATIVE):
            raise ValueError(f"unknown variant: {self.variant!r}")
        if self.variant == RELATIVE and self.baseline_window_s is None:
            raise ValueError("the relative variant needs baseline_window_s")
        if not 0.0 < self.release_factor <= 1.0:
            raise ValueError("release_factor must be in (0, 1]")

    def to_dict(self) -> dict:
        return asdict(self)


def _is_missing(value: float) -> bool:
    return value is None or value != value  # NaN is the only float not equal to itself


def open_episodes(
    times_s: Sequence[float],
    ratio: Sequence[float],
    on_threshold: float,
    off_threshold: float,
    max_gap_s: float,
) -> list[Episode]:
    """All open-mouth episodes of a series, in order. See the module docstring."""
    if len(times_s) != len(ratio):
        raise ValueError("times_s and ratio must have the same length")
    if off_threshold > on_threshold:
        raise ValueError("off_threshold must not exceed on_threshold")
    episodes: list[Episode] = []
    if _is_missing(on_threshold) or _is_missing(off_threshold):
        return episodes  # no baseline could be measured: nothing can be detected

    is_open = False
    start = last = peak = 0.0
    frames = 0
    for t, r in zip(times_s, ratio):
        if is_open and t - last > max_gap_s + _EPS:
            episodes.append(Episode(start, last, peak, frames))
            is_open = False
        if _is_missing(r):
            continue
        if not is_open:
            if r >= on_threshold:
                is_open = True
                start = last = t
                peak = r
                frames = 1
        elif r >= off_threshold:
            last = t
            frames += 1
            if r > peak:
                peak = r
        else:
            episodes.append(Episode(start, last, peak, frames))
            is_open = False
    if is_open:
        episodes.append(Episode(start, last, peak, frames))
    return episodes


def baseline_ratio(times_s: Sequence[float], ratio: Sequence[float], window_s: float) -> float:
    """Median ratio of the valid frames in the first ``window_s`` seconds.

    The window starts at the first valid frame (``t0 <= t < t0 + window_s``). Returns NaN
    when the series has no valid frame.
    """
    values: list[float] = []
    t0: float | None = None
    for t, r in zip(times_s, ratio):
        if _is_missing(r):
            continue
        if t0 is None:
            t0 = t
        if t - t0 >= window_s - _EPS:
            break
        values.append(r)
    if not values:
        return math.nan
    values.sort()
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return 0.5 * (values[middle - 1] + values[middle])


def thresholds(params: YawnParams, baseline: float = 0.0) -> tuple[float, float]:
    """``(on, off)`` thresholds for a series whose baseline is ``baseline``."""
    base = baseline if params.variant == RELATIVE else 0.0
    on = base + params.threshold
    off = base + params.release_factor * params.threshold
    return on, off


def yawns_from_episodes(episodes: Sequence[Episode], min_duration_s: float) -> list[Episode]:
    return [e for e in episodes if e.duration_s >= min_duration_s - _EPS]


def detect_yawns(times_s: Sequence[float], ratio: Sequence[float], params: YawnParams) -> list[Episode]:
    """Yawns in a series: open episodes lasting at least ``params.min_duration_s``."""
    baseline = 0.0
    if params.variant == RELATIVE:
        baseline = baseline_ratio(times_s, ratio, params.baseline_window_s)
    on, off = thresholds(params, baseline)
    episodes = open_episodes(times_s, ratio, on, off, params.max_gap_s)
    return yawns_from_episodes(episodes, params.min_duration_s)
