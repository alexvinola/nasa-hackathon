# G3 · PVT-B test

Owner: FS1 · Branch: `goal/G3-pvt` · Depends on: G0

## Goal
3-minute Psychomotor Vigilance Test (brief version) that records every reaction and writes the mean and lapses to the contract.

## Done when
With simulated timings (fake clock, no browser):

- **Intervals.** After each response or time-out, the next stimulus appears after a random 1-4 s; the reaction time is shown during the first 1 s of that interval.
- **Every trial is recorded** as one of: valid response, false start or time-out, with its reaction time.
- **Valid response.** A reaction of 100 ms or more to a stimulus on screen.
- **Lapse.** A valid response of 355 ms or more (PVT-B criterion), or a time-out.
- **False start.** A response with no stimulus on screen, or a reaction under 100 ms. It is not a lapse and does not enter the mean.
- **Time-out.** 30 s with a stimulus on screen and no response: the trial ends, counts as one lapse and is recorded with a 30 s reaction time.
- **Duration.** No stimulus is presented after 180 s; a trial still open at 180 s is discarded.
- **Result.** When it ends, the store has `biometrics.lastPvtMeanMs` = mean reaction time of the valid responses (time-outs and false starts excluded) and `biometrics.lastPvtLapses` = number of lapses. With no valid response, `lastPvtMeanMs` is null.

## Check
`make check-G3` → `frontend/src/acceptance/pvt.test.ts` (Vitest with fake timers, no browser).

## Notes
- Source: `basner-2011-pvtb`, Sections 2.2 and 2.3, read from the original on 2026-11-14. Intervals, the 100 ms and 355 ms limits and the 30 s time-out are the paper's.
- **Our choices, not the paper's:**
  - Mean reaction time in milliseconds. The paper reports response speed (1/RT), lapses and a performance score, not a mean in ms; the contract has `lastPvtMeanMs`, so we keep it.
  - Leaving time-outs out of the mean. One 30 s trial would swamp it; the time-out still counts as a lapse.
  - Discarding the trial open at 180 s. The part of the paper we read does not say how the test ends.
- 355 ms was calibrated on a handheld device (PVT-192), not on a laptop keyboard and screen. Our milliseconds are compared with each person's own rested run, not with the paper's.
- Sanity check while building: the paper sampled 62.3 stimuli per 3-minute test on average.

## Changed on 2026-11-14
Before the acceptance test was written, "Done when" was aligned with the original paper. Added: reactions under 100 ms are false starts, the 30 s time-out, the 1 s feedback inside the interval, the end rule and what the mean includes. Nothing was removed.

## Out of scope
Measuring the laptop's input and display delay (do it on the demo laptop, see `docs/PREP.md`); the camera-triggered PVT and the fit-for-task check (Tier 1 in `goals/SCOPE-fatigue.md`); the paper's other metrics (1/RT, performance score), which would need new contract fields.
