#!/bin/bash
set -euo pipefail
git init -q -b main
git config user.email eval@example.com
git config user.name eval
mkdir -p app specs/PAY-412 .ai
printf 'def status_label(s):\n    return s\n' > app/status.py
printf 'repo:\n  name: demo\n  stack: frontend\nchecks: []\n' > .ai/repo.yaml
printf -- '---\njira: PAY-412\nstatus: draft\n---\n# PAY-412\n## 3. Acceptance criteria\n- **AC-1** Given status "done", when labelled, then the label is "Completed".\n' > specs/PAY-412/spec.md
git add -A && git commit -qm base
git checkout -qb feat/PAY-412-status-label
