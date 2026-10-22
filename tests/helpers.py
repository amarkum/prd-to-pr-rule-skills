"""Shared helpers: script paths, subprocess wrappers and throwaway git repos."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "plugins" / "sdlc-core" / "scripts"
HOOKS = ROOT / "plugins" / "sdlc-core" / "hooks" / "aisdlc_hooks.py"
EXAMPLES = ROOT / "examples"

# A dependency-free test runner that writes JUnit XML, so fail-to-pass and evidence
# can be exercised in per-test-case mode without pytest. Usage: runner.py JUNIT FILE...
RUNNER = textwrap.dedent('''
    import sys, unittest, xml.etree.ElementTree as ET
    junit, files = sys.argv[1], sys.argv[2:]
    suite_el = ET.Element("testsuite", name="runner")
    failed = False

    def walk(s):
        for t in s:
            yield from (walk(t) if isinstance(t, unittest.TestSuite) else [t])

    for f in files:
        mod = f[:-3].replace("/", ".")
        try:
            tests = list(walk(unittest.defaultTestLoader.loadTestsFromName(mod)))
        except Exception as exc:
            tc = ET.SubElement(suite_el, "testcase", classname=mod, name="collection")
            ET.SubElement(tc, "error", message=str(exc))
            failed = True
            continue
        for t in tests:
            r = unittest.TestResult()
            t.run(r)
            if type(t).__name__ == "_FailedTest" or r.errors:
                status = "error"
            elif r.failures:
                status = "failure"
            elif r.skipped:
                status = "skipped"
            else:
                status = "passed"
            tc = ET.SubElement(suite_el, "testcase", classname=mod, name=t._testMethodName)
            if status != "passed":
                ET.SubElement(tc, status)
                failed = failed or status in ("failure", "error")
    root = ET.Element("testsuites")
    root.append(suite_el)
    ET.ElementTree(root).write(junit)
    sys.exit(1 if failed else 0)
''')


def run(cmd: list[str], cwd: Path | None = None, stdin: str | None = None, env: dict | None = None):
    full_env = {**os.environ, **(env or {})}
    return subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True, text=True, env=full_env)


def script(name: str, *args: str, cwd: Path | None = None, env: dict | None = None):
    return run([sys.executable, str(SCRIPTS / name), *args], cwd=cwd, env=env)


def hook(command: str, payload: dict, cwd: Path, env: dict | None = None):
    res = run([sys.executable, str(HOOKS), command], cwd=cwd, stdin=json.dumps(payload),
              env={"CLAUDE_PROJECT_DIR": str(cwd), **(env or {})})
    return json.loads(res.stdout) if res.stdout.strip() else None


def write(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")
    return p


def git(root: Path, *args: str) -> str:
    res = run(["git", *args], cwd=root)
    if res.returncode != 0:
        raise RuntimeError(res.stderr)
    return res.stdout.strip()


def make_repo() -> tuple[tempfile.TemporaryDirectory, Path]:
    """A git repo on `main` with a tiny package, a passing test and the JUnit runner."""
    tmp = tempfile.TemporaryDirectory(prefix="aisdlc-test-")
    root = Path(tmp.name)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "test")
    git(root, "config", "commit.gpgsign", "false")
    write(root, "app/__init__.py", "")
    write(root, "app/status.py", '''
        def normalize_status(raw):
            return raw.upper()
    ''')
    write(root, "tests/__init__.py", "")
    write(root, "tests/test_status.py", '''
        import unittest
        from app.status import normalize_status

        class T(unittest.TestCase):
            def test_upper(self):
                self.assertEqual(normalize_status("done"), "DONE")
    ''')
    write(root, "runner.py", RUNNER)
    write(root, ".gitignore", ".ai/evidence/\nreports/\n__pycache__/\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    return tmp, root


def add_feature(root: Path, test_body: str | None = None, impl: bool = True) -> None:
    """Branch feat/PAY-412-status with an alias feature and a new AC test."""
    git(root, "checkout", "-q", "-b", "feat/PAY-412-status")
    if impl:
        write(root, "app/status.py", '''
            ALIASES = {"FINISHED": "COMPLETED", "DONE": "COMPLETED"}

            def normalize_status(raw):
                s = raw.strip().upper()
                return ALIASES.get(s, s)
        ''')
    write(root, "tests/test_status.py", test_body or '''
        import unittest
        from app.status import normalize_status

        class T(unittest.TestCase):
            def test_upper(self):
                self.assertEqual(normalize_status("processing"), "PROCESSING")

            def test_pay_412_ac_2_aliases_map_to_completed(self):
                self.assertEqual(normalize_status(" finished "), "COMPLETED")
    ''')
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "PAY-412: normalize statuses")
