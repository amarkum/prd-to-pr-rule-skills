#!/usr/bin/env python3
"""evidence.py - run a repo's checks and record verifiable evidence for a PR.

Subcommands:
  run      run `checks` from .ai/repo.yaml, then AC coverage, fail-to-pass and the plan checks
           (plan accepted, every changed file listed in plan.md, locked tests untouched);
           write <out>/manifest.json, <out>/summary.md and <out>/logs/*
  check    exit 0 only if <out>/manifest.json is a PASS for the current HEAD on a
           clean tree (docs/spec-only branches pass with --docs-only-ok)
  summary  print <out>/summary.md (PR body section / sticky comment)
  lock     record committed test files in plan.md "## Locked tests" with their git blob ids,
           so `run` fails if they change afterwards (the proof of a bug fix can't be weakened)

Usage:
  evidence.py run --manifest .ai/repo.yaml [--spec specs/KEY/spec.md] [--acs AC-1,AC-2]
                  [--base origin/main] [--out .ai/evidence] [--only lint,unit] [--skip-f2p]
  evidence.py check [--out .ai/evidence] [--base origin/main --docs-only-ok]
  evidence.py summary [--out .ai/evidence]
  evidence.py lock tests/test_x.py [...] [--plan specs/KEY/plan.md]

Exit codes: 0 pass, 1 fail/incomplete, 2 usage or input error (lock: 2 also when a file is
uncommitted or already locked at a different blob; only a human edits an existing lock).
Requires PyYAML for `run` (pip install pyyaml). `check` and `summary` are stdlib only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import glob
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

SCHEMA = "ai-sdlc/evidence@1"
HERE = Path(__file__).resolve().parent
KEY_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9]+-\d+)(?![0-9])")
DOCS_ONLY = re.compile(r"^(?:specs/|docs/)|\.md$")
# Changed files that never need a line in plan.md "Files that change".
PLAN_IGNORE = ["specs/**", ".ai/**", "CHANGELOG.md", "**/package-lock.json", "**/pnpm-lock.yaml", "**/yarn.lock",
               "**/poetry.lock", "**/uv.lock", "**/Pipfile.lock"]
LOCK_LINE = re.compile(r"^\s*[-*]\s+`?([^`\s]+)`?\s+@\s+`?([0-9a-f]{7,40})`?", re.MULTILINE)
PATH_TOKEN = re.compile(r"(?<![\w`/.-])((?:[\w.@{},*-]+/)+[\w.@{},*-]*)")


def sh(*args: str, cwd=None, check=True) -> str:
    res = subprocess.run(list(args), cwd=cwd, capture_output=True, text=True)
    if check and res.returncode != 0:
        raise RuntimeError(f"{' '.join(args)}: {res.stderr.strip()}")
    return res.stdout.strip()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def dirty_paths(root: Path, out_rel: str) -> list[str]:
    lines = sh("git", "status", "--porcelain", "--untracked-files=all", cwd=root).splitlines()
    paths = [ln[3:].split(" -> ")[-1].strip('"') for ln in lines if ln.strip()]
    return [p for p in paths if not p.startswith(out_rel.rstrip("/") + "/")]


def git_info(root: Path, base: str | None, out_rel: str) -> dict:
    branch = sh("git", "rev-parse", "--abbrev-ref", "HEAD", cwd=root)
    if branch == "HEAD":  # detached checkout, e.g. a PR job in CI
        branch = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("CI_COMMIT_REF_NAME") or branch
    info = {"head_sha": sh("git", "rev-parse", "HEAD", cwd=root),
            "branch": branch,
            "remote": sh("git", "config", "--get", "remote.origin.url", cwd=root, check=False),
            "base_ref": base, "merge_base": None}
    if base:
        info["merge_base"] = sh("git", "merge-base", base, "HEAD", cwd=root, check=False) or None
    dirty = dirty_paths(root, out_rel)
    info["dirty"] = bool(dirty)
    info["dirty_paths"] = dirty[:50]
    return info


def runner_info() -> dict:
    ci = os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI") == "true"
    url = None
    if os.environ.get("GITHUB_RUN_ID"):
        url = (f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
               f"{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{os.environ['GITHUB_RUN_ID']}")
        if os.environ.get("GITHUB_RUN_ATTEMPT"):
            url += f"/attempts/{os.environ['GITHUB_RUN_ATTEMPT']}"
    return {"kind": "ci" if ci else "local", "ci_run_url": url, "host": socket.gethostname(),
            "platform": platform.platform(), "python": platform.python_version()}


def load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError:
        raise RuntimeError("evidence.py run needs PyYAML: pip install pyyaml")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def spec_meta(spec: Path) -> dict:
    meta = {}
    lines = spec.read_text(encoding="utf-8").splitlines()
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
            if m:
                meta[m.group(1).lower()] = m.group(2).strip().strip("'\"")
    return meta


def section(text: str, title: str) -> str | None:
    """Body of the first `## <title>` section (case-insensitive), up to the next `## ` heading."""
    m = re.search(rf"^##\s+{re.escape(title)}\s*$", text, re.IGNORECASE | re.MULTILINE)
    if not m:
        return None
    rest = text[m.end():]
    nxt = re.search(r"^##\s", rest, re.MULTILINE)
    return rest[:nxt.start()] if nxt else rest


def glob_to_regex(pattern: str) -> str:
    out, i = "", 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif c == "*":
            out, i = out + "[^/]*", i + 1
        elif c == "?":
            out, i = out + "[^/]", i + 1
        elif c == "{" and "}" in pattern[i:]:
            j = pattern.index("}", i)
            out, i = out + "(?:" + "|".join(re.escape(x) for x in pattern[i + 1:j].split(",")) + ")", j + 1
        else:
            out, i = out + re.escape(c), i + 1
    return out


def covered(path: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if any(ch in pat for ch in "*?{"):
            if re.fullmatch(glob_to_regex(pat), path):
                return True
        elif path == pat or path.startswith(pat.rstrip("/") + "/"):
            return True
    return False


def plan_patterns(body: str, repo_name: str) -> list[str]:
    """Paths and globs listed under "Files that change". `### <repo>` subsections scope entries to one repo."""
    pats: list[str] = []
    in_scope = True
    for line in body.splitlines():
        heading = re.match(r"^###\s+(.+?)\s*$", line)
        if heading:
            in_scope = not repo_name or bool(re.search(rf"(?<![\w-]){re.escape(repo_name)}(?![\w-])", heading.group(1)))
            continue
        if not in_scope:
            continue
        tokens = re.findall(r"`([^`\s]+)`", line) or PATH_TOKEN.findall(line)
        for tok in tokens:
            tok = tok.rstrip(",;:.")
            for prefix in (f"{repo_name}/", f"{repo_name}:"):
                if repo_name and tok.startswith(prefix):
                    tok = tok[len(prefix):]
            if "/" in tok or re.fullmatch(r"[\w.-]+\.\w+", tok) or any(ch in tok for ch in "*?{"):
                pats.append(tok)
    return pats


def locked_tests(plan_text: str) -> list[tuple[str, str]]:
    body = section(plan_text, "Locked tests")
    return LOCK_LINE.findall(body) if body else []


def plan_check(root: Path, plan: Path, repo_name: str, merge_base: str | None, ignore: list[str]) -> tuple[dict, list, list]:
    """(record, failures, gaps) for plan.md: accepted, lists every changed file, locked tests untouched."""
    text = plan.read_text(encoding="utf-8")
    meta = spec_meta(plan)
    rec = {"path": str(plan.relative_to(root)), "sha256": sha256_file(plan), "status": meta.get("status"),
           "unplanned": [], "locked_tests": []}
    failures, gaps = [], []
    if meta.get("status") != "accepted":
        failures.append(f"plan status is '{meta.get('status')}', not 'accepted'")
    pats = plan_patterns(section(text, "Files that change") or "", repo_name)
    changed = sh("git", "diff", "--name-only", merge_base, "HEAD", cwd=root, check=False).splitlines() if merge_base else []
    rec["unplanned"] = [f for f in changed if not covered(f, pats) and not covered(f, ignore)]
    if not pats:
        gaps.append("plan.md has no 'Files that change' list")
    elif rec["unplanned"]:
        shown = ", ".join(rec["unplanned"][:8]) + (" ..." if len(rec["unplanned"]) > 8 else "")
        gaps.append(f"plan.md does not list {len(rec['unplanned'])} changed file(s): {shown}; "
                    "update plan.md in the same commit when the work departs from the plan")
    for path, blob in locked_tests(text):
        fp = root / path
        current = sh("git", "hash-object", str(fp), cwd=root) if fp.is_file() else None
        ok = bool(current) and current.startswith(blob)
        rec["locked_tests"].append({"path": path, "locked_blob": blob, "current_blob": current, "unchanged": ok})
        if not ok:
            failures.append(f"locked test {path} " + ("is missing" if current is None else
                            f"changed since it was locked ({blob[:7]} -> {current[:7]}); fix the code, not the test"))
    return rec, failures, gaps


def repo_acs(spec: Path, repo_name: str) -> list[str]:
    """ACs assigned to this repo in the spec's repo-impact table (rows naming the repo)."""
    acs: list[str] = []
    for line in spec.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip().strip("`*") for c in line.strip().strip("|").split("|")]
        if repo_name in cells:
            for ac in re.findall(r"AC-\d+", line):
                if ac not in acs:
                    acs.append(ac)
    return acs


