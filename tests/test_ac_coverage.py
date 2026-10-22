import json
import tempfile
import unittest
from pathlib import Path

from helpers import EXAMPLES, script, write

SPEC = EXAMPLES / "specs" / "PAY-412" / "spec.md"
EV = EXAMPLES / "evidence"


def cover(*args: str) -> dict:
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "cov.json"
        res = script("ac_coverage.py", *args, "--json", str(out), "--quiet")
        r = json.loads(out.read_text()) if out.exists() else {}
        r["_exit"] = res.returncode
        return r


def status(report: dict) -> dict:
    return {a["ac"]: a["status"] for a in report["acs"]}


def junit(cases: str) -> str:
    return f'<testsuites><testsuite name="s">{cases}</testsuite></testsuites>'


class AcCoverageTests(unittest.TestCase):
    def test_all_three_stacks_cover_every_ac(self):
        r = cover("--spec", str(SPEC), "--junit", str(EV / "junit-*.xml"))
        self.assertEqual(r["verdict"], "pass")
        self.assertEqual(set(status(r).values()), {"COVERED"})
        self.assertEqual(len(status(r)), 7)

    def test_missing_e2e_leaves_ac5_uncovered(self):
        r = cover("--spec", str(SPEC), "--junit", str(EV / "junit-data-airflow.xml"),
                  "--junit", str(EV / "junit-payroll-mfe.xml"))
        self.assertEqual(r["_exit"], 1)
        self.assertEqual(status(r)["AC-5"], "MISSING")
        self.assertEqual(r["gaps"], ["AC-5"])

    def test_scope_to_one_repo(self):
        r = cover("--spec", str(SPEC), "--junit", str(EV / "junit-payroll-mfe.xml"), "--only", "AC-1,AC-3,AC-4,AC-6,AC-7")
        self.assertEqual(r["verdict"], "pass")

    def test_failing_linked_test_fails_the_ac(self):
        with tempfile.TemporaryDirectory() as d:
            j = write(Path(d), "j.xml", junit(
                '<testcase name="PAY-412 AC-1: ok" classname="a"/>'
                '<testcase name="PAY-412 AC-1: edge" classname="a"><failure message="boom"/></testcase>'))
            r = cover("--spec", str(SPEC), "--junit", str(j), "--only", "AC-1")
        self.assertEqual(status(r)["AC-1"], "FAILING")
        self.assertEqual(r["_exit"], 1)

    def test_skipped_only_is_not_coverage(self):
        with tempfile.TemporaryDirectory() as d:
            j = write(Path(d), "j.xml", junit('<testcase name="PAY-412 AC-1" classname="a"><skipped/></testcase>'))
            r = cover("--spec", str(SPEC), "--junit", str(j), "--only", "AC-1")
        self.assertEqual(status(r)["AC-1"], "MISSING")

    def test_other_story_with_same_ac_number_does_not_count(self):
        with tempfile.TemporaryDirectory() as d:
            j = write(Path(d), "j.xml", junit('<testcase name="PAY-399 AC-1: older story" classname="a"/>'))
            r = cover("--spec", str(SPEC), "--junit", str(j), "--only", "AC-1")
        self.assertEqual(status(r)["AC-1"], "MISSING")

    def test_bare_ids_need_opt_in(self):
        with tempfile.TemporaryDirectory() as d:
            j = write(Path(d), "j.xml", junit('<testcase name="AC-1 renders" classname="a"/>'))
            strict = cover("--spec", str(SPEC), "--junit", str(j), "--only", "AC-1")
            loose = cover("--spec", str(SPEC), "--junit", str(j), "--only", "AC-1", "--allow-unqualified")
        self.assertEqual(status(strict)["AC-1"], "MISSING")
        self.assertEqual(status(loose)["AC-1"], "COVERED")
        self.assertEqual(loose["unqualified_links"], 1)

    def test_pytest_property_and_function_name_styles(self):
        with tempfile.TemporaryDirectory() as d:
            j = write(Path(d), "j.xml", junit(
                '<testcase name="test_pay_412_ac_2_upsert" classname="tests.x"/>'
                '<testcase name="test_x" classname="tests.x"><properties>'
                '<property name="ac" value="PAY-412/AC-6"/></properties></testcase>'))
            r = cover("--spec", str(SPEC), "--junit", str(j), "--only", "AC-2,AC-6")
        self.assertEqual(r["verdict"], "pass")

    def test_manual_verification_counts_unless_disabled(self):
        with tempfile.TemporaryDirectory() as d:
            spec = write(Path(d), "spec.md", SPEC.read_text().replace(
                "## 11. Manual verification\n\nNone.",
                "## 11. Manual verification\n\n- AC-4: checked in staging with an ops account by @qa on 2026-10-21"))
            j = write(Path(d), "j.xml", junit('<testcase name="unrelated" classname="a"/>'))
            r = cover("--spec", str(spec), "--junit", str(j), "--only", "AC-4")
            strict = cover("--spec", str(spec), "--junit", str(j), "--only", "AC-4", "--no-manual")
        self.assertEqual(status(r)["AC-4"], "MANUAL")
        self.assertEqual(r["verdict"], "pass")
        self.assertEqual(status(strict)["AC-4"], "MISSING")

    def test_orphan_reference_reported(self):
        with tempfile.TemporaryDirectory() as d:
            j = write(Path(d), "j.xml", junit('<testcase name="PAY-412 AC-9: typo" classname="a"/>'))
            r = cover("--spec", str(SPEC), "--junit", str(j))
        self.assertEqual([o["ac"] for o in r["orphans"]], ["AC-9"])

    def test_no_junit_files_fails(self):
        r = cover("--spec", str(SPEC), "--junit", "/nonexistent/*.xml")
        self.assertEqual(r["verdict"], "fail")


if __name__ == "__main__":
    unittest.main()
