#!/usr/bin/env python3
"""Stop: while a goal is active, the agent does not finish until its check passes.

- .synapse/active-goal holds the id (G4). The work-goal skill writes it.
- .synapse/blocked with an explanation lets the agent stop: it needs the human.
- After MAX_ATTEMPTS consecutive failures it lets the agent stop and asks for help, to avoid looping.
- SYNAPSE_GATE=off disables it.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(__file__).resolve().parents[2])).resolve()
STATE = ROOT / ".synapse"
MAX_ATTEMPTS = 6
TIMEOUT_S = 540


def say(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(0)


def main() -> None:
    json.load(sys.stdin)
    active = STATE / "active-goal"
    if os.environ.get("SYNAPSE_GATE") == "off" or not active.exists():
        return
    goal = active.read_text().strip()
    attempts_file = STATE / f"attempts-{goal}"

    if (STATE / "blocked").exists():
        attempts_file.unlink(missing_ok=True)
        return

    try:
        result = subprocess.run(["make", "-s", f"check-{goal}"], cwd=ROOT, capture_output=True, text=True,
                                timeout=TIMEOUT_S)
        ok, output = result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        ok, output = False, f"make check-{goal} took longer than {TIMEOUT_S} s"

    if ok:
        attempts_file.unlink(missing_ok=True)
        say({"systemMessage": f"{goal}: check is green"})

    attempts = int(attempts_file.read_text()) + 1 if attempts_file.exists() else 1
    attempts_file.write_text(str(attempts))
    tail = "\n".join(output.strip().splitlines()[-40:])
    if attempts > MAX_ATTEMPTS:
        attempts_file.unlink(missing_ok=True)
        say({"systemMessage": f"{goal}: {MAX_ATTEMPTS} attempts without passing; the gate lets the agent stop. Look into the blocker."})
    say({
        "decision": "block",
        "reason": (
            f"make check-{goal} fails (attempt {attempts}/{MAX_ATTEMPTS}). Keep working on {goal} without "
            "touching the check or the protected paths. If you need a decision from the human or the "
            "criterion looks wrong, write the reason in .synapse/blocked and explain it.\n\n" + tail
        ),
    })


if __name__ == "__main__":
    main()
