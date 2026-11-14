# Goals

A goal is done when its check passes. Status is never written by hand: `make goals` computes it.
Details for each goal live in `goals/`. The figures (0.7, 5 s, 15 fps) are proposals: tune them to the demo laptop.

| Goal | Done when | Check | Owner |
|---|---|---|---|
| [G0 Contract](goals/G0-contract.md) | `telemetry.schema.json` validates the examples and both front and back use it | `make check-G0` | Everyone (first hour) |
| [G1 Camera fatigue](goals/G1-camera-fatigue.md) | With the eyes-closed video, fatigueScore > 0.7 in < 5 s; ≥ 15 fps | `make check-G1` | FS1 |
| [G2 Fatigue model](goals/G2-fatigue-model.md) | One command extracts features, trains leave-subject-out, writes metrics and `fatigue_model.json` | `make check-G2` | FS1 |
| [G3 PVT-B test](goals/G3-pvt.md) | 3 min of stimuli; records every reaction, mean and lapses | `make check-G3` | FS1 |
| [G4 Rules engine](goals/G4-rules-engine.md) | Every scenario in `shared/scenarios/` returns the expected status, escalation, HRP risk and factors | `make check-G4` | FS2 |
| [G5 Voice](goals/G5-voice.md) | Audio to spoken answer with no network; latency measured and logged | `make check-G5` | FS2 |
| [G6 Twin and sliders](goals/G6-twin-sliders.md) | Each slider changes the contract and the affected system on the twin changes color | `make check-G6` | FS3 |
| [G7 Forensic intro](goals/G7-forensic-intro.md) | The sequence plays and "Rewind" opens the HUD | `make check-G7` | FS3 |
| [G8 Demo](goals/G8-demo.md) | The 2-minute script runs locally with Wi-Fi off | `make check-G8` + rehearsal | Everyone |

## Schedule and gate

| | Sat. midday | Sat. afternoon | Sat. night | Sunday |
|---|---|---|---|---|
| FS1 | G0, G1 (worker, PERCLOS) | G2 | G1 with the model, G3 | Backup video; rPPG if time allows |
| FS2 | G0, G4 | G5 | G5 wired to the verdict | Cached audio, final prompt |
| FS3 | G0, G6 with mocks | G6 | G7 (4 h max) | G8: `start_synapse`, rehearsal, video |

**Saturday-night gate:** an end-to-end demo. If there is none, cut in this order: rPPG, Science Contribution Score, trends and, last, voice (cached audio only). Cutting means rewriting "Done when" with the `new-goal` skill, never skipping the check.
