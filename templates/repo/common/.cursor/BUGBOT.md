# Review guidance for AI reviewers (Claude Code Review, pr-reviewer, Bugbot)

- Check the diff against `specs/<KEY>/spec.md`: every in-scope AC is implemented, and nothing outside the spec changed.
- Trust the CI evidence comment ("Evidence: PASS" at the PR head SHA) over claims in the description.
- Prioritise: authorization enforced server-side; idempotent writes; additive contract and schema changes; error, empty
  and no-access states; no PII in logs or analytics; tests that assert outcomes rather than rendering.
- Don't comment on style that linters enforce.
