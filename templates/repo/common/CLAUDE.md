# {{name}}

<!-- What a new joiner needs on day one. Keep it under a page: Claude reads all of it at the start of every
     session. Org-wide rules come from the ai-sdlc plugins; don't repeat them here. -->

{{description}}

Stack: **{{stack}}** · Jira: **{{jira_project}}** · Owners: CODEOWNERS · Manifest: `.ai/repo.yaml`

## Commands

The canonical list is `checks:` in `.ai/repo.yaml`; `evidence.py` and CI run exactly those.

<!-- fill in: each command with what a healthy run prints, for example
- Test: `pytest -q` (ends with "N passed", no errors)
- Lint: `ruff check .` ("All checks passed!") -->

## Architecture

<!-- fill in: the 5-10 directories that matter and what lives in each; generated paths nobody edits -->

## Conventions

<!-- fill in: only what differs from the stack-{{stack}} skill: naming, state management, data stores -->

## Things Claude gets wrong

<!-- When Claude makes the same mistake twice, the correction goes here (the learn skill proposes entries). -->

## Verifying your work

Run every command in `checks:` before reporting a task complete, and paste the output. On a `<KEY>` branch,
run the verify skill: it records evidence in `.ai/evidence/`. If a test fails, fix the code, not the test.

## Data and contracts

- Schema snapshots: `docs/schemas/` (update them in the same PR as any change to what this repo writes).
- Related repos and contracts: `repo.related_repos` in `.ai/repo.yaml`.

## How work flows here

Plan (`prd-review` -> `intent.md`) -> Design (`spec.md`, approved by a human) -> Build (`plan.md` accepted, then
test-first code) -> Test (`verify`) -> Deploy (draft PR, review, human merge) -> Maintain (`learn`, `triage`).
Artifacts live in `specs/<KEY>/`. Start with `/sdlc-core:prd-to-pr <PRD link or Jira key>`.
