#!/usr/bin/env bash
# Package the starter kit's skills, subagents and hooks as a Claude Code plugin.
#
#   packaging/build_plugin.sh [output-dir]      default output: dist/agentic-sdlc
#
# Then validate it, and publish it from an internal marketplace repository:
#   claude plugin validate --strict dist/agentic-sdlc
#   <marketplace repo>/.claude-plugin/marketplace.json   (see packaging/marketplace.json)
#   <marketplace repo>/plugins/agentic-sdlc/            (this output)
set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$KIT/dist/agentic-sdlc}"

rm -rf "$OUT"
mkdir -p "$OUT/.claude-plugin" "$OUT/hooks"
cp "$KIT/packaging/plugin.json" "$OUT/.claude-plugin/plugin.json"
cp "$KIT/packaging/hooks.json" "$OUT/hooks/hooks.json"
cp -R "$KIT/.claude/skills" "$OUT/skills"
cp -R "$KIT/.claude/agents" "$OUT/agents"
cp "$KIT"/.claude/hooks/*.py "$OUT/hooks/"
find "$OUT" -name '__pycache__' -prune -exec rm -rf {} +
cat > "$OUT/README.md" <<'TXT'
# agentic-sdlc plugin

Install (Claude Code 2.1.275 or later; replace <owner>/<repo> with the internal marketplace repository):

    /plugin install agentic-sdlc --marketplace <owner>/<repo>

Skills: /agentic-sdlc:intent, :spec, :plan-change, :verify-change, :release-manifest, :incident-to-intent.
Subagents: intent-agent, architecture-reviewer, security-reviewer, test-engineer, verifier, review-synthesizer.
Hooks: test guard, production-boundary guard, verify gate (Stop).

Each repository still owns .claude/frozen-tests.txt, its permission rules, CLAUDE.md and a Makefile
with build, lint, test and verify targets. Built from the Agentic SDLC starter kit.
TXT
echo "built $OUT"
