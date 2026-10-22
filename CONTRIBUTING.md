# Changing the standard

The standard is code. Every change goes through a PR, reviewed by the CODEOWNERS of what it touches. **Merging to
`main` is the release:** nobody bumps a version or tags anything, and no product repo needs a PR.

1. **Branch and change.** Keep the change small. Lessons arrive here from the `learn` skill as PRs labelled
   `ai-knowledge`.
2. **Prove it.** Branch protection on `main` requires the `validate` checks.
   - `make test`: add or update unit tests for any script or hook change.
   - `make validate`: strict plugin validation. The only warning it allows is the missing `version`, which is
     deliberate.
   - Workflow changes: CI lints `.github/workflows/` and the caller template with actionlint.
   - A behaviour change to a skill or hook: add or extend an eval case in `plugins/<plugin>/evals/`, then run
     `make evals` or the manual `plugin-evals` workflow.
   - `make details`: check that the always-on token cost didn't jump.
3. **Changelog.** Add a dated line to `CHANGELOG.md`: what changed, and what anyone must do about it.
4. **Merge.** That releases it.

## Don't add a `version`

The manifests carry no `version` on purpose. Claude Code then versions each plugin by the commit it came from, so
every merge to `main` reaches every machine on its next auto-update. A pinned `version` would hold everyone on their
cached copy until someone remembered to bump it. `tests/test_manifests.py` fails if a `version` appears in a plugin
manifest or the marketplace.

A new plugin goes into the marketplace and into `sdlc-standard`'s `dependencies`. The bundle is what managed settings
enable, so the new plugin reaches everyone without a settings change. `tests/test_manifests.py` fails if the bundle
misses a plugin.

## How a merge reaches people

| Consumer | How they get it |
|---|---|
| Claude Code: terminal, IDE, desktop and web sessions | Managed settings set `autoUpdate: true`. The update arrives within about ten minutes of a session's first message, and loads at the next launch or with `/reload-plugins`. |
| Claude Tag (Slack), claude.ai chat and Cowork | Organization sync with **Sync automatically** on: a push to the default branch releases. |
| CI in every product repo | The caller uses `sdlc.yml@main`, so the next workflow run uses the new workflow, scripts and plugins. |
| Vendored repos (fallback only) | Re-run `tools/aisdlc.py vendor` and open a PR. |

To **roll back**, revert the commit: the revert reaches everyone the same way.

To **hold everyone on a known-good commit** while you investigate:
- add `"ref"` to the marketplace source in managed settings;
- turn off **Sync automatically** for organization sync.

`policy/README.md` covers both.

Breaking changes, such as a stricter gate or a new required field in `.ai/repo.yaml`, reach everyone at once. Land
them behind a manifest flag with a safe default, announce them in `companyAnnouncements` and the changelog, and give
repos a migration note.
