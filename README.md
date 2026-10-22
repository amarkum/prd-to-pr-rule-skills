# AI SDLC standard for Claude Code: from a Confluence PRD to a reviewed pull request

This repository is an organisation's **AI software delivery standard**, built for **Claude Code**. It turns a product
requirements document (PRD) in Confluence into a reviewed pull request with test evidence. It covers three kinds of
repo: an **Airflow** data repo, **Module Federation micro-frontends** and a **React frontend shell**. One builder works
in all three.

It is working code, not a slide deck. It contains:

- **Claude Code plugins** (skills, subagents, hooks, scripts and connectors), delivered to every developer through
  managed settings.
- **One shared CI workflow** that every repo calls from a single small file, to re-run and attest the evidence.
- **A CLI** that writes a product repo's few own files in one command.
- **Managed policy**: the one file an administrator deploys.
- **A knowledge base** that grows with every story.
- **Documentation** as interactive HTML pages and a PDF.

**Distribution takes no effort from developers and little upkeep.**
- Developers install nothing. Each repo carries one CI file that never changes.
- Merging to `main` is the release. Installs track the commit, so there are no versions to bump. A merge reaches
  every machine, CI run and Slack thread by itself, and a revert rolls it back the same way.

[`policy/README.md`](policy/README.md) has the one-time setup.

The process follows the six-stage loop of Anthropic's AI-native SDLC playbook: Plan, Design, Build, Test, Deploy and
Maintain. Each stage saves a file that the next stage reads. People make the decisions at the gates, and hooks enforce
those gates as code. An incomplete PRD goes back to its product owner as concrete questions. Context comes from:

- the codebase;
- the read-only MongoDB and schema database;
- past Jira issues and production bugs (through Sentry).

## Contents

