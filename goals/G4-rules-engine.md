# G4 · Rules engine

Owner: FS2 · Branch: `goal/G4-rules-engine` · Depends on: G0

## Goal
An explicit rules engine (thresholds + hazards + HRP risks) that returns status, escalation, affected systems, HRP risk, factors and countermeasure. It is the only component that decides; Gemma only phrases the answer.

## Done when
- For each scenario in `shared/scenarios/`, `POST /rules/evaluate` returns the expected `status`, `escalation`, `hrpRisk` and `affectedSystems`, includes the expected factors (each with a message) and, when not GREEN, a countermeasure.
- Every factor's `source` is an id from `shared/sources.json`, or null when the threshold is an assumption.
- `GET /rules` lists every rule as `{id, signal, threshold, source, assumption}`: each rule cites a source id or explains its assumption.

## Check
`make check-G4` → `backend/tests/acceptance/test_rules_scenarios.py` (already written).

## Notes
- The scenarios are a draft: the owner reviews the expected values with the team before starting. Adding a scenario is a team decision and happens in `shared/scenarios/`.
- Thresholds come from `shared/sources.json` (`jones-2022-sleep` for sleep, `basner-2011-pvtb` for PVT lapses). A threshold with no source yet is an explicit `assumption`, listed in `docs/sources.md`; a new source is added to `shared/sources.json` first.
- HRP risk and hazard ids are the official ones in `shared/hrp.json`; the UI shows the official name.
- Rules live in data (YAML or JSON), not in scattered `if`s, so they can be shown to the judges.
- Countermeasures: `backend/assets/countermeasures.json`, short steps navigable by voice.
