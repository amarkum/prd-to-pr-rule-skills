# Changelog

## Unreleased

Breaking: the standard is Claude Code only.
- Removed the Cursor marketplace, plugin manifests, hook wiring (`cursor-hooks.json`, `--format cursor`), `.mdc` rule
  format, `.cursor/` templates and `cursor/` docs. Rules are now `rules/*.md`, injected by the SessionStart hook.
- Product repos get a single `CLAUDE.md` (Commands, Architecture, Conventions, Things Claude gets wrong, Verifying your
  work) instead of `AGENTS.md` plus an import. `aisdlc.py doctor` checks `CLAUDE.md`. Existing repos: move the content
  of `AGENTS.md` into `CLAUDE.md`.

## 1.0.0 (2026-10-22)

Initial standard.
- sdlc-core: PRD gate with product-owner feedback; context, spec, tasks, build, verify, pr-open and learn skills; five
  subagents; always-on rules; hooks for shell, edit, spec-approval, PR-evidence and stop-verify guards; evidence
  scripts (PRD lint, AC coverage, fail-to-pass, evidence manifest, Atlassian REST client).
- sdlc-connectors: Atlassian Rovo and Sentry MCP; schema-lookup and history-lookup; schema snapshot and diff.
- Stack packs: airflow, frontend and mfe, as path-activated skills.
- Templates and `tools/aisdlc.py` (init, vendor, doctor, knowledge-audit); CI workflows; managed-settings policy.
