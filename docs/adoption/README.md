# Agentic SDLC adoption plan

The plan for taking the organisation from AI-tool adoption to the Agentic SDLC described in
[`vision.md`](vision.md), with the execution tracker the program is run from and a tested reference starter kit.

| What | Where | What you'll find |
|---|---|---|
| The plan | [`index.html`](index.html) | What the vision says in plain words, the risks and how the plan counters them, a dated 12-month roadmap from Mon 26 Oct 2026, when each autonomy stage arrives, the Claude capability map, the measurement model with an ROI calculator, the gap-assessment trajectory, leadership decisions, copy-paste Claude prompts and the next 10 working days. Open it in a browser; it needs no build step or server. |
| Execution tracker | [`agentic-sdlc-execution-plan.xlsx`](agentic-sdlc-execution-plan.xlsx) | 54 actions across 8 areas, each with sub-steps, a measurable output, current status, RAG, dates, owner and the support it needs. Also: a status summary, a weekly timeline, KPIs with formula targets, milestones and autonomy stages, decisions, the task force, the agent framework map, risks, and industry evidence with sources. |
| Source vision | [`vision.md`](vision.md) | "The Continuous Agentic SDLC": the operating model, artifact chain, autonomy ladder, pillars and leadership decisions the plan implements. |
| Starter kit | [`starter-kit/`](starter-kit/README.md) | A tested reference kit: artifact templates, CLAUDE.md and Makefile templates, guard hooks, six subagents, six skills, CI gate scripts, a `claude -p` eval harness, CI workflows and plugin packaging. |

## How this relates to the rest of the repository

`plugins/` is the standard that reaches every machine, through the marketplace and managed settings. Nothing in this
folder is in the marketplace, so merging it changes nobody's Claude Code.

The plan treats this repository as the home of the agent framework. The starter kit is reference material: its
frozen-test and production-boundary guards, artifact gates, eval harness, architecture, security and test agents, and
release-manifest and incident-to-intent skills are candidates to move into `sdlc-core` through the normal PR and eval
process (tracker actions 3.5, 4.5 and 4.6). Until they do, `sdlc-core` is what people run.

## Keeping it current

- Action owners update the tracker's Plan sheet every Friday: current status, status and RAG.
- Dates change only with a decision at the biweekly review; the reason goes in Remarks.
- When dates or targets change, update `index.html` so the page and the tracker agree.

## Checks

```bash
python3 docs/adoption/starter-kit/.claude/hooks/tests/run_hook_tests.py   # 116 hook checks, piped sample JSON
python3 docs/adoption/starter-kit/evals/run_evals.py --self-test          # needs PyYAML; no API calls
```

The tracker's formulas were recalculated with LibreOffice with zero errors. Dates were checked against the calendar.
