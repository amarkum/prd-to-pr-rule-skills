---
name: plan
description: Turns an approved spec into plan.md (files that change, test-first tasks, risks, proof per AC, locked tests) in plan mode, so nothing is edited until the plan is accepted. Use after spec approval, or for "plan the work" or "split this into tasks".
argument-hint: "<JIRA-KEY>"
---

# Plan (Stage 3: Build starts here)

Precondition: `specs/<KEY>/spec.md` has `status: approved`. If it doesn't, stop and say so.
Output: `specs/<KEY>/plan.md` from `templates/plan.md`. The edit hook blocks code changes until it says `status: accepted`.

## 1. Draft it in plan mode

Interactive sessions: ask the engineer to switch to plan mode (Shift+Tab or `/plan`, or start with `claude --permission-mode plan`)
so you can read the codebase without changing anything. Headless: research read-only, write only `plan.md`.
Read `spec.md`, `intent.md` and `context.md`, then write:

- **Files that change.** Every file the diff will touch, test files included, grouped under `### <repo>` with the repo
  names from `.ai/repo.yaml`. Globs are fine for generated or bulk changes. `evidence.py` fails the PR if the diff
  touches a file that isn't listed, so the plan stays true.
- **Order of work.** Tasks as checkboxes, one green commit each, under about 200 changed lines. Each names the failing
  tests to write first (qualified AC names from the spec's test plan) and its done-when command from the manifest
  `checks`. Data and contracts first (additive), then producers, then consumers, then UI wiring behind the flag.
  Every in-scope AC appears in at least one task. Tasks that touch different files can run in parallel worktrees.
- **Risks.** What the change could break, the riskiest step, and the options you didn't choose and why.
- **Proof.** One row per AC: test name, level, repo. Add screenshots for UI ACs and any manual check the spec allows.
- **Locked tests.** For a bug fix, the reproducing tests that `build` will commit and lock before touching the code.

## 2. Interrogate it before asking for acceptance

Answer in the plan: what could this break, which step is riskiest, what didn't you choose? Iterate until an engineer
who never saw this conversation could implement the change from `plan.md` alone. A task touching a protected path
(`.ai/repo.yaml` `protected_paths`) is marked `needs-approval`.

## 3. Acceptance (the plan gate)

- **Routine work, interactive**: present the plan (in plan mode, by exiting plan mode with it). When the engineer
  accepts, write `plan.md` with `status: accepted`, `accepted_by: <engineer>`, `accepted_at`, and commit it.
- **risk: high** (from the spec): the tech lead or architect accepts. Commit `plan.md` as `status: draft` and ask for
  it; the edit hook blocks you from accepting it yourself.
- **CI, routine work** (auto mode): `accepted_by: "auto (CI, risk <tier>)"`. Never for risk: high.
- Anything the spec doesn't cover (new dependency, migration, auth change, another team's code): stop and raise it with
  the tech lead instead of planning around it.

## 4. Keep it true

When the implementation departs from the plan, update `plan.md` in the same commit. Review checks the diff against it,
and the share of PRs that still match their plan is one of the team's metrics.
