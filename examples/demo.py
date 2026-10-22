#!/usr/bin/env python3
"""End-to-end demo of the deterministic layer: no LLM, no network, about 10 seconds.

1. The PRD gate bounces an incomplete PRD and passes the fixed one.
2. AC coverage links JUnit results from three stacks to the spec's acceptance criteria.
3. In a throwaway git repo, a feature is built test-first, the PR gate refuses to open a PR without evidence,
   evidence.py proves fail-to-pass on a clean commit, and the gate then allows the PR.

Run: python3 examples/demo.py   (needs PyYAML for step 3: pip install pyyaml)
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from helpers import HOOKS, SCRIPTS, add_feature, git, make_repo, write  # noqa: E402


def banner(text):
    print(f"\n{'=' * 100}\n{text}\n{'=' * 100}")


def run(args, cwd=None, stdin=None, env=None):
    import os
    res = subprocess.run(args, cwd=cwd, input=stdin, capture_output=True, text=True, env={**os.environ, **(env or {})})
    return res.returncode, res.stdout + res.stderr


banner("1a. PRD gate: incomplete PRD (expect NEEDS CLARIFICATION, exit 1)")
code, out = run([sys.executable, str(SCRIPTS / "prd_lint.py"), str(ROOT / "examples/prds/PAY-412-incomplete.md")])
print(out[out.find("## Blocking"):out.find("## Advisory")].strip())
print(out[out.find("## Questions for the product owner"):].strip()[:1200], f"\n[exit {code}]")

banner("1b. PRD gate: the fixed PRD (expect READY, exit 0)")
code, out = run([sys.executable, str(SCRIPTS / "prd_lint.py"), str(ROOT / "examples/prds/PAY-412-complete.md")])
print(out.splitlines()[0], f"[exit {code}]")

banner("2. AC coverage: pytest (Airflow) + Vitest (MFE) + Playwright (shell) JUnit -> spec PAY-412")
code, out = run([sys.executable, str(SCRIPTS / "ac_coverage.py"), "--spec", str(ROOT / "examples/specs/PAY-412/spec.md"),
                 "--junit", str(ROOT / "examples/evidence/junit-*.xml")])
print(out, f"[exit {code}]")

banner("3. Evidence in a throwaway repo: test-first change -> PR gate -> evidence.py -> PR gate")
tmp, repo = make_repo()
try:
    write(repo, ".ai/repo.yaml", f"""
        schema_version: 1
        repo: {{name: data-airflow, stack: airflow}}
        checks:
          - id: unit
            run: mkdir -p reports && {sys.executable} runner.py reports/junit-unit.xml tests/test_status.py
        tests:
          junit_glob: "reports/junit-*.xml"
          run_files: "{sys.executable} runner.py {{junit}} {{files}}"
          test_patterns: ["tests/**/test_*.py"]
        """)
    write(repo, "specs/PAY-412/spec.md", """
        ---
        jira: PAY-412
        status: approved
        approved_by: "@tech-lead"
        ---
        # PAY-412
        ## 3. Acceptance criteria
        - **AC-2** Given a FINISHED status, when normalized, then it is COMPLETED.
        ## 6. Repo impact and sequencing
        | Order | Repo | Change | ACs |
        |---|---|---|---|
        | 1 | data-airflow | status aliases | AC-2 |
        """)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "manifest and approved spec")
    add_feature(repo)   # feat/PAY-412-status: new AC test + implementation, committed

    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "gh pr create --draft --title PAY-412"}})
    _, out = run([sys.executable, str(HOOKS), "shell-guard"], cwd=repo, stdin=payload, env={"CLAUDE_PROJECT_DIR": str(repo)})
    print("PR gate before evidence ->", json.loads(out)["hookSpecificOutput"]["permissionDecision"].upper())

    code, out = run([sys.executable, str(SCRIPTS / "evidence.py"), "run", "--base", "main"], cwd=repo)
    print(out[out.find("## Evidence"):].strip(), f"\n[exit {code}]")

    _, out = run([sys.executable, str(HOOKS), "shell-guard"], cwd=repo, stdin=payload, env={"CLAUDE_PROJECT_DIR": str(repo)})
    print("\nPR gate after evidence ->", "ALLOW" if not out.strip() else out)
finally:
    tmp.cleanup()
