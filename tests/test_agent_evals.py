import json
import os
import stat
import sys
import unittest

from helpers import git, make_repo, script, write

# A stand-in for `claude -p`: "fixes" the bug only when the prompt asks for it, and reports like the real CLI.
FAKE_CLAUDE = f"""#!{sys.executable}
import json, pathlib, sys
prompt = sys.argv[sys.argv.index("-p") + 1]
if "fix" in prompt:
    pathlib.Path("app/fixed.txt").write_text("fixed")
print(json.dumps({{"type": "result", "is_error": False, "num_turns": 3, "total_cost_usd": 0.04}}))
"""


class AgentEvalTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.root = make_repo()
        write(self.root, "evals/fix-bug.json", json.dumps({
            "prompt": "Please fix the bug", "allowed_tools": "Read,Edit", "checks": ["test -f app/fixed.txt"]}))
        write(self.root, "evals/no-op.json", json.dumps({
            "prompt": "Describe the code", "checks": ["test -f app/fixed.txt"]}))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "evals")
        fake = self.root.parent / f"{self.root.name}-claude"
        fake.write_text(FAKE_CLAUDE)
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        self.env = {"AISDLC_CLAUDE_BIN": str(fake)}
        self.addCleanup(lambda: fake.unlink(missing_ok=True))

    def tearDown(self):
        self.tmp.cleanup()

    def run_evals(self, *args):
        res = script("agent_evals.py", "run", "--json", str(self.root / "report.json"), *args, cwd=self.root, env=self.env)
        report = json.loads((self.root / "report.json").read_text()) if (self.root / "report.json").exists() else None
        return res, report

    def test_pass_rate_against_threshold(self):
        res, report = self.run_evals("--threshold", "0.5")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual((report["passed"], report["total"]), (1, 2))
        by_name = {r["name"]: r for r in report["results"]}
        self.assertTrue(by_name["fix-bug"]["passed"])
        self.assertEqual(by_name["fix-bug"]["agent"]["cost_usd"], 0.04)
        self.assertFalse(by_name["no-op"]["passed"])
        self.assertIn("1/2 passed", res.stdout)
        strict, report = self.run_evals("--threshold", "1.0")
        self.assertEqual(strict.returncode, 1)
        self.assertEqual(report["verdict"], "fail")

    def test_each_eval_runs_in_a_throwaway_worktree(self):
        self.run_evals("--only", "fix-bug")
        self.assertFalse((self.root / "app/fixed.txt").exists())            # the main checkout is untouched
        self.assertEqual(len(git(self.root, "worktree", "list").splitlines()), 1)

    def test_invalid_eval_is_a_usage_error(self):
        write(self.root, "evals/broken.json", json.dumps({"prompt": "x"}))
        res = script("agent_evals.py", "run", cwd=self.root, env=self.env)
        self.assertEqual(res.returncode, 2)
        self.assertIn("checks", res.stderr)


if __name__ == "__main__":
    unittest.main()
