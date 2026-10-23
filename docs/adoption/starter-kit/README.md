# Agentic SDLC starter kit

A working kit that makes a pilot repository agent-ready: artifact templates, repository context,
standard `make` targets, guard hooks, specialist subagents, workflow skills, an agent eval harness,
CI workflows and plugin packaging. The plan that explains why and when is `../index.html`.

Requirements: git, make, Python 3.8 or later (hooks and gate scripts use only the standard
library), Claude Code. The eval harness also needs PyYAML.

## Install into a pilot repository

```bash
./install.sh /path/to/pilot-repo             # never overwrites; writes *.agentic-sdlc.* next to clashes
./install.sh /path/to/pilot-repo --with-ci   # also copies the GitHub workflows
```

Then, in the pilot repository:
1. Fill in `CLAUDE.md`, or run `/init` first and merge. Keep it short: commands, architecture,
   conventions, known traps, must-not-change rules.
2. Set `BUILD_CMD`, `LINT_CMD` and `TEST_CMD` in the `Makefile` and make `make verify` pass.
3. Tune production and non-production names in `.claude/hooks/prod_boundary_guard.py`, or set
   `PROD_NAME_REGEX`, `NONPROD_NAME_REGEX` and `PROTECTED_BRANCH_REGEX`.
4. Add CODEOWNERS for `.claude/settings.json`, `.claude/hooks/` and `.claude/frozen-tests.txt`.
5. Run `make hooks-test` and `python3 evals/run_evals.py --self-test`.
6. Commit on a branch and open a PR. Agent configuration is reviewed like production code.

## What is inside

| Path | What it does |
|---|---|
| `CLAUDE.md.template` | Repository context: commands, architecture, conventions, known traps, must-not-change |
| `Makefile.template` | `make build`, `lint`, `test`, `verify` (plus `verify-frozen`, `verify-artifacts`, `hooks-test`, `evals`) |
| `docs/changes/_templates/` | intent.md, spec.md, plan.md, evidence.md, release-manifest.yaml |
| `docs/changes/README.md` | Change classes (trivial, standard, significant, high-risk) and the lifecycle |
| `docs/policies/` | Policy pack format and a starter security pack |
| `.claude/settings.json` | Permission allow, ask and deny rules (secrets, guardrail files) and hook registration |
| `.claude/frozen-tests.txt` | Tests agents may not change; edited by humans only |
| `.claude/hooks/test_guard.py` | PreToolUse: denies edits to frozen tests; asks when an edit adds skip or focus markers, removes tests or deselects tests in runner config |
| `.claude/hooks/prod_boundary_guard.py` | PreToolUse on Bash: denies production changes, pushes to protected branches, secret reads and guardrail tampering; asks on production reads and unnamed-environment infrastructure changes |
| `.claude/hooks/stop_verify_gate.py` | Stop: runs `make verify` when the tree is dirty and blocks "done" on failure, at most 3 times per session |
| `.claude/hooks/tests/` | `run_hook_tests.py` (116 checks) and sample payloads |
| `.claude/agents/` | intent-agent, architecture-reviewer, security-reviewer, test-engineer, verifier, review-synthesizer |
| `.claude/skills/` | `/intent`, `/spec`, `/plan-change`, `/verify-change`, `/release-manifest`, `/incident-to-intent` |
| `scripts/check_frozen_tests.py` | CI gate: no frozen test changed since the merge base |
| `scripts/check_artifacts.py` | CI gate: each change folder has the artifacts and approvals its class requires |
| `evals/` | Headless `claude -p` eval harness and an example case (EVAL-0001) |
| `metrics/` | Feature-level record schema and the metric formulas |
| `ci/github/` | PR review with `anthropics/claude-code-action`, agent evals, verify |
| `packaging/` | Build the skills, agents and hooks into the `agentic-sdlc` plugin for an internal marketplace |
| `managed-settings.example.json` | Org-wide policy: no bypass mode, secret deny rules, sandbox network allowlist, telemetry |

`/plan-change` and `/verify-change` are named that way on purpose: a project skill called `plan`
would replace Claude Code's built-in `/plan` command, and one called `verify` would replace the
bundled `/verify` skill.

## How the guardrails fit together

| Layer | Stops | Where |
|---|---|---|
| Permission deny rules | Reading secret files, editing hooks, settings and the frozen list | `.claude/settings.json`, managed settings |
| PreToolUse hooks | Weakening tests, crossing the production boundary, tampering with guardrails | `.claude/hooks/` |
| Stop hook | Declaring "done" while `make verify` fails | `.claude/hooks/stop_verify_gate.py` |
| CI gates | Anything the hooks missed: frozen tests changed, artifacts missing | `scripts/`, `ci/github/verify.yml` |
| Credentials and sandbox | Everything else: agents never hold production credentials | Identity provider, `sandbox` in managed settings |

Hooks are seatbelts, not the boundary. Pattern matching on shell commands can be evaded, so keep
the hard boundary in credentials, the sandbox and branch protection.

Day-to-day switches: `CLAUDE_VERIFY_CMD`, `CLAUDE_VERIFY_MAX_BLOCKS`, `CLAUDE_VERIFY_TIMEOUT` and
`CLAUDE_VERIFY_SKIP_REGEX` for the Stop hook; `ARTIFACTS_MODE=warn` to run the artifact gate in
shadow mode while a team learns the workflow; `ALLOW_FROZEN_CHANGE=1` for a human-approved
exception in CI.

## Test it

```bash
python3 .claude/hooks/tests/run_hook_tests.py           # 116 checks: every hook, piped sample JSON
cat .claude/hooks/tests/samples/pretooluse-bash-prod-deploy.json | python3 .claude/hooks/prod_boundary_guard.py
python3 evals/run_evals.py --self-test                   # eval cases tell good from bad; no API calls
```

## Org-wide rollout (Wave 3 onward)

1. Build the plugin: `packaging/build_plugin.sh`, then `claude plugin validate --strict dist/agentic-sdlc`.
2. Publish it from an internal marketplace repository: `.claude-plugin/marketplace.json` (see
   `packaging/marketplace.json`) plus `plugins/agentic-sdlc/`.
3. In each repository's `.claude/settings.json`, point at the marketplace and enable the plugin,
   then delete the repo copies of the skills, agents and hooks so nothing runs twice:
   ```json
   {
     "extraKnownMarketplaces": {
       "acme-engineering": { "source": { "source": "github", "repo": "acme/claude-plugins" } }
     },
     "enabledPlugins": { "agentic-sdlc@acme-engineering": true }
   }
   ```
4. Put org policy in managed settings (`managed-settings.example.json`). On macOS the file is
   `/Library/Application Support/ClaudeCode/managed-settings.json`; on Linux and WSL,
   `/etc/claude-code/managed-settings.json`. Add `strictKnownMarketplaces` to allow only approved
   marketplaces. Set `allowManagedHooksOnly` only once the guard hooks themselves are defined in
   managed settings, because it stops hooks defined anywhere else from running.
