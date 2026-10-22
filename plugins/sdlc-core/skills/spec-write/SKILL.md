---
name: spec-write
description: The Design stage: writes spec.md from an accepted intent, the PRD and the context pack (traceable requirements, Given/When/Then ACs with IDs, design, repo impact and sequencing, test plan, rollout, flagged policy concerns) as a draft for human approval. Use after context-gather, or for "write the spec" or "design this story".
argument-hint: "<JIRA-KEY>"
---

# Spec write

Inputs: `specs/<KEY>/intent.md` (accepted), `prd.md` when the intent came from a PRD, and `context.md`.
Output: `specs/<KEY>/spec.md` from `templates/spec.md`, with front matter `status: draft`. The spec is the contract that
plan, build, verify and review are checked against, so make it precise rather than long.

Apply the organisation's policy skills while you write (security, data, brand, accessibility, compliance, whichever are
installed), so policy is applied now rather than discovered in review.

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
7. **Flagged concerns.** Where the intent conflicts with a policy, or two policies conflict, say so in "Flagged
   concerns" with the policy, its owner and the decision needed. The product owner resolves each one with its policy
   owner before engineering sees the spec. Never resolve a policy conflict by quietly picking a side.
8. **No open questions.** The "Open questions" section must say `None.` before the spec can be approved. Unresolved
   product questions go back to the product owner; design questions go to the tech lead. Carry the intent's open
   questions forward or answer them.

## Fast lane for small, low-risk changes

A `risk: low` change (one repo, no data, contract or auth change, roughly under 100 lines, e.g. a bug with a clear
reproduction) needs only the summary, ACs, repo impact and test plan sections. Ceremony scales with risk;
the gates (human approval, evidence) do not.

## Hand-off

1. Commit the spec on `spec/<KEY>-<slug>` or the feature branch, and open a draft PR or share it with the tech lead
   (CODEOWNERS of `specs/` review it).
2. **Do not approve it yourself.** The product owner checks it solves the intent; a human sets `status: approved`,
   `approved_by` and `approved_at` (the tech lead for risk: medium or high). The edit hook blocks agents from doing so,
   and blocks code changes on the branch until then.
3. Report the spec path, the risk tier, the number of ACs per repo, the flagged concerns with their owners, and
   anything the reviewer should challenge.
