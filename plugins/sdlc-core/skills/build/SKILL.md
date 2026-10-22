---
name: build
description: Implements an approved spec task by task with strict test-first discipline, one green commit per task, using the stack skill for the repo (Airflow, MFE or frontend). Use when the spec is approved and tasks.md exists, or when asked to "implement", "build" or "code" a planned task.
argument-hint: "<JIRA-KEY> [T-n]"
---

# Build

Preconditions (check them; stop if any fails):
- `specs/<KEY>/spec.md` has `status: approved`;
- `specs/<KEY>/tasks.md` exists;
- you are on branch `feat/<KEY>-<slug>` with a clean tree.

Delegate each task to the `builder` subagent, in the order given in `tasks.md`, one task at a time. Pass it the task text,
the spec path and the repo's stack. For a single small task you may do the work in the main session, following the same loop.

## The loop, per task

1. **Load the stack skill** for `.ai/repo.yaml` `repo.stack`: `airflow-dag`, `mfe-remote` or `frontend-feature`.
   It holds the conventions and the test patterns for that stack.
2. **Write the failing tests first**, using the qualified AC names from the spec (`PAY-412 AC-3: ...` or `test_pay_412_ac_3_...`).
3. **Run them and confirm they fail for the right reason** (an assertion about the missing behaviour, not an import error or
   a typo). Write down what failed.
4. **Implement the minimum** to make them pass. Follow the existing patterns cited in `context.md`.
5. **Run the task's done-when command** and the fast checks from `.ai/repo.yaml` (lint, typecheck, unit).
6. **Commit**: `<KEY> T-n: <imperative summary>`. Tick the task in `tasks.md` (`- [x]`) in the same commit; that file is
   the resume point for any later session.

## Limits

- **Three attempts per task.** If a task still fails after three implement-and-test cycles, stop and report what you tried
  and what you saw. Don't flail.
- **Don't change a test to make it pass** unless the test contradicts the spec. If so, say so explicitly and cite the AC.
- **Stay in scope.** If you need a migration, a new dependency, an auth change or a protected path that the spec does not
  cover, stop and ask.
- **No speculative abstractions or drive-by refactors.** If you notice a real problem outside scope, note it for the PR description.

## Finish

When every task is ticked, run the `verify` skill. Building is not finished until verify passes.
