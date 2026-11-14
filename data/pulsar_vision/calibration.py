"""Grid search and video-level metrics for the yawn detector. Pure functions, no I/O.

A *candidate* is one ``YawnParams``. For every video the number of yawns each candidate
detects is computed once (``count_yawns_grid``); folds then only add up columns, so the
grid is searched on train videos without touching the test ones.

Selection score (higher is better), computed on videos, not frames::

    score = recall_yawning - 0.5 * (false_alarm_talking + false_alarm_normal)

where ``recall_yawning`` is the share of Yawning videos with at least one detected yawn
and each false-alarm rate is the share of Talking / Normal videos with any detected yawn.
Many candidates tie on such a score; the tie is broken towards the centre of the tied
region of the grid (``select_candidate``), which is the choice least sensitive to small
shifts in threshold or duration.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .detector import (
    ABSOLUTE,
    RELATIVE,
    YawnParams,
    baseline_ratio,
    open_episodes,
    thresholds,
)
from .yawdd_names import NORMAL, TALKING, YAWNING


def _arange(start: float, stop: float, step: float) -> tuple[float, ...]:
    count = int(round((stop - start) / step)) + 1
    return tuple(round(start + i * step, 6) for i in range(count))


@dataclass(frozen=True)
class Grid:
    thresholds: tuple[float, ...]
    min_durations_s: tuple[float, ...]
    release_factors: tuple[float, ...]
    baseline_windows_s: tuple[float, ...]
    max_gap_s: float

    def to_dict(self) -> dict:
        return {
            "thresholds": list(self.thresholds),
            "min_durations_s": list(self.min_durations_s),
            "release_factors": list(self.release_factors),
            "baseline_windows_s": list(self.baseline_windows_s),
            "max_gap_s": self.max_gap_s,
        }


# max_gap_s is a design choice, not searched: at 15 fps, 0.25 s bridges up to 2 consecutive
# frames without a face (the next valid frame is 0.200 s after the last one); with 3 missing
# frames the next valid one is 0.267 s away and the episode is closed.
MAX_GAP_S = 0.25

DEFAULT_GRID = Grid(
    thresholds=_arange(0.10, 0.70, 0.02),
    min_durations_s=_arange(0.4, 4.0, 0.2),
    release_factors=(1.0, 0.8),
    baseline_windows_s=(1.0, 2.0, 3.0),
    max_gap_s=MAX_GAP_S,
)


def candidates(grid: Grid, variant: str) -> list[YawnParams]:
    """Every candidate of a variant, in the order ``count_yawns_grid`` reports them."""
    windows: Sequence[float | None] = grid.baseline_windows_s if variant == RELATIVE else (None,)
    return [
        YawnParams(
            variant=variant,
            threshold=threshold,
            min_duration_s=min_duration,
            release_factor=release,
            max_gap_s=grid.max_gap_s,
            baseline_window_s=window,
        )
        for window in windows
        for threshold in grid.thresholds
        for release in grid.release_factors
        for min_duration in grid.min_durations_s
    ]


def count_yawns_grid(times_s: Sequence[float], ratio: Sequence[float], grid: Grid, variant: str) -> np.ndarray:
    """Yawns detected in one series by every candidate; same order as ``candidates``.

    Equivalent to ``len(detect_yawns(times_s, ratio, c))`` for each candidate ``c``, but
    the open episodes are computed once per threshold and reused for every duration.
    """
    times = [float(t) for t in times_s]
    values = [float(r) for r in ratio]
    durations_grid = np.asarray(grid.min_durations_s) - 1e-9
    windows: Sequence[float | None] = grid.baseline_windows_s if variant == RELATIVE else (None,)
    counts: list[np.ndarray] = []
    for window in windows:
        baseline = baseline_ratio(times, values, window) if window is not None else 0.0
        for threshold in grid.thresholds:
            for release in grid.release_factors:
                probe = YawnParams(variant, threshold, 0.0, release, grid.max_gap_s, window)
                on, off = thresholds(probe, baseline)
                episodes = open_episodes(times, values, on, off, grid.max_gap_s)
                durations = np.array([e.duration_s for e in episodes], dtype=np.float64)
                counts.append((durations[None, :] >= durations_grid[:, None]).sum(axis=1))
    return np.concatenate(counts).astype(np.int32)


def wilson_interval(successes: int, total: int, z: float = 1.959964) -> tuple[float, float] | None:
    """95 % Wilson score interval for a proportion; ``None`` when there are no trials."""
    if total <= 0:
        return None
    p = successes / total
    denominator = 1.0 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def proportion(successes: int, total: int) -> dict:
    interval = wilson_interval(successes, total)
    return {
        "count": int(successes),
        "of": int(total),
        "rate": (successes / total) if total else None,
        "ci95_wilson": [interval[0], interval[1]] if interval else None,
    }


def score_from_rates(recall: float, false_alarm_talking: float, false_alarm_normal: float) -> float:
    return recall - 0.5 * (false_alarm_talking + false_alarm_normal)


def candidate_scores(count_matrix: np.ndarray, conditions: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Selection score of every candidate on the videos selected by ``mask``.

    ``count_matrix`` is ``[n_candidates, n_videos]``; ``conditions`` and ``mask`` are per video.
    """
    detected = count_matrix > 0
    rates = []
    for condition in (YAWNING, TALKING, NORMAL):
        columns = mask & (conditions == condition)
        if not columns.any():
            raise ValueError(f"no {condition} video in the selection: the score is undefined")
        rates.append(detected[:, columns].mean(axis=1))
    return score_from_rates(*rates)


