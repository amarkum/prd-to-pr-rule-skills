#!/usr/bin/env python3
"""aisdlc_hooks.py - deterministic guardrails for the PRD-to-PR workflow.

One script, both tools. Claude Code and Cursor call it with a subcommand and
--format; it reads the hook payload from stdin and answers in that tool's format.

  shell-guard      block irreversible / outward / secret-reading shell commands; gate PR creation
  edit-guard       block secrets, hand-edited evidence, weakened tests, code before an approved spec
  pr-gate          gate PR creation done through an MCP tool (e.g. GitHub MCP create_pull_request)
  session-context  inject repo stack, workflow state and evidence status at session start
  stop-verify      at the end of a turn, ask for verification if code changed since the last evidence

Rules are advice; these hooks are law. Policy lives here, not in prompts.
Standard library only. Exit 0 always; decisions are carried in the JSON output.
Set AISDLC_HOOKS=off to disable (for example while repairing the hooks themselves).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = PLUGIN_ROOT / "scripts" / "evidence.py"
KEY_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9]+-\d+)(?![0-9])")

# (pattern, decision, reason). Decisions: deny | ask.
SHELL_RULES = [
    (r"\bgit\s+push\b[^;&|\n]*\s(?:--force(?!-with-lease)|-f\b)", "deny",
     "Force-push rewrites shared history. Push a new commit instead."),
    (r"\bgit\s+push\b[^;&|\n]*\s(?:\S+\s+)?(?:\S*:)?(?:refs/heads/)?(?:main|master|develop|production|release/[\w.-]+)(?=\s|$)",
     "deny", "Agents never push to protected branches. Push the feature branch and open a draft PR."),
    (r"\bgit\s+commit\b[^;&|\n]*\s(?:--no-verify|-n)\b", "deny", "Do not skip git hooks (--no-verify)."),
    (r"\bgh\s+pr\s+merge\b|\bgh\s+api\b[^\n]*/merge\b", "deny", "Humans merge. Agents only open draft PRs."),
    (r"\bgh\s+pr\s+ready\b", "ask", "Marking a PR ready for review is the developer's call."),
    (r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:ba|z|da|k)?sh\b", "deny",
     "Piping a download into a shell is not allowed."),
    (r"\brm\s+-[a-zA-Z]*[rR][a-zA-Z]*\s+(?:/|~|\$HOME|\.\.?)/?(?:\s|$)", "deny",
     "Refusing a recursive delete of /, ~, . or .."),
    (r"\b(?:terraform|tofu)\s+(?:apply|destroy|import|state\s+(?:rm|mv|push))\b", "deny",
     "Infrastructure changes go through the infrastructure pipeline, not the coding agent."),
    (r"\bkubectl\s+(?:apply|delete|create|replace|patch|scale|rollout|edit|drain|cordon|annotate|label)\b", "deny",
     "Cluster changes are out of scope for the coding agent."),
    (r"\bhelm\s+(?:install|upgrade|uninstall|rollback|delete)\b", "deny",
     "Release changes are out of scope for the coding agent."),
    (r"\bairflow\s+(?:dags\s+(?:trigger|backfill|delete|pause|unpause)|tasks\s+(?:run|clear)|db\s+(?:reset|clean|downgrade|migrate)"
     r"|connections\s+(?:add|delete|import)|variables\s+(?:set|delete|import)|pools\s+(?:set|delete|import)|users\s+(?:create|delete))\b",
     "deny", "Do not mutate a running Airflow. Use `airflow dags test` or dag.test() against local services."),
    (r"\b(?:mongo|mongosh)\b[^\n]*\b(?:drop(?:Database)?|deleteMany|deleteOne|remove|updateMany|updateOne|insertMany|insertOne"
     r"|replaceOne|findOneAndUpdate|findOneAndDelete|findOneAndReplace|renameCollection|createIndex|dropIndex|bulkWrite)\s*\(",
     "deny", "Data stores are read-only for agents. Express data changes as reviewed code (DAG task or migration) with tests."),
    (r"(?i)\b(?:psql|mysql|sqlcmd|sqlite3|clickhouse-client|bq)\b[^\n]*\b(?:DROP|TRUNCATE|DELETE\s+FROM|UPDATE\s+\S+\s+SET|INSERT\s+INTO"
     r"|ALTER\s+TABLE|GRANT|REVOKE|CREATE\s+(?:TABLE|INDEX|USER|ROLE))\b",
     "deny", "Data stores are read-only for agents. Express schema/data changes as reviewed migrations with tests."),
    (r"(?:^|[;&|]\s*)(?:env|printenv|set|export\s+-p)\s*(?:$|[;&|>])", "deny",
     "Dumping the environment can expose secrets into the transcript."),
    (r"\b(?:cat|less|more|head|tail|bat|nl|strings|xxd|od|base64|grep|rg|awk|sed|cp|scp|rsync)\b[^\n;|]*"
     r"(?:\.env(?!\.example|\.sample|\.template|\.dist)\b|id_rsa|id_ed25519|\.pem\b|\.p12\b|\.pfx\b|\.key\b"
     r"|\.npmrc\b|\.pypirc\b|\.netrc\b|kubeconfig|credentials(?:\.json)?\b|secrets?\.(?:ya?ml|json|env)\b)",
     "deny", "Reading secret or credential files is not allowed. Ask the developer for the value you need."),
    (r"\bgit\s+(?:reset\s+--hard|clean\s+-[a-zA-Z]*f|checkout\s+--\s+\.|restore\s+(?:--source\s+\S+\s+)?\.(?:\s|$))", "ask",
     "This discards local work. Confirm before running it."),
]

SECRET_PATTERNS = [
    ("AWS access key", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("private key", r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----"),
    ("GitHub token", r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})\b"),
    ("Slack token", r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b"),
    ("Atlassian API token", r"\bATATT3[A-Za-z0-9_\-=]{20,}"),
    ("Anthropic API key", r"\bsk-ant-[A-Za-z0-9_\-]{20,}"),
    ("OpenAI API key", r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{32,}"),
    ("Google API key", r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    ("credentials in a connection string",
     r"\b(?:mongodb(?:\+srv)?|postgres(?:ql)?|mysql|mssql|redis|amqps?)://[^\s:/@'\"]+:"
     r"(?!\$\{|<|\{\{|password@|pass@|changeme@|example@|secret@|xxx+@)[^\s@/'\"]{3,}@"
     r"(?!localhost|127\.0\.0\.1|0\.0\.0\.0|mongo[:/]|mongodb[:/]|postgres[:/]|db[:/]|host\.docker\.internal)"),
]

TEST_FILE_RE = re.compile(
    r"(?:^|/)(?:test_[^/]*\.py|[^/]*_test\.py|[^/]*\.(?:test|spec)\.[cm]?[jt]sx?|conftest\.py)$"
    r"|(?:^|/)(?:tests?|__tests__|e2e|integration-tests)/")
SKIP_RE = re.compile(
    r"@pytest\.mark\.(?:skip|skipif|xfail)\b|\bpytest\.(?:skip|xfail)\s*\(|@unittest\.(?:skip\w*|expectedFailure)\b"
    r"|\b(?:it|test|describe|context|suite)\.(?:skip|only|todo|fixme)\s*\(|\b(?:xit|xdescribe|xtest|fit|fdescribe)\s*\(")
ALLOW_SKIP_RE = re.compile(r"aisdlc:\s*allow-skip\s+\S+")

DENY_PATHS = [
    (r"(?:^|/)\.ai/evidence/", "Evidence is produced by evidence.py, never edited by hand."),
    (r"(?:^|/)\.git/", "Do not edit git internals."),
    (r"(?:^|/)\.env(?!\.example$|\.sample$|\.template$|\.dist$)(?:\.[\w.-]+)?$", "Do not write secret env files; use .env.example."),
    (r"\.(?:pem|p12|pfx|key)$|(?:^|/)id_(?:rsa|ed25519)", "Do not write key material."),
]
ASK_PATHS = [
    (r"(?:^|/)\.claude/settings(?:\.local)?\.json$|(?:^|/)\.cursor/(?:hooks\.json|hooks/|cli\.json)",
     "This file controls the agent's own guardrails."),
    (r"(?:^|/)\.github/workflows/|(?:^|/)CODEOWNERS$|(?:^|/)\.github/CODEOWNERS$", "CI and ownership changes need a human."),
    (r"(?:^|/)(?:migrations|alembic/versions|db/migrate)/", "Database migrations need explicit approval."),
]
SPEC_FREE_RE = re.compile(r"^(?:specs/|docs/|\.ai/(?!evidence/)|README|CHANGELOG)")


# ---------------------------------------------------------------- I/O helpers

def read_payload() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except ValueError:
        return {}


def project_dir(payload: dict) -> Path:
    for var in ("CLAUDE_PROJECT_DIR", "CURSOR_PROJECT_DIR"):
        if os.environ.get(var):
            return Path(os.environ[var])
    roots = payload.get("workspace_roots") or []
    return Path(payload.get("cwd") or (roots[0] if roots else os.getcwd()))


def out(obj: dict | None) -> int:
    if obj:
        print(json.dumps(obj))
    return 0


def decision(fmt: str, event: str, verdict: str | None, reason: str = "") -> int:
    """verdict: None (no opinion), 'deny' or 'ask'."""
    if fmt == "cursor":
        if verdict is None:
            return out({"permission": "allow"})
        # Cursor does not enforce 'ask' on preToolUse; deny there with an explanation instead.
        if verdict == "ask" and event == "preToolUse":
            verdict, reason = "deny", reason + " Ask the developer to run or approve this step."
        msg = f"[ai-sdlc] {reason}"
        return out({"permission": verdict, "user_message": msg, "agent_message": msg})
    if verdict is None:
        return 0  # no output: Claude Code's normal permission flow continues
    return out({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": verdict,
                                       "permissionDecisionReason": f"[ai-sdlc] {reason}"}})


def git(cwd: Path, *args: str) -> str:
    try:
        res = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10)
        return res.stdout.strip() if res.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def base_ref(cwd: Path) -> str:
    head = git(cwd, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    return head.replace("refs/remotes/", "") if head else "origin/main"


def branch_key(cwd: Path) -> str | None:
    m = KEY_RE.search(git(cwd, "rev-parse", "--abbrev-ref", "HEAD"))
    return m.group(1).upper() if m else None


def spec_status(cwd: Path, key: str | None) -> tuple[Path | None, str | None]:
    if not key:
        return None, None
    spec = cwd / "specs" / key / "spec.md"
    if not spec.is_file():
        return None, None
    text = spec.read_text(encoding="utf-8", errors="replace")
    fm = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    m = re.search(r"^status:\s*['\"]?([\w-]+)", fm.group(1), re.MULTILINE) if fm else None
    return spec, (m.group(1).lower() if m else "draft")


def evidence_check(cwd: Path) -> tuple[bool, str]:
    if not EVIDENCE.is_file():
        return False, f"evidence.py not found at {EVIDENCE}"
    try:
        res = subprocess.run([sys.executable, str(EVIDENCE), "check", "--docs-only-ok", "--base", base_ref(cwd)],
                             cwd=cwd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    return res.returncode == 0, (res.stdout + res.stderr).strip()


def rel(path: str, cwd: Path) -> str:
    p = Path(path)
    try:
        return p.resolve().relative_to(cwd.resolve()).as_posix() if p.is_absolute() else p.as_posix()
    except ValueError:
        return p.as_posix()


# ---------------------------------------------------------------- guards

def shell_guard(payload: dict, fmt: str) -> int:
    event = "beforeShellExecution" if fmt == "cursor" else "PreToolUse"
    cmd = payload.get("command") or (payload.get("tool_input") or {}).get("command") or ""
    cwd = project_dir(payload)
    for pattern, verdict, reason in SHELL_RULES:
        if re.search(pattern, cmd):
            return decision(fmt, event, verdict, reason)
    if re.search(r"\bgit\s+push\b", cmd) and re.fullmatch(
            r"main|master|develop|production|release/[\w.-]+", git(cwd, "rev-parse", "--abbrev-ref", "HEAD")):
        return decision(fmt, event, "deny", "You are on a protected branch. Create a feature branch named after the Jira key.")
    if re.search(r"\bgh\s+pr\s+create\b", cmd):
        if not re.search(r"\s(?:--draft|-d)\b", cmd):
            return decision(fmt, event, "deny", "Agents open draft PRs only: add --draft.")
        ok, detail = evidence_check(cwd)
        if not ok:
            return decision(fmt, event, "deny", "No passing evidence for this commit. Run the verify skill "
                                                f"(evidence.py run) and commit first.\n{detail}")
    return decision(fmt, event, None)


def pr_gate(payload: dict, fmt: str) -> int:
    event = "beforeMCPExecution" if fmt == "cursor" else "PreToolUse"
    tool = str(payload.get("tool_name", ""))
    if fmt == "cursor" and not re.search(r"create_pull_request", tool):
        return decision(fmt, event, None)
    params = payload.get("tool_input") or {}
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except ValueError:
            params = {}
    if params.get("draft") is not True:
        return decision(fmt, event, "deny", "Agents open draft PRs only: set draft: true.")
    ok, detail = evidence_check(project_dir(payload))
    if not ok:
        return decision(fmt, event, "deny", f"No passing evidence for this commit. Run the verify skill first.\n{detail}")
    return decision(fmt, event, None)


def edit_texts(tool_input: dict) -> tuple[str, str]:
    """(old_text, new_text) across Claude Write/Edit/MultiEdit/NotebookEdit and Cursor Write shapes."""
    old_parts, new_parts = [], []
    for k in ("old_string",):
        if isinstance(tool_input.get(k), str):
            old_parts.append(tool_input[k])
    for k in ("content", "contents", "new_string", "new_source", "code_edit", "text"):
        if isinstance(tool_input.get(k), str):
            new_parts.append(tool_input[k])
    for e in tool_input.get("edits") or []:
        if isinstance(e, dict):
            old_parts.append(str(e.get("old_string", "")))
            new_parts.append(str(e.get("new_string", "")))
    return "\n".join(old_parts), "\n".join(new_parts)


def edit_guard(payload: dict, fmt: str) -> int:
    event = "preToolUse" if fmt == "cursor" else "PreToolUse"
    ti = payload.get("tool_input") or {}
    if isinstance(ti, str):
        try:
            ti = json.loads(ti)
        except ValueError:
            ti = {}
    cwd = project_dir(payload)
    raw_path = ti.get("file_path") or ti.get("path") or ti.get("notebook_path") or ti.get("target_file") or ""
    path = rel(str(raw_path), cwd) if raw_path else ""
    old, new = edit_texts(ti)

    for pattern, reason in DENY_PATHS:
        if path and re.search(pattern, path):
            return decision(fmt, event, "deny", f"{path}: {reason}")
    for name, pattern in SECRET_PATTERNS:
        if re.search(pattern, new):
            return decision(fmt, event, "deny", f"The new content contains what looks like a {name}. "
                                                "Use an environment variable or secret manager reference.")
    if path and TEST_FILE_RE.search(path):
        before = old
        if not old and (cwd / path).is_file() and any(k in ti for k in ("content", "contents")):
            before = (cwd / path).read_text(encoding="utf-8", errors="replace")
        added = len(SKIP_RE.findall(new)) - len(SKIP_RE.findall(before))
        if added > 0 and not ALLOW_SKIP_RE.search(new):
            return decision(fmt, event, "deny",
                            "This edit adds skip/only/xfail markers to tests. Fix the code or the test instead; "
                            "if a skip is genuinely required, put `aisdlc: allow-skip <reason + ticket>` on that line "
                            "and call it out in the PR.")
    if path and re.fullmatch(r"specs/[^/]+/spec\.md", path):
        approve = re.compile(r"^status:\s*['\"]?approved", re.MULTILINE)
        before = old or ((cwd / path).read_text(encoding="utf-8", errors="replace") if (cwd / path).is_file() else "")
        if approve.search(new) and not approve.search(before):
            return decision(fmt, event, "deny", "Approving a spec is a human decision. Ask the tech lead to set "
                                                "`status: approved` / `approved_by` themselves (or approve the spec PR).")
    if path and os.environ.get("AISDLC_SPEC_GATE", "on") != "off" and not SPEC_FREE_RE.search(path):
        spec, status = spec_status(cwd, branch_key(cwd))
        if spec is not None and status != "approved":
            return decision(fmt, event, "deny",
                            f"{spec.relative_to(cwd)} is '{status}', not 'approved'. No code before the spec is approved: "
                            "get the spec reviewed (set status: approved with approved_by), or work only in specs/.")
    for pattern, reason in ASK_PATHS:
        if path and re.search(pattern, path):
            return decision(fmt, event, "ask", f"{path}: {reason}")
    return decision(fmt, event, None)


# ---------------------------------------------------------------- context & stop

def manifest_summary(cwd: Path) -> dict:
    path = cwd / ".ai" / "repo.yaml"
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text) or {}
    except Exception:  # PyYAML missing or invalid YAML: fall back to the two fields we need
        data = {"repo": {k: (re.search(rf"^\s+{k}:\s*([\w.-]+)", text, re.MULTILINE) or [None, None])[1]
                         for k in ("name", "stack")}}
    return data if isinstance(data, dict) else {}


def evidence_state(cwd: Path) -> str:
    path = cwd / ".ai" / "evidence" / "manifest.json"
    if not path.is_file():
        return "none"
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return "unreadable"
    head = git(cwd, "rev-parse", "HEAD")
    if rec.get("repo", {}).get("head_sha") != head:
        return f"stale ({rec.get('verdict')} for {str(rec.get('repo', {}).get('head_sha', ''))[:10]}, HEAD {head[:10]})"
    return f"{rec.get('verdict')} for HEAD {head[:10]}"


def core_rules() -> str:
    """Bodies of the plugin's alwaysApply rules. Cursor loads rules/ natively; Claude Code gets them here."""
    parts = []
    for path in sorted((PLUGIN_ROOT / "rules").glob("*.mdc")):
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if fm and re.search(r"^alwaysApply:\s*true\s*$", fm.group(1), re.MULTILINE):
            parts.append(text[fm.end():].strip())
    return "\n\n".join(parts)


