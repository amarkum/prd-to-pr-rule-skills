"""Keep the plugin manifests, the marketplace and the skill files consistent."""
import json
import re
import unittest

from helpers import ROOT

PLUGINS = sorted(p for p in (ROOT / "plugins").iterdir() if p.is_dir())


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class ManifestTests(unittest.TestCase):
    def test_marketplace_lists_every_plugin_without_version_pins(self):
        catalog = load(ROOT / ".claude-plugin/marketplace.json")
        market = {e["name"]: e for e in catalog["plugins"]}
        self.assertEqual(set(market), {p.name for p in PLUGINS})
        # No `version` anywhere: installs track the commit, so every merge to main reaches every machine. A pinned
        # version would keep everyone on their cached copy until someone remembered to bump it.
        self.assertNotIn("version", catalog.get("metadata", {}))
        for plugin in PLUGINS:
            manifest = load(plugin / ".claude-plugin/plugin.json")
            self.assertEqual(manifest["name"], plugin.name)
            self.assertNotIn("version", manifest, plugin.name)
            self.assertNotIn("version", market[plugin.name], plugin.name)
            self.assertEqual(market[plugin.name]["source"], f"./plugins/{plugin.name}")
        self.assertEqual(sorted(ROOT.glob("**/.cursor*")), [])               # Claude Code only

    def test_bundle_installs_every_plugin(self):
        bundle = load(ROOT / "plugins/sdlc-standard/.claude-plugin/plugin.json")
        self.assertEqual(sorted(bundle["dependencies"]), sorted(p.name for p in PLUGINS if p.name != "sdlc-standard"))
        policy = load(ROOT / "policy/managed-settings.json")["enabledPlugins"]
        self.assertTrue(policy.get("sdlc-standard@ai-sdlc") and policy.get("sdlc-core@ai-sdlc"))

    def test_skill_names_match_folders_and_descriptions_fit(self):
        for skill in ROOT.glob("plugins/*/skills/*/SKILL.md"):
            fm = re.match(r"^---\n(.*?)\n---", skill.read_text(encoding="utf-8"), re.DOTALL).group(1)
            name = re.search(r"^name:\s*(\S+)", fm, re.MULTILINE).group(1)
            desc = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE).group(1)
            self.assertEqual(name, skill.parent.name, skill)
            self.assertRegex(name, r"^[a-z0-9-]{1,64}$")
            self.assertLessEqual(len(desc), 1024, skill)                     # Agent Skills spec limit
            self.assertLess(len(skill.read_text().splitlines()), 200, skill)  # keep bodies lean

    def test_hook_config_points_at_existing_script(self):
        hooks = load(ROOT / "plugins/sdlc-core/hooks/hooks.json")["hooks"]
        self.assertTrue((ROOT / "plugins/sdlc-core/hooks/aisdlc_hooks.py").is_file())
        for groups in hooks.values():
            for group in groups:
                for h in group["hooks"]:
                    self.assertEqual(h["args"][0], "${CLAUDE_PLUGIN_ROOT}/hooks/aisdlc_hooks.py")
                    self.assertIn(h["args"][1], {"shell-guard", "edit-guard", "pr-gate", "session-context", "stop-verify"})


if __name__ == "__main__":
    unittest.main()
