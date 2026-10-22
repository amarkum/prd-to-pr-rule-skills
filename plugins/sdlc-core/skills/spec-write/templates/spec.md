---
jira: <KEY>
title: <title>
prd: <confluence url> (version <N>)
status: draft            # draft | approved  (only a human sets approved)
risk: <low|medium|high>
approved_by:
approved_at:
repos: [<repo-a>, <repo-b>]
---

# <KEY> <title>: technical spec

## 1. Summary

<Two or three sentences: what changes, where, and why.>

## 2. Requirements

| ID | Requirement | PRD ref |
|---|---|---|
| FR-1 | | |

## 3. Acceptance criteria

- **AC-1** (FR-1) Given <context>, when <action>, then <one observable outcome>.

## 4. Context and constraints

<Cite context.md: existing behaviour, incidents to respect, team knowledge applied.>

## 5. Design

### 5.1 Data

<Schemas before and after, indexes, backward compatibility, migration or backfill plan.>

### 5.2 Pipelines

### 5.3 Contracts

<APIs, exposed MFE modules (props and events), events. Versioning and deprecation.>

### 5.4 UI

<Routes, states (loading, empty, error, no access), accessibility, flags.>

## 6. Repo impact and sequencing

| Order | Repo | Change | ACs | Backward compatible |
|---|---|---|---|---|
| 1 | | | AC-1 | Yes |

## 7. Test plan

| AC | Level | Test (qualified name) | Repo |
|---|---|---|---|
| AC-1 | component | `<KEY> AC-1: ...` | |

## 8. Rollout and rollback

## 9. Risks

## 10. Open questions

None.

## 11. Manual verification

None.
