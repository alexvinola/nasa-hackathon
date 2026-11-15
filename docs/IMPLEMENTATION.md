# Implementation evidence and remaining work

Snapshot: 2026-11-14. Source inspection plus explicitly listed executions below.
This is not a scoreboard; [GOALS.md](../GOALS.md) and exact checks remain authoritative.
No goal is declared complete without independent verifier confirmation.

| Goal | Existing evidence | Remaining implementation or verification |
|---|---|---|
| G0 | Shared schema/examples; backend contract acceptance | Frontend contract acceptance file missing |
| G1 | MediaPipe worker, vision metrics and Python extractor | G1 E2E and alert/eyes-closed fixtures missing; required performance unverified |
| G2 | Python feature extraction, training pipeline, fatigue model, metrics and model acceptance now present | Exact `make check-G2` and independent confirmation not run in this audit |
| G3 | PVT implementation and unit acceptance | Exact check and full integration need verification |
| G4 | Rules engine/API, policy, countermeasures and scenario acceptance | Exact check and independent confirmation; unresolved assumptions remain explicit |
| G5 | Local voice implementation, API, voice fixtures and benchmark script | Exact voice acceptance, preloaded models and measured offline latency |
| G6 | Twin/simulation and guide-related UI | G6 E2E missing; slider/contract/zone criteria unverified |
| G7 | Frontend and animation dependency | Required intro sequence and G7 E2E not evidenced |
| G8 | Separate frontend/backend and model prefetch script | `start_synapse`, `scripts/check_demo.sh` and rehearsal evidence missing |
| G9 (optional) | Six indicator guides, data acceptance and one-click E2E | Exact check passes: 25 unit tests and 6 E2E; independent verdict NOT CONFIRMED |
| G10 (optional) | Goal specification | Emergency tree asset, API/UI and acceptance missing |
| G11 (optional) | Webcam hook | Camera source selection/persistence/fallback acceptance and Enabot constraints not evidenced |

G2 now has `data/pipeline.py`, `data/acceptance/check_model.py`, `data/fatigue_model.json`
and `data/out/metrics.json`. These appeared after the initial source inventory.
Yawn artifacts in `data/out/` are a separate calibration, not a replacement for G2.
The harness inventory checks explicit Makefile prerequisites; an absent prerequisite
does not mean all other source is absent, and present prerequisites do not prove behavior.

## Verified execution

- Initial `make check-G9`: indicator suite passed but Playwright was blocked by
  an existing Next.js server. A later exact rerun through the harness succeeded:
  **25 unit tests and 6 E2E passed**. The independent verifier returned
  **NOT CONFIRMED**: its available tools could not rerun the check or inspect Git diffs.
  The audited checkout is `main`, not an established goal branch.
- Harness unit validation: **11 tests passed**; static wiring/link validation passed.
  The inventory correctly returns nonzero for missing prerequisites. Local reports:
  `.synapse/harness-inventory.json` and `.synapse/harness-G9.json`.

No model latency, camera FPS, classifier accuracy or disconnected-demo result is
claimed from this audit. Do not convert fixture presence into measured performance.

## HUD additions after the snapshot (2026-11-15)

- Daily habits (`frontend/src/modules/habits`): four habits, perfect-day score, 3/7/30-day ranges, expanded
  month/range view, 60 days of demo data. Unit tests in `habits.test.ts`.
- One measurement panel (`guides/SelfReportPanel.tsx`) now carries the guide of the selected marker and the form;
  the G9 Playwright spec passes against it (6 of 6, served with `next start` on 3100 because a dev server of this
  folder holds the dev lock).
- PULSAR drives the HUD (`backend/pulsar/hud_actions.py`, `frontend/src/modules/hud/hudActions.ts`): closed action
  list, no model call, values checked against the contract on both sides. Unit tests in
  `backend/tests/unit/test_hud_actions.py`. Not exercised end to end against a restarted backend.
- HUD skill (`backend/assets/hud_skill.json`, `pulsar/hud_skill.py`): catalogue of HUD actions for the model to choose from when no fixed phrase matches; tests in `test_hud_skill.py`; tried against gemma4:e2b-it-qat on a laptop (7 phrases, right panel each time).
- Backend acceptance tests that call Ollama (`test_voice.py` phrasing and bench) need the local model running.

## G9 independent review limitations

The verifier mapped the six guides, sources, official HRP names, rule references and
one-click UI assertions to the specification. It identified an acceptance coverage gap:
current values are checked for nonempty content/BPM formatting rather than exact equality
to current telemetry. Numbered step rendering exists but is not explicitly asserted.

It also flagged rule-list fetch error visibility for follow-up and potential ambiguity
if an indicator gains multiple rules. These observations do not establish a current
multi-rule failure or erase the passing check. Existing-server reuse also limits proof
of which source revision served the tested UI.

No protected tests were changed. Any acceptance correction must go through `new-goal`
and human approval; verification needs an independently executable environment.

## Recommended order, one goal at a time

1. Finish G0's shared/frontend acceptance integration.
2. Verify implemented G3/G4 and independently confirm G9 without weakening tests.
3. Complete G1 fixtures and verify G2's existing training/model artifacts with its exact check.
4. Verify G5 against actual local models; complete G6/G7 acceptance and behavior.
5. Implement G8 launcher, health checks and disconnected rehearsals.
6. Reassess optional G9/G10/G11 under the agreed cut order.

Use `work-goal` for implementation, `new-goal` only for approved criterion changes,
`explain-dataset` for data interpretation and `review-change` before closure.
The [routing table](HARNESS.md#agent-and-skill-routing) lists all repository skills.
No new product feature or protected acceptance file was implemented by this documentation task.
