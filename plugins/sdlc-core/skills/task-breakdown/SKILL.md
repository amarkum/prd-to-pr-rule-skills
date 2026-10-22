---
name: task-breakdown
description: Breaks an approved spec into small, ordered, test-first tasks per repository, each mapped to acceptance criteria with explicit done-when checks. Use after a spec is approved, or when asked to "plan the work", "split this into tasks" or "what's the implementation order".
argument-hint: "<JIRA-KEY>"
---

# Task breakdown

Precondition: `specs/<KEY>/spec.md` has `status: approved`. If it does not, stop and say so.

Output: `specs/<KEY>/tasks.md` from `templates/tasks.md`.

## How to cut tasks

- **One task = one commit** that leaves the repo green. Aim for under about 200 changed lines; split larger ones.
- **Test first.** Each task names the failing test or tests to write first (the qualified AC names from the spec's test plan),
  then the minimal code to make them pass.
- **Order by dependency.** Data and contracts first (additive), then producers, then consumers, then UI wiring behind the
  flag, then cleanup.
- **Every in-scope AC appears in at least one task.** Add a coverage line at the end: `AC-1: T-2, T-4 ...`.
- **Name the files** you expect to touch, from `context.md`. A task touching a protected path (`.ai/repo.yaml`
  `protected_paths`) is flagged `needs-approval`.
- **Done when** is a command from the manifest `checks`, plus the named tests passing. Never "looks good".

## Multi-repo

Group tasks by repo in sequencing order. Note the cross-repo contract each group relies on, and how the consumer is tested
against it before the producer ships (contract test, mocked response from the agreed schema, or the MF type snapshot).

## Then

Show the task list and total size. If anything exceeds the spec (new dependency, migration, other team's code), stop and
raise it with the tech lead instead of planning around it.
