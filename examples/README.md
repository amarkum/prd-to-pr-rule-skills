# Examples

One fictional cross-repo story, **PAY-412 Payroll run status tracker**, used across the docs, tests and evals:

- An Airflow DAG (`data-airflow`) writes run status to MongoDB.
- A micro-frontend (`payroll-mfe`) exposes a status panel.
- The shell (`web-shell`) mounts it behind a role gate and a flag.

| File | Shows |
|---|---|
| `prds/PAY-412-incomplete.md` | A PRD the gate bounces: no non-goals, two unresolved open questions, "load fast", no error states (16/100) |
| `prds/PAY-412-complete.md` | The same PRD after the product owner's answers: READY (97/100) |
| `specs/PAY-412/spec.md` | An approved spec with FR/AC IDs, repo impact and sequencing, and a test plan |
| `evidence/junit-*.xml` | JUnit in the shape pytest, Vitest and Playwright emit, with AC-named tests from the three repos |
| `demo.py` | The deterministic layer end to end in a throwaway git repo (run `make demo`) |

Try it:

```bash
python3 plugins/sdlc-core/scripts/prd_lint.py examples/prds/PAY-412-incomplete.md
python3 plugins/sdlc-core/scripts/ac_coverage.py --spec examples/specs/PAY-412/spec.md --junit 'examples/evidence/junit-*.xml'
```
