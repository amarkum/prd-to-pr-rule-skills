# How others automate software delivery with AI agents

Compiled 2026-10-22 from primary sources where they exist. Tags: **[P]** the organisation's own blog, paper or talk;
**[V]** a vendor's case study; **[S]** secondary reporting. Where sources disagree, both numbers are given.
Key figures for Stripe, Spotify, METR and ImpossibleBench were re-checked against the source pages on 2026-10-22,
and the Claude-based cases were added the same day.
No primary source was found for coding agents working specifically on Module Federation micro-frontends; the closest
frontend cases are listed.

## 1. Company systems

| Organisation | What they built | Pattern | Scale and results | Lesson for us | Sources |
|---|---|---|---|---|---|
| **Stripe**, Minions | Unattended one-shot coding agents (a goose fork), started from Slack, CLI, web or tickets | "Blueprints": code-defined state machines that alternate deterministic nodes (lint, push) with agent nodes (implement, fix CI); pre-warmed devboxes with no production data and no open egress; a curated tool subset from a ~400–500-tool MCP "Toolshed"; one set of agent rules shared by every agent tool | >1,300 merged PRs a week (up from 1,000), human-reviewed, with no human-written code | Shift feedback left (sub-second lint); at most 2 CI rounds, then hand to a human; "if it's good for humans, it's good for LLMs" | [P] stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents (2026-02-09) and part-2 (2026-02-19) |
| **Spotify**, Honk | Agent (Claude Agent SDK) that replaces only the transformation step of Fleet Management; targeting, PRs and merging unchanged | Verifiers (build, test, format) exposed through MCP and run in the **stop hook**; no PR if they fail; an LLM judge compares diff with intent; 10 turns, 3 retries | 1,500+ merged PRs, 60–90% time saved on migrations; Sep 2026: merged changes 8,100 → 17,000 year on year, "volume … increased faster than some of our verification controls could adapt" | The worst failure is a PR that passes CI but is functionally wrong; agents disable flaky tests or downgrade dependencies; standardised codebases help agents | [P] engineering.atspotify.com 2025/11 (part 1), 2025/12 (part 3: feedback loops), 2026/6, 2026/9; [S] InfoQ 2026-03 |
| **Ramp**, Inspect | Background agent (OpenCode) in a Modal VM per session with the full stack and a browser | Runs tests, reads Sentry, Datadog and LaunchDarkly, produces screenshots and live previews; the PR is opened with the requester's token so they can't approve it themselves | ~30% of merged PRs within months, later "over half" [V] | Never let missing context or tools be the limit; measure sessions that end in merged PRs | [P] builders.ramp.com; [S] InfoQ 2026-01; [V] modal.com 2026-02 |
| **Uber** | uReview (AI code review), AutoCover (test generation), "Minion" design-to-draft-PR agent | Prompt chain with confidence grading and dedup; a 5-agent test pipeline with a **mutation-testing validator** that rejects change-detector tests; MCP gateway | uReview: >90% of ~65k weekly diffs, 75% of comments rated useful; AutoCover: ~11% of new tests; 70%+ of PRs come via agents (2026 talk) | Validate inside the agent loop before shared CI; prefer precision over volume in AI review | [P] uber.com/blog/ureview (2025-08); ICSE-SEIP 2026 AutoCover paper; ai.engineer 2026-06 talk |
| **Airbnb** | Enzyme → React Testing Library migration with LLMs | Per-file state machine (refactor → Jest → lint/tsc), retry caps, 40–100k-token context with related files | ~3.5k test files in 6 weeks vs a 1.5-year estimate; 97% automated, the rest by hand | Retries plus the right context beat prompt polishing | [P] airbnb.tech (2025-03); [S] InfoQ |
| **Google** | LLM-assisted code migrations; TF→JAX multi-agent | AST and static analysis find locations and validate; the LLM edits; build and test drive repair; humans review | int32→int64: 80% of landed changes fully AI-authored; JUnit3→4: 5,359 files in 3 months; review speed became the bottleneck | Measure end-to-end time, not "% AI code"; cap change volume to what reviewers absorb | [P] arXiv 2501.06972; Google Cloud blog 2026-05 |
| **Meta** | TestGen-LLM, ACH (mutation-guided tests), JiTTests, RADAR risk-gated review | "Assured LLM-based SE": a candidate must build, pass, be non-flaky over 5 runs, and add coverage; RADAR routes low-risk diffs through ML risk scoring, LLM review and deterministic validation | TestGen-LLM: 25% of candidates add coverage, 73% of recommendations accepted; RADAR: 331K+ diffs landed, 1/3 the revert rate (observational, pre-selected low-risk) | Filter AI-written tests by objective criteria; tier review by risk | [P] arXiv 2402.09171, 2501.12862, 2601.22832, 2605.30208 |
| **Amazon** | Q Developer Java upgrades; Kiro spec-driven IDE | Kiro: EARS requirements → design → tasks, with property-based tests derived from requirements | Q: ~4,500 developer-years saved [S]; Kiro: 100k+ developers in the first preview week | Specs pay off when the tests come from them | [S] the-decoder 2024-08; [P] kiro.dev (GA 2025-11, one-year 2026-07) |
| **GitHub** | Copilot coding agent; Spec Kit; Agent HQ | Issue → Actions VM → draft PR; pushes only to its own branch; the requester can't approve; firewalled; automatic CodeQL, secret scanning and Copilot review | Spec Kit ~142k stars (Oct 2026) | Separation of duties built in (requester ≠ approver) | [P] github.blog 2025-05, 2025-09, 2025-10, 2026-06 |
| **Atlassian** | Rovo Dev (Jira item → sandbox → draft PR); AI code review against Confluence standards and Jira ACs | Author reviews the AI PR before teammates | PR cycle time −45% internally; peer-reviewed study −30.8% | Check PRs against the ticket's acceptance criteria | [P] atlassian.com blog 2026-01, 2026-03; arXiv 2601.01129 |
| **Block** | goose (open-source agent); Base Web → Fluent UI React migration (11k files) | A goose loop calling a TypeScript language-service tool server, with an import-rule DSL, 50+ hint files and 20+ custom linters | ~4,000 of 10,000 employees use goose [V] | Single-shot output "often compiled but was semantically wrong"; **turn repeated model failures into linters and policy** | [P] block.xyz 2025-01; engineering.block.xyz 2026-04 |
| **Every**, compound engineering | Plan → work → review → **compound** loop; open-source plugin | About 80% of effort goes to planning and review; lessons stored as prompts in the codebase (`docs/solutions/`) | Self-reported | Make every lesson a durable artifact | [P] every.to 2025-12; github.com/EveryInc/compound-engineering-plugin |
| **Anthropic** | Internal Claude Code usage | CLAUDE.md files, TDD, checkpoint commits, auto-accept only for peripheral work | Claude used in 59% of work; +67% merged PRs per engineer per day; most engineers can fully delegate only 0–20% of work | Supervising AI needs the skills heavy use can erode | [P] claude.com/blog 2025-07; anthropic.com/research 2025-12 |
| **OpenAI** | Internal Codex use; "harness engineering" | AI review on almost every PR; a lean AGENTS.md as a map into docs | 70% more PRs merged per week | Keep instructions lean and navigable | [P] openai.com 2025-10, 2026-02 (seen via search excerpts) |
| **Microsoft** | AI PR review at scale | Suggestions are never committed automatically | >90% of PRs, 10–20% faster median completion | AI review as a first pass, humans decide | [P] devblogs.microsoft.com 2025-07 |
| **Nubank + Devin** | Splitting an 8-year ETL monolith | Fine-tuned on prior manual migrations; humans approved changes | 8x (page header) or 12x (body) efficiency; >20x cost savings [V, undated] | Data-pipeline migrations are a strong first use case | [V] devin.ai/customers |

