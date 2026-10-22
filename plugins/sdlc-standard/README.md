# sdlc-standard: the whole standard in one plugin

This plugin has no skills, agents or hooks of its own. It depends on every other plugin in the marketplace, so
enabling it installs all of them:

- `sdlc-core`: the six-stage loop, its subagents, the hooks that enforce the gates, and the scripts.
- `sdlc-connectors`: Atlassian and Sentry MCP servers, and the schema and history lookups.
- `stack-airflow`, `stack-frontend` and `stack-mfe`: the stack packs. Their skills load only when Claude works on
  files of that stack, so enabling all of them costs a few hundred tokens of skill descriptions.

## Why a bundle

An administrator enables it once in managed settings:

```json
"enabledPlugins": { "sdlc-standard@ai-sdlc": true, "sdlc-core@ai-sdlc": true }
```

When the standard gains a plugin, it is added to this plugin's `dependencies`, and the next auto-update installs it
on every machine. The managed settings never change.

`sdlc-core` is also listed by itself so that it is force-enabled: a developer who disables a stack pack loses only
that pack, never the hooks that enforce the gates.

`tests/test_manifests.py` fails if a plugin in the marketplace is missing from `dependencies`.
