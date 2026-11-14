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
- DROZY license (`drozy` in `shared/sources.json`): the repository goes public, so nothing from DROZY is committed.
  The raw data lives in `data/raw/drozy/` (git-ignored) and each person downloads it and accepts the license.
  - The G1 fixtures (`data/fixtures/*.y4m`) come from our own recordings, never from DROZY.
  - Notebooks are committed without outputs (`nbstripout`): a cell that shows a frame would embed it in the `.ipynb`.
  - No screenshot of DROZY frames in `docs/`, `research/`, PRs, slides or the video; charts and numbers are fine.
  - Every place that reports a DROZY result cites Massoz et al. (2016), WACV.
- DROZY video is near-infrared grayscale, not a colour webcam: check MediaPipe finds the face and eyelids on a few
  videos before building on it.
