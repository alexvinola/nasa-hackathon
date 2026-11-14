"""Goal scoreboard: runs `make check-Gn` for every goals/Gn-*.md and reports which pass.

uv run python scripts/goals.py            # all of them
uv run python scripts/goals.py G4 G6      # only those
uv run python scripts/goals.py --skip G2  # without training (slow)
"""

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIMEOUT_S = 600


def goals():
    for path in sorted((ROOT / "goals").glob("G*-*.md"), key=lambda p: int(p.name[1:].split("-")[0])):
        text = path.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ").strip()
        owner = re.search(r"Owner:\s*([^·\n]+)", text)
        optional = re.search(r"Optional:\s*yes", text) is not None
        yield path.name.split("-")[0], title, owner.group(1).strip() if owner else "?", optional


def run(goal_id):
    started = time.monotonic()
    try:
        result = subprocess.run(
            ["make", "-s", f"check-{goal_id}"], cwd=ROOT, capture_output=True, text=True, timeout=TIMEOUT_S
        )
    except subprocess.TimeoutExpired:
        return "TIMEOUT", f"over {TIMEOUT_S} s", time.monotonic() - started
    output = (result.stdout + result.stderr).strip().splitlines()
    missing = next((line for line in output if line.startswith("MISSING:")), None)
    if result.returncode == 0:
        return "PASS", "", time.monotonic() - started
    return ("MISSING" if missing else "FAIL"), (missing or (output[-1] if output else "")), time.monotonic() - started


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("only", nargs="*")
    parser.add_argument("--skip", nargs="*", default=[])
    args = parser.parse_args()

    passed = total = optional_passed = optional_total = 0
    for goal_id, title, owner, optional in goals():
        if (args.only and goal_id not in args.only) or goal_id in args.skip:
            continue
        status, detail, seconds = run(goal_id)
        if optional:  # listed, but never what makes the scoreboard red
            optional_total += 1
            optional_passed += status == "PASS"
        else:
            total += 1
            passed += status == "PASS"
        print(f"{status:<8} {title:<34} {owner:<22} {seconds:5.0f}s  {detail[:90]}", flush=True)
    print(f"\n{passed}/{total} goals green" + (f", {optional_passed}/{optional_total} optional" if optional_total else ""))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
