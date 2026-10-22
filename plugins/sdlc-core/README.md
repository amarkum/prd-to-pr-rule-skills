# sdlc-core: PRD to verified pull request

The workflow half of the AI SDLC standard. It takes a Confluence PRD through a gate that reports gaps back to the product
owner, then through context, spec (human-approved), tasks, test-first build, verification with fail-to-pass evidence,
a draft PR and a learning step. Deterministic hooks enforce the gates, so they hold even when a prompt is ignored.

| Component | What it is |
|---|---|
| `skills/` | `prd-to-pr` (orchestrator, run it with `/sdlc-core:prd-to-pr <PRD link or KEY>`), `prd-review`, `context-gather`, `spec-write`, `task-breakdown`, `build`, `verify`, `pr-open`, `learn` |
| `agents/` | `prd-analyst`, `repo-investigator`, `qa-verifier`, `pr-reviewer` (all read-only) and `builder` |
| `rules/` | Always-on rules, injected at session start by the SessionStart hook (plugins can't ship a CLAUDE.md) |
| `hooks/` | `hooks.json` wiring Claude Code events to `aisdlc_hooks.py` |
| `scripts/` | `prd_lint.py`, `ac_coverage.py`, `fail_to_pass.py`, `evidence.py`, `atlassian.py`: standard library only, also used by CI |

## Install

Claude Code: `/plugin marketplace add amarkum/prd-to-pr-rule-skills`, then `/plugin install sdlc-core@ai-sdlc`.
Teams usually enable it per repo from `.claude/settings.json`, which `tools/aisdlc.py init` writes.

## Requirements

`python3` 3.9 or later on PATH, plus `git`, and `gh` for PR creation. `evidence.py run` needs PyYAML (`pip install pyyaml`).

## Controls

- `AISDLC_HOOKS=off` turns every hook off (to repair the hooks themselves). `AISDLC_SPEC_GATE=off` turns off only the
  "no code before the spec is approved" gate.
- Guard hooks are fail-closed (`onFailure: block`): if the hook can't run, the tool call is blocked.

Privacy: the plugin itself sends nothing anywhere. Data leaves only through the connectors you configure
(see `sdlc-connectors`) and through `git push` or `gh`.
