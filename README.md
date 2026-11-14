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
- [NASA data](research/nasa-data/README.md) and [brand assets](docs/brand/).

Repository documentation is in English. No automatic downloads, publishing,
server termination or clinical threshold changes are part of the harness.