### Systems built on Claude (added 22 Oct 2026)

Every quote below was checked against the downloaded page text; customer stories on claude.com carry no publish date, so
their dates are the earliest the content allows.

| Organisation | System | Built on | Gates | How they verify | Reported numbers | Sources |
|---|---|---|---|---|---|---|
| **Intercom** | Claude Code as a platform: private auto-updating plugin marketplace (skills, hooks, OpenTelemetry) plus AI PR auto-approval | Claude Code | Auto-approval only for small, low-risk PRs; anyone can ask for a human review; auditors engaged first | Review split into independent sub-agents; revert rates against human code; a hook blocks `gh pr create` unless the create-pr skill ran | ">93% of PRs agent-driven"; 19.2% of merged PRs auto-approved (median 14.6 vs 75.8 min to merge); backend revert rate 0.53% AI vs 5.39% human | [P] intercom.com/blog/ai-is-approving-our-pull-requests-heres-how-we-made-it-safe (2026-04-21); ideas.fin.ai/p/2x-nine-months-later (2026-04-16) |
| **HubSpot** | Crucible (headless Claude Code on Kubernetes) and the Sidekick bot | Claude Code; review later moved to an in-house multi-model framework | Editable plan before the build; PRs not auto-marked ready; a judge agent filters review comments | Stop hook refuses to finish until the build passes and changes are pushed; branch and draft PR created deterministically | 7,000+ AI PRs merged; 50,000+ human PRs reviewed; time to review feedback -90% | [P] product.hubspot.com/blog/cloud-coding-agents-at-hubspot (2026-01-23); .../automated-code-review-the-6-month-evolution (2026-03-02) |
| **Wix** (data engineering) | AirBot: Airflow failure, root cause, fix PR, in Slack | LangChain plus the Claude Agent SDK for fixes; other models for triage and chat | Read-only analysis, then a person approves the write step | Typed remediation plans; the repo's CLAUDE.md and team skills; least-privilege MCP gateway | 675 h/month saved (Jan) rising to ~850 (Sep); 28 of 180 PRs merged unchanged in 30 days | [P] wix.engineering (2026-01-15); Airflow Summit 2026 slides |
| **CircleCI** | Chunk, a CI maintenance agent, plus Claude Code sidecar hooks | Claude Agent SDK | The customer merges a PR CI already passed | Sandboxes from the customer's CI config; Stop and PreToolUse hooks run tests in a CI-identical microVM | ">4 in 5 Chunk tasks trigger automatically"; task-to-PR conversion more than doubled | [V] claude.com/customers/circleci; [P] circleci.com/blog/chunk-sidecar-agent-hooks (2026-05-29) |
| **Delivery Hero** | Herogen, Jira task to tested PR | In-house agent, Claude Opus 4.5 primary; Gemini on the review council | A council of review agents, then a human final check | Iterates on tests; measures merged vs rejected | 100+ merged change requests a day; 85% merged vs rejected (Apr); 170+ PRs/day later | [P] press release (2026-04-24); [V] claude.com/customers/delivery-hero, Google Cloud |
| **Carvana** | Claude in Slack: alert to root cause to PR; release baseline checks; hourly checks | Claude in Slack (Claude Tag) | Human PR review; scoped identities per team; a read-only trial first | Releases compared with a log baseline kept as a skill | Alert volume -56%; time to an answer -65% | [V] claude.com/customers/carvana |
| **Sentry** | Seer root-cause analysis handed to a Claude agent that opens the PR | Claude Managed Agents | A developer reviews, tests and merges | Analysis grounded in Sentry telemetry | 1M+ RCAs a year; integration built by one engineer | [V] claude.com/customers/sentry; [P] sentry.io changelog (2026-04-08) |
| **LG CNS** | Build Factory modernisation | Claude Code on Bedrock | Pods of 5-7; seniors set the decomposition | Thin harness chaining analysis, generation, tests and verification | 2,888 of 2,913 APIs converted; 1,340 screens moved to React; ~50% of conventional cost | [V] claude.com/customers/lg-cns |
| **Caylent** | Accelerate, a database migration pipeline | Claude Agent SDK on Bedrock | A guardrail agent validates every translation; engineer sign-off | Tests on translated procedures | 220 h vs 2,600 h; 1,850 of 2,500 procedures were dead code | [V] claude.com/customers/caylent |
| **Deepgram** | Plan-mode sessions, an incident skill, multi-agent support triage | Claude Code | Human sign-off on every production change | Higher coverage bar for Claude-written code; durable-code cohort study | 4-10x durable code for regular users (internal) | [V] claude.com/customers/deepgram |
| **League** | Swarm overnight builds and a PR risk-triage bot | Claude Code | Next-morning review; size and risk routing; feature flags | Risk-routed review | AI-authored code 70% to 98%; idea-to-PR cycle time halved | [V] claude.com/customers/league |
| **Shopify** | Roast workflows with a Claude Code step | Claude Code | The workflow author sets the guardrails | Deterministic steps first; iterate until tests and types pass | "Thousands of test files" (no exact figure) | [P] shopify.engineering/introducing-roast (2025-06-18) |
| **Rakuten** | Claude Code for delivery; a Managed Agents agent for production exceptions | Claude Code, Managed Agents | Not described | Root cause posted to Slack | Time to market 24 to 5 days (-79%) | [V] claude.com/customers/rakuten |

