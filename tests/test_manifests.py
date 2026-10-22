"""Keep the Claude Code and Cursor manifests, the two marketplaces and the skill files consistent."""
import json
import re
import unittest

from helpers import ROOT

PLUGINS = sorted(p for p in (ROOT / "plugins").iterdir() if p.is_dir())


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class ManifestTests(unittest.TestCase):
    def test_versions_match_across_tools_and_marketplaces(self):
        claude_mk = {e["name"]: e for e in load(ROOT / ".claude-plugin/marketplace.json")["plugins"]}
        cursor_mk = {e["name"]: e for e in load(ROOT / ".cursor-plugin/marketplace.json")["plugins"]}
        for plugin in PLUGINS:
            c = load(plugin / ".claude-plugin/plugin.json")
            k = load(plugin / ".cursor-plugin/plugin.json")
            self.assertEqual(c["name"], plugin.name)
            self.assertEqual(k["name"], plugin.name)
            self.assertEqual(c["version"], k["version"], plugin.name)
            self.assertEqual(claude_mk[plugin.name]["version"], c["version"], plugin.name)
            self.assertEqual(claude_mk[plugin.name]["source"], f"./plugins/{plugin.name}")
            self.assertEqual(cursor_mk[plugin.name]["source"], f"plugins/{plugin.name}")

    def test_skill_names_match_folders_and_descriptions_fit(self):
        for skill in ROOT.glob("plugins/*/skills/*/SKILL.md"):
            fm = re.match(r"^---\n(.*?)\n---", skill.read_text(encoding="utf-8"), re.DOTALL).group(1)
            name = re.search(r"^name:\s*(\S+)", fm, re.MULTILINE).group(1)
            desc = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE).group(1)
            self.assertEqual(name, skill.parent.name, skill)                 # Cursor requires it
            self.assertRegex(name, r"^[a-z0-9-]{1,64}$")
            self.assertLessEqual(len(desc), 1024, skill)                     # Agent Skills spec limit
            self.assertLess(len(skill.read_text().splitlines()), 200, skill)  # keep bodies lean

    def test_hook_configs_point_at_existing_script(self):
        claude = load(ROOT / "plugins/sdlc-core/hooks/hooks.json")["hooks"]
        cursor = load(ROOT / "plugins/sdlc-core/hooks/cursor-hooks.json")
        self.assertEqual(cursor["version"], 1)
        cmds = [h["args"][1] for groups in claude.values() for g in groups for h in g["hooks"]]
        cmds += [h["command"].split()[-3 if "--format" in h["command"] else -1]
                 for hs in cursor["hooks"].values() for h in hs]
        self.assertTrue((ROOT / "plugins/sdlc-core/hooks/aisdlc_hooks.py").is_file())
        for sub in cmds:
            self.assertIn(sub, {"shell-guard", "edit-guard", "pr-gate", "session-context", "stop-verify"})
        cursor_manifest = load(ROOT / "plugins/sdlc-core/.cursor-plugin/plugin.json")
        self.assertEqual(cursor_manifest["hooks"], "./hooks/cursor-hooks.json")


if __name__ == "__main__":
    unittest.main()
