# ai-sdlc standard: working on this repo

This repo is the organisation's AI SDLC standard: a plugin marketplace for Claude Code and Cursor, plus the
templates, policy, knowledge base and playbook around it. Product repos consume it; they don't copy it, except in
vendored mode.

## Layout

- `plugins/<name>/`: one plugin each, with `.claude-plugin/plugin.json` **and** `.cursor-plugin/plugin.json`
  (keep versions equal). Components: `skills/`, `agents/`, `rules/` (Cursor-native; Claude gets them through the
  SessionStart hook), `hooks/hooks.json` (Claude) and `hooks/cursor-hooks.json` (Cursor), `scripts/`, `evals/`.
- `.claude-plugin/marketplace.json` and `.cursor-plugin/marketplace.json`: the two catalogs.
- `templates/repo/`: files `tools/aisdlc.py init` writes into product repos (common plus per-stack overlays).
- `tools/aisdlc.py`: init, vendor, doctor and knowledge-audit.
- `standards/`: the PRD template and the repo-manifest schema. `policy/`: managed settings. `knowledge/`: org and
  stack lessons.
- `docs/`: the playbook (HTML and PDF), research and eval results. `examples/`: PRDs, spec, JUnit, `demo.py`.

## Commands

- `make test`: unit tests (Python 3.9+, stdlib + PyYAML). Run them before every commit.
- `make validate`: `claude plugin validate --strict` for the marketplace and every plugin.
- `make demo`: the deterministic end-to-end demo. `make evals`: behavioural evals (they cost money).
- `make details`: always-on token cost per plugin. Keep sdlc-core under about 2k tokens.

## Conventions

- Scripts and hooks: Python 3.9+, standard library only (PyYAML optional), self-contained (no cross-imports), each with
  unittest coverage in `tests/`. Exit codes are documented in the docstring.
- Skills: `name` equals the folder name. The description says what the skill does and when to use it (≤1024 characters).
  The body stays under 200 lines, procedural, with detail in `references/`. Use `${CLAUDE_PLUGIN_ROOT}` for bundled
  scripts, and add the Cursor path note.
- Enforcement belongs in hooks or scripts, not prose. If a rule matters, add a check and a test.
- Any behaviour change to a skill or hook needs an eval case, or a reason why not.
- Release: see CONTRIBUTING.md (semver, CHANGELOG, `claude plugin tag`).
