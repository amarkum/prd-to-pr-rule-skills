# sdlc-core: the AI-native loop, PRD to verified pull request

The workflow half of the AI SDLC standard, organised around the six-stage loop of Anthropic's AI-native SDLC
playbook. Plan: a PRD gate that
reports gaps back to the product owner and writes `intent.md`. Design: context and a human-approved `spec.md`. Build:
an accepted `plan.md`, then test-first code. Test: evidence with fail-to-pass, plan match and locked tests. Deploy: a
draft PR, review and a babysat fix loop; humans merge and authorise releases. Maintain: control bands, triage into new
intents, and lessons that compound. Deterministic hooks enforce the gates, so they hold even when a prompt is ignored.

| Component | What it is |
|---|---|
| `skills/` | `prd-to-pr` (orchestrator, run it with `/sdlc-core:prd-to-pr <PRD link or KEY>`), `prd-review`, `context-gather`, `spec-write`, `plan`, `build`, `verify`, `pr-open`, `pr-babysit`, `triage`, `learn` |
| `agents/` | `prd-analyst`, `repo-investigator`, `qa-verifier`, `pr-reviewer` (all read-only) and `builder` |
| `rules/` | Always-on rules, injected at session start by the SessionStart hook (plugins can't ship a CLAUDE.md) |
| `hooks/` | `hooks.json` wiring Claude Code events to `aisdlc_hooks.py` |
| `scripts/` | `prd_lint.py`, `ac_coverage.py`, `fail_to_pass.py`, `evidence.py` (also `lock`), `agent_evals.py`, `bands.py`, `atlassian.py`: standard library only, also used by CI |

## Install

Claude Code: `/plugin marketplace add amarkum/prd-to-pr-rule-skills`, then `/plugin install sdlc-core@ai-sdlc`.
Teams usually enable it per repo from `.claude/settings.json`, which `tools/aisdlc.py init` writes.

## Requirements

`python3` 3.9 or later on PATH, plus `git`, and `gh` for PR creation. `evidence.py run` needs PyYAML (`pip install pyyaml`).

## Controls

- `AISDLC_HOOKS=off` turns every hook off (to repair the hooks themselves). `AISDLC_SPEC_GATE=off` turns off only the
  "no code before the spec is approved and the plan accepted" gates.
- `RELEASE_APPROVAL=<change ticket>`, set by a release manager for one session, lets production release commands
  through to a per-command confirmation; without it they are blocked.
- Guard hooks are fail-closed (`onFailure: block`): if the hook can't run, the tool call is blocked.

Privacy: the plugin itself sends nothing anywhere. Data leaves only through the connectors you configure
(see `sdlc-connectors`) and through `git push` or `gh`.
