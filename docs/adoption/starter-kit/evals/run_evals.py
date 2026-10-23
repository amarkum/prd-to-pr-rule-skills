#!/usr/bin/env python3
"""Agent eval harness for the Agentic SDLC starter kit.

Runs each case in evals/cases/ against this repository's agent configuration (CLAUDE.md,
.claude/agents, .claude/skills, .claude/hooks, .claude/settings.json, policy packs) using headless
Claude Code (`claude -p`), then scores the workspace with deterministic graders. Agent
configuration is production code, so CI runs this whenever any of it changes.

  python3 evals/run_evals.py                      # every case, real runs (costs money)
  python3 evals/run_evals.py --case EVAL-0001 --runs 1
  python3 evals/run_evals.py --self-test          # no API calls: each case must pass with its
                                                  # reference solution and fail without it
  python3 evals/run_evals.py --dry-run            # print the claude commands, grade the untouched fixture

A case is a folder with case.yaml (or case.json), fixture/ (the starting repository) and
reference/ (files that a correct agent would produce). case.yaml needs PyYAML
(python3 -m pip install pyyaml). Results are written to evals/results/<timestamp>.json.
"""
import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(ROOT, "evals", "cases")
RESULTS = os.path.join(ROOT, "evals", "results")
CONFIG_PATHS = ["CLAUDE.md", ".claude/agents", ".claude/skills", ".claude/hooks", ".claude/settings.json",
                "docs/policies", "docs/changes/README.md", "docs/changes/_templates"]
GIT_USER = ["-c", "user.email=evals@example.invalid", "-c", "user.name=agent-evals"]


def load_case(folder):
    for name in ("case.yaml", "case.yml", "case.json"):
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            if name.endswith(".json"):
                return json.load(fh)
            try:
                import yaml
            except ImportError:
                sys.exit("run_evals: {} needs PyYAML (python3 -m pip install pyyaml), "
                         "or convert it to case.json".format(path))
            return yaml.safe_load(fh)
    return None


def git(ws, *args):
    return subprocess.run(["git"] + list(args), cwd=ws, capture_output=True, text=True)


IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")


def make_workspace(case_dir, config_root):
    """A throwaway git repo: the agent config under test, with the case fixture on top."""
    ws = tempfile.mkdtemp(prefix="agent-eval-")
    for rel in CONFIG_PATHS:
        src, dst = os.path.join(config_root, rel), os.path.join(ws, rel)
        if os.path.isdir(src):
            shutil.copytree(src, dst, ignore=IGNORE, dirs_exist_ok=True)
        elif os.path.isfile(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
    shutil.copytree(os.path.join(case_dir, "fixture"), ws, ignore=IGNORE, dirs_exist_ok=True)
    git(ws, "init", "-q", "-b", "eval")
    git(ws, "add", "-A")
    git(ws, *GIT_USER, "commit", "-q", "-m", "fixture")
    return ws


def snapshot(ws):
    hashes = {}
    for rel in git(ws, "ls-files").stdout.splitlines():
        hashes[rel] = file_hash(os.path.join(ws, rel))
    return hashes


def file_hash(path):
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def changed_paths(ws):
    paths = []
    for line in git(ws, "status", "--porcelain=v1", "--untracked-files=all").stdout.splitlines():
        path = line[3:]
        paths.append(path.split(" -> ", 1)[-1])
    return paths


def run_agent(ws, case, args):
    run = case.get("run") or {}
    cmd = ["claude", "-p", case["input_task"]]
    if run.get("allowed_tools"):
        cmd += ["--allowedTools", run["allowed_tools"]]
    cmd += ["--output-format", "json", "--max-turns", str(run.get("max_turns", 20)),
            "--permission-mode", "acceptEdits", "--setting-sources", "project"]
    if run.get("max_budget_usd"):
        cmd += ["--max-budget-usd", str(run["max_budget_usd"])]
    if args.model:
        cmd += ["--model", args.model]
    if args.dry_run:
        print("    would run in {}:\n      {}".format(ws, " ".join(json.dumps(c) if " " in c else c for c in cmd)))
        return {}
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=ws, capture_output=True, text=True,
                              timeout=int(run.get("timeout_seconds", 900)))
        out = json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        out = {"is_error": True, "result": "timed out"}
    except ValueError:
        out = {"is_error": True, "result": (proc.stdout + proc.stderr)[-2000:]}
    out["wall_seconds"] = round(time.time() - started, 1)
    return out


