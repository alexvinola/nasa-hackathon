# PULSAR agent entry point

Read [CLAUDE.md](CLAUDE.md) for product constraints, ownership and the goal workflow.
Use [the harness guide](docs/HARNESS.md) for commands, agent routing and verification.
Use the existing `work-goal` skill for one approved goal at a time.

- Preserve `goals/protected.txt`: never change acceptance criteria to make checks pass.
- Inspect git status and `SYNAPSE_VERTICAL` before editing. Keep repository text in English.
- File presence, passing unit tests and a complete goal are different evidence levels.
- A goal needs its exact `make check-Gn` and independent `goal-verifier` confirmation.
- Hooks are host-specific; do not assume every editor or tool enforces them.
- Do not stop another user's server, download models or publish changes without authorization.
- The demo stays local and offline; the rules engine decides and the LLM only phrases its verdict.
