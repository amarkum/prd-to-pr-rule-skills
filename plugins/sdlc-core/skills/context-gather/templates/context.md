# <KEY> context pack

PRD: <url> (version <N>) · Gathered: <date> · Repos scanned: <list>

## Affected components

| Component | Repo | Evidence | Notes |
|---|---|---|---|
| `payroll_processing` DAG | data-airflow | `dags/payroll_processing.py:40-118` | emits task state; no status collection today |

## Data shapes

| Store / collection or table | Source | Fields relevant to the story | Notes |
|---|---|---|---|
| MongoDB `payroll.payroll_runs` | `docs/schemas/mongo/payroll.payroll_runs.json` (snapshot 2026-10-01) | run_id, employer_id, state | no index on employer_id |

## Contracts

| Contract | Producer -> consumer | Location | Change needed? |
|---|---|---|---|

## Production history

| Item | What happened | Source | Regression test to add |
|---|---|---|---|
| INC-2291 | duplicate status rows after a backfill | Confluence postmortem <url> | re-run the same interval twice -> one row |

## Team knowledge applied

- KB-airflow-0007: use `data_interval_start`, not `now()` (knowledge/airflow/...)

## Risks

1. <risk> (source) -> <test or mitigation>

## Open questions for the tech lead

1. <question>