def session_context(payload: dict, fmt: str) -> int:
    cwd = project_dir(payload)
    m = manifest_summary(cwd)
    repo = m.get("repo") or {}
    lines = ["[ai-sdlc] Workflow: PRD -> prd-review -> spec (approved) -> build (TDD) -> verify (evidence) -> draft PR -> learn."]
    if repo:
        lines.append(f"Repo `{repo.get('name')}` (stack: {repo.get('stack')}). Read .ai/repo.yaml for commands; "
                     f"load the {repo.get('stack')} stack skill before changing code.")
        checks = [f"{c.get('id')}=`{c.get('run')}`" for c in (m.get("checks") or [])[:6] if isinstance(c, dict)]
        if checks:
            lines.append("Checks: " + "; ".join(checks))
    else:
        lines.append("No .ai/repo.yaml here: run the onboarding (tools/aisdlc.py init) before using the workflow.")
    key = branch_key(cwd)
    if key:
        spec, status = spec_status(cwd, key)
        lines.append(f"Branch is for {key}; spec: {spec.relative_to(cwd) if spec else 'not found'}"
                     + (f" (status: {status})" if status else "") + f"; evidence: {evidence_state(cwd)}.")
    text = "\n".join(lines)
    if fmt == "claude" and not os.environ.get("CURSOR_VERSION"):
        rules = core_rules()
        if rules:
            text += "\n\n" + rules
    if fmt == "cursor":
        return out({"additional_context": text})
    return out({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}})


