# G0 · Telemetry contract

Owner: Everyone (first hour) · Branch: `goal/G0-contract` · Depends on: —

## Goal
A single contract (`shared/telemetry.schema.json`) validated by both frontend and backend, so each vertical can work against mock data from the first hour.

## Done when
- The schema is valid JSON Schema 2020-12, the examples in `shared/examples/` and the inputs in `shared/scenarios/` pass, and those in `shared/examples/invalid/` are rejected.
- The backend answers 200 to valid examples and 422 to invalid ones on `POST /rules/evaluate` (it may return a fixed GREEN verdict for now).
- The frontend validates the same file (Ajv) in `src/acceptance/contract.test.ts`, and the Zustand store boots from `shared/examples/nominal.json`.

## Check
`make check-G0`
1. `scripts/check_contract.py` (shared part, already green)
2. `backend/tests/acceptance/test_contract.py` (written; the backend is missing)
3. `frontend/src/acceptance/contract.test.ts` (to be written once the Next.js app exists)

## Interface it fixes
- `backend/main.py` exposes `app`; `POST /rules/evaluate` takes the full contract and returns the `decision` block.
- Any contract change bumps `schemaVersion` and needs all three people to agree.

## First-hour split
- FS2: `backend/` with uv (Python 3.12), FastAPI, `main.py` with the endpoint and a GREEN stub; dev deps: pytest, httpx, jsonschema, and `[tool.pytest.ini_options] pythonpath = ["."]`.
- FS3: `frontend/` with Next.js + Tailwind + Zustand + Vitest + Playwright; initial store from the nominal example.
- FS1: `data/` with uv and notebooks; start the RLDD download (1 fold) right away.
