import contextlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("harness", Path(__file__).parents[1] / "harness.py")
assert SPEC is not None and SPEC.loader is not None
harness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harness)


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "goals").mkdir()
        (self.root / "goals" / "G9-guides.md").write_text("# G9", encoding="utf-8")
        (self.root / "Makefile").write_text(
            "check-G9: assets\n\t@$(call need,guide.json test.ts)\n"
            "assets:\n\t@$(call need,rules.json)\n", encoding="utf-8")

    def test_transitive_missing_prerequisites(self):
        goal = harness.inventory(self.root)[0]
        self.assertEqual(goal["missing"], ["guide.json", "rules.json", "test.ts"])
        self.assertEqual(goal["status"], "MISSING")

    def test_presence_never_means_pass(self):
        for name in ("guide.json", "rules.json", "test.ts"):
            (self.root / name).touch()
        self.assertEqual(harness.inventory(self.root)[0]["status"], "PRESENT_NOT_VERIFIED")

    def test_missing_target_is_error(self):
        (self.root / "Makefile").write_text("other:\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "missing Makefile target"):
            harness.inventory(self.root)

    def test_empty_inventory_is_error(self):
        (self.root / "goals" / "G9-guides.md").unlink()
        with self.assertRaisesRegex(ValueError, "No goal specifications"):
            harness.inventory(self.root)

    def test_unknown_goal_cannot_execute(self):
        with patch.object(harness.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "Unknown goal"):
                harness.run_check(self.root, "G9; echo unsafe")
            run.assert_not_called()

    def test_check_preserves_exact_command_failure_and_output(self):
        result = subprocess.CompletedProcess(["make"], 2, "unit passed\n", "E2E blocked\n")
        with patch.object(harness.subprocess, "run", return_value=result) as run:
            report = harness.run_check(self.root, "G9")
        self.assertEqual(run.call_args.args[0], ["make", "check-G9"])
        self.assertEqual(run.call_args.kwargs["cwd"], self.root)
        self.assertEqual(report["exit_code"], 2)
        self.assertEqual(report["stderr"], "E2E blocked\n")
        self.assertEqual(report["status"], "CHECK_FAIL")
        self.assertEqual(report["verifier"], "NOT_RUN")

    def test_passing_check_still_needs_verifier(self):
        result = subprocess.CompletedProcess(["make"], 0, "passed\n", "")
        with patch.object(harness.subprocess, "run", return_value=result):
            report = harness.run_check(self.root, "G9")
        self.assertEqual(report["status"], "CHECK_PASS")
        self.assertEqual(report["verifier"], "NOT_RUN")

    def test_missing_files_exit_nonzero_and_report_persists(self):
        report = self.root / "state" / "report.json"
        with patch.object(harness, "ROOT", self.root), contextlib.redirect_stdout(io.StringIO()):
            code = harness.main(["inventory", "--report", str(report)])
        self.assertEqual(code, 1)
        saved = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(saved["exit_code"], 1)
        self.assertEqual(saved["goals"][0]["status"], "MISSING")

    def test_missing_make_is_explicit_error(self):
        report = self.root / "report.json"
        with patch.object(harness, "ROOT", self.root), \
                patch.object(harness.subprocess, "run", side_effect=FileNotFoundError("make missing")), \
                contextlib.redirect_stderr(io.StringIO()):
            code = harness.main(["check", "G9", "--report", str(report)])
        self.assertEqual(code, 2)
        self.assertIn("make missing", json.loads(report.read_text(encoding="utf-8"))["error"])

    def test_validation_detects_bad_skill_and_link(self):
        skill = self.root / ".github" / "skills" / "example" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("---\nname: wrong\n---\n", encoding="utf-8")
        (self.root / "AGENTS.md").write_text("[Missing](missing.md)", encoding="utf-8")
        errors = harness.validate(self.root)
        self.assertTrue(any("Missing description" in error for error in errors))
        self.assertTrue(any("does not match" in error for error in errors))
        self.assertTrue(any("Broken local link" in error for error in errors))

    def test_validation_detects_disconnected_hook(self):
        settings = self.root / ".claude" / "settings.json"
        settings.parent.mkdir()
        settings.write_text('{"hooks": {"Stop": [{"hooks": []}]}}', encoding="utf-8")
        errors = harness.validate(self.root)
        self.assertTrue(any("Stop -> goal_gate.py" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
