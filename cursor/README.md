# Using the standard in Cursor

Cursor reads the same plugin repository. Each plugin ships a `.cursor-plugin/plugin.json` next to its
`.claude-plugin/plugin.json`, and the repo root has `.cursor-plugin/marketplace.json`. Skills, subagents, rules and the
hook script are shared; only the hook wiring differs.

## Option A: team marketplace (recommended; Teams and Enterprise plans)

1. Dashboard → Plugins → import this repository as a team marketplace (GitHub, GitLab, Bitbucket and Azure DevOps all work).
2. Set `sdlc-core` and `sdlc-connectors` to **Required**. Set each repo team's stack pack (`stack-airflow`, `stack-frontend`,
   `stack-mfe`) to Default On or Required for its group.
3. Developers get these automatically:

| Component | How it is used in Cursor |
|---|---|
| `rules/*.mdc` (sdlc-core) | Always-apply rules (workflow contract, security, tests and evidence) |
| `skills/*/SKILL.md` | Run with `/prd-review`, `/verify` and so on. Stack skills auto-load through `paths` (e.g. `dags/**`) |
| `agents/*.md` | Subagents. `readonly: true` keeps the analyst, investigator, QA and reviewer read-only |
| `hooks/cursor-hooks.json` | `beforeShellExecution` (shell guard and PR gate), `preToolUse` matcher `Write` (edit guard), `beforeMCPExecution` (PR gate), `sessionStart` (repo context), `stop` (verify reminder) |
| `mcp.json` (sdlc-connectors) | Atlassian Rovo MCP and Sentry MCP over OAuth |

## Option B: vendored into the repo (no marketplace, cloud agents, other tools)

```bash
python3 tools/aisdlc.py vendor --target ../payroll-mfe --stack mfe
```

This writes skills to `.claude/skills/` and agents to `.claude/agents/` (Cursor reads both), rules to
`.cursor/rules/aisdlc-*.mdc`, hooks to `.cursor/hooks.json`, and connectors to `.cursor/mcp.json`, all pinned in
`.claude/aisdlc/VERSION.json`. Re-run it to update, and review the diff in a PR.

## Per-repo files Cursor reads either way

- `AGENTS.md`, read natively including nested files, and `CLAUDE.md`, which Cursor reads like AGENTS.md.
- `.cursor/mcp.json` for data connectors (MongoDB read-only, DBHub, Airflow). Use `${env:VAR}` interpolation there;
  Claude Code's `.mcp.json` uses `${VAR}`.
- `.cursor/BUGBOT.md`, the review guidance Bugbot reads (project rules don't apply to Bugbot).

## Headless and cloud

- **CLI in CI**: `agent -p "<prompt>" --output-format json` with `CURSOR_API_KEY`; add `--force` for file edits.
  Follow Cursor's "restricted autonomy" advice: let the agent edit, and let later deterministic steps run `git`, `gh` and
  `evidence.py`.
- **Cloud agents**: use `.cursor/environment.json` for the toolchain install (`pip install -r ...`, `npm ci`). Cloud agents
  run only command hooks from `.cursor/hooks.json` (and team or enterprise hooks), so use vendored mode for full guardrails there.

## Behaviour differences to know

- Cursor does not enforce `ask` on `preToolUse`, so the edit guard turns "ask" into "deny" with a note to have a
  developer approve. The shell hook supports `ask` natively.
- In plugin hooks the script path is written as `${CURSOR_PLUGIN_ROOT:-.}/hooks/...`. This works whether Cursor expands
  the variable or runs plugin hooks from the plugin root. Confirm it on your Cursor version with a blocked
  `git push --force`.
- If "Include third-party plugins, skills and other configs" is on and a developer also has the Claude Code plugins
  installed, some hooks may run twice. That is harmless (deny wins), but you can turn the toggle off.

## Verify on your machine (2 minutes)

1. Open a repo initialised with `tools/aisdlc.py init`. The first agent message should mention the repo stack (sessionStart).
2. Ask the agent to run `git push --force` and expect a block.
3. On a `feat/<KEY>-x` branch with a draft spec, ask for a code edit. Expect it to be blocked until the spec is approved.
4. Type `/prd-review` and point it at a PRD.
