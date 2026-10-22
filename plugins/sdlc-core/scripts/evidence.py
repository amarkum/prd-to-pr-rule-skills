#!/usr/bin/env python3
"""evidence.py - run a repo's checks and record verifiable evidence for a PR.

Subcommands:
  run      run `checks` from .ai/repo.yaml, then AC coverage and fail-to-pass;
           write <out>/manifest.json, <out>/summary.md and <out>/logs/*
  check    exit 0 only if <out>/manifest.json is a PASS for the current HEAD on a
           clean tree (docs/spec-only branches pass with --docs-only-ok)
  summary  print <out>/summary.md (PR body section / sticky comment)

Usage:
  evidence.py run --manifest .ai/repo.yaml [--spec specs/KEY/spec.md] [--acs AC-1,AC-2]
                  [--base origin/main] [--out .ai/evidence] [--only lint,unit] [--skip-f2p]
  evidence.py check [--out .ai/evidence] [--base origin/main --docs-only-ok]
  evidence.py summary [--out .ai/evidence]

Exit codes: 0 pass, 1 fail/incomplete, 2 usage or input error.
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
              "jira": key, "spec": None, "checks": results, "ac_coverage": None, "fail_to_pass": None}

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
             if r.get("spec") else "- Spec: none", "",
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
    a = ap.parse_args(argv)
    try:
        return {"run": cmd_run, "check": cmd_check, "summary": cmd_summary}[a.cmd](a)
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"evidence: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
