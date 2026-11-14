---
name: pulsar-harness
description: "Audit PULSAR implementation gaps, refresh README documentation, validate agent wiring or run a local goal check. Use for harness, readiness and existing-skills coverage requests."
---

# PULSAR harness

1. Read [the harness guide](../../../docs/HARNESS.md) and
   [implementation status](../../../docs/IMPLEMENTATION.md).
2. Inspect git status and ownership. Run
   `uv run --no-project --offline python scripts/harness.py validate`.
3. Run `uv run --no-project --offline python scripts/harness.py inventory`.
   This checks required file presence, not behavior. Missing files produce a nonzero exit.
4. Select one relevant exact goal check. Run
   `uv run --no-project --offline python scripts/harness.py check G9` (replace the id).
   Record full output, exit status and environment blockers.
5. For implementation load `work-goal`; for changed criteria use `new-goal`, not a weaker test.
   Use `explain-dataset` for data interpretation, `check-api-compatibility` for HTTP
   contract comparisons and `review-change` before closing.
6. Update documentation with evidence levels and outstanding work. Never mark a goal
   complete without its exact passing check and independent goal-verifier confirmation.

Optional local JSON reports use `--report .synapse/harness.json` after the subcommand.
Do not auto-run all goals, download assets, kill servers or publish changes.
