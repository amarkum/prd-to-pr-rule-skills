---
jira: PAY-412
spec: specs/PAY-412/spec.md
status: accepted
accepted_by: "@payroll-dev (plan mode)"
accepted_at: 2026-10-20
---

# Plan: PAY-412 Payroll run status tracker

## Files that change

### data-airflow
- `dags/payroll_processing.py`: add the `publish_run_status` task after `finalize_run`
- `include/payroll/run_status.py` (new): upsert by `run_id` using the data interval
- `tests/test_publish_run_status.py` (new): AC-2, idempotent re-run
- `docs/schemas/payroll_run_status.json` (new): schema snapshot

### payroll-mfe
- `src/status/StatusPanel.tsx` (new), `src/status/useRunStatus.ts` (new)
- `src/status/StatusPanel.test.tsx` (new): AC-1, AC-3, AC-4, AC-6, AC-7
- `module-federation.config.ts`: expose `./StatusPanel`

### web-shell
- `src/routes/payroll/Dashboard.tsx`: mount the panel behind `payroll_status_tracker` and the role gate
- `e2e/payroll-dashboard.spec.ts`: AC-5

## Order of work

- [x] **T-1** Publish run status from the DAG (AC-2), in data-airflow. Tests first: `test_pay_412_ac_2_*`.
      Done when: `pytest tests/test_publish_run_status.py -q` passes and `ruff check dags include tests` is clean.
- [x] **T-2** Status panel with empty, error and filter states (AC-1, AC-3, AC-4, AC-6, AC-7), in payroll-mfe.
      Tests first: `PAY-412 AC-1` to `AC-7` in `StatusPanel.test.tsx`. Done when: `npm test -- StatusPanel` passes.
- [x] **T-3** Mount behind the flag and the role gate (AC-5), in web-shell. Tests first: `PAY-412 AC-5` (Playwright).
      Done when: `npx playwright test e2e/payroll-dashboard.spec.ts` passes.

## Risks

- Duplicate status rows on backfill (INC-2291): the upsert keys on `run_id` and the data interval; T-1 tests a re-run.
- Riskiest step: the MF expose in T-2, because the shell resolves it at runtime; the type snapshot and the shell e2e
  catch a broken contract.
- Not chosen: polling the Airflow REST API from the panel, because it would expose Airflow to the browser.

## Proof

| AC | Test (qualified name) | Level | Repo |
|---|---|---|---|
| AC-1 | `PAY-412 AC-1: shows one card per run` | component | payroll-mfe |
| AC-2 | `test_pay_412_ac_2_status_upserted_on_completion` | unit + dag.test | data-airflow |
| AC-3 | `PAY-412 AC-3: filters by status and syncs the URL` | component | payroll-mfe |
| AC-4 | `PAY-412 AC-4: shows the employer for ops agents` | component | payroll-mfe |
| AC-5 | `PAY-412 AC-5: employees see the access-unavailable state` | e2e | web-shell |
| AC-6 | `PAY-412 AC-6: empty state` | component | payroll-mfe |
| AC-7 | `PAY-412 AC-7: error state with retry` | component | payroll-mfe |

Evidence: `evidence.py run` PASS at each PR head.

## Locked tests

None.
