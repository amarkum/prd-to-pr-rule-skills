# Review instructions

Read by the managed Claude Code Review, the `ai-review` workflow and the `pr-reviewer` agent. Findings inform people;
they never approve or block a PR on their own. Branch protection requires a code owner's approval.

## Passes

Run three passes and tag each finding with its pass:
- **Bugs**: logic errors, broken edge cases (empty, error, no access, re-run), subtle regressions, non-idempotent writes.
- **Security**: injection, authorization enforced only in the UI, secrets, PII in logs or analytics, new egress.
- **Compliance**: the diff matches `specs/<KEY>/spec.md` (every in-scope AC implemented, nothing outside it) and
  `specs/<KEY>/plan.md` (the files and order it names); contract and schema changes are additive; tests assert the
  AC's outcome rather than "renders without crashing".

## What Important means here

Reserve Important for findings that would break behaviour, leak data or breach a policy. Style and naming are nits.

## Cap the nits

Report at most five nits per review; summarise the rest as a count.

## Do not report

Generated files, lockfiles, and anything CI already enforces (lint, format, types). Don't re-derive test results:
trust the CI evidence comment ("Evidence: PASS" at the head SHA) over claims in the PR description.

## Repeated findings

When a finding repeats one from an earlier PR, say so. The second time a mistake shows up, the correction goes into
`CLAUDE.md` under "Things Claude gets wrong"; the third time, the `learn` skill proposes a check.
