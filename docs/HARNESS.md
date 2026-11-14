# PULSAR local agent harness

The harness connects existing implementation, documentation, skills and exact goal
checks. It does not replace the contract, acceptance tests or the independent verifier.

## Entry points and hosts

| Surface | Entry |
|---|---|
| VS Code / skills-capable Copilot | Root [AGENTS.md](../AGENTS.md), `.github/agents/*.agent.md`, `.github/skills/pulsar-harness/SKILL.md` |
| Claude Code | [CLAUDE.md](../CLAUDE.md), `.claude/agents/`, existing `.claude/skills/`, `.claude/settings.json` |
| Local command line | [scripts/harness.py](../scripts/harness.py) |

The VS Code agent wrappers reuse existing skills rather than copying their workflows.
Reload the agent picker/start a new session after adding customizations. Discovery is
host-dependent: check that the agents and skills are actually visible. Do not assume
Claude-format hooks enforce VS Code tools, terminal edits or every patch operation.

Claude's active configuration is `.claude/settings.json`, not a renamed JSON file.
The path guard and Stop gate must remain enabled. If the configured
`CLAUDE_PROJECT_DIR` is unavailable in a Windows host, correct the command to invoke
the hook relative to the repository root and set its working directory accordingly;
do not rename the configuration to bypass a failing guard.

## Local commands

Run from the repository root with an already-installed Python 3.12:

```powershell
uv run --no-project --offline python scripts\harness.py validate
uv run --no-project --offline python scripts\harness.py inventory
uv run --no-project --offline python scripts\harness.py check G9 --report .synapse\harness.json
uv run --no-project --offline python -m unittest discover -s scripts\tests -p "test_harness.py"
```

- `validate`: customization metadata, local documentation links and Claude hook wiring.
  This is a static wiring check, not proof that a host loaded the customizations.
- `inventory`: goal specs and transitive `$(call need,...)` prerequisites from the existing
  Makefile. It does not discover every runtime/model requirement or execute tests.
- `check G<n>`: runs exactly `make check-G<n>`, preserves its exit code/output and
  explicitly reports that the independent verifier has not run.
- `--report`: optional local JSON evidence, timestamped and containing full check output.
  Reports may contain local paths; do not upload them automatically.

Missing files and failures return nonzero exit codes. A passing check is `CHECK_PASS`,
never a complete goal. `--offline` applies to uv's harness invocation, not every child
command: offline demo readiness still requires preloaded assets and disconnected rehearsal.
No automatic all-goals execution, downloads, dependency installation, process killing or PRs.

## Agent and skill routing

| Task | Agent / skill | Boundary |
|---|---|---|
| Readiness, documentation, harness inventory | `pulsar-harness` | Presence is not acceptance |
| Implement one approved G0-G11 | `pulsar-implementer` + `work-goal` | Goal branch, owner vertical, approved acceptance first |
| Independently confirm a passing goal | `goal-verifier` | Exact check and criterion mapping; no edits |
| Review substantive changes | `review-change`, optionally `code-reviewer` | Evidence-based review, no source edits |
| Add/cut or correct an acceptance criterion | `new-goal` | Human approval; never weaken a failing check |
| Interpret NASA/space-health datasets | `explain-dataset` | Cite evidence; do not invent model metrics |
| Difficult cross-module exploration | `explore-codebase` | Use only when direct navigation is insufficient |
| HTTP compatibility | `check-api-compatibility` | Baseline/candidate OpenAPI; not a general review |
| GitHub operations | `github-workflow` | Publishing/merging needs authorization |
| Requested SonarQube findings | `sonarqube-issues` | Requires configured server; not a default gate |

## Implementation cycle

1. Inspect git status, goal dependencies and `SYNAPSE_VERTICAL`.
   PowerShell: `$env:SYNAPSE_VERTICAL='FS3'` before starting the agent.
2. Load `work-goal`, select the goal branch and record its baseline check.
3. Missing acceptance comes before production code and requires human approval.
   Preserve [protected paths](../goals/protected.txt).
4. Implement in the assigned vertical; use shared scenarios until integration.
   On Windows use `New-Item -ItemType Directory -Force .synapse` and
   `Set-Content -Encoding utf8 .synapse\active-goal G9` for goal state.
5. Run the exact check, review changes, then request `goal-verifier`.
   Record a human/environment blocker in `.synapse/blocked` when necessary.
6. Close only after check and verifier pass. Commit/push/PR/merge require authorization.

## Environment troubleshooting

The G9 Playwright configuration starts Next.js on port 3100 and only reuses that port.
An existing Next.js dev server for the same checkout on port 3000 can prevent startup
because of the dev lock. Do not kill it automatically, change the acceptance target,
or report the unit tests as complete G9 verification. Coordinate with its owner.
The latest exact G9 run passed both suites; this remains a troubleshooting note,
not a current failing-check claim.

## Remaining work

See [implementation status](IMPLEMENTATION.md). Existing skills cover the workflow,
not the missing product features. Integration/offline rehearsal, model training,
missing acceptance suites and optional emergency/camera features still need their own goals.