- [Start here: every link](#start-here-every-link)
- [What it does, in one page](#what-it-does-in-one-page)
- [What's in the repository](#whats-in-the-repository)
- [Roll it out](#roll-it-out)
- [Six ways to run it](#six-ways-to-run-it)
- [What was verified](#what-was-verified)
- [Changing the standard](#changing-the-standard)
- [Sources and inspiration](#sources-and-inspiration)

## Start here: every link

### Read or present it

| What | Where | What you'll find |
|---|---|---|
| **Interactive pages, hosted** | [claude.ai/artifact/PM86xaaRfAo6Z29XtYg1h6](https://claude.ai/artifact/PM86xaaRfAo6Z29XtYg1h6) | All six pages below in one place. The link is private to its owner until it's shared from the page's Share menu. |
| The loop | [`docs/site/index.html`](docs/site/index.html) | A clickable six-stage diagram showing what each stage saves, who decides, what enforces it and how to measure it. It also covers the human gates, and follows one real story (PAY-412) through the loop. |
| What goes where | [`docs/site/setup.html`](docs/site/setup.html) | CLAUDE.md, rules, skills, subagents, hooks, connectors, plugins and policy: what goes in each and what doesn't. Includes a decision helper, which Claude surfaces load what, and the context cost of each plugin. |
| Ways to implement | [`docs/site/implement.html`](docs/site/implement.html) | Six Claude setups, from a developer's terminal to an orchestrated service. Includes a picker based on your needs, a feature map and a rollout timeline. |
| Evidence | [`docs/site/evidence.html`](docs/site/evidence.html) | How a test run becomes proof: the evidence chain, an interactive fail-to-pass explainer, coverage across three repos, and charts from the PRD gate and the evals. |
| How others do it | [`docs/site/companies.html`](docs/site/companies.html) | 29 sourced company cases grouped into seven ways of automating delivery, 16 of them built on Claude. Includes filters, charts and a source link for every number. |
| The full playbook | [`docs/site/playbook.html`](docs/site/playbook.html) | The long-form reference behind all of the above. |
| **The playbook as a PDF** | [`docs/playbook.pdf`](docs/playbook.pdf) | 14 A4 pages for reading offline, printing or attaching, built from the page above. |

GitHub shows the HTML files as source code. To view the pages, clone the repo and open `docs/site/index.html` in a
browser; they need no build step or server. To host them for your team, turn on GitHub Pages for the `main` branch's
`/docs` folder; the pages are then under `/site/`.

### Background and evidence

| What | Where |
|---|---|
| Sourced research behind the companies page (each case's own blog, paper, talk or customer story) | [`docs/research.md`](docs/research.md) |
| Behavioural eval results (real Claude sessions with and without the plugin) | [`docs/evals.md`](docs/evals.md) |
| The worked example: PRDs before and after, intent, spec, plan and test results from three repos | [`examples/`](examples/README.md) |
| The original draft plan this standard replaces | [`AI_Native_Engineering_Implementation_Plan.pdf`](AI_Native_Engineering_Implementation_Plan.pdf) |
| Rolling it out: the one-time admin setup, updates and rollback, and the policy explained line by line | [`policy/README.md`](policy/README.md) |
| What each plugin does and how to install it | [`plugins/sdlc-core/README.md`](plugins/sdlc-core/README.md), [`plugins/sdlc-connectors/README.md`](plugins/sdlc-connectors/README.md) |
| How lessons are recorded and retired | [`knowledge/README.md`](knowledge/README.md) |
| How to change and release the standard | [`CONTRIBUTING.md`](CONTRIBUTING.md), [`CHANGELOG.md`](CHANGELOG.md) |
| Instructions Claude follows when working on this repo | [`CLAUDE.md`](CLAUDE.md) |

### External sources it follows

- Anthropic's [The AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook) (article
  and PDF), and the [Claude Academy course](https://academy.claude.com/courses/ai-native-sdlc-playbook) of the same name.
- The [Claude Code documentation](https://code.claude.com/docs): plugins, skills, hooks, settings, GitHub Actions, the Agent SDK.

## What it does, in one page

```
        ┌──────────────────────────────────────────────────────────────────────────────────────────┐
        ▼                                                                                          │
 1 PLAN            2 DESIGN              3 BUILD                 4 TEST          5 DEPLOY            6 MAINTAIN
 Confluence PRD -> context.md        ->  plan.md (plan mode) ->  verify      ->  draft PR         -> control bands
 PRD gate          spec.md               test-first tasks        evidence.py     REVIEW.md review    triage -> intent.md
 intent.md         (human approves)      locked tests            CI re-runs      humans merge        learn -> rules, evals
   NOT READY: questions to the product owner (Confluence comment + Jira task)    release gate
```

| Stage | Saves in `specs/<KEY>/` | Who decides | Enforced by |
|---|---|---|---|
| **1 Plan** | `prd.md`, `prd-review.md`, `intent.md` | The product owner accepts `intent.md` (marking the PRD ready counts) | `prd_lint.py` and a rubric review. If the PRD isn't ready, questions go back as a Confluence comment and a Jira task |
| **2 Design** | `context.md`, `spec.md` | A human approves the spec (the tech lead for risk: medium or high) | The edit hook stops agents from writing `status: approved` and blocks code until it's set |
| **3 Build** | `plan.md`, then tests and code | The engineer accepts the plan in plan mode (the tech lead for risk: high) | The edit hook blocks code before the plan is accepted and blocks edits to locked tests |
| **4 Test** | `.ai/evidence/` (not committed; a CI artifact) | A check: evidence must PASS for the head commit | `evidence.py` (AC coverage, fail-to-pass, plan match, locked tests); PR hooks; the required CI check |
| **5 Deploy** | The draft PR and its review findings | Code owners merge; the release manager authorises production | Hooks allow draft PRs only and no merging; production commands are blocked without `RELEASE_APPROVAL` |
| **6 Maintain** | An incident `intent.md`, `retro.md`, knowledge entries, evals | The service owner triages | `bands.py`: the tier sets what Claude may do (log, diagnose read-only, or propose a PR) |

Three ideas carry the design:

- **One builder for three stacks.** Each repo declares its stack and commands in `.ai/repo.yaml`. The matching skill
  (Airflow, frontend or micro-frontend) loads automatically when Claude touches those files.
- **Evidence is computed, not claimed.**
  - Tests are named after the acceptance criteria they prove, such as `PAY-412 AC-3: ...`.
  - A new test must fail without the change.
  - The diff must match the plan, and a locked test can't change.
  - CI re-runs all of this and attests the result.
- **Knowledge compounds.** A lesson becomes a knowledge entry. If it recurs, it becomes a CLAUDE.md line, then a rule,
  then a hook or check. Every production incident also becomes an eval.

## What's in the repository

### The plugins (`plugins/`, listed in the marketplace `.claude-plugin/marketplace.json`)

| Plugin | Contents |
|---|---|
| [`sdlc-standard`](plugins/sdlc-standard/README.md) | The bundle: no components of its own. It depends on every plugin below, so enabling it in managed settings installs all of them, and plugins added later arrive with it. |
| [`sdlc-core`](plugins/sdlc-core/README.md) | **11 skills, one or more per stage:**<br>- `prd-to-pr` runs the whole loop: `/sdlc-core:prd-to-pr <PRD link>`.<br>- `prd-review` gates the PRD and writes questions for the product owner.<br>- `context-gather`, `spec-write`, `plan`, `build`, `verify`.<br>- `pr-open`, `pr-babysit`, `triage`, `learn`.<br>**5 subagents:** `prd-analyst`, `repo-investigator`, `builder`, `qa-verifier`, `pr-reviewer`.<br>**3 always-on rules files.**<br>**Hooks:** shell guard, edit guard, PR gate, session context and stop-verify.<br>**7 scripts** (listed below).<br>**5 eval cases.** |
| [`sdlc-connectors`](plugins/sdlc-connectors/README.md) | The Atlassian Rovo (Confluence and Jira) and Sentry MCP servers, both over OAuth.<br>The `schema-lookup` and `history-lookup` skills.<br>`schema_snapshot.py`, which snapshots data contracts and flags breaking changes. |
| `stack-airflow` | The `airflow-dag` skill: idempotent, interval-driven writes; DAG integrity tests; `dag.test()`. |
| `stack-frontend` | The `frontend-feature` skill: accessible components, tests named after ACs, Playwright evidence. |
| `stack-mfe` | The `mfe-remote` skill: Module Federation contracts, shared singletons, fallbacks. It builds on `stack-frontend`. |

The scripts are standard-library Python. Skills, hooks and CI all use the same copies:

| Script | What it does |
|---|---|
| `prd_lint.py` | Scores a PRD and lists the questions for the product owner |
| `ac_coverage.py` | Links JUnit test names to the spec's acceptance criteria |
| `fail_to_pass.py` | Proves that new tests fail on the base commit |
| `evidence.py` | Runs all the checks at a commit and writes a hashed manifest. `lock` records a bug fix's reproducing test |
| `agent_evals.py` | Regression-tests a repo's Claude configuration on real tasks |
| `bands.py` | Control bands that decide when Claude is invoked on a metric, and what it may do |
| `atlassian.py` | Confluence and Jira REST client for CI, on Cloud or Data Center |

### Everything else

| Path | What it is |
|---|---|
| `tools/aisdlc.py` | The onboarding CLI. Commands:<br>- `init` writes a repo's own files.<br>- `doctor` checks a repo's setup and lists leftovers of older setups.<br>- `vendor` copies the plugins into a repo. It's a fallback for organizations without managed settings.<br>- `knowledge-audit` flags stale lessons.<br>`tools/validate_plugins.py` runs strict plugin validation. |
| `templates/repo/` | What `init` writes into a product repo. These are only the files specific to that repo:<br>- `CLAUDE.md`.<br>- `.ai/repo.yaml`: the stack, its checks and how CI installs it.<br>- Connectors in `.mcp.json`. Airflow: read-only MongoDB, the SQL schema database through DBHub, and Airflow. Web stacks: Playwright.<br>- `.github/workflows/ai-sdlc.yml`, the one CI file.<br>`extras/` (with `--extras`) holds the optional `REVIEW.md`, `.ai/bands.yaml`, READMEs and PR template. |
| `standards/` | The Confluence PRD template, and the JSON Schema for `.ai/repo.yaml` |
| `policy/` | Managed settings in two tiers:<br>- **Standard:** the approved marketplace and MCP servers, no bypass mode, a minimum Claude Code version.<br>- **Regulated:** adds a sandbox, credential isolation, and managed-only permissions and hooks. |
| `knowledge/` | Org and stack lessons, each with an owner and a review date |
| `docs/` | The interactive pages (`site/`), the playbook PDF and its build script (`build-pdf.cjs`), the research notes and the eval results |
| `examples/` | PAY-412, one story across three repos:<br>- PRDs before and after the product owner's answers.<br>- Intent, spec and plan.<br>- JUnit results from pytest, Vitest and Playwright.<br>- `demo.py`, which runs the deterministic layer end to end. |
| `tests/` | 105 unit tests (Python 3.9 and 3.13) for every script, hook and CLI command, and for the manifests |
| `.github/` | The shared workflow:<br>- `workflows/sdlc.yml` holds every stage job: evidence, review, `@claude` fixes, PRD intake, design, build, agent evals, maintain and learn.<br>- `actions/toolchain` sets up each repo from its `.ai/repo.yaml`.<br>This repo's own CI:<br>- `validate`: tests, strict plugin validation and actionlint.<br>- `plugin-evals`: run manually, since evals cost money.<br>- `knowledge-audit`: weekly.<br>Also `CODEOWNERS`, with placeholder teams. |
| `Makefile` | `test`, `validate`, `demo`, `evals`, `details` and `pdf` (see [What was verified](#what-was-verified)) |

## Roll it out

**Once, by an administrator.** [`policy/README.md`](policy/README.md) has each step.

1. Copy this repository into your organization as a private or internal repo.
2. Paste [`policy/managed-settings.json`](policy/managed-settings.json) into **claude.ai > Organization settings >
   Claude Code > Managed settings** (or deploy it with MDM). Every developer who signs in gets the plugins on their
   next session, and keeps getting updates. Cloud sessions included.
3. Sync the repository under **Organization settings > Plugins & skills**, so Slack, claude.ai and Cowork get the
   same skills.
4. Store `ANTHROPIC_API_KEY` (and the Atlassian credentials) as organization secrets.

**Once per repo.** Writes the repo's own files: `CLAUDE.md`, `.ai/repo.yaml`, connectors, and the one CI file.

```bash
python3 tools/aisdlc.py init   --target ../data-airflow --stack airflow  --jira PAY --description "Payroll pipelines"
python3 tools/aisdlc.py init   --target ../payroll-mfe  --stack mfe      --jira PAY
python3 tools/aisdlc.py init   --target ../web-shell    --stack frontend --jira PAY
python3 tools/aisdlc.py doctor --target ../data-airflow
```

Then fill in `CLAUDE.md`, commit, and make `ai-sdlc / evidence` a required check. The other CI stages stay off until
you set the repository variable `AISDLC_AUTOMATION=on`.

**Developers** do nothing. They open Claude Code in the repo and start:

```
/sdlc-core:prd-to-pr https://<site>.atlassian.net/wiki/spaces/PAY/pages/<id>
```

**Without managed settings** (no Team or Enterprise plan and no MDM):
- `init --repo-plugins` installs the plugins per repo, after each contributor trusts the folder.
- `vendor` copies them into the repo. It works on every surface, but each release then needs a re-run in every repo.

**Requirements:** Python 3.9 or later (with PyYAML for `evidence.py run`), `git` and `gh`. Node only for the web stacks
and the PDF build.

## Six ways to run it

All six use the same plugins, scripts and repo files, so each step adds automation without changing the process. Start
with the first. The [ways to implement](docs/site/implement.html) page compares them and suggests where to start.

| Setup | Where Claude runs | Started by | When to move on |
|---|---|---|---|
| **1 Developer loop** (start here) | Developer machines: terminal, IDE, desktop | An engineer | After 10 to 20 stories, with metrics compared against the baseline |
| **2 CI evidence and review** | GitHub runners; managed Code Review | Pull request events | When the required check is stable and review time per PR isn't rising |
| **3 Stage-triggered automation** | GitHub Actions | Merged artifacts: a PRD label, an accepted intent, an approved spec | When lead time drops against the baseline and rework doesn't rise |
| **4 Cloud, parallel and Slack** | Anthropic-hosted sandboxes | Engineers on the web or a phone; anyone in a Slack channel | When review capacity, not agent capacity, is the limit |
| **5 Closed loop** | GitHub Actions or scheduled tasks on the web | Metrics and schedules; no person | When the volume of intents outgrows what triage can absorb |
| **6 Orchestrated at scale** | Your services (Agent SDK) or Anthropic's (Managed Agents) | Your workflow engine | This is the end state |

## What was verified

```bash
make test      # 105 unit tests: PRD lint, coverage, fail-to-pass, evidence and plan checks, evals runner, bands, hooks, CLI
make validate  # strict plugin validation of the marketplace and all 6 plugins (the omitted version is the only allowed warning)
make demo      # PRD gate -> AC coverage -> evidence -> PR gate deny/allow -> locked test and release gate
make evals     # behavioural evals: real Claude sessions with and without the plugin (costs money)
make details   # always-on context cost per plugin
make pdf       # rebuild docs/playbook.pdf from docs/site/playbook.html
```

**Verified here:**

- The unit tests pass on Python 3.9 and 3.13.
- Strict plugin validation passes.
- The demo runs end to end.
- `init`, `vendor` and `doctor` work for all three stacks.
- Installing `sdlc-standard` with the Claude Code CLI installs all five plugins, each versioned by its commit.
- actionlint passes on the shared workflow and the caller template.
- The toolchain step reads each stack's `.ai/repo.yaml`.
- The pages render without console errors or sideways scrolling, on desktop and phone, in light and dark.
- The behavioural evals ran 30 real Claude sessions on sdlc-core 2.0.1: 5 cases, with and without the plugin, 3 runs
  each. All five cases pass with the plugin. Without it, Claude wrote code past the spec and plan gates in 6 of 6 runs,
  and its PRD reviews missed parts of the organisation's rubric. The results and their limits are in
  [`docs/evals.md`](docs/evals.md).

**Still to check in your environment:**

- Live calls to your Confluence, Jira, Sentry, MongoDB and schema database.
- The shared workflow on real runners, called from a product repo.
- Managed settings from the admin console: the plugins arriving on a developer machine and in a web session.
- Organization sync to Slack: the plugins arriving in a Claude Tag thread.
- The policy tiers on real machines.
- Replace the placeholder teams in CODEOWNERS with real ones.

## Changing the standard

Merging to `main` is the release:

- **No versions.** Plugins carry no `version`, so installs track the commit. A test fails if one is added.
- **Review and checks.** CODEOWNERS review each change, and branch protection requires the `validate` checks.
- **Evals for behaviour changes.** Any change to a skill or hook's behaviour needs an eval case, or a stated reason why
  not.
- **Rollback.** Revert the commit. To hold everyone on a known-good commit, pin `ref` in managed settings.

How a merge reaches each surface is in [CONTRIBUTING.md](CONTRIBUTING.md).

To change the pages, edit the content in `docs/site/assets/data.js` (stages, mechanisms, setups, evidence) or
`docs/site/assets/companies.js` (the company cases). The layout code doesn't need to change.

## Sources and inspiration

- The six stages, the saved artifacts (`intent.md`, `spec.md`, `plan.md`, `REVIEW.md`), hooks as approval gates,
  continuous evals and control bands all follow Anthropic's
  [AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook).
- [`docs/research.md`](docs/research.md) sources the company cases and the research on test quality and productivity:
  - companies including Intercom, HubSpot, Spotify, Stripe, Wix, Sentry, Carvana, Meta and Google;
  - studies including DORA, METR, UTBoost and ImpossibleBench.
