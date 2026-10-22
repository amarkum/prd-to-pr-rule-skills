# Changelog

## 2.0.0 (2026-10-22)

Breaking. The workflow follows the six-stage loop of Anthropic's AI-native SDLC playbook (Plan, Design, Build, Test,
Deploy, Maintain): each stage commits an artifact to `specs/<KEY>/` that the next stage reads.

- Plan: `prd-review` writes `intent.md` (linked to the PRD version) on READY.
- Design: `spec-write` reads the intent, applies policy skills and records flagged concerns with their owners.
- Build: the `plan` skill replaces `task-breakdown`; `plan.md` (files that change, test-first tasks, risks, proof, locked
  tests) replaces `tasks.md`. New edit-hook gate: no code until the plan is accepted; agents can't accept the plan of a
  risk: high spec. Bug fixes commit and lock the reproducing test first (`evidence.py lock`); hooks block edits to
  locked tests.
- Test: `evidence.py` fails when the plan isn't accepted or a locked test changed, and is incomplete when the diff
  touches files `plan.md` doesn't list. New `agent_evals.py` and `ai-agent-evals.yml` regression-test CLAUDE.md, skills
  and hooks on every change to them and nightly.
- Deploy: `REVIEW.md` in the three-pass format (bugs, security, compliance with spec and plan; Important vs nit; at most
  five nits). `ai-review.yml` adds the `@claude` fix loop; new `pr-babysit` skill drives a PR to green without merging.
  New release gate: production release commands are blocked without `RELEASE_APPROVAL` and confirmed one by one with it.
  `ai-evidence.yml` triages failures read-only.
- Maintain: new `bands.py` (rolling baseline, Western Electric rules) and `ai-maintain.yml` decide when Claude is
  invoked and what it may do (1 sigma log, 2 sigma diagnose read-only, 3 sigma propose a PR or a pre-approved runbook);
  new `triage` skill writes findings as `intent.md`; `learn` adds the CLAUDE.md and eval rungs.
- New workflows `ai-design.yml` and stage triggers in `ai-build.yml`; all automation waits for `AISDLC_AUTOMATION=on`.
- Policy: `requiredMinimumVersion`; new regulated tier (`managed-settings.regulated.json`) with sandbox, credential
  isolation and managed-only permissions and hooks.

- Vendored mode writes the always-on rules to `.claude/rules/aisdlc-*.md`, so cloud sessions, scheduled tasks and
  Claude in Slack load them natively (Slack sessions don't run repo hooks); the SessionStart hook then skips them.

- Docs: interactive pages in `docs/site/` (the loop, what goes where, ways to implement, evidence, how other companies
  do it, the full playbook); `docs/playbook.pdf` is built from `docs/site/playbook.html`. `docs/research.md` adds the
  Claude-based company cases.
- Evals: `plan-gate-blocks-code` and `locked-test-stays` cover the new gates.

Migration for repos on 1.x: rename `specs/<KEY>/tasks.md` to `plan.md` in the new template's shape and set
`status: accepted`; re-run `tools/aisdlc.py init` to pick up the new templates (existing files are kept).

Also breaking: the standard is Claude Code only.
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
