# Metrics from the feature-level record

`feature-record.schema.json` defines one record per change. Build the records nightly from the
change artifacts (front matter), the issue tracker, git and PR data, the deploy system, product
analytics and Claude Code telemetry (OpenTelemetry metrics such as `claude_code.cost.usage`,
tagged with `OTEL_RESOURCE_ATTRIBUTES`). Every number below is computed from these records, so
people argue about definitions once, not every month.

Report medians and 85th percentiles per change class. Never compare raw counts across classes.

## Flow
| Metric | Formula |
|---|---|
| Idea to approved intent | `intent_approved - idea_received` |
| Intent to approved spec | `spec_approved - intent_approved` (significant and high-risk only) |
| Spec or plan to PR | `pr_opened - max(spec_approved, plan_approved)` |
| PR to production | `deployed_production - pr_opened` |
| Idea to impact | `impact_confirmed - idea_received` |

## Output per person (is it really increasing?)
- **Impact-qualified changes per builder per quarter** = sum over changes with
  `impact.threshold_met = true` of `weight(class)`, divided by builder FTE-quarters.
  Calibrate `weight(class)` in Wave 0 from the baseline median effort per class, for example
  standard 1, significant 3, high-risk 5. Trivial changes count 0.
- **Cost per successful change** = (agent cost + CI cost) / changes deployed with no rollback and no
  linked incident within 30 days. Add loaded people cost for the full-cost view.

## Structure (how close to AI-native?)
- **Handoff depth**: median distinct human roles that worked on or approved a change between approved intent and production (`handoff_depth`), by class. Automated and policy gates do not count.
- **Single-builder share**: share of production changes with `handoff_depth = 1`, where the only
  other approvals came from automated or policy gates.
- **Layers and span**: management layers between a builder and the CTO, and builders per manager,
  from the HR system. Track them next to handoff depth; they move together or not at all.

## Agent system
| Metric | Formula |
|---|---|
| Autonomous gate completion rate | `gates_auto_passed / (gates_auto_passed + gates_human_overridden)` |
| Human intervention rate | `human_interventions / sessions` |
| Agent rework rate | `agent_rework_commits / total commits` on agent-authored changes |
| Agent eval pass rate | passed runs / total runs in `evals/results/` |
| Standard-workflow share | changes with `agentic_workflow = true` / eligible (non-trivial) changes |

## Effort distribution
Share of builder time by `work_type`: feature, defect, maintenance, risk-reduction, tech-debt,
operational-support. Without this baseline, a rise in output can just mean defect work was
deferred.

## ROI
    Annual benefit B = (IQC_now - IQC_baseline) x builders x 4 x value per weighted change
                     + (escaped defects avoided x cost per defect)
                     + (incident minutes avoided x cost per minute)
    Annual cost    C = agent compute + licences + enablement team + training time
                     + productivity dip during the transition
    ROI = (B - C) / C        Payback (months) = C / (B / 12)

Value per weighted change starts as a conservative proxy: the loaded cost of the effort that
change took at baseline productivity. Replace it with measured impact as adoption data matures.
