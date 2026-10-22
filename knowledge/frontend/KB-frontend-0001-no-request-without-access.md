---
id: KB-frontend-0001
title: When access is denied, render guidance and make no data request
scope: stack:frontend
type: pitfall
status: active
owner: "@org/web-platform"
provenance: [example security review finding on PAY-388]
created: 2026-10-22
review_by: 2027-04-22
promoted_to: rule:sdlc-core/10-security-and-data
---

**Symptom.** An employee opening an admin URL saw a spinner. The network tab showed a 403 from the status endpoint,
which revealed that the endpoint exists and what it returns.

**Cause.** The component fetched first and checked the role afterwards.

**Do.** Check the role before mounting the data hook, render the access-unavailable state, and assert in an e2e test
that no request is made.

**Don't.** Rely on the API's 403 as the UI's access check.

**Guarded by.** The "no request without access" assertion pattern in `frontend-feature/references/testing-evidence.md`.
