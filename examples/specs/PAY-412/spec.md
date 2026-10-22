---
jira: PAY-412
title: Payroll run status tracker
prd: https://example.atlassian.net/wiki/spaces/PAY/pages/123456789 (version 9)
status: approved
risk: medium
approved_by: "@payroll-tech-lead"
approved_at: 2026-10-20
repos: [data-airflow, payroll-mfe, web-shell]
---

# PAY-412 Payroll run status tracker: technical spec

## 1. Summary

Expose per-run processing status for the current pay period. The `payroll_processing` DAG
writes status transitions to a new MongoDB collection; the payroll MFE renders a status panel;
the web shell mounts it on the payroll dashboard behind a role gate and feature flag.

## 2. Requirements

| ID | Requirement | PRD ref |
|---|---|---|
| FR-1 | One status card per run in the current pay period | FR-1 |
| FR-2 | Status no older than 15 minutes | FR-2, NFR freshness |
| FR-3 | Filter by status, reflected in URL | FR-3 |
| FR-4 | Ops agents see all employers; admins only their entities | FR-4 |
| FR-5 | Access-unavailable state for other roles, no data requested | FR-5 |

## 3. Acceptance criteria

- **AC-1** (FR-1) Given an admin with two runs in the current period, when they open the dashboard, then they see two status cards with run name, status and last-updated time.
- **AC-2** (FR-2) Given a run moves from Processing to Completed, when the DAG task completes, then a `payroll_run_status` document with status `COMPLETED` and `updated_at` is upserted within the same task run.
- **AC-3** (FR-3) Given runs in several statuses, when the admin selects "Failed", then only failed runs are shown and `?status=failed` is in the URL.
- **AC-4** (FR-4) Given an operations agent, when the panel renders runs from several employers, then each card shows the employer name.
- **AC-5** (FR-5) Given a user with the Employee role, when they open the dashboard URL, then they see the access-unavailable state and no request is made to the status endpoint.
- **AC-6** (FR-1) Given no runs in the current period, when the panel renders, then it shows the empty state "No payroll runs scheduled yet".
- **AC-7** (FR-2) Given the status endpoint returns 5xx, when the panel renders, then it shows an error message with a Retry button and the rest of the dashboard still renders.

## 4. Context and constraints

- `payroll_processing` DAG already emits task-level state; see `context.md` (sources cited there).
- Prior incident INC-2291: duplicate status rows after a backfill. Upsert by `(run_id)` and use the
  DAG run's data interval, never `now()`.
- MFE shared deps: React 18 singleton, design system `@acme/ds` ^7.

## 5. Design

### 5.1 Data

New collection `payroll_run_status` (MongoDB `payroll` db):
`{ run_id: string (unique), employer_id: string, entity_id: string, run_name: string,
status: "PENDING"|"PROCESSING"|"COMPLETED"|"FAILED", updated_at: ISODate, dag_run_id: string }`.
Index: `{ run_id: 1 }` unique, `{ employer_id: 1, updated_at: -1 }`. Additive; no existing readers.

### 5.2 Pipeline (data-airflow)

Add task `publish_run_status` after each state-changing task group; idempotent upsert keyed by `run_id`.

### 5.3 Contract

Payroll API exposes `GET /v1/payroll-runs/status?period=current` (dependency, owned by Payroll API team).

### 5.4 UI (payroll-mfe, web-shell)

`payroll-mfe` exposes `./StatusPanel` (props: `employerScope`, `onError`). States: loading, empty, error+retry,
list. `web-shell` mounts it at `/payroll/dashboard` when flag `payroll_status_tracker` is on and role is
Payroll admin or Ops agent; other roles get the access-unavailable component and no fetch.

## 6. Repo impact and sequencing

| Order | Repo | Change | ACs | Backward compatible |
|---|---|---|---|---|
| 1 | data-airflow | `publish_run_status` task + collection + indexes | AC-2 | Yes (new collection) |
| 2 | payroll-mfe | `./StatusPanel` exposed module | AC-1, AC-3, AC-4, AC-6, AC-7 | Yes (new expose) |
| 3 | web-shell | Route mount, role gate, flag | AC-5 | Yes (flag off by default) |

## 7. Test plan

| AC | Level | Test | Repo |
|---|---|---|---|
| AC-1 | component | `StatusPanel.test.tsx` "PAY-412 AC-1" | payroll-mfe |
| AC-2 | unit + dag.test | `tests/test_publish_run_status.py::test_pay_412_ac_2_*` | data-airflow |
| AC-3 | component | `StatusPanel.test.tsx` "PAY-412 AC-3" | payroll-mfe |
| AC-4 | component | `StatusPanel.test.tsx` "PAY-412 AC-4" | payroll-mfe |
| AC-5 | e2e | `e2e/payroll-dashboard.spec.ts` "PAY-412 AC-5" | web-shell |
| AC-6 | component | `StatusPanel.test.tsx` "PAY-412 AC-6" | payroll-mfe |
| AC-7 | component | `StatusPanel.test.tsx` "PAY-412 AC-7" | payroll-mfe |

## 8. Rollout and rollback

Flag `payroll_status_tracker` off by default; pilot 5 employers for one cycle. Rollback: turn the flag off;
the collection is additive and can stay.

## 9. Risks

- Status lag if the DAG is backlogged: card shows last-updated time so stale data is visible.

## 10. Open questions

None.

## 11. Manual verification

None.
