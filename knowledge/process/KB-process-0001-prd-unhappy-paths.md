---
id: KB-process-0001
title: PRDs must state what users see when data is empty, loading fails, or access is denied
scope: org
type: pattern
status: active
owner: "@org/product-ops"
provenance: [example: 4 of 6 pilot stories reworked in review for missing states]
created: 2026-10-22
review_by: 2027-04-22
promoted_to: lint:prd_lint.py PRD-050
---

**Symptom.** Specs and builds missed error and empty states; reviewers sent stories back.

**Cause.** The PRD template had no prompt for unhappy paths, so product owners didn't specify them.

**Do.** The PRD template's acceptance-criteria guidance now asks for unhappy paths, and the PRD gate checks for them.

**Guarded by.** `prd_lint.py` rule PRD-050 (deterministic), backed by the rubric's "Unhappy paths" check.
