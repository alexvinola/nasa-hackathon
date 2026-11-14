# G8 · Offline demo

Owner: Everyone · Branch: `main` · Depends on: G0-G7 (or their cut-down versions)

## Goal
The 2-minute script runs locally with Wi-Fi off and starts with `./start_synapse`.

## Done when
- `./start_synapse` brings up Next.js (3000), FastAPI (8000) and Ollama (11434), and all three answer their health check.
- The G0-G7 checks that have not been cut are green.
- A timed rehearsal with Wi-Fi off, logged in `docs/rehearsals.md` (date, duration, what failed).

## Check
`make check-G8` → `scripts/check_demo.sh` (starts everything, runs health checks, runs `make goals`, stops). The rehearsal is done by humans.

## Plan B
Hidden webcam/video switch, 4 pre-generated Piper clips, cached Gemma answers, a recorded video of the full demo.
