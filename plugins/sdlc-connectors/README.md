# sdlc-connectors: Atlassian, Sentry, schemas and production history

Org-wide connectors for the AI SDLC workflow. It adds the Atlassian Rovo MCP server (Confluence PRDs, Jira issues,
comments and transitions) and the Sentry MCP server (production errors), both over OAuth, plus two skills:
`schema-lookup` (snapshots first, then read-only MongoDB and SQL-schema MCP) and `history-lookup` (bugs, incidents,
failed DAG runs, reverts). `scripts/schema_snapshot.py` creates and diffs data-contract snapshots.

Repository-specific data connectors (MongoDB `--readOnly`, the DBHub SQL schema database with `readonly = true`, the
Airflow MCP with `AF_READ_ONLY=true`) live in each repo's `.mcp.json`, because their connection details differ per repo.
See `templates/repo/airflow/.mcp.json`.

## Install

`/plugin install sdlc-connectors@ai-sdlc` (it also enables `sdlc-core`). Authenticate once with `/mcp`. Headless CI
uses `sdlc-core/scripts/atlassian.py` with an API token instead of OAuth.

## Swap or extend observability

Datadog: `https://mcp.datadoghq.com/v1/mcp` (US1). Grafana: `grafana/mcp-grafana` with `--disable-write`.
PagerDuty: `https://mcp.pagerduty.com/mcp`. Add them to `.mcp.json` the same way.

Privacy: data flows to Atlassian and Sentry under your existing agreements. See the Atlassian privacy policy
(https://www.atlassian.com/legal/privacy-policy) and the Sentry privacy policy (https://sentry.io/privacy/).
