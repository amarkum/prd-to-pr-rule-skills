---
name: pr-babysit
description: Drives an open AI-assisted PR to green: fixes failing checks and in-scope review comments with evidence re-run, answers every thread, and stops when only code-owner approval is left. Never merges. Use after pr-open, or for "address the review" or "fix CI".
argument-hint: "<PR-number>"
---

# PR babysit (Stage 5: Deploy)

Goal: the PR is green, every review thread has an answer, and it waits only on a code owner. The PR thread is the audit
record, so every fix is a commit that a reply points to.

## 1. Read the whole PR on its current head

```bash
gh pr view <n> --json number,headRefName,headRefOid,isDraft,mergeable,reviewDecision,statusCheckRollup
gh pr checks <n>
gh api repos/{owner}/{repo}/pulls/<n>/comments      # inline review comments
gh pr view <n> --comments                            # conversation, including the AI review and evidence comments
```

Work on the PR's own branch, checked out and up to date. Never on the default branch.

## 2. Failing checks first

- Read the failure (`gh run view <run-id> --log-failed`). Name the root cause before changing anything.
- A failure in code the PR touches: fix it. A failure that is red on the base branch too: say so on the PR; don't widen
  the PR to fix someone else's code.
- "Flaky" is not a root cause. Re-run a job once only if it died before any test ran (checkout, install, runner lost).
- Never skip, disable or quarantine a test, and never push an empty commit to re-trigger CI.

## 3. Review comments

- Small, in-scope asks (a missed edge case, a rename, an added test, a one-function refactor): implement them.
- Larger asks (multi-file redesign, API or schema change) or a disagreement: reply with your reasoning or a proposal and
  leave the decision to the human. Don't push it.
- Reply on each thread with what changed and the commit SHA, or why not. Resolve only threads you addressed.
- A finding that repeats one from an earlier PR: add the correction to `CLAUDE.md` "Things Claude gets wrong" in this
  PR (repo-scoped) or note it for `learn`.

## 4. After each round of fixes

Commit (`<KEY>: address review: <summary>`), run the `verify` skill so the evidence matches the new HEAD, then push to
the PR branch. Never force-push, rebase or amend a branch other people have pulled.

## 5. Stop when

- all checks are green and no thread waits on you: report "waiting on code-owner approval" and stop;
- three rounds haven't turned the PR green: report what is failing, what you tried, and what you need;
- a fix needs something outside the approved spec or plan: stop and ask.

Never merge, approve, or mark the PR ready for review: those are the humans' calls (the hooks block or ask).
