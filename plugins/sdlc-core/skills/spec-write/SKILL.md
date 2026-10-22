---
name: spec-write
description: Writes the technical spec for a story from a READY PRD and its context pack - traceable requirements, Given/When/Then acceptance criteria with IDs, data and contract design, repo impact and sequencing, test plan, rollout and rollback - and leaves it as a draft for human approval. Use after context-gather, or when asked to "write the spec", "design this story" or "turn this PRD into a tech spec".
argument-hint: "<JIRA-KEY>"
---

# Spec write

Output: `specs/<KEY>/spec.md` from `templates/spec.md`, with front matter `status: draft`. The spec is the contract that
build, verify and review are checked against, so make it precise rather than long.

## Rules for a good spec

1. **Traceability.** Number requirements `FR-n` (taken from the PRD) and acceptance criteria `AC-n`. Every AC cites the FRs
   it proves, and every FR has at least one AC.
2. **Testable ACs.** Use Given / When / Then with one observable outcome each (UI state, API response, or stored data).
   Cover the unhappy paths the PRD defined: empty, error, no access, re-run.
3. **Design only where it changes something.** Cover data shapes (before and after, with indexes and backward compatibility),
   pipeline tasks, contracts (API, exposed MFE modules, events) and UI states. Cite `context.md` for existing behaviour.
4. **Repo impact and sequencing table.** One row per repo: change, ACs, order, and whether it is backward compatible.
   Producers ship before consumers. Every change is safe to deploy alone (flags, additive schema).
   `evidence.py` reads this table to work out which ACs each repo must cover, so use the repo names from `.ai/repo.yaml`.
5. **Test plan.** For each AC: test level (unit, component, contract, DAG, e2e), the planned test name in qualified form
   (`PAY-412 AC-3: ...`), and the repo. Plan a manual check only when automation is impossible, and say why.
6. **Risk tier.**
   - `low`: UI copy or isolated logic.
   - `medium`: new data or contract, or more than one repo.
   - `high`: auth, PII, migrations, money, or anything irreversible.
   High-risk specs list the extra approvals they need (security, data owner).
7. **No open questions.** The "Open questions" section must say `None.` before the spec can be approved. Unresolved
   product questions go back through `prd-review`; design questions go to the tech lead.

## Fast lane for small, low-risk changes

A `risk: low` change (one repo, no data, contract or auth change, roughly under 100 lines, e.g. a bug with a clear
reproduction) needs only sections 1, 3, 6 and 7: summary, ACs, repo impact and test plan. Ceremony scales with risk;
the gates (human approval, evidence) do not.

## Hand-off

1. Commit the spec on `spec/<KEY>-<slug>` or the feature branch, and open a draft PR or share it with the tech lead
   (CODEOWNERS of `specs/` review it).
2. **Do not approve it yourself.** A human sets `status: approved`, `approved_by` and `approved_at`; the edit hook blocks
   agents from doing so. Until then the hook also blocks code changes on the branch.
3. Report the spec path, the risk tier, the number of ACs per repo, and anything the reviewer should challenge.
