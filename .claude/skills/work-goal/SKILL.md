---
name: work-goal
description: Work on a goal from GOALS.md (G0-G8) until its check `make check-Gn` passes. Use it when the human says "work on G4", "/work-goal G1" or asks to move a hackathon goal forward.
---

# Work on a goal

A goal is done when `make check-<id>` passes and the verifier confirms it. There is no other criterion.

## 1. Prepare

1. Read `goals/<id>-*.md` in full and the part of the contract it touches in `shared/telemetry.schema.json`.
2. Check that `SYNAPSE_VERTICAL` (`echo $SYNAPSE_VERTICAL`) is the goal's owner or `ALL`. If not, stop and tell the human.
3. Branch: `git switch -c goal/<id>-<slug>` from an up-to-date `main` (or switch back to it if it exists).
4. Run `make check-<id>` to see the starting point and note the error.

## 2. If the check does not exist yet

The acceptance test is the specification, so it comes before the code:

1. Write it at the path the goal names (always under an `acceptance/` directory), turning each "Done when" point into an assertion. No production logic inside it.
2. Run it: it must fail for the right reason (the feature is missing, not a syntax error).
3. Show it to the human and wait for approval. The hook asks for confirmation when writing under `acceptance/`; that is expected.
4. Separate commit: `test(<id>): acceptance test`.

## 3. Loop

1. `mkdir -p .synapse && echo <id> > .synapse/active-goal && rm -f .synapse/blocked`. From now on the Stop hook runs the check every time you try to finish.
2. Small step → `make check-<id>` → read the failure → next step. Small commits on the branch.
3. Work against mock contract data (`shared/examples/`, `shared/scenarios/`) while the other vertical is not integrated. Never write in another vertical's folders; the hook denies it.
4. Forbidden to make it pass: editing the acceptance test, the contract or `goals/`; returning fixed values keyed on the scenario or file name; skipping tests; catching the exception that makes the test fail. If the criterion looks wrong, write it in `.synapse/blocked` and ask.
5. If you need a decision from the human (clinical threshold, contract change, dependency on another vertical), write the question in `.synapse/blocked` and stop.

## 4. Close

1. `make check-<id>` green.
2. Launch the `goal-verifier` subagent with the id and the branch. If it does not confirm, go back to the loop with its findings.
3. `rm .synapse/active-goal`, final commit and `git push -u origin goal/<id>-<slug>`.
4. Open the PR against `main` with the `github-workflow` skill, pasting the output of `make check-<id>` and the verifier report. It is merged only if the check also passes on `main` after rebasing.
5. Report to the human: what was done, what the check proved, what was left out and any measured figure (fps, latency).
