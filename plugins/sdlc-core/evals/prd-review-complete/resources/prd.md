# PRD: Payroll run status tracker

| Field | Value |
|---|---|
| Product owner | Priya Sharma |
| Status | Ready for Engineering |
| Jira epic | PAY-412 |
| Version | 9 |

## Summary

Payroll admins see the processing status of each payroll run in the current pay period on the
payroll dashboard, so they no longer raise tickets to ask the payroll operations team.

## Problem

Every pay cycle the payroll operations team receives about 120 tickets (Jira filter "WISMP",
last 3 cycles) asking whether a payroll run has finished. Admins have no visibility into the
processing pipeline, and operations agents spend roughly 9 hours per cycle answering.

## Goals

- Cut "where is my payroll" tickets by 60% within two pay cycles of launch.
- Admins can self-serve the status of their payroll runs without contacting support.

## Non-goals

- Editing, cancelling or re-running payroll runs from the dashboard.
- Email or SMS notifications about status changes (separate PRD, PAY-430).
- Historical pay periods; only the current pay period is shown.

## Users and roles

- **Payroll admin** (customer employer): sees runs for the entities they administer.
- **Payroll operations agent** (internal): sees runs for all employers.
- **Employee** and **Finance viewer** roles must NOT see the tracker.

## User flow

1. Admin opens the payroll dashboard.
2. A "Payroll runs" panel lists one status card per run in the current pay period.
3. Admin filters by status; the list updates without a page reload.

## Functional requirements

- FR-1: Show a status card for each payroll run in the current pay period on the payroll dashboard.
- FR-2: Card status reflects the processing pipeline within 15 minutes of a state change.
- FR-3: Users can filter runs by status (Pending, Processing, Completed, Failed).
- FR-4: Operations agents can see runs for all employers; admins only for their entities.
- FR-5: Users without access see an access-unavailable state with guidance, without confidential details.

## Acceptance criteria

- AC-1 (FR-1): Given an admin with two runs in the current period, when they open the dashboard,
  then they see two status cards showing run name, status and last-updated time.
- AC-2 (FR-2): Given a run moves from Processing to Completed, when 15 minutes have passed,
  then the card shows Completed and the new last-updated time.
- AC-3 (FR-3): Given runs in several statuses, when the admin selects the "Failed" filter,
  then only failed runs are shown and the filter is reflected in the URL.
- AC-4 (FR-4): Given an operations agent, when they open the tracker, then runs from all employers
  are listed with the employer name on each card.
- AC-5 (FR-5): Given a user with the Employee role, when they open the dashboard URL directly,
  then they see the access-unavailable state and no run data is requested.
- AC-6 (FR-1): Given an admin with no runs in the current period, when they open the dashboard,
  then they see an empty state that says no runs are scheduled yet.
- AC-7 (FR-2): Given the status service fails, when the dashboard loads, then the panel shows an
  error message with a retry button and the rest of the dashboard still works.

## Non-functional requirements

- Performance: the panel renders within 2 s at p95 for employers with up to 50 runs per period.
- Data freshness: status no older than 15 minutes.
- Accessibility: WCAG 2.2 AA; status is not conveyed by colour alone.
- Availability: inherits the dashboard SLO (99.9% monthly).

## Data

- Source: payroll processing pipeline (Airflow DAG `payroll_processing`) state transitions.
- Shown: run name, entity, status, last-updated time. No salary amounts or employee data.
- Retention: current pay period only in the UI.

## Security and privacy

- Authorization is enforced server-side by role and entity; the UI only reflects it.
- No personal data is displayed on the cards.

## Dependencies

- Payroll API team must expose run status read access for the dashboard (contract change).

## Success metrics

- "Where is my payroll" tickets per cycle (baseline 120).
- Weekly active admins viewing the panel.

## Rollout

- Behind feature flag `payroll_status_tracker`; pilot with 5 employers for one pay cycle, then all.

## Open questions

- Should admins of multi-entity employers see all entities? Resolved: yes, all entities they administer.
- Which statuses exist? Answered: Pending, Processing, Completed, Failed.
- Should we show the expected completion time? [non-blocking] Revisit after the pilot.
