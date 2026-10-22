# PRD review rubric

`prd_lint.py` checks structure (sections, placeholders, Given/When/Then, vague terms, numbers in NFRs, open questions).
This rubric covers what only a reader can judge. A finding is **blocking** if building from the PRD as written would
likely cause rework, an untestable result, or an unsafe change. Everything else is **advisory**.

## Blocking checks

| Check | Ask yourself | Typical question for the product owner |
|---|---|---|
| Contradictions | Do two sections disagree (scope vs non-goals, roles vs ACs, NFR vs flow)? | "Section A says X, section B says Y. Which is right?" |
| Testable outcomes | Does each AC have one observable result (UI, API response or stored data)? | "What exactly does the user see when ...?" |
| Requirement coverage | Does every functional requirement have at least one AC? | "How do we know FR-3 works?" |
| Roles and access | Is it stated who can and who must NOT see or do each thing, and for which data scope (own entity, all entities)? | "Should multi-entity admins see all entities?" |
| Unhappy paths | Are loading, empty, error, timeout and no-access states covered? For pipelines: late, duplicate or bad input data, re-runs and backfills? | "What should happen when the source file arrives late?" |
| Data source and freshness | Is the source of truth named, and how fresh must the data be? Does it exist (check the schema snapshots)? | "Status comes from which system, and how stale may it be?" |
| Sensitive data | Is PII or regulated data shown, stored or exported? Is the classification stated? | "Will salary amounts appear anywhere?" |
| Hidden scope | Does an AC silently imply work outside this team or system (a new API, a migration, another team's MFE)? | "This needs the Payroll API to expose X. Is that agreed with that team?" |
| Production history | Does the PRD touch an area with recent bugs or incidents (from `history-lookup`) without addressing them? | "INC-2291 duplicated status rows on backfill. Must re-runs be idempotent?" |

## Advisory checks

- Success metrics have a baseline, a target and a data source.
- Rollout covers the flag, pilot group, rollback and who is told.
- NFRs cover accessibility (WCAG level), supported browsers and devices, and localization where relevant.
- Out of scope is explicit about the obvious adjacent asks.
- Terminology is consistent (one name per concept).

## Proposed defaults (offer them, never assume them)

| Gap | Proposed default |
|---|---|
| Page performance | p95 render < 2 s at expected data volume |
| Accessibility | WCAG 2.2 AA; information not conveyed by colour alone |
| Empty state | neutral message with the next action |
| Error state | message + retry; the rest of the page keeps working |
| No access | guidance without revealing data or its existence; no data request made |
| Data freshness | no older than the pipeline schedule interval; show "last updated" |
| Pipeline re-runs | idempotent: re-running the same interval produces the same result |
