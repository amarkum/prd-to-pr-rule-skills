---
name: plan-change
description: Explore the repository and propose docs/changes/<id>/plan.md (files affected, sequence, tests, migration, risks, rollback, verification) from the approved intent and spec. No code changes until the builder approves. Named plan-change so it does not replace Claude Code's built-in /plan command. Use when the builder types /plan-change.
argument-hint: "<change id>"
disable-model-invocation: true
---

# /plan-change: spec to plan.md

Change id: $ARGUMENTS

Run this in plan mode. Press Shift+Tab until plan mode shows, or start with
`claude --permission-mode plan`. In plan mode you can read and explore but cannot edit, so the
builder's approval of your plan is the approval of plan.md.

1. **Preconditions.** The intent is approved. For significant and high-risk changes, the spec is
   approved too. If not, stop and say what is missing.
2. **Explore.** Read the components the spec names. Find files and callers with Grep and Glob. Read
   the tests that cover the area and the Known traps in `CLAUDE.md`. For impact analysis, run
   `kompactor graph impact <file|symbol>` on each entry point you will change if it is installed.
   Otherwise list the callers you found.
3. **Draft the plan** in the shape of `docs/changes/_templates/plan.md`: components, files and modules
   with what changes in each, API and database changes, an implementation sequence of small steps
   that can each be verified, the tests required (citing FR and NFR ids), migration steps, risks,
   rollback as exact steps, and verification as exact commands ending in `make verify`. For a
   defect, the first step is always the failing test.
4. **Parallel work.** If the plan has independent streams, say so and suggest one git worktree per
   stream (`claude --worktree <name>`). Run two or three sessions at most, and only while a human
   can still review them.
5. **Ask for approval** with the plan-mode approval prompt.
6. **After approval,** write `docs/changes/<id>/plan.md` with `status: approved`, `approved:` set to
   today and `approver:` set to the builder. Then stop, unless the builder said to start building.
