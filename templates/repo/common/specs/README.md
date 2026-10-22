# specs/

One folder per Jira key, `specs/<KEY>/`. Each stage of the loop commits an artifact here that the next stage reads,
so the folder's git history is the audit trail: who asked for what, what the agent produced, who approved it.

| Stage | Artifact | Written by | Accepted by |
|---|---|---|---|
| Plan | `prd.md` (the PRD version reviewed), `prd-review.md`, `intent.md` | `prd-review`, or `triage` for bugs and incidents | the product owner (PRD marked ready, or the intent PR merged) |
| Design | `context.md`, `spec.md` | `context-gather`, `spec-write` | a human sets `status: approved` (tech lead for risk: medium or high) |
| Build | `plan.md` | `plan` (plan mode) | the engineer in plan mode; the tech lead for risk: high |
| Test | `.ai/evidence/` (not committed; CI re-runs and attests it) | `verify` | CI |
| Deploy | the PR, with review findings | `pr-open`, `pr-babysit` | code owners merge; the release manager authorises production |
| Maintain | `retro.md`, knowledge entries, new `intent.md` files | `learn`, `triage` | owners of the destination |

Rules the hooks enforce:
- Agents never set `status: approved` in `spec.md`, and never accept a `plan.md` whose spec is `risk: high`.
- No code edits until the spec is approved and the plan accepted.
- `plan.md` "Files that change" lists every file the diff touches; update it in the same commit when the work departs
  from the plan. Tests listed under "Locked tests" can't be edited by the agent.

For multi-repo stories the artifacts live in the lead repo (first row of the spec's "Repo impact and sequencing"). Each
other repo's feature branch carries `spec.md` and its own `plan.md` at the same path, with `canonical: <link>` in the
front matter.
