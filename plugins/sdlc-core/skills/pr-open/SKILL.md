---
name: pr-open
description: Opens a draft pull request whose description carries the traceability and evidence reviewers need - Jira and PRD links, spec, AC coverage, evidence verdict at the commit SHA, risks, rollout and rollback - then links it back to Jira. Use when verify has passed and the user asks to open, raise or create the PR.
argument-hint: "<JIRA-KEY>"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py check *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py summary *)
---

# Open the draft PR

## 1. Gate

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py check --base origin/<default-branch> --docs-only-ok
```

If it fails, stop and run `verify`. The hooks will refuse `gh pr create` anyway; don't try to work around them.

## 2. Compose the description

Fill `templates/pr-body.md` into `.ai/pr-body.md` (gitignored), using:
- `specs/<KEY>/spec.md`: summary, ACs, risk tier, rollout and rollback;
- `.ai/evidence/summary.md`: paste it whole;
- `specs/<KEY>/tasks.md`: what was built;
- the things a reviewer should look at first (risky files, contract changes, anything you were unsure about).

No secrets, internal hostnames, customer data or raw logs.

## 3. Create it as a draft

```bash
git push -u origin HEAD
gh pr create --draft --title "<KEY>: <spec title>" --body-file .ai/pr-body.md --label ai-assisted
```

CODEOWNERS adds the reviewers. For multi-repo stories, add "Part N of M" and links to the sibling PRs.

## 4. Link back

- Comment on the Jira issue with the PR link (Atlassian MCP `addOrEditJiraIssueComment`, or `atlassian.py jira-comment`),
  and transition the issue to "In Review" if the workflow has that status.
- Tell the user the PR URL. CI will now re-run evidence on a clean runner and post the attested result.

Humans review and merge. After review comments arrive or the PR merges, run `learn`.
