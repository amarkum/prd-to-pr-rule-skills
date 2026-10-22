import json
import sys
import unittest
from pathlib import Path

from helpers import add_feature, git, make_repo, script, write

JUNIT_CMD = f"{sys.executable} runner.py {{junit}} {{files}}"
FILE_CMD = f"{sys.executable} -m unittest {{files}}"


def f2p(root: Path, *extra: str, cmd: str = JUNIT_CMD) -> dict:
    out = root.parent / f"{root.name}-f2p.json"
    res = script("fail_to_pass.py", "--base", "main", "--cmd", cmd, "--patterns", "tests/**/test_*.py",
                 "--json", str(out), "--quiet", *extra, cwd=root)
    r = json.loads(out.read_text()) if out.exists() else {"stderr": res.stderr}
    r["_exit"] = res.returncode
    return r


class FailToPassTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.root = make_repo()

    def tearDown(self):
        self.tmp.cleanup()

    def classes(self, r):
        return {x["test"].split("::")[-1]: (x["class"], x["strength"]) for x in r["results"]}

    def test_new_test_fails_on_base_and_passes_on_head(self):
        add_feature(self.root)
        r = f2p(self.root)
        self.assertEqual(r["verdict"], "pass", r)
        c = self.classes(r)
        self.assertEqual(c["test_pay_412_ac_2_aliases_map_to_completed"], ("FAIL_TO_PASS", "strong"))
        self.assertEqual(c["test_upper"], ("PASS_TO_PASS", None))
        self.assertNotIn("f2p-", git(self.root, "worktree", "list"))  # temp worktree removed

    def test_file_mode_without_junit(self):
        add_feature(self.root)
        r = f2p(self.root, cmd=FILE_CMD)
        self.assertEqual(r["mode"], "file")
        self.assertEqual(r["verdict"], "pass", r)

    def test_tautological_test_is_rejected(self):
        add_feature(self.root, test_body='''
            import unittest
            from app.status import normalize_status

            class T(unittest.TestCase):
                def test_pay_412_ac_2_returns_a_string(self):
                    self.assertIsInstance(normalize_status("x"), str)
        ''')
        r = f2p(self.root)
        self.assertEqual(r["verdict"], "fail")
        self.assertEqual(r["_exit"], 1)
        self.assertTrue(any("nothing proves the change" in x for x in r["reasons"]))
        self.assertEqual(f2p(self.root, "--allow-p2p-only")["verdict"], "pass")

    def test_import_error_on_base_is_weak(self):
        add_feature(self.root, test_body='''
            import unittest
            from app.status import ALIASES

            class T(unittest.TestCase):
                def test_pay_412_ac_2_alias_table(self):
                    self.assertEqual(ALIASES["DONE"], "COMPLETED")
        ''')
        r = f2p(self.root)
        self.assertEqual(r["verdict"], "pass")
        self.assertEqual(self.classes(r)["test_pay_412_ac_2_alias_table"], ("FAIL_TO_PASS", "weak"))
        self.assertEqual(f2p(self.root, "--strict")["verdict"], "fail")

    def test_failing_on_head_fails(self):
        add_feature(self.root, impl=False)
        r = f2p(self.root)
        self.assertEqual(r["verdict"], "fail")
        self.assertIn("FAIL_ON_HEAD", r["counts"])

    def test_no_changed_tests_exit_3(self):
        git(self.root, "checkout", "-q", "-b", "feat/PAY-1-docs")
        write(self.root, "README.md", "docs only\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "docs")
        r = f2p(self.root)
        self.assertEqual(r["_exit"], 3)
        self.assertEqual(f2p(self.root, "--allow-none")["_exit"], 0)

    def test_unknown_base_is_usage_error(self):
        res = script("fail_to_pass.py", "--base", "origin/nope", "--cmd", JUNIT_CMD, "--patterns", "tests/*.py",
                     cwd=self.root)
        self.assertEqual(res.returncode, 2)


if __name__ == "__main__":
    unittest.main()
