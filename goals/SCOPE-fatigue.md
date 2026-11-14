# Fatigue scope: how far we go

Fatigue is the deep vertical of PULSAR: with one webcam and one weekend it is the only thing we can measure for real.
Everything else in the contract stays as context around it. This file is the **limit**: what we build, what waits for
the Saturday-night gate, and what we neither build nor claim. It is not a goal and has no check; the goals are still
`G1`, `G2`, `G3` and `G4`.

**Rule of thumb.** If an idea is not in Tier 0, it does not start before its tier opens, and it starts with the
`new-goal` skill, not with code.

## The principle

**The camera screens, the PVT-B confirms, the rules engine decides.** Three independent views of the same person:

| View | What | Where |
|---|---|---|
| Passive, continuous | Webcam features and `fatigueScore` | G1, G2 |
| Active, objective | 3-minute PVT-B: mean reaction and lapses | G3 |
| Subjective | `selfReport.sleepHoursLast24h` | Contract, already there |

The camera alone never raises a RED. A high `fatigueScore` is a reason to ask for a PVT-B; the escalation comes from
the rules engine combining the views (G4). Disagreement between views is information too, not an error to hide.

## Tier 0 · Committed (already in the goals, nothing new)

| What | Goal | Stop when |
|---|---|---|
| PERCLOS, yawns, head nods, arm asymmetry in the worker; `fatigueScore` in the store | G1 | `make check-G1` is green on the demo laptop. No tuning beyond the two fixtures |
| Feature extraction in Python with the same extractor, leave-subject-out training, `fatigue_model.json` | G2 | `make check-G2` is green. Metrics are reported as they come out: no F1 target to chase |
| Per-subject baseline from the first minutes | G2 (notes) | It exists and is used; no adaptive or online recalibration |
| Score vs PVT reaction time correlation on DROZY | G2 (metrics, if DROZY arrives) | One number in `metrics.json`, measured on unseen subjects |
| PVT-B with mean and lapses (355 ms, `basner-2011-pvtb`) | G3 | `make check-G3` is green |
| Sleep + PVT + camera combined into status, escalation and factors | G4 | Every scenario in `shared/scenarios/` passes |
| The rest of the contract as context: CO2, mood, glucose, temperature, radiation, gravity | G4, G6 | Manual or simulated inputs only. No new sensor, no new field |

"The rest as context" means: fatigue is the symptom, the other fields explain it. Same drowsy face, different cause,
different countermeasure (high cabin CO2: check the cabin; under 6 h of sleep: rest, `jones-2022-sleep`). That is
already what scenarios 02, 03 and 05 test; it is rules, not new measurement.

## Tier 1 · Only if the Saturday-night gate is green (each one needs `new-goal`)

In this order. Each is small on purpose; none changes the contract.

1. **Camera-triggered PVT.** A sustained high `fatigueScore` makes the rules engine return a "take the PVT-B"
   countermeasure. Needs one new scenario in `shared/scenarios/` (team decision) and one entry in the countermeasures.
   The duration and the threshold are assumptions until G2 gives us a measured one.
2. **Fit-for-task check.** Before a critical operation: a short camera window plus the PVT-B, then go / caution /
   hand over, decided by the rules engine. It is a screen that reuses G1, G3 and G4; it adds no new signal.
   Grounding: the ASRS pattern in `asrs-report-sets` (82 of 100 reports involve a procedural deviation, 46 happen in
   approach, descent or landing) and the forensic intro (G7).
3. **Our own recordings.** Each of us records two minutes of camera plus a PVT-B at three moments of the weekend
   (rested, late night, Sunday). Limits: three people is a story, not evidence; it never trains the model; the videos
   are faces, so they stay on the laptop, git-ignored, and are never committed or uploaded.

## Tier 2 · Stretch, Sunday only, after G8 rehearses clean

| Idea | Limit |
|---|---|
| Blink duration, blink rate and long eye closures as model features | Inside the model only. Showing them as numbers needs a contract bump (`schemaVersion`) and is a team decision |
| One-question sleepiness scale (KSS) in the self-report | Contract bump; source must be registered first |
| Alertness "what if" on the twin (sleep 2 h more) | Declared as an assumption on screen; never feeds a rule |
| Gaze dispersion from the iris landmarks | Experimental label; never feeds the score |
| rPPG heart rate | Already the first item in the cut order of `GOALS.md` |

Trends stay where `GOALS.md` puts them: third in the cut order.

## Out · We do not build it and we do not claim it

- Camera-based HRV, SANS detection (already product rules in `CLAUDE.md`).
- Emotion or mood recognition from the face. Mood is the 1-5 self-report, nothing else.
- Pupil size and saccade velocity: a 30 fps visible-light webcam cannot measure them.
- "Microsleep detection", "diagnosis" or any medical wording. We say "signs consistent with drowsiness".
- Face recognition or identifying who is in front of the camera.
- Storing or sending video. Features are computed live; frames are discarded.
- Letting the model or Gemma decide a status or an escalation.
- New hardware (IR camera, wearables). A watch or oximeter is only a live comparison for the demo (`docs/PREP.md`).

## What we may say in the pitch

| We may say | We may not say |
|---|---|
| "The camera estimates drowsiness signs and the rules engine decides" | "PULSAR detects fatigue" as a medical fact |
| The metrics in `data/out/metrics.json`, exactly as measured | Any accuracy, latency or fps we did not measure on the demo laptop |
| "Trained on lab and volunteer drowsiness video, not on astronauts" | That it is validated for spaceflight |
| "RLDD labels are self-reported; we validate against PVT where DROZY allows" | That the score equals cognitive performance |

Known limits to state openly: glasses and lighting change the eye measurements; head nods rely on gravity pulling the
head down, so in microgravity we expect the eye features to carry the signal (our hypothesis, no source yet).

## Before any of this is quoted

These came up in the research and are **not in `shared/sources.json`**. Verify the original, register it, then use it:

- The PERCLOS definition and its eye-closure threshold.
- Self-rated alertness underestimating real impairment under chronic sleep restriction (candidate: Van Dongen et al., 2003).
- The Karolinska Sleepiness Scale (KSS), if Tier 2 uses it.
- Facial puffiness from fluid shift in microgravity, as the reason a personal baseline matters in flight.

## Changing this file

It is a team decision, like the contract: all three agree, and the change is committed as `chore(goals): ...` on `main`.
Moving an item up a tier means writing its goal with `new-goal` first.
