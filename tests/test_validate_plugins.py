import json
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, run

TOOL = ROOT / "tools" / "validate_plugins.py"
NO_VERSION = {"path": "version", "message": "No version specified. Consider adding a version following semver (e.g., \"1.0.0\")"}


def report(errors=(), warnings=(), contents=()):
    return {"success": not errors, "manifest": {"file": "plugin.json", "errors": list(errors), "warnings": list(warnings)},
            "contents": list(contents)}


class ValidatePluginsTests(unittest.TestCase):
    def judge(self, *reports):
        with tempfile.TemporaryDirectory() as tmp:
            args = []
            for i, r in enumerate(reports):
                p = Path(tmp) / f"r{i}.json"
                p.write_text(json.dumps(r), encoding="utf-8")
                args += ["--report", str(p)]
            return run([sys.executable, str(TOOL), *args])

    def test_missing_version_is_the_only_allowed_warning(self):
        self.assertEqual(self.judge(report(warnings=[NO_VERSION])).returncode, 0)
        res = self.judge(report(warnings=[NO_VERSION, {"path": "keywords", "message": "Unrecognized field"}]))
        self.assertEqual(res.returncode, 1)
        self.assertIn("Unrecognized field", res.stdout)
        self.assertNotIn("No version specified", res.stdout)

    def test_errors_fail_including_skill_level_ones(self):
        self.assertEqual(self.judge(report(errors=[{"path": "name", "message": "Required"}])).returncode, 1)
        skill = {"file": "skills/x/SKILL.md", "errors": [], "warnings": [{"path": "description", "message": "Too long"}]}
        res = self.judge(report(), report(contents=[skill]))
        self.assertEqual(res.returncode, 1)
        self.assertIn("Too long", res.stdout)

    def test_unreadable_report_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("not json", encoding="utf-8")
            self.assertEqual(run([sys.executable, str(TOOL), "--report", str(bad)]).returncode, 2)


if __name__ == "__main__":
    unittest.main()
