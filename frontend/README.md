# PULSAR frontend

Next.js/React HUD with Zustand state, Three.js rendering, MediaPipe vision worker,
PVT logic and indicator guides. Not a medical device.
Read the generated [Next.js agent guidance](AGENTS.md) before changing framework code.

## Local development

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

Passing indicator data tests alone does not complete G9.
See [implementation status](../docs/IMPLEMENTATION.md) and [the harness](../docs/HARNESS.md).
