# specs/

One folder per Jira key: `specs/<KEY>/`, holding `prd.md` (the reviewed PRD version), `prd-review.md`/`.json`,
`context.md`, `spec.md` (status: draft or approved), `tasks.md` (also the progress tracker) and `retro.md`.

- Only humans approve specs: set `status: approved`, `approved_by` and `approved_at` (the hooks block agents from doing it).
- For multi-repo stories the spec lives in the lead repo (first row of "Repo impact and sequencing"). After approval,
  each other repo's feature branch carries a copy at the same path with `canonical: <link to the lead repo's file>`.
