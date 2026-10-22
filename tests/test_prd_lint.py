import json
import tempfile
import unittest
from pathlib import Path

from helpers import EXAMPLES, script, write


def lint(text: str) -> dict:
    with tempfile.TemporaryDirectory() as d:
        p = write(Path(d), "prd.md", text)
        res = script("prd_lint.py", str(p), "--json", str(Path(d) / "out.json"), "--quiet")
        report = json.loads((Path(d) / "out.json").read_text())
        report["_exit"] = res.returncode
        return report


BASE = """
# PRD: Thing
| Product owner | Sam |
## Summary
We build a thing for admins.
## Problem
Admins file 40 tickets a week.
## Goals
- Fewer tickets
## Non-goals
- Mobile app
## Users and roles
- Admin; Viewer must not have access
## Functional requirements
- FR-1: Show the thing.
## Acceptance criteria
- AC-1 (FR-1): Given an admin, when they open the page, then they see the thing; on error they see a retry button.
## Non-functional requirements
- p95 render under 2 s.
## Open questions
None.
"""


def codes(report, severity=None):
    return [i["code"] for i in report["issues"] if severity in (None, i["severity"])]


class PrdLintTests(unittest.TestCase):
    def test_incomplete_example_needs_clarification(self):
        r = lint((EXAMPLES / "prds" / "PAY-412-incomplete.md").read_text())
        self.assertEqual(r["status"], "NEEDS_CLARIFICATION")
        self.assertEqual(r["_exit"], 1)
        blocking = [i["message"] for i in r["issues"] if i["severity"] == "blocking"]
        self.assertTrue(any("Non-goals" in m for m in blocking))
        self.assertEqual(sum("Unresolved open question" in m for m in blocking), 2)
        self.assertIn("PRD-050", codes(r, "advisory"))   # no error/empty states
        self.assertIn("PRD-040", codes(r, "advisory"))   # "load fast" unquantified

    def test_complete_example_is_ready(self):
        r = lint((EXAMPLES / "prds" / "PAY-412-complete.md").read_text())
        self.assertEqual(r["status"], "READY")
        self.assertEqual(r["_exit"], 0)
        self.assertEqual(r["acceptance"]["criteria"], r["acceptance"]["structured"])

    def test_minimal_valid_prd_is_ready(self):
        r = lint(BASE)
        self.assertEqual(r["status"], "READY", r["issues"])
        self.assertEqual(r["owner"], "Sam")

    def test_placeholder_in_required_section_blocks(self):
        r = lint(BASE.replace("- Mobile app", "TBD"))
        self.assertIn("PRD-010", codes(r, "blocking"))

    def test_unfilled_template_never_passes(self):
        r = lint((Path(__file__).resolve().parent.parent / "standards" / "prd-template.md").read_text())
        self.assertEqual(r["status"], "NEEDS_CLARIFICATION")
        self.assertIn("PRD-010", codes(r, "blocking"))
        r2 = lint(BASE.replace("- p95 render under 2 s.", "- p95 render < 2 s; see <https://perf.example.com>."))
        self.assertNotIn("PRD-010", codes(r2))

    def test_untestable_acceptance_criteria_block(self):
        r = lint(BASE.replace("- AC-1 (FR-1): Given an admin, when they open the page, then they see the thing; "
                              "on error they see a retry button.",
                              "- The page works well and shows errors nicely.\n- Admins are happy with it."))
        self.assertIn("PRD-021", codes(r, "blocking"))

    def test_vague_term_flagged_even_with_requirement_id_on_line(self):
        r = lint(BASE.replace("- FR-1: Show the thing.", "- FR-1: Show the thing in real-time."))
        self.assertTrue(any(i["code"] == "PRD-030" and "real-time" in i["message"] for i in r["issues"]))

    def test_quantified_line_not_flagged(self):
        r = lint(BASE.replace("- FR-1: Show the thing.", "- FR-1: Show the thing fast (p95 < 2 s)."))
        self.assertNotIn("PRD-030", codes(r))

    def test_open_question_non_blocking_tag_is_advisory(self):
        r = lint(BASE.replace("None.", "- Do we need CSV export? [non-blocking]"))
        self.assertEqual(r["status"], "READY")
        self.assertIn("PRD-061", codes(r, "advisory"))

    def test_open_questions_listed_as_none(self):
        r = lint(BASE.replace("None.", "- None."))
        self.assertEqual(r["status"], "READY", r["issues"])
        self.assertEqual(r["sections"]["open_questions"]["state"], "none")

    def test_resolved_open_question_is_ignored(self):
        r = lint(BASE.replace("None.", "- Do we need CSV export? Resolved: no."))
        self.assertNotIn("PRD-060", codes(r))
        self.assertNotIn("PRD-061", codes(r))

    def test_confluence_bold_headings_are_sections(self):
        text = BASE.replace("## Non-goals", "**Out of scope**").replace("## Goals", "**Goals**")
        r = lint(text)
        self.assertEqual(r["sections"]["non_goals"]["state"], "present")
        self.assertEqual(r["sections"]["goals"]["state"], "present")

    def test_fr_without_acceptance_criterion(self):
        r = lint(BASE.replace("- FR-1: Show the thing.", "- FR-1: Show the thing.\n- FR-2: Export it."))
        self.assertTrue(any(i["code"] == "PRD-023" and "FR-2" in i["message"] for i in r["issues"]))

    def test_confluence_front_matter_is_metadata_not_content(self):
        fm = '---\nsource: confluence\npage_id: "123"\nversion: 9\npage_owner: "acc-77"\n---\n'
        r = lint(fm + BASE)
        self.assertEqual(r["meta"]["page_id"], "123")
        self.assertEqual(r["owner"], "Sam")             # the PRD's named owner wins
        r2 = lint(fm + BASE.replace("| Product owner | Sam |", ""))
        self.assertEqual(r2["owner"], "page owner acc-77")

    def test_missing_file_is_usage_error(self):
        self.assertEqual(script("prd_lint.py", "/nonexistent/prd.md").returncode, 2)


if __name__ == "__main__":
    unittest.main()