def stop_verify(payload: dict, fmt: str) -> int:
    cwd = project_dir(payload)
    if payload.get("stop_hook_active") or int(payload.get("loop_count") or 0) >= 1:
        return 0 if fmt != "cursor" else out({})
    key = branch_key(cwd)
    spec, status = spec_status(cwd, key)
    if spec is None or status != "approved":
        return 0 if fmt != "cursor" else out({})
    changed = [ln[3:] for ln in git(cwd, "status", "--porcelain").splitlines()
               if ln[3:] and not SPEC_FREE_RE.search(ln[3:]) and not ln[3:].startswith(".ai/")]
    state = evidence_state(cwd)
    if not changed and state.startswith("pass"):
        return 0 if fmt != "cursor" else out({})
    msg = (f"[ai-sdlc] {key}: code changed but evidence is '{state}'"
           + (f" and {len(changed)} file(s) are uncommitted" if changed else "")
           + ". Before finishing: commit, run the verify skill, and report the evidence verdict. "
             "If you are intentionally stopping mid-task, say so explicitly.")
    if fmt == "cursor":
        return out({"followup_message": msg})
    return out({"decision": "block", "reason": msg})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["shell-guard", "edit-guard", "pr-gate", "session-context", "stop-verify"])
    ap.add_argument("--format", choices=["claude", "cursor"], default="claude")
    args = ap.parse_args()
    if os.environ.get("AISDLC_HOOKS", "on") == "off":
        return out({"permission": "allow"}) if args.format == "cursor" and "guard" in args.command else 0
    payload = read_payload()
    handler = {"shell-guard": shell_guard, "edit-guard": edit_guard, "pr-gate": pr_gate,
               "session-context": session_context, "stop-verify": stop_verify}[args.command]
    try:
        return handler(payload, args.format)
    except Exception as exc:  # a crashing guard must not wedge the session; report and fail open
        print(f"[ai-sdlc] hook {args.command} error: {exc}", file=sys.stderr)
        return out({"permission": "allow"}) if args.format == "cursor" and "guard" in args.command else 0


if __name__ == "__main__":
    sys.exit(main())
