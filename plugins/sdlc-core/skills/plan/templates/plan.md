---
jira: <KEY>
spec: specs/<KEY>/spec.md
status: draft            # draft | accepted  (risk: high plans are accepted by the tech lead)
accepted_by:
accepted_at:
---

# Plan: <KEY> <title>

## Files that change

### <repo-a>
- `path/to/new_module.py` (new): <why>
- `tests/test_new_module.py`: AC-1, AC-2

### <repo-b>
- `src/feature/Panel.tsx`: AC-3

## Order of work

- [ ] **T-1** <imperative title> (AC-2), in <repo-a>. Tests first: `test_<key>_ac_2_<behaviour>`.
      Done when: `pytest tests/test_new_module.py -q` passes and `ruff check .` is clean.
- [ ] **T-2** <imperative title> (AC-1, AC-3), in <repo-b>. Tests first: `<KEY> AC-3: ...`.
      Done when: `npm test -- Panel` passes.

## Risks

- <What could break, and the test that would catch it.>
- Riskiest step: <which, and why>.
- Not chosen: <alternative>, because <reason>.

## Proof

| AC | Test (qualified name) | Level | Repo |
|---|---|---|---|
| AC-1 | `<KEY> AC-1: ...` | component | <repo-b> |

Evidence: `evidence.py run` PASS at the PR head (checks, AC coverage, fail-to-pass, this plan).

## Locked tests

None.
