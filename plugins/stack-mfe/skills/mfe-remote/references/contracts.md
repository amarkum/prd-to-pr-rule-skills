# Micro-frontend contract patterns

## Exposed module: a stable, typed boundary

```ts
// src/exposes/StatusPanel.tsx  (exposed as "./StatusPanel")
export type StatusPanelProps = {
  employerScope: string;                       // required since v1
  onError?: (e: { code: string }) => void;     // optional: additive change, v1.1
};
export const STATUS_PANEL_EVENTS = { filterChanged: "mfe:payroll:filter-changed" } as const;
export default function StatusPanel(props: StatusPanelProps) { /* ... */ }
```

The remote's federation config (Module Federation 2 / `@module-federation/enhanced`):

```ts
new ModuleFederationPlugin({
  name: "payroll",
  exposes: { "./StatusPanel": "./src/exposes/StatusPanel.tsx" },
  shared: {
    react: { singleton: true, requiredVersion: deps.react },
    "react-dom": { singleton: true, requiredVersion: deps["react-dom"] },
    "@acme/ds": { singleton: true, requiredVersion: deps["@acme/ds"] },
  },
  dts: { generateTypes: { abortOnError: true }, consumeTypes: { abortOnError: true, typesOnBuild: true } },
});
```

## Contract test in the remote (render it the way the host does)

```tsx
it("PAY-412 AC-3: emits filter-changed with the selected status", async () => {
  const events: CustomEvent[] = [];
  window.addEventListener("mfe:payroll:filter-changed", (e) => events.push(e as CustomEvent));
  render(<HostProviders><StatusPanel employerScope="E-1" /></HostProviders>);   // same providers as the shell
  await userEvent.click(await screen.findByRole("button", { name: /failed/i }));
  expect(events.at(-1)?.detail).toEqual({ status: "FAILED" });
});
```

## Host: isolation and fallback

```tsx
const StatusPanel = lazy(() => loadRemote("payroll/StatusPanel"));   // or import("payroll/StatusPanel")

<ErrorBoundary fallback={<PanelUnavailable />}>
  <Suspense fallback={<PanelSkeleton />}>
    <StatusPanel employerScope={employer.id} />
  </Suspense>
</ErrorBoundary>
```

Smoke test it in Playwright by blocking `remoteEntry` with `page.route("**/payroll/remoteEntry.js", r => r.abort())`
and asserting that the fallback renders and the dashboard's other panels still work.

## Breaking-change protocol

1. Add `./StatusPanelV2` alongside v1. Keep v1 working.
2. Move hosts to V2 behind a flag, one PR per host.
3. Remove v1 only after every consumer listed in `.ai/repo.yaml` `mfe.consumers` has shipped. Record this in the spec's rollout.

## HTTP contracts to a BFF or API

When the MFE calls an API that another team owns, consumer-driven contract tests (Pact `PactV3`) pin the requests and
responses the MFE relies on. Publish them to the provider's pipeline.
