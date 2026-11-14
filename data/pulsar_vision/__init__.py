"""PULSAR vision features in Python, mirroring the browser worker (goals G1 and G2).

The modules here are the reference implementation the JavaScript worker ports:

- ``mouth``      landmark indices and the mouth opening formula
- ``detector``   the yawn detector, a pure function over the per-frame series
- ``landmarks``  MediaPipe FaceLandmarker extraction (same model file as the browser)
- ``yawdd``      calibration and evaluation on the YawDD dataset (``python -m pulsar_vision.yawdd``)

Fatigue model (goal G2, ``make model``):

- ``fatigue_features``  THE definitions the worker ports: eye closure, the seven window features,
                        the per-person calibration, the model arithmetic and the ``fatigueScore`` formula
- ``face_series``       FaceLandmarker extraction for those features (eyes, blendshapes, head pose), cached
- ``rldd``              the UTA-RLDD videos: discovery, extraction and the table of 60 s windows
- ``fatigue_model``     logistic regression, subject-grouped validation and metrics
- ``fatigue_pipeline``  the end-to-end run behind ``data/pipeline.py``; ``fatigue_report`` writes the report
"""
