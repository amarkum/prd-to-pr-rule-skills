# Enterprise policy (managed settings)

`managed-settings.json` is the standard organisation policy for Claude Code; `managed-settings.regulated.json` is a
stricter tier for regulated repos, adapted from the worked example in Anthropic's AI-native SDLC playbook. Deliver it with **server-managed settings**
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
| `requiredMinimumVersion` | Claude Code refuses to start below the version this standard was tested on, so the hooks behave as tested. |

## The regulated tier (`managed-settings.regulated.json`)

Everything above, plus what each extra line buys:

| Key | Effect |
|---|---|
| `permissions.deny` (`WebFetch`, `curl`, `wget`, `.env*`, `secrets/**`) | Secrets stay out of the agent's context and tools can't reach arbitrary hosts. |
| `permissions.allow` | Pre-approves the safe inner loop (git reads, tests, lint, build) so the deny list doesn't become prompt fatigue. |
| `allowManagedPermissionRulesOnly` | No repo file, user setting or flag can widen the rules; the per-repo allow lists that `aisdlc.py init` writes are ignored, so keep this allow list complete. |
| `sandbox` (`failIfUnavailable`, `allowUnsandboxedCommands: false`, `network.allowedDomains`) | OS-level isolation for Bash: a shell command can't reach a host the list doesn't name, Claude Code won't start without the sandbox, and a command that fails inside it can't be retried outside. Add your Atlassian site and package mirrors. |
| `sandbox.credentials` | Sandboxed commands can't read `~/.ssh` or `~/.aws/credentials` and don't see `GITHUB_TOKEN` (use `gh`'s own login for PRs). |
| `allowManagedHooksOnly` | Only managed hooks and the force-enabled plugins' hooks run: the approval gates can't be replaced locally. |
| `disableSideloadFlags` | Every skill, agent, hook and MCP server arrives through the approved marketplace, never from `--plugin-dir` or a home directory. Keep it off for CI images that seed plugins. |

Every deny trades against capability. Start from the standard tier and move a repo to the regulated tier when its data
classification requires it. Vendored mode doesn't work under the regulated tier: it relies on project-level hooks.

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
