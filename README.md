# prd-to-pr-rule-skills: the AI SDLC standard

Turn a Confluence PRD into a reviewed pull request with test evidence, using **Claude Code**, across an
**Airflow** data repo, **Module Federation micro-frontends** and a **React frontend**. Incomplete PRDs go back to the
product owner as concrete questions. Specs are approved by a human. Every PR carries computed evidence. Lessons
compound into rules and checks.

**Read first:** [`docs/playbook.html`](docs/playbook.html) (also as [`docs/playbook.pdf`](docs/playbook.pdf)) covers
the approach, the changes to the draft plan, what goes in rules, skills, hooks, plugins and connectors, the setups to
try, and the research behind it.

## How it works

```
Confluence PRD ──► G1 PRD ready? ──► context ──► spec ──► G2 approved by a human? ──► tasks ──► build (test-first)
      ▲   NO: questions to the product owner                                                           │
      └──────────────── (Confluence comment + Jira task)                                               ▼
learn ◄── G3 human merge ◄── CI re-run + attested evidence + AI review ◄── draft PR ◄── verify (evidence.py)
```

- **One plugin marketplace.** Skills, subagents, always-on rules, hooks and connectors ship as versioned Claude Code
  plugins that every repo enables from `.claude/settings.json`.
- **Gates are code.** Hooks block code edits before the spec is approved, block agents from approving specs, block PRs
  without passing evidence for the current commit, and block secrets, force-pushes, merges and data-store writes.
- **Evidence is computed.** Tests are named after acceptance criteria (`PAY-412 AC-3: ...`). `ac_coverage.py` maps JUnit
  to ACs, `fail_to_pass.py` proves new tests fail on the base commit, and `evidence.py` hashes everything at a SHA. CI
  re-runs it and attests the result.
- **One builder, three stacks.** `.ai/repo.yaml` declares the stack and commands; stack skills load by file path.

## Quick start

```bash
# 1. Onboard a repo (writes CLAUDE.md, REVIEW.md, .ai/repo.yaml, .claude/settings.json, connectors, CI workflows)
python3 tools/aisdlc.py init --target ../data-airflow --stack airflow --jira PAY --description "Payroll pipelines"
python3 tools/aisdlc.py doctor --target ../data-airflow

# 2. Claude Code: open the repo, trust the folder (the plugins install from this marketplace), then
/sdlc-core:prd-to-pr https://<site>.atlassian.net/wiki/spaces/PAY/pages/<id>

# Environments that don't install marketplace plugins: vendor a pinned copy into the repo
python3 tools/aisdlc.py vendor --target ../payroll-mfe --stack mfe
```

Requirements: Python 3.9+ (PyYAML for `evidence.py run`), git, gh. Node only for the web stacks and the PDF build.

## What's in the repo

| Path | What it is |
|---|---|
| `plugins/sdlc-core/` | Workflow skills (`prd-to-pr`, `prd-review`, `context-gather`, `spec-write`, `task-breakdown`, `build`, `verify`, `pr-open`, `learn`), 5 subagents, always-on rules, hooks, scripts, evals |
| `plugins/sdlc-connectors/` | Atlassian Rovo and Sentry MCP; `schema-lookup`, `history-lookup`; `schema_snapshot.py` (data-contract diff) |
| `plugins/stack-airflow/`, `stack-frontend/`, `stack-mfe/` | Path-activated stack skills with references and templates |
| `.claude-plugin/` | The marketplace catalog |
| `templates/repo/` | What `aisdlc.py init` writes into product repos (common plus per-stack) |
| `tools/aisdlc.py` | `init`, `vendor`, `doctor`, `knowledge-audit` |
| `standards/` | Confluence PRD template; `.ai/repo.yaml` JSON Schema |
| `policy/` | Managed settings for enterprise rollout (allowlists, telemetry, plugin enforcement) |
| `knowledge/` | Org and stack lessons with owners and review dates |
| `docs/` | Playbook (HTML and PDF), research survey, eval results |
| `examples/` | Example PRDs (incomplete and fixed), spec, three-stack JUnit, `demo.py` |
| `tests/` | 76 unit tests (Python 3.9 and 3.13) |

## Proof

```bash
make test      # 76 unit tests: lint, coverage, fail-to-pass, evidence, Atlassian client, hooks, CLI, manifests
make validate  # claude plugin validate --strict: marketplace + 5 plugins
make demo      # PRD gate -> AC coverage -> fail-to-pass evidence -> PR gate deny/allow, in a throwaway repo
make evals     # behavioural evals with real model runs (results: docs/evals.md)
make pdf       # rebuild docs/playbook.pdf
```

The eval suite measured the guardrails. Asked to implement against a draft spec, the agent stopped and asked for
approval with the plugin (score 1.0), and wrote the code anyway without it (0.5).

## Changing the standard

See [CONTRIBUTING.md](CONTRIBUTING.md): semver per plugin, both manifests in lockstep (a test enforces it), an eval
case for behaviour changes, CODEOWNERS review, and `claude plugin tag` to release. `CLAUDE.md` describes how to work
on this repo.
