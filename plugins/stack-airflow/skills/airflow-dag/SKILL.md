---
name: airflow-dag
description: Conventions and evidence-grade tests for this organisation's Airflow data pipelines - idempotent interval-driven loads into MongoDB or SQL, parse-time hygiene, retries and alerting, data contracts and schema snapshots, plus DagBag, unit, idempotency, dag.test and data-quality tests named by acceptance criterion. Use when creating or changing DAGs, tasks, operators, sensors or the data a pipeline writes, or when writing Airflow tests.
paths:
  - "dags/**"
  - "include/**"
  - "plugins/**"
  - "tests/**/*.py"
---

# Airflow DAG builder

First check the Airflow major version (requirements, constraints file, Dockerfile) and match the repo's imports:
Airflow 3 uses `from airflow.sdk import DAG, dag, task, Asset`; Airflow 2 uses `airflow.decorators` and `airflow.models`.
Never mix the two.

## Non-negotiables

1. **Idempotent tasks.** Re-running the same data interval must give the same result. Take time from the context
   (`data_interval_start` / `data_interval_end`), never from `datetime.now()`. Write with upserts keyed by natural keys,
   or load into staging and swap.
2. **Parse-time hygiene.** No I/O, network, database calls or heavy work at module top level. No `Variable.get()` at top
   level: use templates (`{{ var.value.x }}`) or read it inside the task. The scheduler imports DAG files constantly.
3. **Explicit scheduling.** A static, timezone-aware `start_date`, an explicit `schedule` and explicit `catchup`.
   Set `max_active_runs` when runs could overlap on the same target.
4. **Resilience on every task.** `retries`, `retry_delay` (exponential backoff for flaky sources) and `execution_timeout`.
   Add failure callbacks or alerts per repo convention. (SLAs were removed in Airflow 3; use deadline alerts there.)
5. **Credentials** come from Connections and the secrets backend, referenced by conn id. Never hardcode hosts or credentials.
6. **Small XComs.** XCom carries references (ids, paths, counts), never datasets.
7. **Logic out of the DAG file.** Business logic lives in `include/` as pure, unit-testable functions; DAG files only wire tasks.
8. **Waiting** uses deferrable operators or sensors in `mode="reschedule"`, never `sleep` loops.
9. **The data a DAG writes is a contract.** Changes are additive (new fields, new collections). A rename or removal needs a
   versioned migration plan in the spec. Update the snapshot in `docs/schemas/` in the same PR (`schema_snapshot.py` from
   sdlc-connectors) and create indexes for new query patterns, idempotently.
10. **Data-quality gates.** After a load, check row counts, nulls and uniqueness as tasks that fail the run.
    Never log a bad load and carry on.

## Tests that count as evidence

- **DAG integrity**: copy `templates/test_dag_integrity.py` into `tests/dags/`. It asserts no import errors; owner, tags and
  retries on every task; no top-level `now()` or `Variable.get()`.
- **Unit tests** for `include/` logic, named `test_<key>_ac_<n>_<behaviour>`.
- **Idempotency test** for every write path: run the load twice for the same interval and assert an identical end state
  (same count, same keys).
- **`dag.test()` integration test** for the changed DAG, against local services (Docker Mongo) with synthetic data.
  Mark it `integration` if the repo separates those.
- **Contract test**: a produced document validates against its `docs/schemas/` snapshot.

Patterns and snippets: `references/testing.md`.

## Commands (use the ones in `.ai/repo.yaml`; these are typical)

- `ruff check dags include tests`. Add `--select AIR301,AIR302` when moving to Airflow 3.
- `pytest tests/dags -q`, then `pytest tests -q -m "not integration"`.
- `airflow dags list-import-errors -l -o json` checks parsing without a scheduler.
- `airflow dags test <dag_id> <logical_date>` runs end to end against a **local** metadata DB only.

Never trigger, backfill, pause or clear DAGs on a shared Airflow; the shell hook blocks it. Ask for an approved run instead.

## Before you say a DAG change is done

- [ ] A re-run of the same interval is safe, and an idempotency test proves it
- [ ] No top-level I/O, `now()` or `Variable.get()`
- [ ] Retries, timeouts and alerts are set
- [ ] The contract snapshot is updated, and the change is additive or has an approved migration
- [ ] Indexes exist for new queries
- [ ] The backfill and re-processing impact is stated in the PR