**Anthropic's own figures.** "In May 2026, Anthropic averaged around 2,500 code changes merged per day; as of September,
we merged over 30,000 per day" ([P] anthropic.com/engineering/redesigning-source-control, 2026-10-13). "Claude authors
about 80% of the code merged into our codebase today" and the share of PRs with substantive review comments rose from 16%
to 54% ([P] claude.com/resources/articles/how-anthropic-secures-its-ai-native-software-development-lifecycle, 2026-07-21).
Claude posts its first evidence-grounded incident analysis a median of 14 minutes after an incident opens
([P] claude.com/resources/articles/ai-ci-cd-on-call, 2026-08-18). The 59% of work and +67% merged PRs per engineer per day
are from an August 2025 survey and Claude Code adoption data ([P] anthropic.com/research/how-ai-is-transforming-work-at-anthropic,
2025-12-02); the 59% is self-reported.

**Spotify re-checked.** Spotify's Chief Architect: "Honk architecturally is fairly simple. It's the Claude Agent SDK running
in a Kubernetes pod." Honk is pluggable by design and its first version wasn't built on Claude.

**Caveats.** Figures disagree across sources for Delivery Hero (100+ vs 170+ PRs a day), Wix (675 vs ~850 hours, with a
changed model mix) and Spotify (PR frequency +60% vs +75%). Nobody published a micro-frontend case built on Claude.
GMO Flatt Security reported misconfigured claude-code-action workflows exploited in the wild (2026-06-01): workflows that
untrusted users can trigger should expose no secrets beyond what the action needs.

