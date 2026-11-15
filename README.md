# PULSAR

**Personal Unit for Learning, Support, Assistance & Reminders.**
Your personal health companion in space: a laptop-local astronaut health prototype
for NASA Space Apps 2026. Not a medical device.

Vision measures, the fatigue classifier estimates, the rules engine decides,
and Gemma phrases the verdict. No cloud calls during the demo.
The internal S.Y.N.A.P.S.E. identifiers remain for compatibility.

## What exists

- Shared telemetry schema, scenarios, sources and official HRP identifiers.
- FastAPI deterministic rules and countermeasures, with a local voice pipeline.
- Next.js HUD, MediaPipe worker, PVT logic and indicator guides.
- HUD companions: a daily-habits panel (four habits, a perfect-day score, 3/7/30-day ranges and an expanded
  month view), guided relaxation exercises, one panel that merges "how to measure" with the measurement form,
  a gear menu for the developer panels (AI check with Gemma 4, debug, log), and ES/EN text.
- PULSAR drives the HUD by voice or chat through a closed list of actions (open relaxation or an exercise, open a
  measurement, type a measurement or a habit in, show the habits); see [the backend guide](backend/README.md).
- Python vision extraction, fatigue training/model artifacts and yawn calibration.
- Acceptance checks and goal-oriented agent workflows.

These are implementation evidence, not a declaration that every goal passes.
See [implementation status and gaps](docs/IMPLEMENTATION.md).

## Develop and verify

Prerequisites: Python 3.12 with uv, Node/pnpm, make and Git Bash on Windows.
Install dependencies during setup, before offline operation:

```powershell
Set-Location frontend
pnpm install --frozen-lockfile
Set-Location ..\backend
uv sync --frozen
Set-Location ..
make contract
uv run --no-project --offline python scripts\harness.py validate
uv run --no-project --offline python scripts\harness.py inventory
```

Run the frontend and backend separately for now; see their
[frontend](frontend/README.md) and [backend](backend/README.md) guides.
`make start` is specified but its launcher is still missing.
Model downloads require connectivity during preparation; see [PREP](docs/PREP.md).

```powershell
make check-G4
make check-G9
uv run --no-project --offline python scripts\harness.py check G9 --report .synapse\harness.json
```

Use the exact goal check, not a substitute. `make goals` runs all checks, including
potentially expensive model training; the harness inventory only checks prerequisites.
The harness does not declare a goal complete or replace independent verification.

## Agents and documentation

- [Agent entry point](AGENTS.md) and [project conventions](CLAUDE.md).
- [Harness guide](docs/HARNESS.md): agent/skill routing and local validation.
- [Goals](GOALS.md): authoritative acceptance criteria and dependencies.
- [Sources](docs/sources.md): provenance and explicit assumptions.
- [Judging](docs/JUDGING.md): the Space Apps rubric, eligibility rules and where PULSAR stands.
- [NASA data](research/nasa-data/README.md) and [brand assets](docs/brand/).

Repository documentation is in English. No automatic downloads, publishing,
server termination or clinical threshold changes are part of the harness.
