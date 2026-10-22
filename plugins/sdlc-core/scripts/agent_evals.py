#!/usr/bin/env python3
"""agent_evals.py - regression-test the agent's configuration (CLAUDE.md, skills, hooks) like code.

Each eval is a real task from recent work, stored as evals/<name>.json:

  {
    "prompt": "Fix the bug in PAY-499: ...",            required
    "allowed_tools": "Read,Edit,Bash(make test)",        passed to claude --allowedTools
    "setup": ["git apply evals/fixtures/pay-499.patch"], optional, run before the agent
    "checks": ["make test", "git diff --quiet -- tests/"], required; every command must exit 0
    "timeout": 900, "max_turns": 30, "model": null       optional
  }

`run` gives every eval a fresh git worktree at HEAD, runs `claude -p` there non-interactively, then runs
the checks in that worktree. A pass is all checks exiting 0. The suite fails below --threshold, so a
change to CLAUDE.md, a skill or a hook that makes the agent worse can't merge unnoticed.

Usage:
  agent_evals.py run [--dir evals] [--only a,b] [--threshold 0.8] [--json out.json] [--md out.md] [--keep]
  agent_evals.py list [--dir evals]

Exit codes: 0 pass rate >= threshold, 1 below threshold, 2 usage or input error.
Set AISDLC_CLAUDE_BIN to use another claude binary (tests use a stub). Standard library only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCHEMA = "ai-sdlc/agent-evals@1"


def sh(args, cwd=None, timeout=None, shell=False):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, shell=shell)


def load_evals(directory: Path, only: set | None) -> list[dict]:
    evals = []
    for path in sorted(directory.glob("*.json")):
        if only and path.stem not in only:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data.get("prompt"), str) or not data.get("checks"):
            raise ValueError(f"{path}: needs a string 'prompt' and a non-empty 'checks' list")
        data["name"] = path.stem
        evals.append(data)
    return evals


def run_one(ev: dict, root: Path, claude: str, keep: bool) -> dict:
    work = Path(tempfile.mkdtemp(prefix=f"agent-eval-{ev['name']}-"))
    shutil.rmtree(work)  # git worktree add wants a missing directory
    res = sh(["git", "worktree", "add", "--detach", str(work), "HEAD"], cwd=root)
    if res.returncode != 0:
        return {"name": ev["name"], "passed": False, "error": f"worktree: {res.stderr.strip()}"}
    started = time.time()
    rec = {"name": ev["name"], "passed": False, "checks": [], "agent": {}, "worktree": str(work) if keep else None}
    try:
        for cmd in ev.get("setup") or []:
            s = sh(cmd, cwd=work, shell=True, timeout=600)
            if s.returncode != 0:
                rec["error"] = f"setup failed: {cmd}: {s.stderr.strip()[:300]}"
                return rec
        args = [claude, "-p", ev["prompt"], "--output-format", "json"]
        if ev.get("allowed_tools"):
            args += ["--allowedTools", ev["allowed_tools"]]
        if ev.get("max_turns"):
            args += ["--max-turns", str(ev["max_turns"])]
        if ev.get("model"):
            args += ["--model", ev["model"]]
        try:
            agent = sh(args, cwd=work, timeout=int(ev.get("timeout", 900)))
            out = agent.stdout.strip()
            try:
                payload = json.loads(out.splitlines()[-1]) if out else {}
            except ValueError:
                payload = {}
            rec["agent"] = {"exit": agent.returncode, "cost_usd": payload.get("total_cost_usd"),
                            "turns": payload.get("num_turns"), "is_error": payload.get("is_error")}
        except subprocess.TimeoutExpired:
            rec["agent"] = {"exit": 124, "timeout": True}
        for cmd in ev["checks"]:
            c = sh(cmd, cwd=work, shell=True, timeout=1800)
            rec["checks"].append({"cmd": cmd, "exit": c.returncode, "tail": (c.stdout + c.stderr).strip()[-400:]})
        rec["passed"] = all(c["exit"] == 0 for c in rec["checks"])
        return rec
    finally:
        rec["seconds"] = round(time.time() - started, 1)
        if not keep:
            sh(["git", "worktree", "remove", "--force", str(work)], cwd=root)


def to_markdown(report: dict) -> str:
    lines = [f"## Agent evals: {report['passed']}/{report['total']} passed "
             f"({report['pass_rate']:.0%}, threshold {report['threshold']:.0%}) - "
             f"{'PASS' if report['verdict'] == 'pass' else 'FAIL'}", "",
             "| Eval | Result | Agent exit | Turns | Cost | Failed check |", "|---|---|---|---|---|---|"]
    for r in report["results"]:
        failed = next((c["cmd"] for c in r.get("checks", []) if c["exit"] != 0), r.get("error", ""))
        cost = r.get("agent", {}).get("cost_usd")
        lines.append(f"| `{r['name']}` | {'pass' if r['passed'] else 'FAIL'} | {r.get('agent', {}).get('exit', '-')} | "
                     f"{r.get('agent', {}).get('turns') or '-'} | {f'${cost:.2f}' if cost else '-'} | "
                     f"{('`' + failed + '`') if failed else ''} |")
    lines += ["", f"<sub>{SCHEMA} - commit {report['head_sha'][:12]} - {report['generated_at']}</sub>"]
    return "\n".join(lines) + "\n"


def cmd_run(a) -> int:
    root = Path(sh(["git", "rev-parse", "--show-toplevel"]).stdout.strip() or ".")
    directory = root / a.dir
    if not directory.is_dir():
        print(f"agent_evals: no eval directory at {directory}", file=sys.stderr)
        return 2
    evals = load_evals(directory, set(a.only.split(",")) if a.only else None)
    if not evals:
        print(f"agent_evals: no evals in {directory}", file=sys.stderr)
        return 2
    claude = os.environ.get("AISDLC_CLAUDE_BIN", "claude")
    results = []
    for ev in evals:
        print(f"[agent-evals] {ev['name']} ...", file=sys.stderr)
        results.append(run_one(ev, root, claude, a.keep))
    passed = sum(1 for r in results if r["passed"])
    rate = passed / len(results)
    report = {"schema": SCHEMA, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
              "head_sha": sh(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip(), "threshold": a.threshold,
              "total": len(results), "passed": passed, "pass_rate": round(rate, 4),
              "verdict": "pass" if rate >= a.threshold else "fail", "results": results}
    if a.json:
        Path(a.json).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md = to_markdown(report)
    if a.md:
        Path(a.md).write_text(md, encoding="utf-8")
    print(md)
    return 0 if report["verdict"] == "pass" else 1


def cmd_list(a) -> int:
    root = Path(sh(["git", "rev-parse", "--show-toplevel"]).stdout.strip() or ".")
    for ev in load_evals(root / a.dir, None):
        print(f"{ev['name']}: {ev['prompt'][:80]}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--dir", default="evals")
    r.add_argument("--only", help="comma-separated eval names")
    r.add_argument("--threshold", type=float, default=0.8)
    r.add_argument("--json")
    r.add_argument("--md")
    r.add_argument("--keep", action="store_true", help="keep the worktrees for inspection")
    ls = sub.add_parser("list")
    ls.add_argument("--dir", default="evals")
    a = ap.parse_args(argv)
    try:
        return {"run": cmd_run, "list": cmd_list}[a.cmd](a)
    except (ValueError, OSError) as exc:
        print(f"agent_evals: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
