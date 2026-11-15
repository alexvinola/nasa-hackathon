# PULSAR frontend

Next.js/React HUD with Zustand state, Three.js rendering, MediaPipe vision worker,
PVT logic and indicator guides. Not a medical device.
Read the generated [Next.js agent guidance](AGENTS.md) before changing framework code.

## The HUD at a glance

- **How to measure** (left column): the body markers open the measurement panel on that signal; the same panel
  holds the guide (steps, picture, why it matters, when abnormal) and the form to type the reading in. It is open
  from the start; R or its close button folds it.
- **Daily habits**: sleep (typed in the measurement form), exercise, hydration and relaxation add up to the day's
  score; all four on target is exactly 100 %. 3/7/30-day histogram, and EXPAND for a month or any date range.
  The first run shows 60 days of demo data (clearly mock, today empty); the log lives in `localStorage`
  (`pulsar-habits-v2`).
- **Gear** (bottom left): click it for the developer panels: AI check with Gemma 4 (face mesh off and AI check on
  by default), debug and the backend log. The Debug and Log panels unfold upwards.
- **RELAX** button: guided breathing, eye rest and body relaxation; finishing one counts for the relaxation habit.
- **PULSAR as a controller**: what the astronaut says or types can open relaxation, a measurement or the habits and
  can log a habit or a measurement. The backend returns an `action` (`src/modules/hud/hudActions.ts`); every panel
  that owns the piece listens for it and checks it again. Examples are in [the backend guide](../backend/README.md).

## Local development## Local development

```powershell
Set-Location frontend
pnpm install --frozen-lockfile
pnpm dev
```

The backend runs separately on localhost:8000. Model assets must be prefetched before
offline operation; see [preparation](../docs/PREP.md). The combined G8 launcher is missing.

## Validation

```powershell
pnpm lint
pnpm exec vitest run src/acceptance/pvt.test.ts src/acceptance/indicators.test.ts
Set-Location ..
make check-G9
```

`pnpm lint` is the repository's TypeScript no-emit check.
G9 Playwright mocks the backend and starts Next.js on port 3100. An existing server on
3000 is not reused and may block startup with a dev lock. Coordinate with its owner;
do not kill it automatically or change the acceptance check to hide the problem.

The `make check-G9` Playwright spec drives the merged measurement panel through the same `data-guide*`
attributes the old guide panel had. If port 3000 is taken by a dev server of this same folder, build with
`NEXT_PUBLIC_LANG=en pnpm exec next build`, serve it with `next start -p 3100` and run
`pnpm exec playwright test e2e/acceptance/g9-guides.spec.ts` (the config reuses a server already on 3100).

Passing indicator data tests alone does not complete G9.
See [implementation status](../docs/IMPLEMENTATION.md) and [the harness](../docs/HARNESS.md).
