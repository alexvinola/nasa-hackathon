# G3 · PVT-B test

Owner: FS1 · Branch: `goal/G3-pvt` · Depends on: G0

## Goal
3-minute Psychomotor Vigilance Test (brief version) that records every reaction and writes the mean and lapses to the contract.

## Done when
- With simulated timings: stimuli at random 1-4 s intervals; every reaction is recorded; a lapse is a reaction ≥ 355 ms (PVT-B criterion); a response before the stimulus counts as a false start.
- When it ends, `biometrics.lastPvtMeanMs` and `biometrics.lastPvtLapses` are updated in the store.

## Check
`make check-G3` → `frontend/src/acceptance/pvt.test.ts` (Vitest with fake timers, no browser).
