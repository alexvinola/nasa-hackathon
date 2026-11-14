---
name: new-goal
description: Define a new goal, or cut down an existing one, in GOALS.md with a "done" criterion that a command can check. Use it when the team wants to add, split or cut a goal during the hackathon.
---

# Define or cut a goal

A vague goal is useless because it does not say when it is finished.

1. Ask the minimum: what must be visible or measurable, who owns it (FS1, FS2, FS3, Everyone) and what it depends on.
2. Write `goals/G<n>-<slug>.md` in the same format as the others: Owner · Branch · Depends on; Goal; Done when (each point observable, with a number when there is one); Check (the command and the `acceptance/` path of the test); Out of scope.
3. Add `check-G<n>` to the `Makefile`, with `$(call need,...)` for whatever does not exist yet, and the row in `GOALS.md`.
4. To cut a goal: do not delete it; rewrite "Done when" with the cut-down version and note in the file what was removed and why. The agreed cut order is in `GOALS.md`.
5. These are all protected paths: the human approves every write. Commit `chore(goals): ...` on `main`, so every branch picks it up when rebasing.
