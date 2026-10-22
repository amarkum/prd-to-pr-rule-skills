# Changing the standard

The standard is code: every change goes through a PR, reviewed by the CODEOWNERS of what it touches.

1. **Branch and change.** Keep the change small. Lessons arrive here from the `learn` skill as PRs labelled `ai-knowledge`.
2. **Prove it.**
   - `make test`: add or update unit tests for any script or hook change.
   - `make validate`: strict plugin validation.
   - Behaviour change to a skill or hook: add or extend an eval case in `plugins/<plugin>/evals/` and run `make evals`
     (or the manual `plugin-evals` workflow).
   - `make details`: check the always-on token cost didn't jump.
3. **Version** (semver, per plugin): bump `version` in **both** `.claude-plugin/plugin.json` and
   `.cursor-plugin/plugin.json`, and in the plugin's entry in `.claude-plugin/marketplace.json`.
   `tests/test_manifests.py` fails if they drift.
   - patch: wording, references, examples;
   - minor: a new skill, check or connector; anything that adds without changing a gate;
   - major: a changed gate, stricter enforcement, a renamed skill, a manifest schema change (product repos may need edits).
4. **Changelog.** Add a line to `CHANGELOG.md`: what changed, who must do what.
5. **Merge and tag.** After the merge, `claude plugin tag plugins/<name>` creates `<name>--v<version>` and checks that the
   manifest and marketplace agree. Push the tag.

## How updates reach people

| Consumer | How they get it |
|---|---|
| Claude Code (plugin mode) | `autoUpdate: true` on the marketplace in repo or managed settings, or `/plugin update`. Running sessions need `/reload-plugins` |
| Cursor (team marketplace) | Auto Refresh (needs the GitHub App) or a manual refresh in the dashboard |
| Vendored repos | Re-run `tools/aisdlc.py vendor` and open a PR (a scheduled job can do this) |
| CI (`ai-evidence.yml` etc.) | Bump `AISDLC_REF` to the new tag |

Breaking changes: announce them in `companyAnnouncements` (managed settings) and the changelog, and give repos a
migration note.
