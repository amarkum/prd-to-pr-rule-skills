# <KEY> tasks

Spec: `specs/<KEY>/spec.md` (approved by <name> on <date>)

## <repo-a> (order 1)

### T-1 <imperative title> (ACs: AC-2)

- Tests first: `test_<key>_ac_2_<behaviour>` in `tests/...`
- Change: `<files>`
- Done when: `pytest tests/test_x.py -q` passes and `ruff check .` is clean
- Notes: <contract or data assumption>

## <repo-b> (order 2)

### T-2 ...

## Coverage

- AC-1: T-2
- AC-2: T-1
