---
name: frontend-feature
description: React and TypeScript feature conventions for the frontend shell and micro-frontends - every UI state, accessibility, typed API access, flags, analytics and security - plus evidence-grade tests (Testing Library per acceptance criterion, MSW at the network boundary, Playwright e2e with AC-named tests, screenshots, traces and axe). Use when building or changing components, pages, routes, hooks, styles or frontend tests.
paths:
  - "src/**/*.{ts,tsx,js,jsx,css,scss}"
  - "e2e/**"
  - "tests/**"
  - "playwright.config.*"
---

# Frontend builder

Start from the closest existing feature (the "similar feature" in `context.md`) and copy its structure: folder layout,
data-fetching hook, state management, error handling, i18n and design-system components. Don't add a library for
something the repo already does.

## Non-negotiables

1. **Every state the spec lists is built and tested**: loading, empty, error (with retry), no access, partial data.
2. **Accessibility**: semantic elements and roles, labelled controls, keyboard operable, visible focus, nothing conveyed
   by colour alone. axe must report zero serious or critical violations on changed views.
3. **Types**: no `any`. API types come from the shared client or schema (OpenAPI or generated), not hand-written guesses.
4. **Security**: never render untrusted HTML (`dangerouslySetInnerHTML` only with a sanitiser and a stated reason).
   No secrets or personal data in the bundle, logs or analytics. Authorization is enforced server-side; the UI only
   reflects it, and makes **no data request** when access is denied.
5. **Feature flags** gate new user-visible behaviour as the spec's rollout says. Test both flag states.
6. **Copy and analytics**: copy goes through i18n; analytics events follow the tracking plan behind the PRD's success metrics.
7. **Performance**: lazy-load new routes and panels; no heavy dependency without a reason in the PR; respect any budget
   stated in the spec.

## Tests that count as evidence

- **Component and integration tests** (Vitest or Jest with Testing Library), at least one per AC, named
  `"<KEY> AC-n: <behaviour>"`. Query by role or label; assert what the user perceives; mock the network at the boundary
  with MSW, not the component's own hooks.
- **E2E tests** (Playwright) for ACs that cross routes, roles or the shell. Title `"<KEY> AC-n: ..."`, tag `@<KEY>-AC-n`.
  Use synthetic users and data. Keep the screenshot and trace, and run an axe scan on the changed view.
- **JUnit reporters** for both runners, written to the paths in `.ai/repo.yaml` `tests.junit_glob`.

Config and snippets: `references/testing-evidence.md`.

## Before you say a UI change is done

- [ ] All spec states are implemented and each has a test
- [ ] axe is clean on the changed views; keyboard path checked
- [ ] No request is made without access; no PII in logs or analytics
- [ ] Both flag states are tested
- [ ] Types are generated or shared, not guessed
