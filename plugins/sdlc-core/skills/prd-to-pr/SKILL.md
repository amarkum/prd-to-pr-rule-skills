---
name: prd-to-pr
description: Runs the whole PRD-to-pull-request workflow for one Jira story or epic (PRD gate, context, spec, tasks, build, verify, draft PR), stopping at every human gate and resuming from repo state. Use when the user says "take this PRD to a PR", "start PAY-123", or hands over a Confluence PRD to implement.
argument-hint: "<confluence-url | page-id | JIRA-KEY> [resume-from-stage]"
disable-model-invocation: true
---

# PRD to PR

Input: `$ARGUMENTS` — a Confluence PRD link or page id, or a Jira key, optionally followed by a stage to resume from.

Run the stages in order. Each stage has an exit condition; never start the next stage until it holds.
Workflow state lives in git (`specs/<KEY>/`) and Jira, so any session (or teammate) can resume.

| # | Stage | Skill | Writes | Exit condition |
|---|---|---|---|---|
| 1 | PRD gate | `prd-review` | `specs/<KEY>/prd.md`, `prd-review.md` | verdict READY. Otherwise questions go to the product owner and the workflow STOPS |
| 2 | Context | `context-gather` | `context.md` | every claim cites a file, query, ticket or URL |
| 3 | Spec | `spec-write` | `spec.md` (`status: draft`) | a human sets `status: approved`. STOP until then |
| 4 | Plan | `task-breakdown` | `tasks.md` | every in-scope AC maps to a task in a named repo |
| 5 | Build | `build` | tests + code, one commit per task | all tasks done, local checks green |
| 6 | Verify | `verify` | `.ai/evidence/` | evidence PASS for the committed HEAD |
| 7 | Draft PR | `pr-open` | draft PR, Jira link | PR open as draft with the evidence summary |
| 8 | Learn | `learn` (after review or merge) | knowledge/rule PR | lessons captured, or "none" recorded |

## Resolve the work item

1. Find the Jira key in the argument, the PRD header table, or the branch name. If there is none, ask. Never invent a key.
2. When resuming, inspect `specs/<KEY>/` and the branch to find the last completed stage. Tell the user which stage you
   will resume from before continuing.
3. Work on branch `feat/<KEY>-<short-slug>` created from the default branch. Spec-only work may use `spec/<KEY>-<slug>`.

## Gates (never bypass, never self-certify)

- **PRD gate**: NEEDS_CLARIFICATION means the product owner receives the questions and the workflow stops. It resumes
  when the PRD page has a new version.
- **Spec gate**: only a human approves a spec. The edit hook blocks agents from writing `status: approved` and blocks
  code edits while the spec is a draft.
- **Evidence gate**: the shell and MCP hooks refuse to create a PR without passing evidence for HEAD.
- **Merge**: humans merge. Agents open draft PRs only.

## Multi-repo stories

The spec's "Repo impact and sequencing" table sets the order: producers before consumers (data pipeline, then API
contract, then MFE, then shell), backward compatible at every step. Each repo gets its own branch, evidence and draft PR,
all linked to the same Jira epic. Prefer one session per repo, so each repo's permissions, hooks and checks apply.
For a small change, `/add-dir ../other-repo` works, but run `verify` and `pr-open` from inside each repo.

## Stop and report instead of pushing on when

- a gate is not met;
- two repair rounds have not made `verify` pass;
- the change needs a migration, an auth or infrastructure change, or a new dependency that the approved spec does not cover;
- scope grows beyond the spec, or the spec contradicts the code you find.

## At every stop, report

The stage reached, the artifacts written (paths), the decision needed and from whom, and the exact command to resume,
for example `/sdlc-core:prd-to-pr PAY-412 build`.
