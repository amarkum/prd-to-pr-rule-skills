# Enterprise policy (managed settings)

`managed-settings.json` is an example organisation policy for Claude Code. Deliver it with **server-managed settings**
(claude.ai admin console → Organization settings → Claude Code → Managed settings; needs the Owner role), with MDM
(macOS profile domain `com.anthropic.claudecode`, Windows `HKLM\SOFTWARE\Policies\ClaudeCode`), or as a file at
`/Library/Application Support/ClaudeCode/managed-settings.json` (macOS), `/etc/claude-code/managed-settings.json`
(Linux/WSL) or `C:\Program Files\ClaudeCode\managed-settings.json` (Windows). Users can't override managed settings.

| Key | Effect |
|---|---|
| `extraKnownMarketplaces` + `enabledPlugins` | Registers the ai-sdlc marketplace on every machine and force-enables `sdlc-core` and `sdlc-connectors`. Stack packs stay per repo (`.claude/settings.json`). |
| `strictKnownMarketplaces` | Only approved marketplaces can be added. Add `{"source":"github","repo":"anthropics/claude-plugins-official"}` if you also allow official plugins such as `claude-security`. |
| `permissions.deny` | Org-wide floor: secrets can't be read, history can't be force-pushed. The plugin hooks add the content-aware checks. |
| `permissions.disableBypassPermissionsMode` | No one can run with all permission checks off. |
| `allowManagedMcpServersOnly` + `allowedMcpServers` | Only the vetted MCP servers can run. `serverCommand` must match the configured command exactly, so pin versions here and in the repo templates together. |
| `env` (OpenTelemetry) | Sends usage metrics (`claude_code.session.count`, `claude_code.cost.usage`, `claude_code.token.usage`, ...) and events (including `claude_code.plugin_loaded`) to your collector. OTel variables in repo settings are ignored, so set them here. |
| `companyAnnouncements` | One-line reminder at startup. |

## Optional, stricter controls

- `strictPluginOnlyCustomization: ["skills", "hooks"]` blocks repo- and user-level skills and hooks so they can come only
  from approved plugins. Don't use it together with **vendored mode** (`tools/aisdlc.py vendor`), which relies on
  project-level skills and hooks.
- `allowManagedHooksOnly: true` blocks every hook that isn't managed. Plugin hooks still run when the plugin is
  force-enabled in managed `enabledPlugins`, which this file does for `sdlc-core`.
- `disableSideloadFlags: true` rejects `--plugin-dir`, `--agents` and `--mcp-config` on developer machines (keep it off
  for CI images that seed plugins).
- `sandbox` settings (`enabled`, `filesystem`, `network.allowedDomains`) confine Bash on macOS, Linux and WSL2. Combine
  them with `sandbox.network.allowManagedDomainsOnly` for egress control.
