---
id: "<TICKET>-<short-slug>"
title: "<same as intent>"
class: standard
status: draft                       # draft | approved | superseded
owner: "<builder handle>"
approver: "<builder handle>"        # the builder approves the plan; add a reviewer for high-risk
approved: ""                        # YYYY-MM-DD
spec: "spec.md"                     # or "none" for standard changes without a spec
---

# Plan: <title>

How it will be built. Written after exploring the repository and approved before any code changes.

## Components affected
-

## Files and modules affected
| Path | Change | Why |
|---|---|---|
|  |  |  |

## Impact analysis
Callers and dependents of what changes. Paste `kompactor graph impact <file|symbol>` output if
the tool is installed, otherwise the callers found with search.

## API changes
None, or the contract diff.

## Database changes
None, or the schema diff and the migration file names.

## Implementation sequence
Small steps that can each be verified. For a defect, step 1 is always the failing test.
1.

## Tests required
| Test | Proves | Layer |
|---|---|---|
|  | FR-1 | unit |

## Migration steps
None, or ordered steps with a dry run.

## Risks
-

## Rollback
Exact steps or commands, and how to confirm the rollback worked.

## Verification
Exact commands, ending with `make verify`, plus any manual or staging checks.
```bash
make verify
```