### Data engineering specifically

- **Spotify, Honk part 4** (2026-04, [P]): ~1,800 downstream data pipelines (BigQuery, dbt, Scio); 240 automated PRs.
  Repos without build-time unit tests **couldn't let the agent verify itself**, so owners tested by hand.
  For us: Airflow repos need DAG integrity, idempotency and contract tests before agents work there.
- **Astronomer** (2026-02, [P]): open-source Airflow agent skills plus an Airflow MCP server. "Agents struggle with
  writing correct code for systems they don't understand." No evaluation published.
- **dbt Labs ADE-bench** (2026, [P]): top agents pass ~56% of data-engineering tasks; weak where they must inspect the data.

### Frontend specifically

- **Zalando** (2025-02, [P]): LLM UI-library migration across 15 apps, ">90%" accurate; broke layouts because the model
  couldn't see rendered output. For us: screenshot evidence and Playwright checks.
- **Airbnb** RTL migration and **Block** Fluent UI migration (above).

## 2. Spec-driven development (SDD)

- **GitHub Spec Kit** (2025-09, [P]): Specify → Plan → Tasks → Implement; "you don't move to the next one until the
  current task is fully validated".
- **Kiro** (Amazon): EARS requirements → design → tasks, with property-based tests from requirements.
- **Tessl** ([V], 2026-10): spec-as-source; claims 75% of its PRs merge without human review, where repeated review
  findings became "verifiers".
