# Airflow test patterns

All test names cite the AC: `test_<key>_ac_<n>_<behaviour>`, for example `test_pay_412_ac_2_upserts_status_once`.
`ac_coverage.py` reads these names from the JUnit file (`pytest --junitxml=reports/junit-unit.xml`).
Prefer the name over `record_property`: properties need `-o junit_family=xunit1` to appear in the JUnit output.

## 1. Pure task logic (fast, no Airflow needed)

```python
# include/run_status.py
def to_status_doc(run: dict, interval_end) -> dict:
    return {"run_id": run["id"], "status": run["state"].upper(), "updated_at": interval_end}

# tests/test_run_status.py
import pendulum
from include.run_status import to_status_doc

def test_pay_412_ac_2_status_doc_uses_interval_end_not_now():
    end = pendulum.datetime(2026, 10, 1, 6, tz="UTC")
    doc = to_status_doc({"id": "R-1", "state": "completed"}, end)
    assert doc == {"run_id": "R-1", "status": "COMPLETED", "updated_at": end}
```

## 2. Idempotency (required for every write path)

Write through a small function that takes the collection, so the test can pass a fake or a local Mongo collection.

```python
# include/publish.py
from pymongo import UpdateOne

def publish_status(collection, docs: list[dict]) -> int:
    ops = [UpdateOne({"run_id": d["run_id"]}, {"$set": d}, upsert=True) for d in docs]
    return collection.bulk_write(ops).upserted_count if ops else 0

# tests/test_publish.py  (mongomock, or a local Mongo fixture)
import mongomock
from include.publish import publish_status

def test_pay_412_ac_2_rerun_of_same_interval_is_idempotent():
    coll = mongomock.MongoClient().payroll.payroll_run_status
    docs = [{"run_id": "R-1", "status": "COMPLETED"}]
    publish_status(coll, docs)
    publish_status(coll, docs)           # same interval re-run
    assert coll.count_documents({}) == 1
    assert coll.find_one({"run_id": "R-1"})["status"] == "COMPLETED"
```

## 3. DAG integration with `dag.test()` (local services, synthetic data)

```python
import pendulum
import pytest

@pytest.mark.integration
def test_pay_412_ac_2_dag_run_publishes_completed_status(local_mongo):  # fixture: docker Mongo + seeded synthetic runs
    from dags.payroll_processing import dag
    # Airflow 3: logical_date=...; Airflow 2.5+: execution_date=...
    dag.test(logical_date=pendulum.datetime(2026, 10, 1, tz="UTC"))
    doc = local_mongo.payroll.payroll_run_status.find_one({"run_id": "R-1"})
    assert doc["status"] == "COMPLETED"
```

`dag.test()` needs an initialised local metadata DB (`airflow db migrate` in the test environment). Never point it at a shared one.

## 4. Data contract against the committed snapshot

```python
import json, pathlib

SNAPSHOT = json.loads(pathlib.Path("docs/schemas/mongo/payroll.payroll_run_status.json").read_text())

def test_pay_412_ac_2_status_doc_matches_contract():
    doc = {"run_id": "R-1", "employer_id": "E-1", "entity_id": "N-1", "run_name": "Oct", "status": "COMPLETED",
           "updated_at": "2026-10-01T06:00:00Z", "dag_run_id": "scheduled__2026-10-01"}
    missing = [f for f in SNAPSHOT["required"] if f not in doc]
    assert not missing, f"contract fields missing: {missing}"
```

To check whether a snapshot change is additive or breaking, run
`python3 <sdlc-connectors>/scripts/schema_snapshot.py diff old.json new.json` (exit 1 = breaking).

## 5. Data-quality checks inside the DAG

Implement them as tasks after the load (an SQL check operator, or a small Python task that queries counts) that **raise**
on violation, so the run fails visibly. Unit-test the check function with good and bad inputs, named by AC when the PRD
states a data requirement.

## Airflow 3 notes that affect tests

- Imports come from `airflow.sdk`. `DagBag` moved to `airflow.dag_processing.dagbag` (3.3; the old path is deprecated).
- SubDAGs, SLAs and `execution_date` are gone; `schedule_interval` became `schedule`, and the default schedule is `None`.
- `catchup` defaults to False. `xcom_pull()` without `task_ids` reads only the current task.
- Task code cannot use the metadata DB directly. Pass what a task needs through XCom or its parameters.
- `ruff check --select AIR301,AIR302` flags removed and moved APIs.
