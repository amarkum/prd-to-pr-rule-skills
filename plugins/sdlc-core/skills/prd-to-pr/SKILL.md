---
name: prd-to-pr
description: Runs one Jira story or epic through the AI-native loop (Plan, Design, Build, Test, Deploy, Maintain) from a Confluence PRD to a draft PR with evidence, stopping at every human gate and resuming from specs/<KEY>/. Use for "take this PRD to a PR" or "start PAY-123".
argument-hint: "<confluence-url | page-id | JIRA-KEY> [intent|design|plan|build|verify|pr]"
disable-model-invocation: true
---

# PRD to PR: the loop

Input: `$ARGUMENTS`: a Confluence PRD link or page id, or a Jira key, optionally followed by the stage to resume from.

Every stage ends by committing an artifact to `specs/<KEY>/` that the next stage reads. Any session or teammate can
resume from them, and their git history is the audit trail: who asked for what, what the agent produced, who approved
it. Never start a stage until the previous stage's exit condition holds.

| Stage | Skills | Commits | Exit condition (the gate) |
|---|---|---|---|
| 1 Plan | `prd-review` | `prd.md`, `prd-review.md`, `intent.md` | PRD READY and the intent accepted by the product owner. NEEDS_CLARIFICATION: questions go to the product owner and the workflow STOPS |
| 2 Design | `context-gather`, `spec-write` | `context.md`, `spec.md` | a human sets `status: approved`, after flagged concerns are resolved with their policy owners. STOP until then |
| 3 Build | `plan`, `build` | `plan.md`, then tests and code | plan accepted (the engineer, or the tech lead for risk: high); every task ticked and green |
| 4 Test | `verify` | `.ai/evidence/` (not committed) | evidence PASS for the committed HEAD: checks, AC coverage, fail-to-pass, plan match, locked tests |
| 5 Deploy | `pr-open`, `pr-babysit` | draft PR, Jira link | PR open as a draft with evidence; review comments and failing checks addressed. Humans merge |
| 6 Maintain | `learn`, `triage` | `retro.md`, knowledge PRs, new `intent.md` | lessons captured (or "none recorded"); incidents re-enter as intents with an eval |

## Resolve the work item

1. Find the Jira key in the argument, the PRD header table, or the branch name. If there is none, ask. Never invent a key.
2. When resuming, read `specs/<KEY>/` (front matter `status` of intent, spec and plan; ticked tasks in plan) and the
   branch, and tell the user which stage you will resume from before continuing.
3. Work on branch `feat/<KEY>-<short-slug>` from the default branch. Spec-only work may use `spec/<KEY>-<slug>`.

## Gates (never bypass, never self-certify)

- **Intent**: NEEDS_CLARIFICATION means the product owner receives the questions and the workflow stops. It resumes
  when the PRD page has a new version. READY plus the product owner marking the PRD ready accepts the intent.
- **Spec**: only a human approves a spec. The edit hook blocks agents from writing `status: approved` and blocks code
  edits while the spec is a draft.
- **Plan**: the edit hook blocks code edits until `plan.md` is accepted, and blocks agents from accepting the plan of a
  risk: high spec.
- **Evidence**: the shell and MCP hooks refuse to create a PR without passing evidence for HEAD.
- **Merge and release**: humans merge; agents open draft PRs only. The shell hook blocks production releases without a
  release authorization (`RELEASE_APPROVAL`) and asks for each one even with it.

## Multi-repo stories

The spec's "Repo impact and sequencing" table sets the order: producers before consumers (data pipeline, then API
contract, then MFE, then shell), backward compatible at every step. Each repo gets its own branch, plan section,
evidence and draft PR, all linked to the same Jira epic. Run one session per repo (or `claude --worktree` per
independent task) so each repo's permissions, hooks and checks apply.

## Stop and report instead of pushing on when

- a gate is not met;
- two repair rounds have not made `verify` pass;
- the change needs a migration, an auth or infrastructure change, or a new dependency that the approved spec doesn't cover;
- scope grows beyond the spec, or the spec contradicts the code you find.

## At every stop, report

The stage reached, the artifacts written (paths), the decision needed and from whom, and the exact command to resume,
for example `/sdlc-core:prd-to-pr PAY-412 build`.
