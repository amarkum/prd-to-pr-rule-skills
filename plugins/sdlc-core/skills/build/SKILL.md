---
name: build
description: Implements an accepted plan task by task with strict test-first discipline, one green commit per task, using the stack skill for the repo (Airflow, MFE or frontend); bug fixes commit and lock the reproducing test before the fix. Use when plan.md is accepted, or when asked to "implement", "build" or "code" a planned task.
argument-hint: "<JIRA-KEY> [T-n]"
---

# Build

Preconditions (check them; stop if any fails):
- `specs/<KEY>/spec.md` has `status: approved` and `specs/<KEY>/plan.md` has `status: accepted`
  (the edit hook blocks code changes otherwise);
- you are on branch `feat/<KEY>-<slug>` with a clean tree.

Delegate each task to the `builder` subagent, in the order given in `plan.md`, one task at a time. Pass it the task text,
the spec and plan paths, and the repo's stack. For a single small task you may do the work in the main session,
following the same loop. Tasks the plan marks independent (different files) can run in parallel sessions, each in its
own worktree (`claude --worktree <KEY>-T<n>`): start with two or three, and add more only while review keeps up.

## The loop, per task

1. **Load the stack skill** for `.ai/repo.yaml` `repo.stack`: `airflow-dag`, `mfe-remote` or `frontend-feature`.
   It holds the conventions and the test patterns for that stack.
2. **Write the failing tests first**, using the qualified AC names from the spec (`PAY-412 AC-3: ...` or `test_pay_412_ac_3_...`).
3. **Run them and confirm they fail for the right reason** (an assertion about the missing behaviour, not an import error or
   a typo). Write down what failed.
4. **Implement the minimum** to make them pass. Follow the existing patterns cited in `context.md`.
5. **Run the task's done-when command** and the fast checks from `.ai/repo.yaml` (lint, typecheck, unit).
6. **Commit**: `<KEY> T-n: <imperative summary>`. Tick the task in `plan.md` (`- [x]`) in the same commit; that file is
   the resume point for any later session. If the work touched a file the plan doesn't list, add it to "Files that
   change" in the same commit, with the reason.

## Bug fixes: lock the proof first

1. Reproduce the bug as a test. Run it and confirm it fails for the reason you expect.
2. Commit the test on its own: `<KEY>: failing test for <bug>`.
3. Lock it: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py lock <test-file>`, then commit `plan.md`.
4. Make it pass without touching the test. The hooks block edits to locked tests, and `evidence.py` fails if a locked
   test's content changes, however it was edited. A test that existed before the fix and that you couldn't rewrite
   is the proof the bug is gone.

## Limits

- **Three attempts per task.** If a task still fails after three implement-and-test cycles, stop and report what you tried
  and what you saw. Don't flail.
- **Don't change a test to make it pass** unless the test contradicts the spec. If so, say so explicitly and cite the AC.
- **Stay in scope.** If you need a migration, a new dependency, an auth change or a protected path that the plan doesn't
  cover, stop and ask.
- **No speculative abstractions or drive-by refactors.** If you notice a real problem outside scope, note it for the PR description.

## Finish

When every task is ticked, run the `verify` skill. Building is not finished until verify passes.
