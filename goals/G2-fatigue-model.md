# G2 · Fatigue model

Owner: FS1 · Branch: `goal/G2-fatigue-model` · Depends on: RLDD / DROZY download

## Goal
One command extracts features with MediaPipe in Python (the same extractor as the demo), trains with leave-subject-out validation and produces `data/fatigue_model.json`.

## Done when
- `make model` runs end to end without errors on the downloaded data.
- `data/out/metrics.json` contains macro F1, AUC, a 3-class confusion matrix, score vs PVT reaction time correlation (if DROZY is available) and the subjects in each fold, with no overlap between train and test.
- `data/fatigue_model.json` contains `features` (names in the same order as the JS), `mean`, `std`, `coef`, `intercept` and `trainedOn`.
- Results are reported as they come out: there is no F1 target to chase.

## Check
`make check-G2` → `make model` + `data/acceptance/check_model.py` (checks the format, that no subject appears in both train and test, and that AUC > 0.5, i.e. better than chance).

## Notes
- 60 s windows with a 10 s step; per-subject normalization using their first minutes as baseline.
- If RLDD does not arrive in time: DROZY/YawDD; if nothing arrives, thresholds from the NASA paper, and we say so in the pitch.