def select_candidate(scores: np.ndarray, params: Sequence[YawnParams], grid: Grid) -> int:
    """Index of the best candidate; ties go to the centre of the tied region of the grid.

    Each tied candidate is placed at its grid position (rank of threshold, duration,
    release factor and baseline window, each scaled to 0..1); the one closest to the
    per-axis median of the tied set wins (L1 distance, first in grid order on equal distance).
    """
    best = float(np.max(scores))
    tied = np.flatnonzero(scores >= best - 1e-12)
    if len(tied) == 1:
        return int(tied[0])

    def rank(values: Sequence[float], value: float | None) -> float:
        if value is None or len(values) < 2:
            return 0.0
        return values.index(value) / (len(values) - 1)

    positions = np.array(
        [
            (
                rank(grid.thresholds, params[i].threshold),
                rank(grid.min_durations_s, params[i].min_duration_s),
                rank(grid.release_factors, params[i].release_factor),
                rank(grid.baseline_windows_s, params[i].baseline_window_s),
            )
            for i in tied
        ]
    )
    centre = np.median(positions, axis=0)
    distance = np.abs(positions - centre).sum(axis=1)
    return int(tied[int(np.argmin(distance))])


def video_metrics(yawns: np.ndarray, conditions: np.ndarray, minutes: np.ndarray) -> dict:
    """Video-level metrics of a set of labelled videos given the yawns detected in each."""
    result: dict = {"videos": {}, "yawns_per_minute": {}, "detected_yawns": {}}
    rates: dict[str, float | None] = {}
    for condition, key in ((YAWNING, "yawning_recall"), (TALKING, "talking_false_alarm"), (NORMAL, "normal_false_alarm")):
        columns = conditions == condition
        total = int(columns.sum())
        hits = int((yawns[columns] > 0).sum())
        result["videos"][condition] = total
        result[key] = proportion(hits, total)
        rates[key] = result[key]["rate"]
        total_minutes = float(minutes[columns].sum())
        result["detected_yawns"][condition] = int(yawns[columns].sum())
        result["yawns_per_minute"][condition] = (float(yawns[columns].sum()) / total_minutes) if total_minutes else None
    if all(value is not None for value in rates.values()):
        result["score"] = score_from_rates(
            rates["yawning_recall"], rates["talking_false_alarm"], rates["normal_false_alarm"]
        )
    else:
        result["score"] = None
    yawning = yawns[conditions == YAWNING]
    if len(yawning):
        result["yawns_per_yawning_video"] = {
            "mean": float(yawning.mean()),
            "median": float(np.median(yawning)),
            "max": int(yawning.max()),
        }
    return result


__all__ = [
    "ABSOLUTE",
    "RELATIVE",
    "DEFAULT_GRID",
    "Grid",
    "MAX_GAP_S",
    "candidate_scores",
    "candidates",
    "count_yawns_grid",
    "proportion",
    "score_from_rates",
    "select_candidate",
    "video_metrics",
    "wilson_interval",
]
