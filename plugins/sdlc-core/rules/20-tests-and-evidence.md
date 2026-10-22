---
description: Test and evidence standard for AI-built changes
---
# Tests and evidence (always on)

- Test first, per acceptance criterion: write the failing test, watch it fail for the right reason, then implement.
- Name AC tests with the qualified ID so coverage is computed, not claimed:
  `it("PAY-412 AC-3: ...")` in JS/TS, `def test_pay_412_ac_3_...` in Python.
- A new test must fail on the base commit; `fail_to_pass.py` checks this. A test that passes before and after
  does not prove the change.
- Never skip, delete, xfail, `.only`, or loosen assertions to get to green. If a test is wrong, fix it and
  justify the change in the PR.
- Tests are deterministic: frozen time, no real network, no shared state, seeded randomness.
- Evidence is what `evidence.py run` records for a committed HEAD, not a summary. Re-run it after every commit
  you intend to ship.
