# G9 · Indicator guides (optional)

Owner: FS3 · Branch: `goal/G9-indicator-guides` · Depends on: G0, G4 (rules and countermeasures), G6 (twin) · Optional: yes

## Goal
"Astronauts are not doctors" (`challenge-video`): for every health indicator the challenge names, a guide a
non-doctor can follow, with how to take the measurement, why it matters in spaceflight and what to do when it is
out of range. Reachable from the twin or the HUD readings.

## Done when
- `shared/indicators.json` has one guide for each of `selfReport.bloodPressure`, `biometrics.heartRateBpm`,
  `selfReport.glucoseMgDl`, `selfReport.bodyTempC`, `selfReport.sleepHoursLast24h` and `selfReport.mood`.
- Each guide has non-empty `how` (numbered steps), `why` and `whenAbnormal`, and at least one `source` that exists in
  `shared/sources.json`; `why` names a hazard or risk from `shared/hrp.json` with its official name.
- Guides quote no thresholds: `whenAbnormal` lists rule ids and countermeasure ids that exist in
  `backend/assets/rules.json` and `countermeasures.json`. An indicator with no rule says so ("PULSAR does not judge
  this value yet: tell the crew medical officer") instead of giving a range.
- Clicking an indicator on the twin or the HUD opens its guide in one click, with the current value and the
  engine's status for it, and the line "Not a medical device".

## Check
`make check-G9` → `frontend/src/acceptance/indicators.test.ts` (Vitest: the data rules above) and
`frontend/e2e/acceptance/g9-guides.spec.ts` (Playwright with the engine mocked from `shared/scenarios/`: a click
opens the guide).

## Out of scope
Instructions for a specific device brand, diagnosis, new contract fields, normal ranges that are not a rule in the
engine.
