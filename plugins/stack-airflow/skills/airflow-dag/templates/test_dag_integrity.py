"""DAG integrity tests: copy to tests/dags/test_dag_integrity.py.

Static checks run everywhere (no Airflow needed); DagBag checks run where Airflow is installed.
Configure DAG_FOLDER / REQUIRED_TAGS for your repo.
"""
import ast
import os
from pathlib import Path

import pytest

DAG_FOLDER = Path(os.environ.get("DAG_FOLDER", "dags"))
FORBIDDEN_TOP_LEVEL_CALLS = {"now", "utcnow", "today", "get"}  # datetime.now(), pendulum.now(), Variable.get()
FORBIDDEN_RECEIVERS = {"datetime", "pendulum", "Variable", "date"}


def _dag_files():
    return sorted(p for p in DAG_FOLDER.rglob("*.py") if not p.name.startswith("_"))


def _top_level_calls(tree: ast.Module):
    """Calls executed at import time: module statements, excluding bodies of functions."""
    stack = list(tree.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Call):
            yield node
        stack.extend(ast.iter_child_nodes(node))


@pytest.mark.parametrize("path", _dag_files(), ids=str)
def test_no_side_effects_at_import(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = []
    for call in _top_level_calls(tree):
        func = call.func
        if isinstance(func, ast.Attribute) and func.attr in FORBIDDEN_TOP_LEVEL_CALLS:
            receiver = func.value
            name = receiver.id if isinstance(receiver, ast.Name) else getattr(receiver, "attr", "")
            if name in FORBIDDEN_RECEIVERS:
                offenders.append(f"{path}:{call.lineno} {name}.{func.attr}()")
    assert not offenders, "import-time calls make DAG parsing slow and runs non-idempotent:\n" + "\n".join(offenders)


@pytest.fixture(scope="session")
def dagbag():
    pytest.importorskip("airflow")
    try:
        from airflow.dag_processing.dagbag import DagBag  # Airflow >= 3.3
    except ImportError:
        from airflow.models import DagBag  # Airflow 2.x / early 3.x
    return DagBag(dag_folder=str(DAG_FOLDER), include_examples=False)


def test_dagbag_has_no_import_errors(dagbag):
    assert dagbag.import_errors == {}, dagbag.import_errors


def test_every_task_has_owner_retries_and_dag_has_tags(dagbag):
    problems = []
    for dag_id, dag in dagbag.dags.items():
        if not dag.tags:
            problems.append(f"{dag_id}: no tags")
        for task in dag.tasks:
            if not task.owner or task.owner == "airflow":
                problems.append(f"{dag_id}.{task.task_id}: owner not set")
            if (task.retries or 0) < 1:
                problems.append(f"{dag_id}.{task.task_id}: retries < 1")
    assert not problems, "\n".join(problems)
