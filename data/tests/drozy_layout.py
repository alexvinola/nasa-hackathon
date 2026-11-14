"""Made-up DROZY material for the tests: the dataset's folder layout with tiny invented files, and synthetic
per-frame signals. Nothing here comes from DROZY."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np

from pulsar_vision import drozy, rldd

# Invented scores in the file's shape: 14 subjects by 3 tests, 0 where none was recorded.
KSS_LINES = ["1 5 9", "2 4 6", "3 3 3", "4 2 8", "5 6 7", "6 1 2", "0 8 4"] + ["5 5 5"] * 7


def fake_drozy(root: Path, tests: list[str], kss_lines: list[str] = KSS_LINES) -> Path:
    """The dataset's folders with tiny made-up files; the videos are empty (the loader never opens them)."""
    for folder in ("videos_i8", "timestamps", "pvt-rt"):
        (root / folder).mkdir(parents=True)
    (root / "KSS.txt").write_text("\n".join(kss_lines), encoding="utf-8")  # no final newline, as in the dataset
    for name in tests:
        (root / "videos_i8" / f"{name}.mp4").touch()
        (root / "timestamps" / f"{name}.txt").write_text(
            "2020 01 02 10 00 00 020 20\n2020 01 02 10 00 00 053 53\n2020 01 02 10 00 00 120 120\n", encoding="utf-8"
        )
        (root / "pvt-rt" / f"{name}.csv").write_text(
            "2020-01-02_10.00.00.000\n"
            "2020-01-02_10.00.05.500;2020-01-02_10.00.05.812\n"
            "2020-01-02_10.01.02.000;2020-01-02_10.01.03.250\n",
            encoding="utf-8",
        )
    return root


FPS = 15.0


def synthetic_signals(sleepiness: float, seconds: float, rng: np.random.Generator, lost: slice | None = None) -> rldd.Signals:
    """A face that blinks more often and for longer the sleepier it is (0..1); frames in ``lost`` have no face."""
    n = int(seconds * FPS)
    time_s = 0.02 + np.arange(n) / FPS + rng.uniform(0, 0.004, n)
    closed = np.zeros(n, dtype=bool)
    every = max(4, int((5.0 - 3.0 * sleepiness) * FPS))
    length = 2 + int(round(4 * sleepiness))
    for start in range(int(rng.integers(3, 20)), n - length, every):
        closed[start : start + length] = True
    face = np.ones(n, dtype=bool)
    if lost is not None:
        face[lost] = False

    def missing(values: np.ndarray) -> np.ndarray:
        return np.where(face, values, np.nan)

    return rldd.Signals(
        time_s=time_s,
        face=face,
        eye_blink=missing(np.where(closed, 0.85, 0.1)),
        ear=missing(np.full(n, 0.3)),
        pitch_deg=missing(rng.normal(0, 1.0 + 3 * sleepiness, n)),
        yaw_deg=missing(np.zeros(n)),
        roll_deg=missing(np.zeros(n)),
        mouth_open_ratio=missing(np.full(n, 0.05)),
        nose_y=missing(0.5 + rng.normal(0, 0.002, n)),
    )


def synthetic_pvt(sleepiness: float, seconds: float, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """A stimulus every 6 s on average; reactions slow down with sleepiness."""
    stimulus_s = np.cumsum(rng.uniform(4.0, 8.0, int(seconds / 4)))
    stimulus_s = stimulus_s[stimulus_s < seconds]
    rt_ms = 250.0 + 300.0 * sleepiness + rng.normal(0, 20.0, len(stimulus_s))
    return stimulus_s, rt_ms


def synthetic_tests(root: Path, sleepiness: dict[str, float], seconds: float = 180.0, seed: int = 3):
    """``(tests, windows, coverage)`` as ``drozy.extract_windows`` would return them, without video or MediaPipe."""
    rng = np.random.default_rng(seed)
    names = list(sleepiness)
    kss = {(int(n.split("-")[0]), int(n.split("-")[1])): 1 + 8 * s for n, s in sleepiness.items()}
    lines = [" ".join(str(int(round(kss.get((subject, test), 5)))) for test in (1, 2, 3)) for subject in range(1, 15)]
    fake_drozy(root, names, lines)
    tests = drozy.load(root)
    rows, covered = [], []
    for test in tests:
        level = sleepiness[test.name]
        signals = synthetic_signals(level, seconds, rng)
        stimulus_s, rt_ms = synthetic_pvt(level, seconds, rng)
        own = drozy.recording_windows(test, signals, _yawn_params(), stimulus_s, rt_ms)
        rows += own
        covered.append(drozy.coverage(test, SimpleNamespace(meta={"frames_read": 2 * len(signals.time_s)}), signals, own))
    import pandas as pd

    return tests, pd.DataFrame(rows), covered


def _yawn_params():
    from pulsar_vision import fatigue_pipeline

    params, _ = fatigue_pipeline.load_yawn_params(fatigue_pipeline.YAWN_PARAMS_FILE)
    return params
