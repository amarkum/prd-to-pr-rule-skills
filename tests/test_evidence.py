import json
import sys
import unittest
from pathlib import Path

from helpers import add_feature, git, make_repo, script, write

MANIFEST = f"""
schema_version: 1
repo:
  name: data-airflow
  stack: airflow
checks:
  - id: lint
    run: {sys.executable} -c "print('lint ok')"
  - id: unit
    run: mkdir -p reports && {sys.executable} runner.py reports/junit-unit.xml tests/test_status.py
    artifacts: ["reports/junit-unit.xml"]
tests:
  junit_glob: "reports/junit-*.xml"
  run_files: "{sys.executable} runner.py {{junit}} {{files}}"
  test_patterns: ["tests/**/test_*.py"]
evidence:
  require_fail_to_pass: true
"""

SPEC = """
---
jira: PAY-412
status: approved
---
# PAY-412
## 3. Acceptance criteria
- **AC-2** Given a FINISHED status, when normalized, then it is COMPLETED.
## 6. Repo impact and sequencing
| Order | Repo | Change | ACs |
|---|---|---|---|
| 1 | data-airflow | aliases | AC-2 |
| 2 | payroll-mfe | panel | AC-1 |
"""


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.root = make_repo()
        write(self.root, ".ai/repo.yaml", MANIFEST)
        write(self.root, "specs/PAY-412/spec.md", SPEC)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "manifest + spec")
        add_feature(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def run_evidence(self, *extra):
        res = script("evidence.py", "run", "--base", "main", *extra, cwd=self.root)
        manifest = self.root / ".ai" / "evidence" / "manifest.json"
        return res, (json.loads(manifest.read_text()) if manifest.exists() else None)

    def test_pass_records_sha_hashes_and_scoped_coverage(self):
        res, m = self.run_evidence()
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(m["verdict"], "pass")
        self.assertEqual(m["repo"]["head_sha"], git(self.root, "rev-parse", "HEAD"))
        self.assertEqual(m["jira"], "PAY-412")
        self.assertEqual(m["ac_coverage"]["scope"], "AC-2")          # only this repo's row of the spec
        self.assertEqual(m["fail_to_pass"]["verdict"], "pass")
        self.assertEqual(len(m["checks"][1]["artifacts"][0]["sha256"]), 64)
        self.assertIn("## Evidence: PASS", (self.root / ".ai/evidence/summary.md").read_text())
        self.assertEqual(script("evidence.py", "check", cwd=self.root).returncode, 0)

    def test_check_rejects_stale_and_dirty(self):
        self.run_evidence()
        write(self.root, "app/extra.py", "X = 1\n")
        dirty = script("evidence.py", "check", cwd=self.root)
        self.assertEqual(dirty.returncode, 1)
        self.assertIn("uncommitted", dirty.stdout)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "more")
        stale = script("evidence.py", "check", cwd=self.root)
        self.assertEqual(stale.returncode, 1)
        self.assertIn("re-run", stale.stdout)

    def test_failing_check_fails_verdict(self):
        text = (self.root / ".ai/repo.yaml").read_text().replace("print('lint ok')", "import sys; sys.exit(3)")
        write(self.root, ".ai/repo.yaml", text)
        git(self.root, "commit", "-qam", "break lint")
        res, m = self.run_evidence()
        self.assertEqual(res.returncode, 1)
        self.assertEqual(m["verdict"], "fail")
        self.assertIn("check 'lint' failed (exit 3)", m["reasons"])

    def test_unapproved_spec_fails(self):
        write(self.root, "specs/PAY-412/spec.md", SPEC.replace("status: approved", "status: draft"))
        git(self.root, "commit", "-qam", "unapprove")
        _, m = self.run_evidence()
        self.assertEqual(m["verdict"], "fail")

    def test_dirty_tree_is_incomplete(self):
        write(self.root, "app/wip.py", "X = 1\n")
        res, m = self.run_evidence()
        self.assertEqual(m["verdict"], "incomplete")
        self.assertEqual(res.returncode, 1)

    def test_detached_ci_checkout_uses_github_head_ref(self):
        git(self.root, "checkout", "-q", "--detach")
        res = script("evidence.py", "run", "--base", "main", cwd=self.root,
                     env={"GITHUB_HEAD_REF": "feat/PAY-412-status", "GITHUB_ACTIONS": "true",
                          "GITHUB_RUN_ID": "42", "GITHUB_REPOSITORY": "acme/data-airflow"})
        m = json.loads((self.root / ".ai/evidence/manifest.json").read_text())
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(m["jira"], "PAY-412")
        self.assertEqual(m["runner"]["kind"], "ci")
        self.assertTrue(m["runner"]["ci_run_url"].endswith("/acme/data-airflow/actions/runs/42"))

    def test_docs_only_branch_passes_check_without_evidence(self):
        git(self.root, "checkout", "-q", "main")
        git(self.root, "checkout", "-q", "-b", "docs/PAY-413-spec")
        write(self.root, "specs/PAY-413/spec.md", "---\njira: PAY-413\nstatus: draft\n---\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "spec only")
        self.assertEqual(script("evidence.py", "check", "--base", "main", "--docs-only-ok", cwd=self.root).returncode, 0)
        self.assertEqual(script("evidence.py", "check", cwd=self.root).returncode, 1)


if __name__ == "__main__":
    unittest.main()