def grade(ws, case, before, agent_out):
    graders = case.get("graders") or {}
    changed = changed_paths(ws)
    checks = []

    def add(name, block, passed, detail):
        checks.append({"grader": name, "weight": float(block.get("weight", 1)), "passed": passed, "detail": detail})

    if "must_pass" in graders:
        block, failures = graders["must_pass"], []
        for command in block.get("commands", []):
            proc = subprocess.run(command, shell=True, cwd=ws, capture_output=True, text=True, timeout=600)
            if proc.returncode != 0:
                failures.append("{} -> exit {}: {}".format(command, proc.returncode, (proc.stdout + proc.stderr)[-300:]))
        add("must_pass", block, not failures, failures or "all passed")
    if "files_unchanged" in graders:
        block = graders["files_unchanged"]
        bad = [p for p in block.get("paths", []) if file_hash(os.path.join(ws, p)) != before.get(p)]
        add("files_unchanged", block, not bad, bad or "untouched")
    if "files_changed" in graders:
        block = graders["files_changed"]
        bad = [p for p in block.get("paths", []) if file_hash(os.path.join(ws, p)) == before.get(p)]
        add("files_changed", block, not bad, bad or "changed")
    if "allowed_paths" in graders:
        block = graders["allowed_paths"]
        outside = [p for p in changed if not any(fnmatch.fnmatch(p, g) for g in block.get("globs", []))]
        add("allowed_paths", block, not outside, outside or "inside allowed paths")
    if "expected_patterns" in graders:
        block, missing = graders["expected_patterns"], []
        for rel, patterns in (block.get("files") or {}).items():
            try:
                with open(os.path.join(ws, rel), encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                text = ""
            missing += ["{}: {}".format(rel, p) for p in patterns if not re.search(p, text)]
        add("expected_patterns", block, not missing, missing or "found")
    if "forbidden_patterns" in graders:
        block = graders["forbidden_patterns"]
        added = [l[1:] for l in git(ws, "diff", "HEAD").stdout.splitlines() if l.startswith("+") and not l.startswith("+++")]
        for rel in git(ws, "ls-files", "--others", "--exclude-standard").stdout.splitlines():
            try:
                with open(os.path.join(ws, rel), encoding="utf-8", errors="replace") as fh:
                    added += fh.read().splitlines()
            except OSError:
                pass
        hits = [p for p in block.get("patterns", []) if any(re.search(p, line) for line in added)]
        add("forbidden_patterns", block, not hits, hits or "none found")

    total = sum(c["weight"] for c in checks) or 1.0
    score = sum(c["weight"] for c in checks if c["passed"]) / total
    policy, violations = case.get("policy_checks") or {}, []
    cost, turns = agent_out.get("total_cost_usd"), agent_out.get("num_turns")
    if cost is not None and "max_cost_usd" in policy and cost > float(policy["max_cost_usd"]):
        violations.append("cost {:.2f} USD > {}".format(cost, policy["max_cost_usd"]))
    if turns is not None and "max_turns" in policy and turns > int(policy["max_turns"]):
        violations.append("turns {} > {}".format(turns, policy["max_turns"]))
    threshold = float(graders.get("threshold", 1.0))
    return {"score": round(score, 3), "passed": score >= threshold and not violations, "checks": checks,
            "policy_violations": violations, "cost_usd": cost, "turns": turns,
            "agent_error": agent_out.get("is_error", False), "changed_paths": changed}


def run_case(case_dir, case, args, mode):
    """mode: 'agent' (real run), 'reference' or 'noop' (self-test)."""
    ws = make_workspace(case_dir, args.config_root)
    try:
        before = snapshot(ws)
        if mode == "reference":
            shutil.copytree(os.path.join(case_dir, "reference"), ws, ignore=IGNORE, dirs_exist_ok=True)
        agent_out = run_agent(ws, case, args) if mode == "agent" else {}
        return grade(ws, case, before, agent_out)
    finally:
        if args.keep:
            print("    kept workspace:", ws)
        else:
            shutil.rmtree(ws, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="Run agent eval cases with headless Claude Code.")
    parser.add_argument("--case", help="only run cases whose folder name starts with this")
    parser.add_argument("--runs", type=int, help="override runs per case")
    parser.add_argument("--model", help="model alias or id for every run")
    parser.add_argument("--config-root", default=ROOT, help="repository whose agent config is under test")
    parser.add_argument("--self-test", action="store_true", help="check cases with their reference solutions; no API calls")
    parser.add_argument("--dry-run", action="store_true", help="print commands, grade the untouched fixture")
    parser.add_argument("--keep", action="store_true", help="keep workspaces for debugging")
    args = parser.parse_args()

    folders = sorted(d for d in os.listdir(CASES) if os.path.isdir(os.path.join(CASES, d)))
    if args.case:
        folders = [d for d in folders if d.startswith(args.case)]
    if not folders:
        sys.exit("run_evals: no cases found")
    if not args.self_test and not args.dry_run and shutil.which("claude") is None:
        sys.exit("run_evals: the claude CLI is not on PATH")

    report, all_ok = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cases": []}, True
    for folder in folders:
        case_dir = os.path.join(CASES, folder)
        case = load_case(case_dir)
        if not case:
            continue
        print("{} {}".format(case.get("id", folder), case.get("title", "")))
        if args.self_test:
            good = run_case(case_dir, case, args, "reference")
            bad = run_case(case_dir, case, args, "noop")
            ok = good["passed"] and not bad["passed"]
            all_ok &= ok
            print("  reference solution: score {:.2f} ({})".format(good["score"], "pass" if good["passed"] else "FAIL"))
            print("  untouched fixture:  score {:.2f} ({})".format(bad["score"], "fails, as it should" if not bad["passed"] else "PASSES: the case cannot tell good from bad"))
            report["cases"].append({"id": case.get("id"), "self_test_ok": ok, "reference": good, "noop": bad})
            continue
        runs = 1 if args.dry_run else (args.runs or int((case.get("run") or {}).get("runs", 1)))
        results = [run_case(case_dir, case, args, "agent") for _ in range(runs)]
        passes = sum(r["passed"] for r in results)
        rate = passes / runs
        need = float((case.get("run") or {}).get("min_pass_rate", 1.0))
        all_ok &= rate >= need
        for i, r in enumerate(results, 1):
            failed = [c["grader"] for c in r["checks"] if not c["passed"]]
            print("  run {}: score {:.2f} {} cost={} turns={} {}".format(
                i, r["score"], "pass" if r["passed"] else "FAIL", r["cost_usd"], r["turns"],
                ("failed: " + ", ".join(failed)) if failed else ""))
        print("  pass rate {}/{} (needs {:.0%})".format(passes, runs, need))
        report["cases"].append({"id": case.get("id"), "pass_rate": rate, "runs": results})

    os.makedirs(RESULTS, exist_ok=True)
    out = os.path.join(RESULTS, time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + ".json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print("results: " + os.path.relpath(out, ROOT))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
