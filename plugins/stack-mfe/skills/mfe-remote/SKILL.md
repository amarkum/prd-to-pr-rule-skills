---
name: mfe-remote
description: Conventions for Module Federation micro-frontends - exposed modules as versioned contracts, shared singleton dependencies, isolation so a failing remote never breaks the host, routing ownership, type sharing and consumer contract tests - layered on the frontend-feature pack. Use when changing an MFE remote or host, federation config, exposed modules, shared dependencies or cross-MFE communication.
paths:
  - "module-federation.config.*"
  - "**/webpack.config.*"
  - "**/rspack.config.*"
  - "**/rsbuild.config.*"
  - "**/vite.config.*"
  - "src/**/*.{ts,tsx}"
---

# Micro-frontend builder

Load `frontend-feature` as well: all of it applies. This pack adds the federation rules.
Find your role in `.ai/repo.yaml` (`repo.mfe.role: host | remote`, `exposes`, `consumers`) and in the federation config.

## Contract rules: exposed modules are public APIs

1. **Treat every `exposes` entry as a published contract**: props, emitted events or callbacks, required providers or
   context, and CSS scope. Change it additively by default (new optional props, new events). A breaking change gets a
   new exposed name (`./StatusPanelV2`) and a deprecation window agreed in the spec.
2. **Share types through federation DTS**, so that a remote's type change breaks the host's CI rather than production:
   `dts: { generateTypes: { abortOnError: true }, consumeTypes: { abortOnError: true, typesOnBuild: true } }`.
3. **Shared singletons** (`react`, `react-dom`, the router, the design system and state libraries) are declared with
   `singleton: true` and `requiredVersion` taken from `package.json`. Never bump a shared singleton's major version in a
   feature PR; that is a platform change.
4. **No imports across MFE boundaries.** Talk through props, typed custom events (`mfe:<name>:<event>`), or the shell's
   documented shared services.
5. **Isolation.** A remote never mutates globals (window, document title, global CSS) and scopes its styles. The host wraps
   every remote in an error boundary with a fallback and a load timeout, so one failing remote never blanks the shell.
6. **Routing.** The shell owns top-level routes; a remote owns only the routes under its mount path.
7. **Independent deployability.** A remote change must work with the host version currently deployed, and the other way
   round. Flag new behaviour and keep old props working until consumers move.

## Tests that count as evidence

- **Component tests per AC** in the remote (see `frontend-feature`), named `"<KEY> AC-n: ..."`.
- **Contract tests in the remote**: render the exposed module exactly as the host does (same props shape and providers)
  and assert the events or callback payloads.
- **Consumer tests in the host** for the props it passes, against the remote's published types.
- **Federation smoke test** (Playwright, in the host): the remote loads and renders; when the remote is unavailable, the
  host shows the fallback and the rest of the page still works.
- **Build check**: the production build emits `remoteEntry` and the DTS types without errors.

Snippets: `references/contracts.md`.
