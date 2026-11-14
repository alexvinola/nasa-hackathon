"""Does a camera signal move with reaction time and with self-rated sleepiness? Nothing is fitted here.

For a dataset that recorded a psychomotor vigilance test (PVT) or the Karolinska Sleepiness Scale (KSS)
next to the video (DROZY). Each signal (the model's ``fatigueScore``, PERCLOS alone, the browser's fixed
formula) is compared with:

- ``pvt_mean_rt_ms``: the mean reaction time of the stimuli shown during the window
  (``start <= stimulus < start + 60 s``, the same half-open interval as the window's frames);
- ``kss``: the score the person gave for the whole recording (the same for all its windows).

Views, all on people the signal was never fitted to:

- ``per_recording``: one point per recording, the mean signal over its scored windows against the mean
  reaction time of the whole test and its KSS. Recordings do not overlap, so this is the view whose ``n``
  counts separate measurements.
- ``within_subject``: the correlation over one person's windows, summarised across people (median,
  range, how many are positive). A person's own level is a constant there, so differences between people
  cannot drive it.
- ``pooled_windows``: every window of every person together.

Windows overlap (60 s every 10 s): a window count is not a count of independent observations, and no
p-value is reported. A positive correlation means the signal rises as reactions slow down or as the
person feels sleepier.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PVT_MEAN_RT = "pvt_mean_rt_ms"
PVT_STIMULI = "pvt_stimuli"
RECORDING_MEAN_RT = "recording_mean_rt_ms"
KSS = "kss"
TARGETS: tuple[str, ...] = (PVT_MEAN_RT, KSS)

MIN_POINTS = 3  # a correlation over fewer points is not reported (two points always correlate perfectly)
STATISTICS: tuple[str, ...] = ("r", "spearman")


def window_pvt(stimulus_s, rt_ms, start_s, end_s) -> tuple[np.ndarray, np.ndarray]:
    """Mean reaction time and number of the stimuli with ``start <= stimulus < end``, per window.

    A window with no stimulus has a missing mean (NaN), never 0.
    """
    order = np.argsort(np.asarray(stimulus_s, dtype=np.float64), kind="stable")
    stimulus_s = np.asarray(stimulus_s, dtype=np.float64)[order]
    rt_ms = np.asarray(rt_ms, dtype=np.float64)[order]
    first = np.searchsorted(stimulus_s, np.asarray(start_s, dtype=np.float64), side="left")
    last = np.searchsorted(stimulus_s, np.asarray(end_s, dtype=np.float64), side="left")
    total = np.concatenate([[0.0], np.cumsum(rt_ms)])
    count = last - first
    with np.errstate(divide="ignore", invalid="ignore"):
        mean = np.where(count > 0, (total[last] - total[first]) / np.maximum(count, 1), np.nan)
    return mean, count


def correlation(a, b) -> dict:
    """Pearson ``r`` and Spearman correlation over the pairs where both values exist; ``None`` when undefined."""
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    both = np.isfinite(a) & np.isfinite(b)
    a, b = a[both], b[both]
    result = {"r": None, "spearman": None, "n": int(len(a))}
    if len(a) >= MIN_POINTS and a.std() > 0.0 and b.std() > 0.0:
        result["r"] = float(np.corrcoef(a, b)[0, 1])
        ranks_a, ranks_b = pd.Series(a).rank().to_numpy(), pd.Series(b).rank().to_numpy()
        result["spearman"] = float(np.corrcoef(ranks_a, ranks_b)[0, 1])
    return result


def _against_targets(rows: pd.DataFrame, signals: tuple[str, ...]) -> dict:
    return {signal: {target: correlation(rows[signal], rows[target]) for target in TARGETS} for signal in signals}


def summarise(values) -> dict:
    """Median, range and sign count of per-person correlations; the people where it is undefined are left out."""
    values = np.array([v for v in values if v is not None], dtype=np.float64)
    return {
        "subjects": int(len(values)),
        "positive": int((values > 0).sum()),
        "median": float(np.median(values)) if len(values) else None,
        "min": float(values.min()) if len(values) else None,
        "max": float(values.max()) if len(values) else None,
    }


def recording_table(windows: pd.DataFrame, signals: tuple[str, ...]) -> pd.DataFrame:
    """One row per recording: the mean of each signal over its windows, its whole-test mean RT and its KSS."""
    table = windows.groupby("recording", sort=True).agg(
        {**{signal: "mean" for signal in signals}, RECORDING_MEAN_RT: "first", KSS: "first", "subject": "first"}
    )
    return table.rename(columns={RECORDING_MEAN_RT: PVT_MEAN_RT})


def validate(windows: pd.DataFrame, signals: tuple[str, ...]) -> dict:
    """Every view for every signal.

    ``windows``: the scored windows, with ``subject``, ``recording``, the signals, ``pvt_mean_rt_ms`` (of the
    window), ``recording_mean_rt_ms`` (of the whole test) and ``kss`` (NaN where none was recorded).
    """
    per_subject: dict = {}
    for subject, rows in windows.groupby("subject", sort=False):
        per_subject[str(subject)] = {
            "recordings": int(rows["recording"].nunique()),
            "windows": int(len(rows)),
            **_against_targets(rows, signals),
        }
    within = {
        signal: {
            target: {stat: summarise(s[signal][target][stat] for s in per_subject.values()) for stat in STATISTICS}
            for target in TARGETS
        }
        for signal in signals
    }
    return {
        "subjects": int(windows["subject"].nunique()),
        "recordings": int(windows["recording"].nunique()),
        "windows": int(len(windows)),
        "per_recording": _against_targets(recording_table(windows, signals), signals),
        "within_subject": within,
        "pooled_windows": _against_targets(windows, signals),
        "per_subject": per_subject,
    }
