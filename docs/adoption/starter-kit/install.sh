#!/usr/bin/env bash
# Install the Agentic SDLC starter kit into a pilot repository. Never overwrites a file: when a
# file already exists, the kit's version is written next to it for you to merge by hand.
#
#   ./install.sh /path/to/pilot-repo            # agent config, templates, scripts, evals
#   ./install.sh /path/to/pilot-repo --with-ci  # also copy the GitHub workflows
set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:?usage: install.sh <repo> [--with-ci]}"
WITH_CI="${2:-}"
TARGET="$(cd "$TARGET" && pwd)"
git -C "$TARGET" rev-parse --git-dir >/dev/null 2>&1 || { echo "install: $TARGET is not a git repository" >&2; exit 1; }

place() {  # place <kit path> <repo path> [<side-by-side name>]
  local src="$KIT/$1" dst="$TARGET/$2" alt="${3:-}"
  mkdir -p "$(dirname "$dst")"
  if [ ! -e "$dst" ]; then
    cp "$src" "$dst"; echo "  added  $2"
  elif cmp -s "$src" "$dst"; then
    echo "  same   $2"
  elif [ -n "$alt" ]; then
    cp "$src" "$TARGET/$alt"; echo "  exists $2 -> wrote $alt to merge by hand"
  else
    echo "  exists $2 (kept yours; compare with $1)"
  fi
}
place_tree() {  # place every file under a kit directory
  local dir="$1" dest="${2:-$1}"
  (cd "$KIT" && find "$dir" -type f ! -path '*/__pycache__/*' ! -name '*.pyc' ! -name '.DS_Store') | while read -r f; do
    place "$f" "$dest${f#"$dir"}"
  done
}

echo "Installing the Agentic SDLC starter kit into $TARGET"
place .claude/settings.json .claude/settings.json .claude/settings.agentic-sdlc.json
place .claude/frozen-tests.txt .claude/frozen-tests.txt
place_tree .claude/hooks
place_tree .claude/agents
place_tree .claude/skills
place CLAUDE.md.template CLAUDE.md CLAUDE.agentic-sdlc.md
place Makefile.template Makefile Makefile.agentic-sdlc
place_tree docs/changes
place_tree docs/policies
place_tree scripts
place_tree evals
place_tree metrics
if [ "$WITH_CI" = "--with-ci" ]; then
  place_tree ci/github .github/workflows
fi
chmod +x "$TARGET"/.claude/hooks/*.py "$TARGET"/scripts/*.py "$TARGET"/evals/run_evals.py 2>/dev/null || true

echo
echo "Self-testing the hooks:"
python3 "$TARGET/.claude/hooks/tests/run_hook_tests.py" | tail -1

cat <<EOF

Next steps
  1. Fill in CLAUDE.md (or merge CLAUDE.agentic-sdlc.md): architecture, conventions, known traps.
  2. Set BUILD_CMD, LINT_CMD and TEST_CMD in the Makefile, then run: make verify
  3. Tune the prod/non-prod names in .claude/hooks/prod_boundary_guard.py if yours differ.
  4. Add a CODEOWNERS entry so humans own .claude/settings.json, .claude/hooks/ and
     .claude/frozen-tests.txt.
  5. Commit on a branch and open a PR: agent configuration is reviewed like production code.
EOF
