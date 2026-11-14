"""PULSAR vision features in Python, mirroring the browser worker (goals G1 and G2).

The modules here are the reference implementation the JavaScript worker ports:

- ``mouth``      landmark indices and the mouth opening formula
- ``detector``   the yawn detector, a pure function over the per-frame series
- ``landmarks``  MediaPipe FaceLandmarker extraction (same model file as the browser)
- ``yawdd``      calibration and evaluation on the YawDD dataset (``python -m pulsar_vision.yawdd``)
"""
