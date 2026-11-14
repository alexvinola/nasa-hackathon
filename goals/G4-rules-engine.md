# G4 · Rules engine

Owner: FS2 · Branch: `goal/G4-rules-engine` · Depends on: G0

## Goal
An explicit rules engine (thresholds + hazards + HRP risks) that returns status, escalation, affected systems, HRP risk, factors and countermeasure. It is the only component that decides; Gemma only phrases the answer.

## Done when
For each scenario in `shared/scenarios/`, `POST /rules/evaluate` returns the expected `status`, `escalation`, `hrpRisk` and `affectedSystems`, includes the expected factors (each with a message) and, when not GREEN, a countermeasure.

## Check
`make check-G4` → `backend/tests/acceptance/test_rules_scenarios.py` (already written).

## Notes
- The scenarios are a draft: the owner reviews the expected values with the team before starting. Adding a scenario is a team decision and happens in `shared/scenarios/`.
- Every threshold cites its source in a comment (the 24-astronaut paper for sleep/PVT, a clinical source for blood pressure, glucose and temperature).
- Rules live in data (YAML or JSON), not in scattered `if`s, so they can be shown to the judges.
- Countermeasures: `backend/assets/countermeasures.json`, short steps navigable by voice.
