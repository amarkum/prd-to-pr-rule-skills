# stack-airflow: Airflow data-pipeline pack

Teaches the AI SDLC builder this organisation's Airflow conventions. The `airflow-dag` skill activates automatically when
you work in `dags/`, `include/`, `plugins/` or `tests/`. It covers idempotent interval-driven loads, parse-time hygiene,
retries and alerting, data contracts with schema snapshots, and the tests that count as evidence: DAG integrity,
idempotency, `dag.test()` integration and data-quality checks, all named by acceptance criterion.
`templates/test_dag_integrity.py` is a ready-to-copy integrity test; it needs no Airflow for its static checks.
Install with `/plugin install stack-airflow@ai-sdlc` (this enables `sdlc-core` too). Owned by the Data Engineering Guild.
