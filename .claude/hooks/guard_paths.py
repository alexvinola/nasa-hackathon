#!/usr/bin/env python3
"""PreToolUse (Edit/Write/MultiEdit/NotebookEdit): each agent writes only inside its vertical.

- SYNAPSE_VERTICAL=FS1|FS2|FS3|ALL selects the vertical (exported when launching `claude`).
- Writing to another vertical is denied.
- Writing to a path in goals/protected.txt (checks, contract, goals) asks the human
  for confirmation: those define what "done" means and are not changed to make a check pass.
"""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(__file__).resolve().parents[2])).resolve()

# First match wins. Anything not listed is shared (docs/, README, scripts/...).
OWNERS = [
    ("frontend/src/modules/vision-hud/**", "FS1"),
    ("frontend/public/mediapipe/**", "FS1"),
    ("data/**", "FS1"),
    ("frontend/src/modules/voice-ai/**", "FS2"),
    ("backend/**", "FS2"),
    ("frontend/src/modules/sim-core/**", "FS3"),
    ("frontend/package.json", None),  # dependencies: shared, reconciled on merge
    ("frontend/pnpm-lock.yaml", None),
    ("frontend/**", "FS3"),
    ("start_synapse", "FS3"),
]


def glob_regex(pattern: str) -> re.Pattern:
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + "$")


def matches(rel: str, pattern: str) -> bool:
    return bool(glob_regex(pattern).match(rel))


def protected_patterns():
    path = ROOT / "goals" / "protected.txt"
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.startswith("#")]


def decide(decision: str, reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": decision, "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


def main() -> None:
    event = json.load(sys.stdin)
    tool_input = event.get("tool_input", {})
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not target:
        return
    path = Path(target)
    path = (path if path.is_absolute() else Path(event.get("cwd", ROOT)) / path).resolve()
    try:
        rel = path.relative_to(ROOT).as_posix()
    except ValueError:
        return  # outside the repo (scratchpad, memory): not this hook's business

    if rel.startswith(".synapse/"):
        return

    for pattern in protected_patterns():
        if matches(rel, pattern):
            decide("ask", f"{rel} defines what 'done' means (goals/protected.txt). "
                          "It changes only with the human's approval, never to make a check pass.")

    vertical = os.environ.get("SYNAPSE_VERTICAL", "").upper()
    owner = next((who for pattern, who in OWNERS if matches(rel, pattern)), None)
    if owner is None or vertical == "ALL" or vertical == owner:
        return
    if not vertical:
        decide("deny", "SYNAPSE_VERTICAL is not set. Ask the human to relaunch with "
                       "`SYNAPSE_VERTICAL=FS1 claude` (FS1, FS2, FS3 or ALL).")
    decide("deny", f"{rel} belongs to {owner} and this session is {vertical}. If you need something from that "
                   "vertical, use mock data from the contract or ask its owner for the change.")


if __name__ == "__main__":
    main()