def run_check(check: dict, root: Path, logs: Path) -> dict:
    cid, cmd = str(check["id"]), str(check["run"])
    log = logs / f"{re.sub(r'[^A-Za-z0-9_.-]', '_', cid)}.log"
    start = time.time()
    try:
        res = subprocess.run(cmd, shell=True, cwd=root, capture_output=True, text=True,
                             timeout=int(check.get("timeout", 1800)))
        code, output = res.returncode, res.stdout + res.stderr
    except subprocess.TimeoutExpired as exc:
        code, output = 124, f"TIMEOUT after {check.get('timeout', 1800)}s\n{exc.stdout or ''}{exc.stderr or ''}"
    log.write_text(f"$ {cmd}\n{output}\n[exit {code}]\n", encoding="utf-8")
    artifacts = []
    for pattern in check.get("artifacts", []) or []:
        for p in sorted(glob.glob(str(root / pattern), recursive=True)):
            fp = Path(p)
            if fp.is_file():
                artifacts.append({"path": str(fp.relative_to(root)), "bytes": fp.stat().st_size,
                                  "sha256": sha256_file(fp)})
    return {"id": cid, "cmd": cmd, "required": bool(check.get("required", True)), "exit": code,
            "seconds": round(time.time() - start, 2), "log": str(log.relative_to(root)),
            "log_sha256": sha256_file(log), "artifacts": artifacts}