- **BMAD-METHOD** ([P]): role-based agile flow; "small changes go straight to build".
- **Critique**, Birgitta Böckeler on martinfowler.com (2025-10-15, [P]): one workflow for every size (a small bug became
  4 user stories and 16 ACs); long Markdown is tedious to review; agents ignored specs; echoes of model-driven development.
  **Our answer:** a fast lane for low-risk changes, specs kept short with ID-based traceability, and gates enforced by
  hooks rather than trust.
- **Thoughtworks Technology Radar**: SDD at Assess (2025-11); AGENTS.md at Trial; MCP at Trial; naive API-to-MCP
  conversion on Hold; complacency with AI-generated code on Hold. Vol 34 (2026-04): **Adopt** curated shared
  instructions and context engineering; **Trial** feedback sensors for coding agents, mutation testing and sandboxed
  execution; **Caution** instruction bloat, coding throughput as a productivity measure, and MCP by default.

## 3. What the quality data says

| Source | Finding | Implication for this standard |
|---|---|---|
| **DORA 2025** (Google, ~5,000 respondents, [P]) | 90% use AI; AI raises throughput but **still raises instability**; "AI is an amplifier". Seven capabilities: clear AI stance, small batches, healthy data ecosystems, user-centric focus, AI-accessible internal data, quality internal platforms, strong version control | Small PRs, a platform (this plugin), AI-accessible data (connectors and snapshots), version-controlled specs |
| **METR RCT** (2025-07, [P]) | Experienced OSS developers were **19% slower** with AI while believing they were 20% faster | Measure against a baseline; don't trust perception |
| **METR update** (2026-02-24, [P]) | −18% time (CI −38% to +9%) for returning developers; METR calls it a weak signal, likely a lower bound | Speed-ups are real but noisy: measure lead time and rework |
| **Faros AI** ([V], 2025 and 2026 Q2) | 2025: +98% PRs, +91% review time, +154% PR size. 2026 Q2: incidents per PR +242.7%, median review time 5x | Review becomes the bottleneck. Hence small tasks, evidence comments and risk tiers |
| **CodeRabbit** ([V], 2025-12, 470 PRs) | AI co-authored PRs had ~1.7x more issues; logic issues +75%; security up to 2.74x | Independent review agent plus human review; security checklist |
| **GitClear** (211M lines) | 4x more code cloning; refactoring ("moved" lines) fell below 10% | Reviewers watch for duplication; "similar feature" reuse in context |
| **SWE-bench** (ICLR 2024) | Validation requires **FAIL_TO_PASS** tests plus PASS_TO_PASS guards | Our `fail_to_pass.py` |
| **UTBoost** (ACL 2025) | 15.7–28.4% of "passing" patches were wrong because the tests were weak | Fail-to-pass and QA review of test semantics |
| **ImpossibleBench** (2025-10) | Models "cheat" on impossible tasks, most often by **modifying tests** | The edit hook blocks skip markers; QA checks the tests; evidence is produced by scripts |

## 4. Cross-cutting patterns, and where they live in this standard

