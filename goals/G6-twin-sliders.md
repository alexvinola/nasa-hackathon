# G6 · Body twin and judge sliders

Owner: FS3 · Branch: `goal/G6-twin-sliders` · Depends on: G0 (G4 for real integration)

## Goal
SVG body twin that lights up by system, and a slider panel (radiation, CO2, sleep) that changes the contract.

## Done when
- Moving each slider changes the matching field in the store.
- With the rules engine mocked (responses from `shared/scenarios/`), the affected system on the twin turns amber or red (`data-status` attribute on each SVG zone).
- ECharts trends for the last few minutes (if time allows; cut before voice).

## Check
`make check-G6` → `frontend/e2e/acceptance/g6-twin.spec.ts` (Playwright).
