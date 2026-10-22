# Rolling out the standard: managed settings and one-time setup

Developers install nothing and repos copy nothing. An administrator does the four steps below once. After that,
merging to the standard's `main` branch is the release: every machine, CI run and Slack thread picks it up by itself.

## Roll out once

**1. Host the standard in your organization.**
- Copy this repository into your GitHub organization as a private or internal repository. Organization sync (step 3)
  accepts only private or internal repositories.
- Replace `amarkum/prd-to-pr-rule-skills` with your repository's name in `managed-settings.json` (both the
  marketplace entry and the allowlist).
- Pass `--standard <org>/<repo>` to `tools/aisdlc.py init`, or change its default.

**2. Claude Code: terminal, IDE, desktop and web sessions.**
- Paste `managed-settings.json` into **claude.ai > Organization settings > Claude Code > Managed settings**. This
  needs the Owner role on a Team or Enterprise plan.
- Every developer who signs in with the organization account then gets the `ai-sdlc` marketplace and the
  `sdlc-standard` bundle at the start of their next session.
- Developers' plugins stay current through `autoUpdate`. A new version arrives within about ten minutes of their first
  message and loads at their next launch, or straight away with `/reload-plugins`.
- Cloud sessions wait for these settings before they install plugins. Claude Code fetches the settings at startup and
  every hour after that.
- Without a Team or Enterprise plan, deliver the same JSON instead through MDM (macOS profile domain
  `com.anthropic.claudecode`; Windows registry value `HKLM\SOFTWARE\Policies\ClaudeCode\Settings`), or as a file:
  - macOS: `/Library/Application Support/ClaudeCode/managed-settings.json`
  - Linux and WSL: `/etc/claude-code/managed-settings.json`
  - Windows: `C:\Program Files\ClaudeCode\managed-settings.json`
- Each machine clones the marketplace with its own git credentials, so developers need read access to the repository.

**3. Slack (Claude Tag), claude.ai chat and Cowork.** These surfaces don't receive Claude Code's managed settings.
- Under **Organization settings > Plugins & skills**, choose **Add > Sync from GitHub** and pick the repository.
  Members don't need access to the repository: the sync reads it through the Claude GitHub App.
- Turn on **Sync automatically**, so a push to the default branch releases.
- Set each of the standard's plugins to **Required**, not only the `sdlc-standard` bundle: whether organization sync
  installs a bundle's dependencies hasn't been verified for this standard.
- In the Claude Tag admin settings, go to **Claude's access > Skills and plugins** and add the same plugins, so they
  apply to all of Slack.
- Skills load on every surface. Hooks don't run in chat. Check what your Slack threads run before you rely on a hook
  there. Required CI checks and branch protection hold wherever Claude ran.

**4. CI.**
- Each repo carries one file, `.github/workflows/ai-sdlc.yml`, written by `aisdlc.py init`. It calls
  `.github/workflows/sdlc.yml@main` in the standard, so workflow changes need no PRs in product repos.
- Store `ANTHROPIC_API_KEY`, `ATLASSIAN_EMAIL` and `ATLASSIAN_API_TOKEN` as organization secrets, and
  `ATLASSIAN_SITE` as an organization variable. Callers pass the secrets with `secrets: inherit`.
