# prd-to-pr-rule-skills: the AI SDLC standard for Claude Code

Turn a Confluence PRD into a reviewed pull request with test evidence, using **Claude Code**, across an **Airflow**
data repo, **Module Federation micro-frontends** and a **React frontend**. The process follows the six-stage loop of
Anthropic's [AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook): every
stage commits an artifact the next stage reads, humans decide at the gates, and hooks enforce the gates as code.
Incomplete PRDs go back to the product owner as concrete questions. Lessons and incidents compound into rules,
checks and evals.

**Read first:** [`docs/playbook.html`](docs/playbook.html) (also as [`docs/playbook.pdf`](docs/playbook.pdf)) covers
the approach, what goes in CLAUDE.md, skills, hooks, plugins and connectors, the setups to try, and the research.

## The loop

```
        ┌──────────────────────────────────────────────────────────────────────────────────────────┐
        ▼                                                                                          │
 1 PLAN            2 DESIGN              3 BUILD                 4 TEST          5 DEPLOY            6 MAINTAIN
 Confluence PRD -> context.md        ->  plan.md (plan mode) ->  verify      ->  draft PR         -> control bands
 PRD gate          spec.md               test-first tasks        evidence.py     REVIEW.md review    triage -> intent.md
 intent.md         (human approves)      locked tests            CI re-runs      humans merge        learn -> rules, evals
   NOT READY: questions to the product owner (Confluence comment + Jira task)    release gate
```

| Stage | Artifact in `specs/<KEY>/` | Gate (enforced by) |
|---|---|---|
| Plan | `prd.md`, `prd-review.md`, `intent.md` | PRD READY (`prd_lint.py` + rubric review) and accepted by the product owner |
| Design | `context.md`, `spec.md` | a human approves the spec (edit hook: agents can't write `status: approved`; no code before it) |
| Build | `plan.md`, then tests and code | the plan is accepted (edit hook: no code before it; agents can't accept a risk: high plan) |
| Test | `.ai/evidence/` | checks, AC coverage, fail-to-pass, diff matches `plan.md`, locked tests unchanged (`evidence.py`; PR hooks) |
| Deploy | the PR and its review findings | draft PRs only; code owners merge; production releases need `RELEASE_APPROVAL` (shell hook) |
| Maintain | `retro.md`, knowledge entries, new `intent.md` | `bands.py` decides when Claude is invoked and what it may do |

## Quick start

```bash
# 1. Onboard a repo (writes CLAUDE.md, REVIEW.md, .ai/repo.yaml, .ai/bands.yaml, evals/, .claude/settings.json,
#    connectors and the stage workflows)
python3 tools/aisdlc.py init --target ../data-airflow --stack airflow --jira PAY --description "Payroll pipelines"
python3 tools/aisdlc.py doctor --target ../data-airflow

# 2. In the repo, with Claude Code: trust the folder (the plugins install from this marketplace), then
/sdlc-core:prd-to-pr https://<site>.atlassian.net/wiki/spaces/PAY/pages/<id>

# Environments that don't install marketplace plugins: vendor a pinned copy into the repo
python3 tools/aisdlc.py vendor --target ../payroll-mfe --stack mfe
```

Requirements: Python 3.9+ (PyYAML for `evidence.py run`), git, gh. Node only for the web stacks and the PDF build.
CI automation (the `ai-*` workflows) is off until you set the repository variable `AISDLC_AUTOMATION=on`.

## What's in the repo

| Path | What it is |
|---|---|
| `plugins/sdlc-core/` | Skills per stage (`prd-to-pr`, `prd-review`, `context-gather`, `spec-write`, `plan`, `build`, `verify`, `pr-open`, `pr-babysit`, `triage`, `learn`), 5 subagents, always-on rules, hooks, scripts (`prd_lint`, `ac_coverage`, `fail_to_pass`, `evidence`, `agent_evals`, `bands`, `atlassian`), evals |
| `plugins/sdlc-connectors/` | Atlassian Rovo and Sentry MCP; `schema-lookup`, `history-lookup`; `schema_snapshot.py` (data-contract diff) |
| `plugins/stack-airflow/`, `stack-frontend/`, `stack-mfe/` | Path-activated stack skills with references and templates |
| `.claude-plugin/` | The marketplace catalog |
| `templates/repo/` | What `aisdlc.py init` writes into product repos: `CLAUDE.md`, `REVIEW.md`, manifests, bands, evals, and the `ai-prd-intake`, `ai-design`, `ai-build`, `ai-evidence`, `ai-review`, `ai-agent-evals`, `ai-maintain`, `ai-learn` workflows |
| `tools/aisdlc.py` | `init`, `vendor`, `doctor`, `knowledge-audit` |
| `standards/` | Confluence PRD template; `.ai/repo.yaml` JSON Schema |
| `policy/` | Managed settings: a standard tier and a regulated tier |
| `knowledge/` | Org and stack lessons with owners and review dates |
| `docs/` | Playbook (HTML and PDF), research survey, eval results |
| `examples/` | Example PRDs (incomplete and fixed), intent, spec and plan, three-stack JUnit, `demo.py` |
| `tests/` | 96 unit tests (Python 3.9 and 3.13) |

## Proof

```bash
make test      # 96 unit tests: lint, coverage, fail-to-pass, evidence and plan checks, evals runner, bands, hooks, CLI
make validate  # claude plugin validate --strict: marketplace + 5 plugins
make demo      # PRD gate -> AC coverage -> evidence -> PR gate deny/allow -> locked test and release gate
make evals     # behavioural evals with real model runs (results: docs/evals.md)
make pdf       # rebuild docs/playbook.pdf
```

The eval suite measured the guardrails. Asked to implement against a draft spec, the agent stopped and asked for
approval with the plugin (score 1.0), and wrote the code anyway without it (0.5).

## Changing the standard

See [CONTRIBUTING.md](CONTRIBUTING.md): semver per plugin, the manifest and the marketplace in lockstep (a test
enforces it), an eval case for behaviour changes, CODEOWNERS review, and `claude plugin tag` to release. `CLAUDE.md`
describes how to work on this repo.
