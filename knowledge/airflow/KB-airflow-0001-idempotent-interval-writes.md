---
id: KB-airflow-0001
title: Derive pipeline timestamps from the data interval and upsert by natural key
scope: stack:airflow
type: incident
status: active
owner: "@org/data-eng"
provenance: [example INC-2291 postmortem, example PR 812]
created: 2026-10-22
review_by: 2027-04-22
promoted_to: skill:stack-airflow/airflow-dag#non-negotiables-1
---

**Symptom.** A backfill re-ran three intervals and produced duplicate status rows; dashboards showed a run as both
Processing and Completed.

**Cause.** The task stamped rows with `datetime.now()` and inserted instead of upserting, so a re-run created new rows.

**Do.** Take time from `data_interval_end`, and upsert keyed by the natural key (`run_id`).

**Don't.** Use `now()` in tasks that write, or `insert_many` for state that can be recomputed.

**Guarded by.** The idempotency test pattern in `airflow-dag/references/testing.md` and the import-time check in
`test_dag_integrity.py`.