- If the standard's repository is private, two more settings:
  - Allow access to it from **Settings > Actions > General > Access** ("Accessible from repositories in the
    organization").
  - Add an `AISDLC_TOKEN` organization secret that can read it, such as a fine-grained token with contents:read on
    that one repository.
- Make `ai-sdlc / evidence` a required check. Turn on the rest per repo with the variable `AISDLC_AUTOMATION=on`.

**Confirm.** On a developer machine:
- `/plugin` lists the `ai-sdlc` marketplace and six plugins. Each plugin's version is a commit SHA of the standard.
- `/status` shows the managed settings among the setting sources.
- After deploying server-managed settings, `claude doctor` reports whether the fetch succeeded.

## Updating and rolling back

| You want to | Do this |
|---|---|
| Release a change | Merge it to `main`. Versions are commit SHAs, so there's no version to bump. |
| Roll back | Revert the commit on `main`. The revert is a new commit, so it reaches everyone the same way. |
| Hold everyone on a known-good version while you investigate | Add `"ref": "<commit or tag>"` to the marketplace `source` in managed settings. For Claude Tag and claude.ai, turn off **Sync automatically**. |
| Run an early-access group | Host a second marketplace at another ref under another name, and give that group its own managed settings (MDM, file, or a Claude apps gateway policy). Server-managed settings apply to the whole organization. |

## What `managed-settings.json` sets

| Key | Effect |
|---|---|
| `extraKnownMarketplaces` | Registers the `ai-sdlc` marketplace on every machine. `autoUpdate: true` keeps it current, and users can't turn that off. |
| `enabledPlugins` | Force-enables two plugins. `sdlc-standard` is the bundle: it installs every plugin in the standard, and plugins added later arrive with it, so this key never changes. `sdlc-core` is listed again so that it is locked on: a developer can disable a stack pack but never the hooks that enforce the gates. |
| `strictKnownMarketplaces` | Only approved marketplaces can be added. Add `{"source":"github","repo":"anthropics/claude-plugins-official"}` if you also allow official plugins. |
| `permissions.allow` / `ask` | Pre-approve the safe inner loop (git reads, tests, lint, build) for every stack, and ask before any `git push`. Repos no longer need their own `.claude/settings.json`. |
| `permissions.deny` | Org-wide floor: no reading secrets, no force-pushing. The plugin hooks add the content-aware checks. |
| `permissions.disableBypassPermissionsMode` | No one can run with every permission check off. |
| `allowManagedMcpServersOnly` + `allowedMcpServers` | Only the vetted MCP servers can run. `serverCommand` must match the configured command exactly, so pin versions here and in the repo templates together. |
| `env` (OpenTelemetry) | Sends usage metrics and events, including `claude_code.plugin_loaded`, to your collector. OTel variables in repo settings are ignored, so set them here. |
| `companyAnnouncements` | A one-line reminder at startup. |
| `requiredMinimumVersion` | Claude Code refuses to start below the version this standard was tested on, so the hooks behave as tested. |

## The regulated tier (`managed-settings.regulated.json`)

Server-managed settings apply to everyone in the organization. Deliver this tier to the regulated group's machines
through MDM or a file, or through a Claude apps gateway policy per identity-provider group.

It includes everything in the standard tier, plus:

| Key | Effect |
|---|---|
| `permissions.deny` (`WebFetch`, `curl`, `wget`, `.env*`, `secrets/**`) | Secrets stay out of the agent's context, and tools can't reach arbitrary hosts. |
| `permissions.allow` | Pre-approves the safe inner loop so that the deny list doesn't become prompt fatigue. |
| `allowManagedPermissionRulesOnly` | No repo file, user setting or flag can widen the rules, so keep this allow list complete. |
| `sandbox` (`failIfUnavailable`, `allowUnsandboxedCommands: false`, `network.allowedDomains`) | OS-level isolation for Bash. A shell command can't reach a host the list doesn't name, Claude Code won't start without the sandbox, and a command that fails inside it can't be retried outside. Add your Atlassian site and package mirrors. |
| `sandbox.credentials` | Sandboxed commands can't read `~/.ssh` or `~/.aws/credentials`, and don't see `GITHUB_TOKEN` (use `gh`'s own login for PRs). |
| `allowManagedHooksOnly` | Only managed hooks and the force-enabled plugins' hooks run, so the approval gates can't be replaced locally. `sdlc-core` is force-enabled for this reason. |
| `disableSideloadFlags` | Every skill, agent, hook and MCP server arrives through the approved marketplace, never from `--plugin-dir` or a home directory. Keep it off for CI images that seed plugins. |

Every deny trades against capability. Start from the standard tier, and move a repo to the regulated tier when its
data classification requires it.

## Fallbacks when managed settings aren't available

- **Repo settings:** `aisdlc.py init --repo-plugins` writes `.claude/settings.json` with the marketplace, the same two
  plugins and the permission rules. Contributors get the plugins after they trust the folder. Cloud sessions don't
  install plugins from repo settings.
- **Vendored copy:** `aisdlc.py vendor` copies the plugins into the repo's `.claude/`. It works on every surface,
  but each release needs a re-run in every repo. That maintenance is what managed settings remove. Don't combine it
  with managed settings, or the skills load twice.
