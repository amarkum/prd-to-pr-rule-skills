---
jira: PAY-412
title: Payroll run status tracker
type: feature
source: confluence:123456789@v9
author: Priya Sharma (product owner)
status: accepted
accepted_by: Priya Sharma (PRD labelled ai-ready, version 9)
accepted_at: 2026-10-18
---

# Intent: Payroll run status tracker

## Problem

Every pay cycle the payroll operations team gets about 120 tickets asking whether a payroll run has finished (Jira
filter "WISMP", last 3 cycles). Admins can't see the processing pipeline, and operations agents spend about 9 hours a
cycle answering.

## Proposed outcome

Payroll admins see the status of each run in the current pay period on the payroll dashboard, no more than 15 minutes
old, and stop raising tickets to ask. Goal: 60% fewer "where is my payroll" tickets within two cycles of launch.

## Affected users and systems

Payroll admins and operations agents. `data-airflow` (the `payroll_processing` DAG), `payroll-mfe` (a new status
panel), `web-shell` (the dashboard route, role gate and flag).

## Constraints

Existing authentication and roles only; employees never see the panel. No employee-level data in the panel.
Non-goals: editing or re-running payroll from the panel, historical periods.

## Open questions

None.
