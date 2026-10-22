# Frontend testing for evidence

Every AC test name carries `<KEY> AC-n`, so `ac_coverage.py` can link the JUnit results to the spec.

## Vitest: JUnit output

```ts
// vitest.config.ts
export default defineConfig({
  test: {
    environment: "jsdom",
    reporters: ["default", "junit"],
    outputFile: { junit: "reports/junit-unit.xml" },
  },
});
```

Jest equivalent: `reporters: ["default", ["jest-junit", { outputDirectory: "reports", outputName: "junit-unit.xml", titleTemplate: "{title}", classNameTemplate: "{classname}", addFileAttribute: "true" }]]`.

## Component test per AC (Testing Library + MSW)

```tsx
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../test/msw-server";
import { StatusPanel } from "./StatusPanel";

const runs = [
  { runId: "R-1", runName: "October A", status: "FAILED", updatedAt: "2026-10-01T06:00:00Z" },
  { runId: "R-2", runName: "October B", status: "COMPLETED", updatedAt: "2026-10-01T06:00:00Z" },
];

it("PAY-412 AC-3: Failed filter shows only failed runs and sets ?status=failed", async () => {
  server.use(http.get("*/v1/payroll-runs/status", () => HttpResponse.json(runs)));
  render(<StatusPanel employerScope="E-1" />);
  await userEvent.click(await screen.findByRole("button", { name: /failed/i }));
  const list = screen.getByRole("list", { name: /payroll runs/i });
  expect(within(list).getAllByRole("listitem")).toHaveLength(1);
  expect(within(list).getByText("October A")).toBeVisible();
  expect(window.location.search).toContain("status=failed");
});

it("PAY-412 AC-7: 5xx shows an error with Retry, and Retry refetches", async () => {
  let calls = 0;
  server.use(http.get("*/v1/payroll-runs/status", () => (++calls === 1 ? new HttpResponse(null, { status: 503 }) : HttpResponse.json(runs))));
  render(<StatusPanel employerScope="E-1" />);
  await userEvent.click(await screen.findByRole("button", { name: /retry/i }));
  expect(await screen.findByText("October A")).toBeVisible();
  expect(calls).toBe(2);
});
```

## Playwright: evidence config

```ts
// playwright.config.ts
export default defineConfig({
  reporter: [
    ["junit", { outputFile: "reports/junit-e2e.xml" }],
    ["html", { outputFolder: "reports/playwright-html", open: "never" }],
    process.env.CI ? ["github"] : ["list"],
  ],
  use: { screenshot: "on", trace: "retain-on-failure", video: "retain-on-failure" },
});
```

`screenshot: "on"` keeps a screenshot for every test, so reviewers see each AC's end state. Use `only-on-failure` if
storage matters more.

## Playwright: AC test with an axe scan

```ts
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("PAY-412 AC-5: employee sees access-unavailable state and no status request",
  { tag: "@PAY-412-AC-5" },
  async ({ page }, testInfo) => {
    const statusCalls: string[] = [];
    page.on("request", (r) => r.url().includes("/payroll-runs/status") && statusCalls.push(r.url()));
    await page.goto("/payroll/dashboard?as=synthetic-employee");
    await expect(page.getByRole("heading", { name: /access unavailable/i })).toBeVisible();
    expect(statusCalls).toEqual([]);
    const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    await testInfo.attach("axe", { body: JSON.stringify(axe.violations, null, 2), contentType: "application/json" });
    expect(axe.violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""))).toEqual([]);
  });
```

## Rules for credible frontend evidence

- Synthetic users and data only. Never record real customer screens.
- No `test.only`, `test.skip` or `test.fixme` in committed tests; the edit hook blocks adding them.
- Freeze time (`vi.useFakeTimers()` or `page.clock`) wherever dates are rendered.
- Assert on what the user perceives (role, name, visible text), not implementation details or snapshot blobs.
