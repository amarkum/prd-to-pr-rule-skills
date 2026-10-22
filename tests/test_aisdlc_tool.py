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

    def test_init_airflow_then_doctor_passes(self):
        res = tool("init", "--target", str(self.repo), "--stack", "airflow", "--jira", "PAY", "--name", "data-airflow",
                   "--description", "Payroll pipelines")
        self.assertEqual(res.returncode, 0, res.stderr)
        for rel in ["CLAUDE.md", "REVIEW.md", ".ai/repo.yaml", ".ai/dbhub.toml", ".mcp.json", ".github/workflows/ai-evidence.yml",
                    ".github/workflows/ai-prd-intake.yml", ".github/workflows/ai-design.yml", ".github/workflows/ai-build.yml",
                    ".github/workflows/ai-review.yml", ".github/workflows/ai-agent-evals.yml",
                    ".github/workflows/ai-maintain.yml", ".ai/bands.yaml", "evals/README.md",
                    ".github/pull_request_template.md", "specs/README.md",
                    "docs/knowledge/README.md", "tests/dags/test_dag_integrity.py"]:
            self.assertTrue((self.repo / rel).is_file(), rel)
        self.assertIn("# data-airflow", (self.repo / "CLAUDE.md").read_text())
        self.assertFalse((self.repo / "AGENTS.md").exists() or (self.repo / ".cursor").exists())
        self.assertIn("name: data-airflow", (self.repo / ".ai/repo.yaml").read_text())
        settings = json.loads((self.repo / ".claude/settings.json").read_text())
        self.assertTrue(settings["enabledPlugins"]["stack-airflow@ai-sdlc"])
        self.assertEqual(settings["extraKnownMarketplaces"]["ai-sdlc"]["source"]["repo"], "amarkum/prd-to-pr-rule-skills")
        self.assertIn("Bash(pytest *)", settings["permissions"]["allow"])
        self.assertIn(".ai/evidence/", (self.repo / ".gitignore").read_text())
        doc = tool("doctor", "--target", str(self.repo))
        self.assertEqual(doc.returncode, 0, doc.stdout)
        self.assertIn("WARN  CLAUDE.md 'fill in' sections completed", doc.stdout)

    def test_init_is_idempotent_and_merges_settings(self):
        (self.repo / ".claude").mkdir()
        (self.repo / ".claude/settings.json").write_text(json.dumps({"permissions": {"allow": ["Bash(make *)"]}}))
        tool("init", "--target", str(self.repo), "--stack", "frontend")
        second = tool("init", "--target", str(self.repo), "--stack", "frontend")
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
