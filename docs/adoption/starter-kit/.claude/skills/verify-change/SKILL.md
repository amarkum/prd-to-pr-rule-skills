---
name: verify-change
description: Close the verification loop before a PR. Runs make verify and fixes failures, then gets an independent verifier pass, parallel specialist reviews and a synthesised review, and writes evidence.md and review.md. Use when implementation looks done or the builder types /verify-change. Named verify-change so it does not replace Claude Code's bundled /verify skill.
argument-hint: "<change id>"
---

# /verify-change: code to continuous evidence

Change id: $ARGUMENTS. If none was given, infer it from the branch name or the newest folder under
`docs/changes/`, and confirm with the builder.

1. **Closed loop.** Run `make verify`. On failure, diagnose the first failure, fix the cause and
   run it again. Never weaken, skip or delete a test to get a pass. Stop after five rounds and
   report what still fails.
2. **Independent verification.** Start the `verifier` subagent with the change id. If it returns
   `VERDICT: FAIL`, fix the items and go back to step 1. These rounds count toward the five.
3. **Specialist review, in parallel.** Get the diff with `git diff origin/main...HEAD` (use the
   repository's base branch). In one message, start `architecture-reviewer`, `security-reviewer`
   and the `test-engineer` (read-only coverage critique) with the diff and the change id.
4. **Synthesise.** Pass every finding array to `review-synthesizer`, which writes
   `docs/changes/<id>/review.md`.
5. **Absorb.** Apply the "Agents absorb" findings, then run `make verify` again. If code changed,
   run the verifier again.
6. **Report** the verdict, the paths to `evidence.md` and `review.md`, the "Humans judge" questions
   and the residual risk. Open a PR only if the builder asks. The PR description links every
   artifact in `docs/changes/<id>/`.
