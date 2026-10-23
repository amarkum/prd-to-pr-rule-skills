---
id: "<TICKET>-<short-slug>"
commit: "<git sha that was verified>"
verified_by: verifier               # the agent or person that produced this evidence
verified_at: "YYYY-MM-DDTHH:MM:SSZ"
verdict: pass                       # pass | fail
loop_iterations: 1                  # rounds of fix-and-rerun before this pass (feeds rework rate)
checks:                             # one entry per command; results are pass | fail | skipped
  - name: build
    command: make build
    result: pass
  - name: lint
    command: make lint
    result: pass
  - name: test
    command: make test
    result: pass
  - name: verify
    command: make verify
    result: pass
frozen_tests: []                    # frozen tests that cover this change
---

# Verification evidence: <title>

Proof that it works and is safe. Only a passing evidence set reaches a human reviewer.

## Summary
One paragraph: what was verified, against which commit, and the verdict.

## Verification loop
| Step | Command | Result | Notes |
|---|---|---|---|
| Compile | make build |  |  |
| Lint | make lint |  |  |
| Unit tests | make test |  |  |
| Integration and contract tests |  |  |  |
| Security checks |  |  |  |
| UI or visual checks |  |  |  |

## Acceptance trace
| Requirement or success metric | Evidence (test, check or measurement) | Result |
|---|---|---|
| FR-1 |  |  |

## Defect reproduction
For defects only: the failing test before the fix, and the same test passing after.

## Review findings
Link `review.md`. Count of findings by severity, and any that remain open.

## Residual risk
What a human still has to judge: problem fit, blast radius, anything not covered by tests.
