#!/usr/bin/env python3
"""Stop: while a goal is active, the agent does not finish until its check passes.

- .synapse/active-goal holds the id (G4). The work-goal skill writes it.
- .synapse/blocked with an explanation lets the agent stop: it needs the human.
- After MAX_ATTEMPTS consecutive failures it lets the agent stop and asks for help, to avoid looping.
- SYNAPSE_GATE=off disables it.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(__file__).resolve().parents[2])).resolve()
STATE = ROOT / ".synapse"
MAX_ATTEMPTS = 6
TIMEOUT_S = 540


def say(payload: dict) -> None:
    # ASCII-escaped on purpose: on Windows stdout is cp1252 and check output often has non-ASCII marks.
    print(json.dumps(payload))
    sys.exit(0)


def read_goal(path: Path) -> str:
    """Goal id from .synapse/active-goal, tolerating the BOM / UTF-16 that PowerShell's `>` writes."""
    raw = path.read_bytes()
    encoding = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    return raw.decode(encoding, errors="replace").strip()


def main() -> None:
    json.load(sys.stdin)
    active = STATE / "active-goal"
    if os.environ.get("SYNAPSE_GATE") == "off" or not active.exists():
        return
    goal = read_goal(active)
    if not re.fullmatch(r"G\d+", goal):
        say({"systemMessage": f".synapse/active-goal holds {goal!r}, not a goal id like G4; the gate did not run. "
                              "Rewrite the file with just the id."})
    attempts_file = STATE / f"attempts-{goal}"

    if (STATE / "blocked").exists():
        attempts_file.unlink(missing_ok=True)
        return

    try:
        result = subprocess.run(["make", "-s", f"check-{goal}"], cwd=ROOT, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=TIMEOUT_S)
        ok, output = result.returncode == 0, result.stdout + result.stderr
    except FileNotFoundError:
        # Not something the agent can fix by working on the goal: say it loudly instead of looping.
        say({"systemMessage": f"{goal}: `make` is not installed or not on PATH, so the gate cannot run "
                              f"check-{goal}. Install it (Windows: `scoop install make` or `choco install make`)."})
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