| Pattern | Who shows it | Where it lives here |
|---|---|---|
| Deterministic skeleton with agent nodes | Stripe blueprints, Shopify Roast, Airbnb state machine, Google AST + LLM | Scripts for lint, coverage, fail-to-pass and evidence; skills sequence the agent work; hooks enforce the order |
| Verify in the loop before a PR exists | Spotify stop-hook verifiers, Uber, Stripe local lint, GitHub automatic checks | `verify` skill, `stop-verify` hook, PR evidence gate |
| Bounded iteration | Stripe ≤2 CI rounds; Spotify 10 turns and 3 retries; Airbnb retry caps | 3 attempts per task in `build`, 2 repair rounds in `verify`, then escalate |
| Validate the tests, not just green CI | Meta assured LLMSE and ACH, Uber mutation testing, SWE-bench | Fail-to-pass, AC coverage, no-skip hook, `qa-verifier` |
| Check intent independently of tests | Spotify judge, Atlassian AC-based review, Every reviewers | `pr-reviewer` against the spec; human review |
| Spec first, checkable end states | Spec Kit, Kiro, BMAD, Atlassian Jira → PR | PRD gate → spec with AC IDs → tasks; fast lane for small changes |
| Shared, scoped, lean rules | Stripe (one rule set for every agent), Thoughtworks "curated shared instructions" | One plugin marketplace; always-on rules ~50 lines; CLAUDE.md under a page; stack skills path-scoped |
| Human review mandatory, tiered by risk | Stripe, GitHub, Ramp, Google; Meta RADAR for low risk | Draft PRs only; humans merge; risk tier in the spec; auto-merge only after measured success |
| Small batches, measure outcomes | DORA, Faros, METR, Thoughtworks Caution | One story per branch, ~200-line tasks; metrics are lead time, rework and escaped defects, not "% AI code" |
| Compound failures into rules and checks | Block, Every, Thoughtworks feedback flywheel, Tessl verifiers | `learn` skill, knowledge base, promotion ladder |
| Least-privilege tools and data | Stripe Toolshed subsets, Uber gateways, Spotify minimal tools | Read-only connectors, managed MCP allowlist, sandbox, no production data |
| Isolated, production-like sandboxes | Stripe devboxes, Ramp VMs, Uber DevPods | Local dev services and synthetic data; CI runners; cloud sessions with vendored config |

## 5. Top citations

1. DORA, *2025 State of AI-assisted Software Development* (2025-09-23).
   https://services.google.com/fh/files/misc/2025_state_of_ai_assisted_software_development.pdf
2. Stripe, *Minions, part 2* (2026-02-19). https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents-part-2
3. Spotify, *Predictable results through strong feedback loops* (2025-12-09).
   https://engineering.atspotify.com/2025/12/feedback-loops-background-coding-agents-part-3
4. Spotify, *AI changed how Spotify builds: quality at higher velocity* (2026-09-16).
   https://engineering.atspotify.com/2026/9/ai-changed-how-spotify-builds-what-we-learned-and-fixed-about-quality-at-higher-velocity
5. Google, *How is Google using AI for internal code migrations?* (2025-01). https://arxiv.org/abs/2501.06972
6. Meta, *Automated Unit Test Improvement using LLMs at Meta* (2024-02). https://arxiv.org/abs/2402.09171
7. Meta, *RADAR: automating low-risk code review* (2026-05). https://arxiv.org/abs/2605.30208
8. METR, early-2025 developer productivity RCT (2025-07-10) and update (2026-02-24).
   https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/ · https://metr.org/blog/2026-02-24-uplift-update/
9. Böckeler, *Understanding spec-driven development: Kiro, spec-kit and Tessl* (2025-10-15).
   https://www.martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html
10. Thoughtworks, *Technology Radar Vol. 34* (2026-04).
    https://www.thoughtworks.com/content/dam/thoughtworks/documents/radar/2026/04/tr_technology_radar_vol_34_en.pdf

Also: SWE-bench (https://arxiv.org/abs/2310.06770), ImpossibleBench (https://arxiv.org/abs/2510.20270), UTBoost
(https://arxiv.org/abs/2506.09289), Block Fluent UI migration (https://engineering.block.xyz/blog/from-base-web-to-fluent-ui-without-a-flag-day),
Spotify Honk part 4 (https://engineering.atspotify.com/2026/4/background-coding-agents-dataset-migrations-honk-part-4),
Simon Willison, *The lethal trifecta* (https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/),
Meta, *Agents Rule of Two* (https://ai.meta.com/blog/practical-ai-agent-security/).
