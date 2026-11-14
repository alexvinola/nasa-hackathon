# Fatigue from the camera: what has been measured

State on 2026-11-14. Every number here was measured by a command in this repository and is copied from its output file;
the detail and the generated wording live in `out/fatigue_report.md` and `out/yawn_report.md`. PULSAR is not a medical
device, and none of these numbers is a validation for spaceflight.

## Summary

- **The fatigue model is trained** (`fatigue_model.json`): seven eye, yawn and head features per 60 s window, a
  three-state logistic regression on UTA-RLDD (24 people), leave-one-subject-out. It ships with eye closure from the
  `eyeBlink` blendshapes and no calibration step, a fixed team decision, not the winner of a comparison.
- **On RLDD it separates alert from drowsy** about as well as eye closure alone, and **not demonstrably better than the
  browser's former fixed formula**.
- **On DROZY (14 people it never saw, near-infrared video) its score rises with PVT reaction time**: Spearman +0.32 per
  test (n = 36), Pearson +0.64. It is a moderate correlation with no interval, not a measurement of performance.
- **Yawns** are calibrated on YawDD. That measures yawning against talking, not drowsiness.

## What each dataset is for

| Dataset | Source id | Role | State |
|---|---|---|---|
| UTA-RLDD | `uta-rldd` | Train and validate the model (labels: the person's own rating per video) | Done on folds 1-2, 24 of 60 people |
| DROZY | `drozy` | Validate the shipped model against PVT reaction time and KSS; never fitted on | Done, all 36 tests |
| YawDD | `yawdd` | Calibrate the yawn detector | Done |

## The model on RLDD

Command: `make model` where RLDD is (its videos or its feature cache in `features/rldd/`). Leave-one-subject-out; 3724
windows of 72 videos. 95 % intervals resample people.

| Measured out of fold | Value |
|---|---|
| AUC, three states | 0.622 (0.574 to 0.675) |
| Macro F1, three states | 0.427 (0.368 to 0.477); accuracy 44.1 % where chance is 33 % |
| `fatigueScore`, alert vs drowsy AUC | 0.747 (0.672 to 0.826) |
| Former browser formula, same windows | 0.728 (0.646 to 0.817); difference +0.019 (-0.033 to 0.074), includes 0 |
| PERCLOS alone, alert vs drowsy | 0.763 (0.676 to 0.851) |
| Mean blink duration alone | 0.733 (0.651 to 0.820) |

The regularisation took the strongest value of its grid, so the score lives in a narrow band (0.39 to 0.99 out of fold)
and a rested face does not score near 0. Thresholds written for the former formula do not carry over.

## The shipped model on DROZY (held out)

DROZY: Massoz, Langohr, François & Verly (2016), *The ULg Multimodality Drowsiness Database (called DROZY) and Examples
of Use*, WACV 2016. Research and evaluation only: no frame is saved, shown or committed, nothing is cached, and only
aggregate numbers are written.

Same extractor and window code as RLDD, with DROZY's own frame times. 36 tests of 14 people, face found in 99.89 % of the
frames (lowest test 98.05 %), 1967 windows, 0 rejected. Nothing is fitted on DROZY.

Per test (n = 36), Pearson / Spearman:

| Camera signal | vs mean PVT reaction time | vs KSS * |
|---|---|---|
| Model `fatigueScore` | +0.64 / **+0.32** | +0.55 / +0.48 |
| PERCLOS alone | +0.54 / +0.15 | +0.50 / +0.39 |
| Former browser formula | +0.55 / +0.12 | +0.50 / +0.35 |

Within each person, window by window (median Pearson r, range, people with a positive r):

| Camera signal | vs PVT reaction time | vs KSS * |
|---|---|---|
| Model `fatigueScore` | +0.48 (-0.16 to +0.87), 11 of 14 | +0.52 (-0.56 to +0.90), 9 of 13 |
| PERCLOS alone | +0.56 (-0.39 to +0.86), 13 of 14 | +0.39 (-0.91 to +0.84), 10 of 13 |
| Former browser formula | +0.56 (-0.35 to +0.85), 12 of 14 | +0.39 (-0.79 to +0.84), 10 of 13 |

\* KSS is not registered in `shared/sources.json`: register it before quoting a KSS figure.

How to read it:

- `pvt_correlation` in `out/metrics.json` is the per-test Spearman (+0.32), chosen before the model's DROZY numbers were
  seen: tests are the only units that do not overlap, and a test's mean reaction time is pulled up by a few very slow
  responses, so Pearson can be carried by two or three tests. Spearman is well below Pearson here for every signal.
- The direction is right for all three signals, but there is no interval: the three cannot be ranked on 36 tests.
  Within a person, PERCLOS alone is positive for more people than the model is.
- Near-infrared video with faces about 65 px wide: these numbers do not transfer to the demo's colour webcam.

## Thresholds (RLDD)

Section "Where a threshold would sit" of `data/out/fatigue_report.md`; block `thresholds` of `metrics.json`.

- The engine's PERCLOS warning (`perclos-high`) is calibrated here: 0.11 lets 5 % of the alert windows of all 24
  subjects fire. Out of fold it fires on 7 % of alert windows and 24 % of the windows of videos called drowsy. At the
  former 0.30 it fired on 6 % of those.
- The false alarms are not spread evenly: the median alert person has none, a few have most of them.
- The danger rule (`fatigueScore` at or above 0.70) never fires on the minute's formula in RLDD. In the browser it is
  reached by eyes held closed for about 3 s (`vision-hud/sleep.ts`), whose timings are team assumptions.
- Not validated on the demo camera.

## Yawns (YawDD)

Command: `make yawns`. A yawn is a mouth opening ratio of at least 0.26 held for at least 1.0 s. Out of fold: 88 of 102
Yawning videos detected, 3 of 100 Talking and 0 of 105 Normal videos with a false yawn. Acted yawns by drivers with one
label per video; nobody labelled yawns in RLDD or DROZY.

## How `make model` behaves

- **RLDD and DROZY here**: trains, validates, writes `fatigue_model.json`, `out/metrics.json` and the report, then
  validates the new model on DROZY and puts it in the same files (DROZY adds about 6.5 minutes with 5 processes).
- **Only DROZY here** (no RLDD videos, no cache): nothing is trained. The existing model is validated on DROZY and the
  result is merged into `out/metrics.json` and the report; the model file and every RLDD number stay as they are.
- **Neither**: it stops with an error and writes nothing. `--no-drozy` skips DROZY; smoke runs (`--limit`) skip it too.

## Not measured

- Anything on the demo's colour webcam, in the venue's lighting, or on astronauts.
- An interval for the DROZY correlations, or whether the model beats PERCLOS alone or the former formula there.
- Whether a calibration at the start of a session helps: RLDD cannot show it, and it was not tried on DROZY.

## Assumptions behind these numbers

Declared in `pulsar_vision/fatigue_features.py` and listed in `out/metrics.json` under `features.constants`.

| Value | Where it comes from |
|---|---|
| 60 s windows, 10 s step | PERCLOS is defined over one minute (`fmcsa-1998-perclos`); step from `goals/G2-fatigue-model.md` |
| Eye closed when mean `eyeBlink` > 0.5 | The browser worker's constant; team assumption |
| Long closure from 0.5 s; nod = 10 degrees down, ending within 5 | Team assumptions |
| Window used with at least 450 frames and a face in 80 % of them | Team assumption |
| Yawn parameters | `out/yawn_params.json` (`yawdd`) |
