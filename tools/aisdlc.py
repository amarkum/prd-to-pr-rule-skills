#!/usr/bin/env python3
"""aisdlc.py - onboard product repos to the AI SDLC standard and keep them healthy.

The plugins reach developers through the organization's managed settings (policy/README.md) and CI logic lives in the
standard's shared workflow, so a repo only carries what is specific to it.

  init             write the repo's own files: CLAUDE.md, .ai/repo.yaml (stack, checks, CI install), data connectors
                   (.mcp.json) and the one-file CI caller .github/workflows/ai-sdlc.yml. --extras adds the optional
                   REVIEW.md, .ai/bands.yaml, evals/, specs/ and docs/knowledge/ READMEs and a PR template.
                   --repo-plugins also writes .claude/settings.json (marketplace, plugins, permissions) for
                   organizations that can't deploy managed settings.
  vendor           copy the plugins into the repo's .claude/, a fallback for surfaces that get neither managed
                   settings nor repo plugins. Re-run it to update. Always-on rules go to .claude/rules/.
  doctor           check a repo's setup, including leftovers of the per-repo workflow copies; exit 1 on failures
  knowledge-audit  flag knowledge entries that are past review_by or missing fields; exit 1 if any

Examples:
  python3 tools/aisdlc.py init --target ../data-airflow --stack airflow --jira PAY --description "Payroll pipelines"
  python3 tools/aisdlc.py doctor --target ../data-airflow
  python3 tools/aisdlc.py vendor --target ../payroll-mfe --stack mfe
  python3 tools/aisdlc.py knowledge-audit knowledge/
Standard library only (PyYAML is used by doctor when present).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates" / "repo"
PLUGINS = ROOT / "plugins"
STACKS = ("airflow", "mfe", "frontend")
STACK_PLUGINS = {
    "airflow": ["sdlc-core", "sdlc-connectors", "stack-airflow"],
    "mfe": ["sdlc-core", "sdlc-connectors", "stack-frontend", "stack-mfe"],
    "frontend": ["sdlc-core", "sdlc-connectors", "stack-frontend"],
}
WEB_ALLOW = ["Bash(npm run lint *)", "Bash(npm run build *)", "Bash(npm test *)", "Bash(npx vitest *)",
             "Bash(npx playwright test *)", "Bash(npx tsc *)"]
STACK_ALLOW = {
    "airflow": ["Bash(pytest *)", "Bash(python -m pytest *)", "Bash(ruff *)",
                "Bash(airflow dags list-import-errors *)", "Bash(airflow dags test *)"],
    "mfe": WEB_ALLOW,
    "frontend": WEB_ALLOW,
}
COMMON_ALLOW = ["Bash(git status *)", "Bash(git diff *)", "Bash(git log *)", "Bash(git show *)",
                "Bash(gh pr view *)", "Bash(gh pr list *)", "Bash(rg *)"]
ASK = ["Bash(git push *)"]
ALWAYS_ON = ["sdlc-standard", "sdlc-core"]   # what managed settings enable: the bundle, and sdlc-core locked on
# The per-repo workflow copies of standard 2.0, replaced by .github/workflows/ai-sdlc.yml calling the shared workflow
LEGACY_WORKFLOWS = ["ai-evidence.yml", "ai-prd-intake.yml", "ai-design.yml", "ai-build.yml", "ai-review.yml",
                    "ai-agent-evals.yml", "ai-maintain.yml", "ai-learn.yml"]
MANAGED_FILES = [Path("/etc/claude-code/managed-settings.json"),
                 Path("/Library/Application Support/ClaudeCode/managed-settings.json"),
                 Path("C:/Program Files/ClaudeCode/managed-settings.json")]
DENY = ["Read(./.env)", "Read(./.env.local)", "Read(./.env.*.local)", "Read(./**/*.pem)", "Read(./**/*.key)",
        "Read(./**/secrets/**)"]
TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".toml", ".py", ".txt", ""}


# ---------------------------------------------------------------- helpers

def render(text: str, values: dict) -> str:
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(values.get(m.group(1), m.group(0))), text)


def merge_list(existing: list, extra: list) -> list:
    return existing + [x for x in extra if x not in existing]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def copy_tree(src: Path, dst: Path, values: dict, force: bool, report: list) -> None:
    for f in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = f.relative_to(src)
        if rel.name == "gitignore.aisdlc":
            continue
        target = dst / rel
        if target.exists() and not force:
            report.append(("skip", str(rel)))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if f.suffix in TEXT_SUFFIXES:
            target.write_text(render(f.read_text(encoding="utf-8"), values), encoding="utf-8")
        else:
            shutil.copy2(f, target)
        report.append(("write", str(rel)))


def ensure_gitignore(target: Path, report: list) -> None:
    wanted = (TEMPLATES / "common" / "gitignore.aisdlc").read_text(encoding="utf-8").splitlines()
    path = target / ".gitignore"
    have = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    missing = [w for w in wanted if w and w not in have]
    if missing:
        path.write_text("\n".join(have + ([""] if have and have[-1] else []) + missing) + "\n", encoding="utf-8")
        report.append(("update", ".gitignore"))


def plugin_settings(settings: dict, stack: str, marketplace: str, enabled: bool = True) -> dict:
    """Repo-level plugin settings: the fallback when managed settings can't deliver the plugins (enabled=True), or
    the plugins switched off where a vendored copy replaces them (enabled=False)."""
    settings.setdefault("$schema", "https://json.schemastore.org/claude-code-settings.json")
    mk = settings.setdefault("extraKnownMarketplaces", {})
    mk.setdefault("ai-sdlc", {"source": {"source": "github", "repo": marketplace}, "autoUpdate": True})
    plugins = settings.setdefault("enabledPlugins", {})
    for p in (ALWAYS_ON if enabled else ["sdlc-standard"] + STACK_PLUGINS[stack]):
        plugins[f"{p}@ai-sdlc"] = enabled
    perms = settings.setdefault("permissions", {})
    perms["allow"] = merge_list(perms.get("allow", []), COMMON_ALLOW + STACK_ALLOW[stack])
    perms["ask"] = merge_list(perms.get("ask", []), ASK)
    perms["deny"] = merge_list(perms.get("deny", []), DENY)
    return settings


# ---------------------------------------------------------------- init

def cmd_init(a) -> int:
    target = Path(a.target).resolve()
    if not target.is_dir():
        print(f"init: {target} is not a directory", file=sys.stderr)
        return 2
    values = {"name": a.name or target.name, "stack": a.stack, "jira_project": a.jira, "standard": a.standard,
              "description": a.description or f"<one-line description of {a.name or target.name}>"}
    report: list = []
    copy_tree(TEMPLATES / "common", target, values, a.force, report)
    copy_tree(TEMPLATES / a.stack, target, values, a.force, report)
    if a.extras:
        copy_tree(TEMPLATES / "extras", target, values, a.force, report)
    ensure_gitignore(target, report)
    if a.repo_plugins:
        settings_path = target / ".claude" / "settings.json"
        write_json(settings_path, plugin_settings(load_json(settings_path), a.stack, a.standard))
        report.append(("merge", ".claude/settings.json"))
    if a.stack == "airflow":
        dst = target / "tests" / "dags" / "test_dag_integrity.py"
        if not dst.exists() or a.force:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PLUGINS / "stack-airflow/skills/airflow-dag/templates/test_dag_integrity.py", dst)
            report.append(("write", "tests/dags/test_dag_integrity.py"))
    for action, rel in report:
        print(f"{action:7} {rel}")
    print(f"\nNext: fill in CLAUDE.md, check `checks:` and `ci:` in .ai/repo.yaml, commit, and run\n"
          f"  python3 {Path(__file__).resolve()} doctor --target {a.target}\n"
          f"Developers get the plugins from the organization's managed settings (policy/README.md); CI runs the shared\n"
          f"workflow through .github/workflows/ai-sdlc.yml. Make \"ai-sdlc / evidence\" a required check.")
    return 0


# ---------------------------------------------------------------- vendor

def cmd_vendor(a) -> int:
    target = Path(a.target).resolve()
    claude, aisdlc = target / ".claude", target / ".claude" / "aisdlc"
    if aisdlc.exists():
        shutil.rmtree(aisdlc)
    (aisdlc / "scripts").mkdir(parents=True)
    (aisdlc / "hooks").mkdir()
    rules_dir = claude / "rules"
    for old in rules_dir.glob("aisdlc-*.md") if rules_dir.is_dir() else []:
        old.unlink()
    sub = "${CLAUDE_PROJECT_DIR}/.claude/aisdlc"
    copied = []
    for plugin in STACK_PLUGINS[a.stack]:
        root = PLUGINS / plugin
        for skill in sorted((root / "skills").glob("*/")):
            dst = claude / "skills" / skill.name
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(skill, dst)
            for md in dst.rglob("*.md"):
                md.write_text(md.read_text(encoding="utf-8").replace("${CLAUDE_PLUGIN_ROOT}", sub), encoding="utf-8")
            copied.append(f"skill {skill.name}")
        for agent in sorted((root / "agents").glob("*.md")) if (root / "agents").is_dir() else []:
            (claude / "agents").mkdir(parents=True, exist_ok=True)
            shutil.copy2(agent, claude / "agents" / agent.name)
            copied.append(f"agent {agent.stem}")
        for script in sorted((root / "scripts").glob("*.py")) if (root / "scripts").is_dir() else []:
            shutil.copy2(script, aisdlc / "scripts" / script.name)
        for rule in sorted((root / "rules").glob("*.md")) if (root / "rules").is_dir() else []:
            # native project rules: no `paths`, so they load at launch on every surface, hooks or not
            body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", rule.read_text(encoding="utf-8"), count=1, flags=re.DOTALL)
            rules_dir.mkdir(parents=True, exist_ok=True)
            (rules_dir / f"aisdlc-{rule.name}").write_text(
                f"<!-- Vendored from the ai-sdlc standard ({plugin}) by tools/aisdlc.py vendor. "
                f"Change the standard, then re-run vendor. -->\n{body}", encoding="utf-8")
            copied.append(f"rule {rule.stem}")
    shutil.copy2(PLUGINS / "sdlc-core/hooks/aisdlc_hooks.py", aisdlc / "hooks" / "aisdlc_hooks.py")

    # Claude Code hooks (shell form: Claude Code exports $CLAUDE_PROJECT_DIR to hook processes)
    hook = 'python3 "$CLAUDE_PROJECT_DIR/.claude/aisdlc/hooks/aisdlc_hooks.py" '
    settings_path = claude / "settings.json"
    settings = plugin_settings(load_json(settings_path), a.stack, a.standard, enabled=False)
    settings["hooks"] = {
        "SessionStart": [{"matcher": "startup|resume|clear|compact",
                          "hooks": [{"type": "command", "command": hook + "session-context", "timeout": 20}]}],
        "PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": hook + "shell-guard", "timeout": 90}]},
            {"matcher": "Edit|Write|MultiEdit|NotebookEdit",
             "hooks": [{"type": "command", "command": hook + "edit-guard", "timeout": 20}]},
            {"matcher": "mcp__.*create_pull_request",
             "hooks": [{"type": "command", "command": hook + "pr-gate", "timeout": 90}]}],
        "Stop": [{"hooks": [{"type": "command", "command": hook + "stop-verify", "timeout": 20}]}],
    }
    write_json(settings_path, settings)
    # Org connectors into project MCP config (data connectors from init are kept)
    mcp = load_json(target / ".mcp.json")
    mcp.setdefault("mcpServers", {}).update(load_json(PLUGINS / "sdlc-connectors/.mcp.json")["mcpServers"])
    write_json(target / ".mcp.json", mcp)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    write_json(aisdlc / "VERSION.json", {"source": a.standard, "commit": sha or None, "plugins": STACK_PLUGINS[a.stack],
                                         "vendored_at": dt.date.today().isoformat()})
    print("\n".join(copied))
    print(f"\nVendored {len(copied)} components into {target}/.claude (plugins for this repo disabled in "
          f".claude/settings.json to avoid duplicates). Re-run to update; commit the result.")
    return 0


# ---------------------------------------------------------------- doctor

def cmd_doctor(a) -> int:
    t = Path(a.target).resolve()
    results: list[tuple[str, str]] = []

    def check(level_if_bad: str, ok: bool, message: str):
        results.append(("ok" if ok else level_if_bad, message))

    check("FAIL", (t / ".git").exists(), "git repository")
    claude_md = t / "CLAUDE.md"
    text = claude_md.read_text(encoding="utf-8") if claude_md.is_file() else ""
    check("FAIL", bool(text), "CLAUDE.md present")
    if text:
        check("FAIL", "{{" not in text, "CLAUDE.md has no unrendered {{placeholders}}")
        check("WARN", "<!-- fill in" not in text, "CLAUDE.md 'fill in' sections completed")
        check("WARN", len(text.splitlines()) <= 100, f"CLAUDE.md fits on a page (<=100 lines; {len(text.splitlines())})")
    manifest = t / ".ai" / "repo.yaml"
    data = None
    if manifest.is_file():
        try:
            import yaml  # type: ignore
            data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        except ImportError:
            results.append(("WARN", "PyYAML missing: manifest only checked for presence (pip install pyyaml)"))
        except Exception as exc:  # invalid YAML
            results.append(("FAIL", f".ai/repo.yaml does not parse: {exc}"))
    check("FAIL", manifest.is_file(), ".ai/repo.yaml present")
    if isinstance(data, dict):
        repo, tests = data.get("repo") or {}, data.get("tests") or {}
        checks = data.get("checks") or []
        check("FAIL", repo.get("stack") in STACKS + ("backend",), f"repo.stack is a known stack ({repo.get('stack')})")
        check("FAIL", bool(checks) and all(isinstance(c, dict) and c.get("id") and c.get("run") for c in checks),
              "checks: non-empty list of {id, run}")
        check("FAIL", bool(tests.get("junit_glob")), "tests.junit_glob set (needed for AC coverage)")
        check("FAIL", "{files}" in str(tests.get("run_files", "")), "tests.run_files contains {files} (fail-to-pass)")
        check("FAIL", bool(tests.get("test_patterns")), "tests.test_patterns set")
        ci = data.get("ci")
        check("FAIL", ci is None or (isinstance(ci, dict) and ci.get("runtime") in (None, "node", "python")),
              "ci: optional mapping; runtime is node or python")
    gi = (t / ".gitignore").read_text(encoding="utf-8") if (t / ".gitignore").is_file() else ""
    check("FAIL", ".ai/evidence/" in gi, ".gitignore excludes .ai/evidence/")
    repo_on = load_json(t / ".claude" / "settings.json").get("enabledPlugins", {}).get("sdlc-core@ai-sdlc") is True
    managed_on = False
    for f in MANAGED_FILES:
        try:
            managed_on = managed_on or load_json(f).get("enabledPlugins", {}).get("sdlc-core@ai-sdlc") is True
        except (OSError, ValueError, AttributeError):   # Claude Code itself refuses to start on a broken policy file
            results.append(("WARN", f"managed settings file {f} can't be read as a JSON object"))
    vendored = (t / ".claude" / "aisdlc" / "VERSION.json").is_file()
    if repo_on or managed_on or vendored:
        how = "managed settings file" if managed_on else "repo settings" if repo_on else "vendored copy"
        results.append(("ok", f"plugins: sdlc-core from the {how}"))
    else:
        results.append(("NOTE", "plugins: none set at repo level; expected from the organization's managed settings "
                                "(confirm with /plugin in Claude Code)"))
    caller = t / ".github" / "workflows" / "ai-sdlc.yml"
    calls = caller.is_file() and "/.github/workflows/sdlc.yml@" in caller.read_text(encoding="utf-8")
    check("WARN", calls, "CI: .github/workflows/ai-sdlc.yml calls the shared workflow")
    legacy = [w for w in LEGACY_WORKFLOWS if (t / ".github" / "workflows" / w).is_file()]
    check("WARN", not legacy, "no per-repo workflow copies left" + (
        f" (delete {', '.join(legacy)}: the shared workflow replaces them)" if legacy else ""))
    check("FAIL", sys.version_info >= (3, 9), f"python >= 3.9 ({sys.version.split()[0]})")
    for tool, level in (("git", "FAIL"), ("gh", "WARN")):
        check(level, shutil.which(tool) is not None, f"{tool} on PATH")
    stack = (data or {}).get("repo", {}).get("stack") if isinstance(data, dict) else None
    if stack in ("mfe", "frontend"):
        check("WARN", shutil.which("node") is not None, "node on PATH")
    width = max(len(m) for _, m in results)
    for level, message in results:
        print(f"{level:4}  {message}")
    fails = sum(1 for lvl, _ in results if lvl == "FAIL")
    warns = sum(1 for lvl, _ in results if lvl == "WARN")
    print(f"\n{'-' * min(width, 60)}\n{fails} failure(s), {warns} warning(s)")
    return 1 if fails else 0


# ---------------------------------------------------------------- knowledge-audit

REQUIRED_KB = ["id", "title", "scope", "type", "status", "owner", "provenance", "created", "review_by"]


def front_matter(text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    meta = {}
    for line in (m.group(1).splitlines() if m else []):
        kv = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*?)\s*(?:#.*)?$", line)
        if kv:
            meta[kv.group(1)] = kv.group(2).strip().strip("'\"")
    return meta


def cmd_knowledge_audit(a) -> int:
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    problems = 0
    files = sorted(p for p in Path(a.dir).rglob("*.md") if p.name.lower() != "readme.md")
    for path in files:
        meta = front_matter(path.read_text(encoding="utf-8"))
        missing = [k for k in REQUIRED_KB if not meta.get(k)]
        issue = None
        if missing:
            issue = f"missing {', '.join(missing)}"
        elif meta.get("status") == "active":
            try:
                if dt.date.fromisoformat(meta["review_by"]) < today:
                    issue = f"stale: review_by {meta['review_by']} (owner {meta.get('owner')})"
            except ValueError:
                issue = f"bad review_by date {meta['review_by']!r}"
        if issue:
            problems += 1
            print(f"{path}: {issue}")
    print(f"{len(files)} entr{'y' if len(files) == 1 else 'ies'} checked, {problems} need attention")
    return 1 if problems else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init")
    i.add_argument("--target", required=True)
    i.add_argument("--stack", required=True, choices=STACKS)
    i.add_argument("--name")
    i.add_argument("--jira", default="PROJ")
    i.add_argument("--description")
    i.add_argument("--standard", "--marketplace", dest="standard", default="amarkum/prd-to-pr-rule-skills",
                   help="owner/repo of the standard (the marketplace and the shared workflow)")
    i.add_argument("--extras", action="store_true", help="also write the optional REVIEW.md, bands, READMEs, PR template")
    i.add_argument("--repo-plugins", action="store_true",
                   help="also write .claude/settings.json with the plugins, for organizations without managed settings")
    i.add_argument("--force", action="store_true")
    v = sub.add_parser("vendor")
    v.add_argument("--target", required=True)
    v.add_argument("--stack", required=True, choices=STACKS)
    v.add_argument("--standard", "--marketplace", dest="standard", default="amarkum/prd-to-pr-rule-skills")
    d = sub.add_parser("doctor")
    d.add_argument("--target", default=".")
    k = sub.add_parser("knowledge-audit")
    k.add_argument("dir")
    k.add_argument("--today", help="YYYY-MM-DD (default: today)")
    a = ap.parse_args(argv)
    return {"init": cmd_init, "vendor": cmd_vendor, "doctor": cmd_doctor, "knowledge-audit": cmd_knowledge_audit}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
