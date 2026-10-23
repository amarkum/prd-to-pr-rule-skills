# ai-sdlc standard: working on this repo

This repo is the organisation's AI SDLC standard for Claude Code: a plugin marketplace plus the templates, policy,
knowledge base and docs around it. Product repos consume it without copying it: managed settings install the plugins on
every machine, and each repo's one-file CI caller runs the shared workflow. Merging to `main` is the release.

## Layout

- `plugins/<name>/`: one plugin each, with `.claude-plugin/plugin.json` and no `version` (installs track the commit).
  Components: `skills/` (one or more per stage of the loop), `agents/`, `rules/` (always-on text, injected by the
  SessionStart hook because plugins can't ship a CLAUDE.md), `hooks/hooks.json`, `scripts/`, `evals/`.
  `sdlc-standard` is the bundle that depends on all the others; managed settings enable it.
- `.claude-plugin/marketplace.json`: the catalog.
- `templates/repo/`: files `tools/aisdlc.py init` writes into product repos: `common/` plus the stack overlay, and
  `extras/` on request. Only what is specific to a repo belongs there.
- `.github/workflows/sdlc.yml`: the shared, reusable workflow every product repo calls; `.github/actions/toolchain/`
  installs a repo's toolchain from its `.ai/repo.yaml`. `validate.yml` is this repo's own CI.
- `tools/aisdlc.py`: init, vendor (fallback), doctor and knowledge-audit. `tools/validate_plugins.py`: `make validate`.
- `standards/`: the PRD template and the repo-manifest schema. `policy/`: managed settings. `knowledge/`: org and
  stack lessons.
- `docs/site/`: the interactive pages (plain HTML, CSS and JS; content in `assets/data.js` and `assets/companies.js`).
  `docs/playbook.pdf` is built from `docs/site/playbook.html` (`make pdf`). `docs/research.md`: sourced notes behind the
  companies page. `examples/`: PRDs, intent, spec, plan, JUnit, `demo.py`.
- `docs/adoption/`: the adoption plan (page, execution tracker, source vision) and a reference starter kit. Nothing in it
  ships through the marketplace; parts of the kit move into `plugins/` through the normal PR and eval process.

## Commands

- `make test`: unit tests (Python 3.9+, stdlib + PyYAML). Run them before every commit; healthy output ends in `OK`.
- `make validate`: strict validation of the marketplace and every plugin (`tools/validate_plugins.py`; the omitted
  `version` is the only warning it allows).
- `make demo`: the deterministic end-to-end demo. `make evals`: behavioural evals (they cost money).
- `make details`: always-on token cost per plugin. Keep sdlc-core under about 2k tokens.

## Conventions

- Scripts and hooks: Python 3.9+, standard library only (PyYAML optional), self-contained (no cross-imports), each with
  unittest coverage in `tests/`. Exit codes are documented in the docstring.
- Skills: `name` equals the folder name. The description says what the skill does and when to use it (≤1024 characters).
  The body stays under 200 lines, procedural, with detail in `references/`. Use `${CLAUDE_PLUGIN_ROOT}` for bundled
  scripts.
- Enforcement belongs in hooks or scripts, not prose. If a rule matters, add a check and a test.
- Any behaviour change to a skill or hook needs an eval case, or a reason why not.
- Claude Code only: no other agent tools' formats or folders (a test checks this).
- Never add `version` to a plugin manifest or the marketplace (a test checks this). A new plugin goes into the
  `sdlc-standard` bundle's `dependencies` (a test checks this too).
- Workflow changes go in the shared `sdlc.yml`, never in templates that repos copy.
- Release: merge to `main`, with a dated CHANGELOG line. See CONTRIBUTING.md.
