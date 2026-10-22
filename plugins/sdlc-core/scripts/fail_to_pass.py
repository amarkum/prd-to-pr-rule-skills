#!/usr/bin/env python3
"""fail_to_pass.py - prove that new tests actually test the change (SWE-bench style).

Every test file added or modified on this branch is run twice: against the
merge-base (with the new test files copied in) and against the working tree.
  FAIL_TO_PASS  fails on base, passes on head -> the test demonstrates the change
                (weak: it only errored on base, e.g. an import of a new module)
  PASS_TO_PASS  passes on both               -> regression guard; does not prove the change
  FAIL_ON_HEAD  fails on head                -> broken test or broken change
With a `{junit}` placeholder in the command, results are per test case;
otherwise each file is run on its own and classified per file.

Usage:
  fail_to_pass.py --base origin/main --cmd "pytest {files} -q --junitxml={junit}"
                  [--patterns 'tests/**/test_*.py' ...] [--support 'tests/**/conftest.py' ...]
                  [--link node_modules] [--files a b ...] [--timeout 900]
                  [--strict] [--allow-none] [--allow-p2p-only] [--json OUT] [--md OUT]
  fail_to_pass.py --manifest .ai/repo.yaml --base origin/main     # reads the `tests:` block

Exit codes: 0 pass, 1 fail, 2 usage/input error, 3 no new or changed tests (0 with --allow-none).
Needs full git history for the merge-base (CI: fetch-depth: 0). Standard library only,
plus PyYAML when --manifest is used.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

VERSION = "1.0.0"
DEFAULT_SUPPORT = ["**/conftest.py", "**/fixtures/**", "**/__fixtures__/**", "**/testdata/**"]


def glob_to_regex(pattern: str) -> re.Pattern:
    """Glob with `**`, `*`, `?` and `{a,b}` -> anchored regex over POSIX paths."""
    i, out = 0, ""
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif c == "*":
            out += "[^/]*"
            i += 1
        elif c == "?":
            out += "[^/]"
            i += 1
        elif c == "{":
            end = pattern.find("}", i)
            if end == -1:
                out += re.escape(c)
                i += 1
            else:
                out += "(?:" + "|".join(re.escape(p) for p in pattern[i + 1:end].split(",")) + ")"
                i = end + 1
        else:
            out += re.escape(c)
            i += 1
    return re.compile("^" + out + "$")


def matches(path: str, patterns: list[str]) -> bool:
    return any(glob_to_regex(p).match(path) for p in patterns)


def git(*args: str, cwd: str | Path | None = None, check: bool = True) -> str:
    res = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {res.stderr.strip()}")
    return res.stdout.strip()


def load_manifest_tests(path: str) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError:
        raise RuntimeError("--manifest needs PyYAML (pip install pyyaml); or pass --cmd/--patterns")
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return data.get("tests") or {}


def run_cmd(template: str, files: list[str], cwd: Path, junit: Path | None, timeout: int) -> dict:
    cmd = template.replace("{files}", " ".join(shlex.quote(f) for f in files))
    if junit is not None:
        cmd = cmd.replace("{junit}", shlex.quote(str(junit)))
    start = time.time()
    try:
        res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        code, output = res.returncode, (res.stdout + res.stderr)
    except subprocess.TimeoutExpired as exc:
        code, output = 124, f"timeout after {timeout}s\n{exc.stdout or ''}"
    return {"cmd": cmd, "exit": code, "seconds": round(time.time() - start, 2),
            "tail": "\n".join(str(output).splitlines()[-40:])}


def junit_results(path: Path) -> dict[str, str] | None:
    if not path.is_file():
        return None
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return None
    out = {}
    for tc in root.iter("testcase"):
        tid = f"{tc.get('classname', '')}::{tc.get('name', '')}"
        if tc.find("failure") is not None:
            out[tid] = "failed"
        elif tc.find("error") is not None:
            out[tid] = "error"
        elif tc.find("skipped") is not None:
            out[tid] = "skipped"
        else:
            out[tid] = "passed"
    return out


def classify(base: str | None, head: str) -> tuple[str, str | None]:
    if head in ("failed", "error"):
        return "FAIL_ON_HEAD", None
    if head == "skipped":
        return "SKIPPED", None
    if base == "passed":
        return "PASS_TO_PASS", None
    if base == "failed":
        return "FAIL_TO_PASS", "strong"
    return "FAIL_TO_PASS", "weak"  # error / absent on base: did not run, e.g. import of new code


def changed_files(root: Path, merge_base: str) -> list[str]:
    tracked = git("diff", "--name-only", "--diff-filter=AMR", merge_base, cwd=root).splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard", cwd=root).splitlines()
    return sorted({f for f in tracked + untracked if f and (root / f).is_file()})


def evaluate(args) -> tuple[dict, int]:
    root = Path(git("rev-parse", "--show-toplevel"))
    try:
        merge_base = git("merge-base", args.base, "HEAD", cwd=root)
    except RuntimeError as exc:
        raise RuntimeError(f"{exc} (fetch the base branch, e.g. `git fetch origin main`, with full history)")
    head_sha = git("rev-parse", "HEAD", cwd=root)
    dirty = bool(git("status", "--porcelain", cwd=root))
    changed = changed_files(root, merge_base)
    tests = args.files or [f for f in changed if matches(f, args.patterns)]
    support = [f for f in changed if matches(f, args.support) and f not in tests]
    report = {"tool": "fail_to_pass", "version": VERSION, "base_ref": args.base, "merge_base": merge_base,
              "head_sha": head_sha, "dirty": dirty, "cmd": args.cmd, "test_files": tests,
              "support_files": support, "mode": "testcase" if "{junit}" in args.cmd else "file",
              "results": [], "verdict": None, "reasons": []}
    if not tests:
        report["verdict"] = "no_tests"
        report["reasons"].append("no added or modified test files matched the test patterns")
        return report, (0 if args.allow_none else 3)

    tmp = Path(tempfile.mkdtemp(prefix="f2p-"))
    base_dir = tmp / "base"
    git("worktree", "add", "--detach", "--quiet", str(base_dir), merge_base, cwd=root)
    try:
        for rel in tests + support:
            dest = base_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / rel, dest)
        for rel in args.link:
            if (root / rel).exists() and not (base_dir / rel).exists():
                (base_dir / rel).parent.mkdir(parents=True, exist_ok=True)
                os.symlink(root / rel, base_dir / rel)
        if report["mode"] == "testcase":
            base_run = run_cmd(args.cmd, tests, base_dir, tmp / "base.xml", args.timeout)
            head_run = run_cmd(args.cmd, tests, root, tmp / "head.xml", args.timeout)
            base_res, head_res = junit_results(tmp / "base.xml") or {}, junit_results(tmp / "head.xml")
            report["runs"] = {"base": base_run, "head": head_run}
            if head_res is None:
                report["reasons"].append("head run produced no JUnit file; check the command's {junit} handling")
                head_res = {}
            for tid, head_status in sorted(head_res.items()):
                kind, strength = classify(base_res.get(tid), head_status)
                report["results"].append({"test": tid, "base": base_res.get(tid, "absent"), "head": head_status,
                                          "class": kind, "strength": strength})
        else:
            report["runs"] = {}
            for rel in tests:
                b = run_cmd(args.cmd, [rel], base_dir, None, args.timeout)
                h = run_cmd(args.cmd, [rel], root, None, args.timeout)
                kind, strength = classify("passed" if b["exit"] == 0 else "failed", "passed" if h["exit"] == 0 else "failed")
                report["runs"][rel] = {"base": b, "head": h}
                report["results"].append({"test": rel, "base": "passed" if b["exit"] == 0 else "failed",
                                          "head": "passed" if h["exit"] == 0 else "failed",
                                          "class": kind, "strength": strength})
    finally:
        git("worktree", "remove", "--force", str(base_dir), cwd=root, check=False)
        shutil.rmtree(tmp, ignore_errors=True)

    counts = {}
    for r in report["results"]:
        key = r["class"] + (f"_{r['strength']}" if r["strength"] else "")
        counts[key] = counts.get(key, 0) + 1
    report["counts"] = counts
    f2p = counts.get("FAIL_TO_PASS_strong", 0) + counts.get("FAIL_TO_PASS_weak", 0)
    if not report["results"]:
        report["reasons"].append("no test results were collected on head")
    if counts.get("FAIL_ON_HEAD"):
        report["reasons"].append(f"{counts['FAIL_ON_HEAD']} new/changed test(s) fail on head")
    if f2p == 0 and not args.allow_p2p_only:
        report["reasons"].append("no new/changed test fails on the base commit: nothing proves the change "
                                 "(use --allow-p2p-only for pure refactors)")
    if args.strict and counts.get("FAIL_TO_PASS_strong", 0) == 0:
        report["reasons"].append("--strict: no test fails on base with an assertion (only import/collection errors)")
    report["verdict"] = "fail" if report["reasons"] else "pass"
    return report, (0 if report["verdict"] == "pass" else 1)


def to_markdown(r: dict) -> str:
    out = [f"### Fail-to-pass: {r['verdict'].upper()}", "",
           f"Base `{r['merge_base'][:12]}` vs head `{r['head_sha'][:12]}`{' (dirty tree)' if r['dirty'] else ''}; "
           f"mode: {r['mode']}; {len(r['test_files'])} new/changed test file(s).", ""]
    if r["results"]:
        out += ["| Test | Base | Head | Class |", "|---|---|---|---|"]
        for x in r["results"][:60]:
            cls = x["class"] + (f" ({x['strength']})" if x["strength"] else "")
            out.append(f"| `{x['test'][:90]}` | {x['base']} | {x['head']} | {cls} |")
        if len(r["results"]) > 60:
            out.append(f"| ... {len(r['results']) - 60} more | | | |")
    for reason in r["reasons"]:
        out.append(f"\n- {reason}")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--manifest", help=".ai/repo.yaml; supplies cmd/patterns/support/link from `tests:`")
    ap.add_argument("--cmd", help="test command with {files} and optionally {junit}")
    ap.add_argument("--patterns", nargs="*", default=None)
    ap.add_argument("--support", nargs="*", default=None)
    ap.add_argument("--link", nargs="*", default=None, help="paths to symlink into the base worktree, e.g. node_modules")
    ap.add_argument("--files", nargs="*", help="explicit test files instead of git diff")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--strict", action="store_true", help="require at least one assertion-level FAIL_TO_PASS")
    ap.add_argument("--allow-none", action="store_true", help="exit 0 when there are no new tests")
    ap.add_argument("--allow-p2p-only", action="store_true", help="pure refactor: no FAIL_TO_PASS required")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--md", dest="md_out")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    try:
        cfg = load_manifest_tests(args.manifest) if args.manifest else {}
    except (RuntimeError, OSError) as exc:
        print(f"fail_to_pass: {exc}", file=sys.stderr)
        return 2
    args.cmd = args.cmd or cfg.get("run_files")
    args.patterns = args.patterns or cfg.get("test_patterns") or []
    args.support = args.support if args.support is not None else (cfg.get("support_patterns") or DEFAULT_SUPPORT)
    args.link = args.link if args.link is not None else (cfg.get("link_paths") or [])
    if not args.cmd or "{files}" not in args.cmd:
        print("fail_to_pass: a command with {files} is required (--cmd or tests.run_files)", file=sys.stderr)
        return 2
    if not args.patterns and not args.files:
        print("fail_to_pass: test patterns are required (--patterns or tests.test_patterns)", file=sys.stderr)
        return 2
    try:
        report, code = evaluate(args)
    except RuntimeError as exc:
        print(f"fail_to_pass: {exc}", file=sys.stderr)
        return 2
    md = to_markdown(report)
    for dest, content in ((args.json_out, json.dumps(report, indent=2) + "\n"), (args.md_out, md)):
        if dest:
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_text(content, encoding="utf-8")
    if not args.quiet:
        print(md)
    return code


if __name__ == "__main__":
    sys.exit(main())
