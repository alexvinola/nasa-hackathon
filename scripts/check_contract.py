"""G0 (shared part): the schema is valid, the examples pass and the invalid ones are rejected.

uv run --with jsonschema python scripts/check_contract.py
"""

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "shared"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    schema = load(SHARED / "telemetry.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    failures = []

    valid = sorted((SHARED / "examples").glob("*.json"))
    valid += sorted((SHARED / "scenarios").glob("*.json"))
    for path in valid:
        doc = load(path)
        doc = doc["input"] if path.parent.name == "scenarios" else doc
        for error in validator.iter_errors(doc):
            failures.append(f"{path.relative_to(ROOT)} should be valid: {error.json_path}: {error.message}")

    for path in sorted((SHARED / "examples" / "invalid").glob("*.json")):
        if validator.is_valid(load(path)):
            failures.append(f"{path.relative_to(ROOT)} should be rejected but the schema accepts it")

    for line in failures:
        print(line)
    print(f"contract: {len(valid)} valid, {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
