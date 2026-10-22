# {{name}}

<!-- Facts about THIS repo for every coding agent (Claude Code, Cursor, Codex, Copilot) and every new developer.
     Keep it under ~120 lines. Org-wide rules come from the ai-sdlc plugins; don't repeat them here. -->

## What this repo is

{{description}}

Stack: **{{stack}}** · Jira project: **{{jira_project}}** · Owners: see CODEOWNERS · Manifest: `.ai/repo.yaml`

## Layout

<!-- fill in: the 5-10 directories that matter and what lives in each -->

## Commands

The canonical list is `checks:` in `.ai/repo.yaml`; `evidence.py` and CI run exactly those. Common ones:

<!-- fill in: setup, lint, typecheck, unit tests, integration tests, local run -->

## Conventions specific to this repo

<!-- fill in: only what differs from the stack pack (stack-{{stack}}), e.g. naming, state management, data stores -->

## Data and contracts

- Schema snapshots: `docs/schemas/` (update them in the same PR as any change to what this repo writes)
- Related repos and contracts: see `repo.related_repos` in `.ai/repo.yaml`

## How AI-assisted work flows here

PRD (Confluence) -> `prd-review` -> `specs/<KEY>/spec.md` (approved by a human) -> `tasks.md` -> build (test-first)
-> `verify` (`.ai/evidence/`) -> draft PR -> human review -> `learn`.
Start with `/sdlc-core:prd-to-pr <PRD link or Jira key>`. Hooks block code before spec approval and PRs without evidence.
