# PRD: Payroll run status tracker

| Field | Value |
|---|---|
| Product owner | Priya Sharma |
| Status | Ready for Engineering |
| Jira epic | PAY-412 |

## Summary

Payroll admins need to see where each payroll run is in processing, so they stop raising
tickets to ask the payroll operations team.

## Problem

Every pay cycle the payroll operations team receives about 120 tickets asking whether a payroll
run has finished. Admins have no visibility into the processing pipeline.

## Goals

- Reduce "where is my payroll" tickets.
- Admins can self-serve the status of their payroll runs.

## Users

- Payroll admin (customer employer)
- Payroll operations agent (internal)

## Functional requirements

- FR-1: Show a status card for each payroll run in the current pay period on the payroll dashboard.
- FR-2: Status must be updated in real-time from the processing pipeline.
- FR-3: Users can filter runs by status.
- FR-4: Operations agents can see all employers' runs.

## Acceptance criteria

- Status card shows the correct status.
- Given an admin with two runs in the current period, when they open the dashboard, then they
  see two status cards with run name, status and last-updated time.
- Filtering should be intuitive.

## Non-functional requirements

- The page should load fast.
- Must be secure.

## Rollout

TBD

## Open questions

- Should admins of multi-entity employers see all entities?
- Which statuses exist? (Pending, Processing, Completed, Failed?)
