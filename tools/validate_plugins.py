#!/usr/bin/env python3
"""validate_plugins.py - strict validation of the marketplace and every plugin, with one deliberate exception.

Runs `claude plugin validate --json` on the marketplace and on each plugin. Any error or warning fails, except the
"No version specified" warning. The standard leaves `version` out of plugin.json on purpose, so that installs track
the commit and every merge to main reaches every machine without a version bump (see CONTRIBUTING.md).

  validate_plugins.py                  validate . and plugins/*/ with the claude CLI
  validate_plugins.py --report r.json  judge saved `claude plugin validate --json` reports instead (offline, tests)

Exit codes: 0 clean, 1 errors or warnings, 2 the claude CLI is missing or a report can't be read.
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED = re.compile(r"^No version specified\b")   # omitted on purpose: installs track the commit


def problems(report: dict) -> list[str]:
    """Errors and warnings in one report, minus the allowed warning."""
    found = []
    sections = [report.get("manifest") or {}] + [c for c in report.get("contents") or [] if isinstance(c, dict)]
    for section in sections:
        for e in section.get("errors") or []:
            found.append(f"error   {e.get('path') or section.get('file', '')}: {e.get('message')}")
        for w in section.get("warnings") or []:
            if not ALLOWED.match(str(w.get("message", ""))):
                found.append(f"warning {w.get('path') or section.get('file', '')}: {w.get('message')}")
    if report.get("success") is False and not found:
        found.append("error   validation failed without details")
    return found


def run_claude(target: Path) -> dict:
    res = subprocess.run(["claude", "plugin", "validate", "--json", str(target)], capture_output=True, text=True)
    return json.loads(res.stdout)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--report", action="append", help="a saved JSON report (repeatable); skips the claude CLI")
    a = ap.parse_args(argv)
    try:
        if a.report:
            reports = {r: json.loads(Path(r).read_text(encoding="utf-8")) for r in a.report}
        else:
            if not shutil.which("claude"):
                print("validate_plugins: the claude CLI is not on PATH", file=sys.stderr)
                return 2
            targets = [ROOT] + sorted(p for p in (ROOT / "plugins").iterdir() if p.is_dir())
            reports = {str(t.relative_to(ROOT) or "."): run_claude(t) for t in targets}
    except (OSError, ValueError) as exc:
        print(f"validate_plugins: can't read a report: {exc}", file=sys.stderr)
        return 2
    failed = 0
    for name, report in reports.items():
        found = problems(report)
        failed += bool(found)
        print(f"{'FAIL' if found else 'ok  '}  {name}")
        for line in found:
            print(f"      {line}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
