import json
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, git, run

TOOL = ROOT / "tools" / "aisdlc.py"


def tool(*args):
    return run([sys.executable, str(TOOL), *args])


class AisdlcToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aisdlc-tool-")
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-q", "-b", "main")

    def tearDown(self):
        self.tmp.cleanup()

    def test_doctor_fails_on_bare_repo(self):
        res = tool("doctor", "--target", str(self.repo))
        self.assertEqual(res.returncode, 1)
        self.assertIn("FAIL  CLAUDE.md present", res.stdout)

    def test_init_writes_only_the_repos_own_files_then_doctor_passes(self):
        res = tool("init", "--target", str(self.repo), "--stack", "airflow", "--jira", "PAY", "--name", "data-airflow",
                   "--description", "Payroll pipelines")
        self.assertEqual(res.returncode, 0, res.stderr)
        written = sorted(str(p.relative_to(self.repo)) for p in self.repo.rglob("*") if p.is_file() and ".git/" not in str(p))
        self.assertEqual(written, [".ai/dbhub.toml", ".ai/repo.yaml", ".github/workflows/ai-sdlc.yml", ".gitignore",
                                   ".mcp.json", "CLAUDE.md", "tests/dags/test_dag_integrity.py"])
        self.assertIn("# data-airflow", (self.repo / "CLAUDE.md").read_text())
        manifest = (self.repo / ".ai/repo.yaml").read_text()
        self.assertIn("name: data-airflow", manifest)
        self.assertIn("runtime: python", manifest)                       # the shared workflow's toolchain
        caller = (self.repo / ".github/workflows/ai-sdlc.yml").read_text()
        self.assertIn('uses: "amarkum/prd-to-pr-rule-skills/.github/workflows/sdlc.yml@main"', caller)
        self.assertNotIn("{{", caller)
        self.assertIn(".ai/evidence/", (self.repo / ".gitignore").read_text())
        doc = tool("doctor", "--target", str(self.repo))
        self.assertEqual(doc.returncode, 0, doc.stdout)
        self.assertIn("WARN  CLAUDE.md 'fill in' sections completed", doc.stdout)
        self.assertIn("NOTE  plugins: none set at repo level; expected from the organization's managed settings", doc.stdout)
        self.assertIn("ok    CI: .github/workflows/ai-sdlc.yml calls the shared workflow", doc.stdout)

    def test_init_extras_repo_plugins_and_own_standard(self):
        res = tool("init", "--target", str(self.repo), "--stack", "mfe", "--extras", "--repo-plugins",
                   "--standard", "octo-org/ai-sdlc")
        self.assertEqual(res.returncode, 0, res.stderr)
        for rel in ["REVIEW.md", ".ai/bands.yaml", "evals/README.md", "specs/README.md", "docs/knowledge/README.md",
                    ".github/pull_request_template.md"]:
            self.assertTrue((self.repo / rel).is_file(), rel)
        settings = json.loads((self.repo / ".claude/settings.json").read_text())
        self.assertEqual(settings["enabledPlugins"], {"sdlc-standard@ai-sdlc": True, "sdlc-core@ai-sdlc": True})
        self.assertEqual(settings["extraKnownMarketplaces"]["ai-sdlc"]["source"]["repo"], "octo-org/ai-sdlc")
        self.assertIn("Bash(npx vitest *)", settings["permissions"]["allow"])
        self.assertIn("octo-org/ai-sdlc/.github/workflows/sdlc.yml@main", (self.repo / ".github/workflows/ai-sdlc.yml").read_text())
        self.assertIn("ok    plugins: sdlc-core from the repo settings", tool("doctor", "--target", str(self.repo)).stdout)

    def test_doctor_flags_per_repo_workflow_copies(self):
        tool("init", "--target", str(self.repo), "--stack", "frontend")
        (self.repo / ".github/workflows/ai-evidence.yml").write_text("name: ai-evidence\n")
        doc = tool("doctor", "--target", str(self.repo))
        self.assertIn("WARN  no per-repo workflow copies left (delete ai-evidence.yml", doc.stdout)

    def test_doctor_reads_a_managed_settings_file_and_survives_a_broken_one(self):
        import contextlib
        import importlib.util
        import io
        spec = importlib.util.spec_from_file_location("aisdlc_tool", TOOL)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        tool("init", "--target", str(self.repo), "--stack", "frontend")
        good, bad = self.repo / "managed.json", self.repo / "broken.json"
        good.write_text(json.dumps({"enabledPlugins": {"sdlc-standard@ai-sdlc": True, "sdlc-core@ai-sdlc": True}}))
        bad.write_text("{not json")
        mod.MANAGED_FILES = [bad, good]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            mod.main(["doctor", "--target", str(self.repo)])
        self.assertIn("ok    plugins: sdlc-core from the managed settings file", out.getvalue())
        self.assertIn("broken.json can't be read as a JSON object", out.getvalue())

    def test_init_is_idempotent_and_merges_settings(self):
        (self.repo / ".claude").mkdir()
        (self.repo / ".claude/settings.json").write_text(json.dumps({"permissions": {"allow": ["Bash(make *)"]}}))
        tool("init", "--target", str(self.repo), "--stack", "frontend", "--repo-plugins")
        second = tool("init", "--target", str(self.repo), "--stack", "frontend", "--repo-plugins")
        self.assertIn("skip    CLAUDE.md", second.stdout)
        allow = json.loads((self.repo / ".claude/settings.json").read_text())["permissions"]["allow"]
        self.assertIn("Bash(make *)", allow)
        self.assertEqual(len(allow), len(set(allow)))

    def test_vendor_mfe_makes_repo_self_contained(self):
        tool("init", "--target", str(self.repo), "--stack", "mfe")
        res = tool("vendor", "--target", str(self.repo), "--stack", "mfe")
        self.assertEqual(res.returncode, 0, res.stderr)
        skill = (self.repo / ".claude/skills/verify/SKILL.md").read_text()
        self.assertIn("${CLAUDE_PROJECT_DIR}/.claude/aisdlc/scripts/evidence.py", skill)
        self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", skill)
        for rel in [".claude/skills/mfe-remote/SKILL.md", ".claude/skills/frontend-feature/SKILL.md",
                    ".claude/skills/plan/templates/plan.md", ".claude/skills/triage/SKILL.md",
                    ".claude/aisdlc/scripts/agent_evals.py", ".claude/aisdlc/scripts/bands.py",
                    ".claude/agents/builder.md", ".claude/aisdlc/hooks/aisdlc_hooks.py",
                    ".claude/aisdlc/scripts/schema_snapshot.py", ".claude/rules/aisdlc-10-security-and-data.md",
                    ".claude/aisdlc/VERSION.json"]:
            self.assertTrue((self.repo / rel).is_file(), rel)
        settings = json.loads((self.repo / ".claude/settings.json").read_text())
        self.assertFalse(settings["enabledPlugins"]["sdlc-core@ai-sdlc"])
        self.assertIn("shell-guard", settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"])
        servers = json.loads((self.repo / ".mcp.json").read_text())["mcpServers"]
        self.assertTrue({"playwright", "atlassian", "sentry"} <= set(servers))
        # the vendored hook works: it blocks a force push and injects the vendored rules
        hook = self.repo / ".claude/aisdlc/hooks/aisdlc_hooks.py"
        deny = run([sys.executable, str(hook), "shell-guard"], cwd=self.repo,
                   stdin=json.dumps({"tool_input": {"command": "git push --force"}}),
                   env={"CLAUDE_PROJECT_DIR": str(self.repo)})
        self.assertEqual(json.loads(deny.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        ctx = run([sys.executable, str(hook), "session-context"], cwd=self.repo, stdin="{}",
                  env={"CLAUDE_PROJECT_DIR": str(self.repo)})
        context = json.loads(ctx.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("The loop:", context)
        self.assertNotIn("Security and data (always on)", context)     # loaded natively from .claude/rules/, not twice
        rule = (self.repo / ".claude/rules/aisdlc-10-security-and-data.md").read_text()
        self.assertIn("# Security and data (always on)", rule)
        self.assertNotIn("description:", rule)
        self.assertEqual(tool("doctor", "--target", str(self.repo)).returncode, 0)

    def test_knowledge_audit(self):
        kb = self.repo / "kb"
        kb.mkdir()
        entry = ("---\nid: KB-airflow-0001\ntitle: t\nscope: stack:airflow\ntype: pitfall\nstatus: active\n"
                 "owner: \"@org/data\"\nprovenance: [PR 1]\ncreated: 2026-01-01\nreview_by: {d}\n---\nbody\n")
        (kb / "fresh.md").write_text(entry.format(d="2027-01-01"))
        self.assertEqual(tool("knowledge-audit", str(kb), "--today", "2026-10-22").returncode, 0)
        (kb / "stale.md").write_text(entry.format(d="2026-06-01"))
        (kb / "bad.md").write_text("---\nid: KB-x\n---\n")
        res = tool("knowledge-audit", str(kb), "--today", "2026-10-22")
        self.assertEqual(res.returncode, 1)
        self.assertIn("stale: review_by 2026-06-01", res.stdout)
        self.assertIn("missing title", res.stdout)


if __name__ == "__main__":
    unittest.main()
