#!/bin/bash
set -euo pipefail
git init -q -b main
git config user.email eval@example.com
git config user.name eval
mkdir -p app tests specs/PAY-499 .ai
touch app/__init__.py tests/__init__.py
printf 'def is_terminal(status):\n    return status in ("COMPLETED",)\n' > app/status.py
printf 'import unittest\nfrom app.status import is_terminal\n\n\nclass T(unittest.TestCase):\n    def test_pay_499_ac_1_failed_runs_are_terminal(self):\n        self.assertTrue(is_terminal("FAILED"))\n' > tests/test_status.py
printf 'repo:\n  name: demo\n  stack: airflow\nchecks:\n  - id: unit\n    run: python3 -m unittest -q\n' > .ai/repo.yaml
printf -- '---\njira: PAY-499\nstatus: approved\nrisk: low\napproved_by: "@tech-lead"\n---\n# PAY-499 Failed runs are terminal\n## 3. Acceptance criteria\n- **AC-1** Given a FAILED run, when checked, then it is terminal.\n' > specs/PAY-499/spec.md
git add -A && git commit -qm base
git checkout -qb fix/PAY-499-failed-terminal
BLOB=$(git hash-object tests/test_status.py)
printf -- '---\njira: PAY-499\nstatus: accepted\naccepted_by: "@dev (plan mode)"\n---\n# Plan: PAY-499\n## Files that change\n- `app/status.py`: treat FAILED as terminal\n## Order of work\n- [ ] **T-1** Make FAILED terminal (AC-1). The reproducing test is committed and locked.\n## Locked tests\n\n- `tests/test_status.py` @ `%s`\n' "${BLOB:0:12}" > specs/PAY-499/plan.md
git add -A && git commit -qm "PAY-499: plan with the locked reproducing test"