def run_script(name: str, args: list[str], root: Path) -> int:
    return subprocess.run([sys.executable, str(HERE / name), *args], cwd=root).returncode


def cmd_run(a) -> int:
    root = Path(sh("git", "rev-parse", "--show-toplevel"))
    manifest = load_yaml(root / a.manifest)
    repo = manifest.get("repo") or {}
    out = root / a.out
    out_rel = str(Path(a.out).as_posix())
    if out.exists():
        shutil.rmtree(out)
    (out / "logs").mkdir(parents=True)
    info = git_info(root, a.base, out_rel)
    key_match = KEY_RE.search(info["branch"])
    key = key_match.group(1).upper() if key_match else None
    spec = Path(a.spec) if a.spec else (root / "specs" / key / "spec.md" if key else None)
    if spec and not spec.is_absolute():
        spec = root / spec
    if spec and not spec.is_file():
        spec = None

    checks = manifest.get("checks") or []
    only = set(a.only.split(",")) if a.only else None
    results = []
    for check in checks:
        if only and str(check.get("id")) not in only:
            continue
        print(f"[evidence] {check.get('id')}: {check.get('run')}", file=sys.stderr)
        results.append(run_check(check, root, out / "logs"))

    # failures make the verdict FAIL; gaps make it INCOMPLETE. Either blocks the PR gate.
    failures = [f"check '{r['id']}' failed (exit {r['exit']})" for r in results if r["required"] and r["exit"] != 0]
    gaps: list[str] = []
    record = {"schema": SCHEMA, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
              "runner": runner_info(),
              "repo": {"name": repo.get("name"), "stack": repo.get("stack"), **info},
              "jira": key, "spec": None, "plan": None, "checks": results, "ac_coverage": None, "fail_to_pass": None}

    tests_cfg = manifest.get("tests") or {}
    evidence_cfg = manifest.get("evidence") or {}
    if spec:
        meta = spec_meta(spec)
        record["jira"] = meta.get("jira", key)
        record["spec"] = {"path": str(spec.relative_to(root)), "sha256": sha256_file(spec),
                          "status": meta.get("status")}
        if meta.get("status") != "approved":
            failures.append(f"spec status is '{meta.get('status')}', not 'approved'")
        acs = a.acs or ",".join(repo_acs(spec, repo.get("name", ""))) or None
        junit = tests_cfg.get("junit_glob")
        if junit:
            args = ["--spec", str(spec), "--junit", junit, "--json", str(out / "ac-coverage.json"),
                    "--md", str(out / "ac-coverage.md"), "--quiet"]
            if acs:
                args += ["--only", acs]
            code = run_script("ac_coverage.py", args, root)
            cov = json.loads((out / "ac-coverage.json").read_text()) if (out / "ac-coverage.json").exists() else {}
            record["ac_coverage"] = {"verdict": cov.get("verdict", "error"), "scope": acs or "all",
                                     "gaps": cov.get("gaps"), "file": f"{out_rel}/ac-coverage.json"}
            if code != 0:
                failures.append(f"AC coverage: not covered {cov.get('gaps')}" if cov else "AC coverage could not run")
        else:
            gaps.append("tests.junit_glob is not set in the manifest; AC coverage cannot be computed")
        plan = spec.parent / "plan.md"
        if plan.is_file():
            ignore = PLAN_IGNORE + list(evidence_cfg.get("plan_ignore") or [])
            record["plan"], f_, g_ = plan_check(root, plan, repo.get("name", ""), info.get("merge_base"), ignore)
            failures += f_
            gaps += g_
        elif evidence_cfg.get("require_plan", True):
            gaps.append(f"no plan.md next to the spec ({plan.relative_to(root)}): run the plan skill")
    else:
        gaps.append("no spec found (pass --spec or use a branch named after the Jira key)")

    if evidence_cfg.get("require_fail_to_pass", True) and not a.skip_f2p and a.base:
        args = ["--manifest", str(root / a.manifest), "--base", a.base, "--json", str(out / "fail-to-pass.json"),
                "--md", str(out / "fail-to-pass.md"), "--quiet"]
        if evidence_cfg.get("allow_p2p_only"):
            args.append("--allow-p2p-only")
        code = run_script("fail_to_pass.py", args, root)
        f2p = json.loads((out / "fail-to-pass.json").read_text()) if (out / "fail-to-pass.json").exists() else {}
        record["fail_to_pass"] = {"verdict": f2p.get("verdict", "error"), "counts": f2p.get("counts"),
                                  "file": f"{out_rel}/fail-to-pass.json"}
        if code == 3:
            failures.append("no new or changed tests: a behaviour change needs a test that fails without it")
        elif code != 0:
            failures += [f"fail-to-pass: {r}" for r in f2p.get("reasons", ["could not run"])]

    if info["dirty"]:
        gaps.append("working tree has uncommitted changes; commit, then re-run so evidence matches a SHA")
    if only:
        gaps.append(f"only a subset of checks ran ({a.only})")
    record["verdict"] = "fail" if failures else ("incomplete" if gaps else "pass")
    record["reasons"] = failures + gaps
    (out / "manifest.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    summary = render_summary(record, out)
    (out / "summary.md").write_text(summary, encoding="utf-8")
    print(summary)
    return 0 if record["verdict"] == "pass" else 1


def render_summary(r: dict, out: Path) -> str:
    v = {"pass": "PASS", "fail": "FAIL", "incomplete": "INCOMPLETE"}[r["verdict"]]
    repo = r["repo"]
    lines = [f"## Evidence: {v}", "",
             f"- Commit `{repo['head_sha'][:12]}` on `{repo['branch']}`"
             + (f" (base `{repo['merge_base'][:12]}`)" if repo.get("merge_base") else ""),
             f"- Runner: {r['runner']['kind']}" + (f" ([run]({r['runner']['ci_run_url']}))" if r['runner']['ci_run_url'] else ""),
             f"- Spec: `{r['spec']['path']}` (status: {r['spec']['status']}, sha256 `{r['spec']['sha256'][:12]}`)"
             if r.get("spec") else "- Spec: none",
             (f"- Plan: `{r['plan']['path']}` (status: {r['plan']['status']}; "
              f"{len(r['plan']['unplanned'])} unplanned file(s); "
              f"{sum(1 for t in r['plan']['locked_tests'] if t['unchanged'])}/{len(r['plan']['locked_tests'])} locked tests unchanged)")
             if r.get("plan") else "- Plan: none", "",
             "| Check | Result | Time | Log sha256 |", "|---|---|---|---|"]
    for c in r["checks"]:
        res = "pass" if c["exit"] == 0 else ("FAIL" if c["required"] else "fail (optional)")
        lines.append(f"| `{c['id']}` | {res} | {c['seconds']}s | `{c['log_sha256'][:12]}` |")
    for name in ("ac-coverage.md", "fail-to-pass.md"):
        if (out / name).exists():
            lines += ["", (out / name).read_text(encoding="utf-8").strip()]
    if r["reasons"]:
        lines += ["", "**Not passing because:**"] + [f"- {x}" for x in r["reasons"]]
    lines += ["", f"<sub>{SCHEMA} - generated {r['generated_at']} - reproduce: "
              f"`python3 evidence.py run --manifest .ai/repo.yaml --base {repo.get('base_ref') or 'origin/main'}`</sub>"]
    return "\n".join(lines) + "\n"


def cmd_check(a) -> int:
    root = Path(sh("git", "rev-parse", "--show-toplevel"))
    out_rel = str(Path(a.out).as_posix())
    head = sh("git", "rev-parse", "HEAD", cwd=root)
    if a.docs_only_ok and a.base:
        mb = sh("git", "merge-base", a.base, "HEAD", cwd=root, check=False)
        changed = sh("git", "diff", "--name-only", mb, "HEAD", cwd=root, check=False).splitlines() if mb else []
        if changed and all(DOCS_ONLY.search(f) for f in changed):
            print("evidence check: docs/spec-only change; no test evidence required")
            return 0
    path = root / a.out / "manifest.json"
    if not path.is_file():
        print(f"evidence check: no evidence at {out_rel}/manifest.json; run the verify skill "
              f"(evidence.py run) first")
        return 1
    rec = json.loads(path.read_text(encoding="utf-8"))
    problems = []
    if rec.get("verdict") != "pass":
        problems.append(f"verdict is {rec.get('verdict')}: {'; '.join(rec.get('reasons', []))}")
    if rec.get("repo", {}).get("head_sha") != head:
        problems.append(f"evidence is for {rec.get('repo', {}).get('head_sha', '?')[:12]}, HEAD is {head[:12]}; re-run")
    dirty = dirty_paths(root, out_rel)
    if dirty:
        problems.append(f"uncommitted changes: {', '.join(dirty[:5])}")
    if problems:
        print("evidence check: FAIL\n- " + "\n- ".join(problems))
        return 1
    print(f"evidence check: PASS for {head[:12]}")
    return 0


def cmd_lock(a) -> int:
    root = Path(sh("git", "rev-parse", "--show-toplevel"))
    if a.plan:
        plan = (root / a.plan) if not Path(a.plan).is_absolute() else Path(a.plan)
    else:
        key = KEY_RE.search(sh("git", "rev-parse", "--abbrev-ref", "HEAD", cwd=root))
        plan = root / "specs" / key.group(1).upper() / "plan.md" if key else Path("")
    if not plan.is_file():
        print(f"lock: plan.md not found ({plan}); pass --plan specs/<KEY>/plan.md", file=sys.stderr)
        return 2
    text = plan.read_text(encoding="utf-8")
    existing = dict(locked_tests(text))
    new_lines = []
    for f in a.files:
        rel = Path(os.path.relpath(Path(f).resolve(), root.resolve())).as_posix()
        if sh("git", "status", "--porcelain", "--", rel, cwd=root):
            print(f"lock: {rel} has uncommitted changes. Commit the failing test first, then lock it.", file=sys.stderr)
            return 2
        blob = sh("git", "rev-parse", f"HEAD:{rel}", cwd=root, check=False)
        if not blob:
            print(f"lock: {rel} is not committed", file=sys.stderr)
            return 2
        if rel in existing:
            if blob.startswith(existing[rel]):
                print(f"lock: {rel} already locked at {existing[rel]}")
                continue
            print(f"lock: {rel} is already locked at {existing[rel]} (now {blob[:12]}). Only a human changes an "
                  f"existing lock, by editing plan.md.", file=sys.stderr)
            return 2
        new_lines.append(f"- `{rel}` @ `{blob[:12]}`")
    if new_lines:
        m = re.search(r"^##\s+Locked tests\s*$", text, re.IGNORECASE | re.MULTILINE)
        if m:
            nxt = re.search(r"^##\s", text[m.end():], re.MULTILINE)
            end = m.end() + nxt.start() if nxt else len(text)
            body = text[m.end():end].rstrip("\n")
            body = re.sub(r"\n\s*None\.?\s*$", "", body)
            body = body if body.strip() else "\n"
            text = text[:m.end()] + body + "\n" + "\n".join(new_lines) + "\n" + ("\n" + text[end:] if nxt else "")
        else:
            text = text.rstrip("\n") + "\n\n## Locked tests\n\n" + "\n".join(new_lines) + "\n"
        plan.write_text(text, encoding="utf-8")
        print("\n".join(new_lines))
        print(f"lock: recorded in {plan.relative_to(root)}; commit plan.md")
    return 0


def cmd_summary(a) -> int:
    root = Path(sh("git", "rev-parse", "--show-toplevel"))
    path = root / a.out / "summary.md"
    if not path.is_file():
        print(f"no summary at {path}", file=sys.stderr)
        return 1
    print(path.read_text(encoding="utf-8"))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--manifest", default=".ai/repo.yaml")
    r.add_argument("--spec")
    r.add_argument("--acs", help="comma-separated ACs in scope; default: this repo's row in the spec")
    r.add_argument("--base", default="origin/main")
    r.add_argument("--out", default=".ai/evidence")
    r.add_argument("--only", help="comma-separated check ids (result is at best 'incomplete')")
    r.add_argument("--skip-f2p", action="store_true")
    c = sub.add_parser("check")
    c.add_argument("--out", default=".ai/evidence")
    c.add_argument("--base", default="origin/main")
    c.add_argument("--docs-only-ok", action="store_true")
    s = sub.add_parser("summary")
    s.add_argument("--out", default=".ai/evidence")
    lk = sub.add_parser("lock")
    lk.add_argument("files", nargs="+")
    lk.add_argument("--plan", help="default: specs/<KEY>/plan.md for the branch's Jira key")
    a = ap.parse_args(argv)
    try:
        return {"run": cmd_run, "check": cmd_check, "summary": cmd_summary, "lock": cmd_lock}[a.cmd](a)
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"evidence: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
