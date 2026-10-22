# PRD: <feature name>

<!-- How to use: copy into Confluence (or create a page from the "AI SDLC PRD" template). Replace every <...>.
     When it's ready, add the label `prd-ready`: automation runs the PRD review and either comments with questions
     or starts the spec. Keep the WHAT and WHY here. The HOW lives in the engineering spec. -->

| Field | Value |
|---|---|
| Product owner | <name> |
| Status | Draft / Ready for Engineering |
| Jira epic | <KEY-123> |
| Target release | <date or quarter> |

## Summary

<Two or three sentences: what we are building, for whom, and the outcome.>

## Problem

<The user or business problem, with evidence: ticket counts, metrics, research, incidents.>

## Goals

- <Outcome, measurable where possible>

## Non-goals

- <What is explicitly out of scope for this release>

## Users and roles

- **<Role>**: what they can see and do, and for which data (their own, their entity, all).
- **<Role that must NOT have access>**: what they see instead.

## User flow

1. <Step>

## Functional requirements

- FR-1: <What the system must do. One behaviour per line.>

## Acceptance criteria

<!-- One observable outcome each, as Given / When / Then. Reference the FRs. Include unhappy paths:
     empty, error, no access, and for data pipelines late or duplicate input and re-runs. -->

- AC-1 (FR-1): Given <context>, when <action>, then <observable result>.

## Non-functional requirements

<!-- Use numbers. -->

- Performance: <e.g. p95 render < 2 s for up to 50 items>
- Data freshness: <e.g. no older than 15 minutes>
- Accessibility: <e.g. WCAG 2.2 AA>
- Availability: <e.g. inherits the dashboard SLO>

## Data

- Source of truth: <system or pipeline>
- Shown, created or changed: <fields at business level>
- Sensitive data: <none / PII / financial: what and why>
- Retention: <how long>

## Security and privacy

- <Who can access what; where authorization is enforced; audit needs>

## Dependencies

- <Teams, APIs, contracts, other PRDs>

## Success metrics

- <Metric: baseline -> target, and where it is measured>

## Rollout

- <Feature flag, pilot group, dates, rollback expectation, who is told>

## Open questions

<!-- Every question blocks engineering unless it is marked [non-blocking]. Mark answered ones "Resolved: <answer>". -->

- None.
