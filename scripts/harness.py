"""Local harness: validate agent wiring, inventory prerequisites, run exact goal checks."""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parent.parent


class Goal(TypedDict):
    id: str
    specification: str
    required: list[str]
    missing: list[str]
    status: str


class Check(TypedDict):
    goal: str
    command: list[str]
    exit_code: int
    status: str
    stdout: str
    stderr: str
    verifier: str


def inventory(root: Path) -> list[Goal]:
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    targets: dict[str, tuple[list[str], list[str]]] = {}
    current = ""
    for line in makefile.splitlines():
        match = re.fullmatch(r"([\w-]+):\s*(.*)", line)
        if match:
            current = match[1]
            targets[current] = (match[2].split(), [])
        if current:
            for paths in re.findall(r"\$\(call need,([^)]*)\)", line):
                targets[current][1].extend(paths.split())

    def requirements(target: str, seen: set[str]) -> set[str]:
        if target in seen or target not in targets:
            return set()
        seen.add(target)
        dependencies, paths = targets[target]
        required = set(paths)
        for dependency in dependencies:
            required.update(requirements(dependency, seen))
        return required

    result: list[Goal] = []
    for path in sorted((root / "goals").glob("G*-*.md"),
                       key=lambda item: int(item.name.split("-")[0][1:])):
        goal_id = path.name.split("-")[0]
        target = f"check-{goal_id}"
        if target not in targets:
            raise ValueError(f"{goal_id}: missing Makefile target {target}")
        required = sorted(requirements(target, set()))
        missing = [item for item in required if not (root / item).exists()]
        result.append({
            "id": goal_id, "specification": path.relative_to(root).as_posix(),
            "required": required, "missing": missing,
            "status": "MISSING" if missing else "PRESENT_NOT_VERIFIED",
        })
    if not result:
        raise ValueError("No goal specifications found")
    return result


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    required = [
        "AGENTS.md", "README.md", "docs/HARNESS.md", "docs/IMPLEMENTATION.md",
        "frontend/README.md", "backend/README.md",
        ".github/agents/pulsar-implementer.agent.md",
        ".github/agents/goal-verifier.agent.md", ".github/agents/code-reviewer.agent.md",
        ".github/skills/pulsar-harness/SKILL.md",
        ".claude/skills/work-goal/SKILL.md", ".claude/skills/review-change/SKILL.md",
        ".claude/agents/goal-verifier.md", ".claude/agents/code-reviewer.md",
        ".claude/hooks/guard_paths.py", ".claude/hooks/goal_gate.py",
        ".claude/settings.json",
    ]
    for item in required:
        if not (root / item).is_file():
            errors.append(f"Missing harness file: {item}")
    customizations = sorted((root / ".github" / "agents").glob("*.agent.md"))
    customizations += sorted((root / ".github" / "skills").glob("*/SKILL.md"))
    customizations += sorted((root / ".claude" / "skills").glob("*/SKILL.md"))
    customizations += sorted((root / ".claude" / "agents").glob("*.md"))
    for path in customizations:
        text = path.read_text(encoding="utf-8")
        frontmatter = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.DOTALL)
        if not frontmatter:
            errors.append(f"Missing frontmatter: {path.relative_to(root)}")
            continue
        fields = dict(re.findall(r"^([\w-]+):[ \t]*(.+)$", frontmatter[1], re.MULTILINE))
        if not fields.get("description", "").strip("'\" \t\r"):
            errors.append(f"Missing description: {path.relative_to(root)}")
        if path.name == "SKILL.md" and fields.get("name", "").strip("'\" \r") != path.parent.name:
            errors.append(f"Skill name does not match directory: {path.relative_to(root)}")
    docs = {root / item for item in required if item.endswith(".md")}
    docs.update(customizations)
    for path in sorted(docs):
        if not path.is_file():
            continue
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if re.match(r"^[\w+-]+:", target) or target.startswith("#"):
                continue
            destination = target.split("#", 1)[0]
            if not (path.parent / destination).exists():
                errors.append(f"Broken local link in {path.relative_to(root)}: {target}")
    settings = root / ".claude" / "settings.json"
    if settings.is_file():
        hooks = json.loads(settings.read_text(encoding="utf-8")).get("hooks", {})
        for event, script in (("PreToolUse", "guard_paths.py"), ("Stop", "goal_gate.py")):
            entries = hooks.get(event, [])
            commands = [hook.get("command", "") for entry in entries for hook in entry.get("hooks", [])]
            if not any(script in command for command in commands):
                errors.append(f"Claude hook not wired: {event} -> {script}")
    inventory(root)
    return errors


def run_check(root: Path, goal_id: str) -> Check:
    if goal_id not in {goal["id"] for goal in inventory(root)}:
        raise ValueError(f"Unknown goal: {goal_id}")
    command = ["make", f"check-{goal_id}"]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    return {"goal": goal_id, "command": command, "exit_code": result.returncode,
            "status": "CHECK_PASS" if result.returncode == 0 else "CHECK_FAIL",
            "stdout": result.stdout, "stderr": result.stderr,
            "verifier": "NOT_RUN"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    for name in ("validate", "inventory", "check"):
        command = subparsers.add_parser(name)
        command.add_argument("--report", type=Path, help="Write a local JSON evidence report")
        if name == "check":
            command.add_argument("goal")
    args = parser.parse_args(argv)
    report: dict[str, object] = {
        "action": args.action, "timestamp": datetime.now(timezone.utc).isoformat(),
        "root": str(ROOT),
    }
    try:
        if args.action == "validate":
            errors = validate(ROOT)
            report["errors"] = errors
            code = int(bool(errors))
            print("\n".join(errors) if errors else "Harness wiring valid (not product acceptance)")
        elif args.action == "inventory":
            goals = inventory(ROOT)
            report["goals"] = goals
            code = int(any(goal["missing"] for goal in goals))
            for goal in goals:
                print(f"{goal['id']}: {goal['status']}")
                for missing in goal["missing"]:
                    print(f"  MISSING: {missing}")
        else:
            check = run_check(ROOT, args.goal)
            report.update(check)
            print(check["stdout"], end="")
            print(check["stderr"], end="", file=sys.stderr)
            code = check["exit_code"]
            print(f"\n{check['status']}; independent verifier NOT_RUN")
    except (OSError, ValueError) as error:
        report["error"] = str(error)
        print(f"Harness error: {error}", file=sys.stderr)
        code = 2
    report["exit_code"] = code
    if args.report:
        try:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        except OSError as error:
            print(f"Cannot write report: {error}", file=sys.stderr)
            return 2
    return code


if __name__ == "__main__":
    sys.exit(main())
