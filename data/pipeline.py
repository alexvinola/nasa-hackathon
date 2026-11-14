"""`make model`: train and validate the PULSAR fatigue model on UTA-RLDD, end to end.

    cd data && uv run python pipeline.py              # full run
    cd data && uv run python pipeline.py --limit 6    # smoke run, writes under out/smoke/

Writes ``fatigue_model.json`` (what the browser loads), ``out/metrics.json`` and
``out/fatigue_report.md``. The steps live in ``pulsar_vision/fatigue_pipeline.py``; the feature
definitions the browser ports live in ``pulsar_vision/fatigue_features.py``.
"""

import sys

from pulsar_vision.fatigue_pipeline import main

if __name__ == "__main__":  # the guard matters: MediaPipe workers are separate processes that import this file
    sys.exit(main())
