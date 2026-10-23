#!/usr/bin/env python3
"""PreToolUse test guard (Agentic SDLC starter kit).

Registered in .claude/settings.json for Edit|Write|MultiEdit|NotebookEdit|Bash.

deny  Edits to existing tests listed in .claude/frozen-tests.txt, edits to that
      list itself, and Bash commands that delete, move or rewrite a frozen test.
      New files inside a frozen directory are allowed.
ask   Edits to test files that add skip or focus markers or remove test cases,
      and edits to test-runner config that add test-selection excludes.
pass  Anything else: print nothing, exit 0, and the normal permission flow decides.

Defect-fix control from the operating model: reproduce, write a failing test,
freeze it, then change the implementation. Agents may not make a failure
disappear by weakening the test.

Stdlib only, Python 3.8+. Self-test: python3 .claude/hooks/tests/run_hook_tests.py
"""
import fnmatch
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _hooklib import (emit_pretooluse, mutation_targets, project_root,  # noqa: E402
                      read_payload, rel_path, split_segments)

FROZEN_LIST = ".claude/frozen-tests.txt"

# Markers that switch a test off (skip, xfail, ignore) or switch every other test off (only, fit).
SKIP_MARKERS = [
    r"@pytest\.mark\.(?:skip|skipif|xfail)\b",
    r"\bpytest\.(?:skip|xfail)\s*\(",
    r"@unittest\.(?:skip|skipIf|skipUnless|expectedFailure)\b",
    r"\.skipTest\s*\(",
    r"\b(?:it|test|describe|context|suite)\.(?:skip|only|fixme)\s*\(",
    r"\b(?:xit|xtest|xdescribe|xcontext|fit|fdescribe)\s*\(",
    r"@(?:Disabled|Ignore)\b",
    r"\[(?:Ignore|Skip)\b",
    r"\bSkip\s*=\s*\"",
    r"\bt\.Skip(?:f|Now)?\s*\(",
    r"#\[ignore\]",
    r"^\s*(?:xit|xdescribe|xcontext|pending)\b",
    r"^\s*skip\s*(?:\(|[\"'])",
]

# Test definitions; a drop in this count means the edit deletes tests.
TEST_DEFS = [
    r"^\s*(?:async\s+)?def\s+test",
    r"\bfunc\s+(?:Test|Benchmark|Fuzz|Example)\w*\s*\(",
    r"(?<![\w.])(?:it|test)\s*\(\s*['\"`]",
    r"@(?:Test|ParameterizedTest|RepeatedTest)\b",
    r"\[(?:Fact|Theory|Test|TestMethod|TestCase)\b",
    r"#\[(?:tokio::)?test\]",
    r"^\s*(?:it|test)\s+['\"]",
]

# Test-runner options that quietly deselect tests.
EXCLUDE_MARKERS = [
    r"--deselect\b",
    r"--ignore(?:-glob)?\b",
    r"(?:^|\s|[\"'])-k\s+[\"']?not\b",
    r"\bcollect_ignore(?:_glob)?\b",
    r"\btestPathIgnorePatterns\b",
    r"\btestIgnore\b",
    r"--passWithNoTests\b",
    r"-DskipTests\b",
    r"\bmaven\.test\.skip\b",
]

TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__|specs?|e2e|testing|src/test)/"
    r"|(^|/)test_[^/]*\.py$|_test\.(py|go|rb|exs?)$"
    r"|\.(test|spec)\.[cm]?[jt]sx?$"
    r"|(Test|Tests|IT|Spec)\.(java|kt|cs|scala|swift)$"
    r"|_spec\.rb$"
)

TEST_CONFIG = re.compile(
    r"(^|/)(pytest\.ini|tox\.ini|setup\.cfg|pyproject\.toml|conftest\.py|package\.json|Makefile"
    r"|(jest|vitest|playwright|cypress|karma)\.config\.[cm]?[jt]s|\.mocharc(\.\w+)?"
    r"|phpunit\.xml(\.dist)?|pom\.xml|build\.gradle(\.kts)?)$"
)


def load_frozen(root):
    patterns = []
    try:
        with open(os.path.join(root, FROZEN_LIST), encoding="utf-8") as fh:
            for line in fh:
                line = line.split("#", 1)[0].strip()
                if line.startswith("./"):
                    line = line[2:]
                if line:
                    patterns.append(line)
    except OSError:
        pass
    return patterns


def frozen_match(rel, patterns):
    if rel == FROZEN_LIST:
        return FROZEN_LIST
    for pat in patterns:
        if pat.endswith("/"):
            if rel.startswith(pat):
                return pat
        elif fnmatch.fnmatchcase(rel, pat) or fnmatch.fnmatchcase(rel, pat.replace("**/", "")):
            return pat
    return None


def count(patterns, text):
    return sum(len(re.findall(p, text or "", re.MULTILINE)) for p in patterns)


def before_after(tool, tin, root):
    """Old and new text for the region an edit touches."""
    if tool == "Edit":
        return tin.get("old_string", ""), tin.get("new_string", "")
    if tool == "MultiEdit":
        edits = tin.get("edits") or []
        return ("\n".join(e.get("old_string", "") for e in edits),
                "\n".join(e.get("new_string", "") for e in edits))
    if tool == "Write":
        path = tin.get("file_path", "")
        full = path if os.path.isabs(path) else os.path.join(root, path)
        try:
            with open(full, encoding="utf-8", errors="replace") as fh:
                old = fh.read(2000000)
        except OSError:
            old = ""
        return old, tin.get("content", "")
    if tool == "NotebookEdit":
        return "", tin.get("new_source", "")
    return "", ""


def deny_frozen(rel, pattern):
    if rel == FROZEN_LIST:
        emit_pretooluse("deny", "Test guard: only a human may change .claude/frozen-tests.txt. "
                        "If a frozen test looks wrong, stop and explain why to the builder.")
    emit_pretooluse("deny", (
        "Test guard: {} is frozen (matches '{}' in .claude/frozen-tests.txt). Frozen tests encode "
        "agreed behaviour, so change the implementation until the test passes. If you believe the "
        "test itself is wrong, stop and explain why to the builder; only a human can unfreeze it."
    ).format(rel, pattern))


def frozen_existing(rel, root, patterns):
    """Pattern that freezes this path. Only files that already exist are frozen,
    so new tests can still be added inside a frozen directory."""
    pattern = frozen_match(rel, patterns)
    if pattern and (rel == FROZEN_LIST or os.path.exists(os.path.join(root, rel))):
        return pattern
    return None


def check_bash(command, root, patterns):
    for segment in split_segments(command):
        for target in mutation_targets(segment):
            rel = rel_path(target, root)
            pattern = frozen_existing(rel, root, patterns)
            if pattern:
                deny_frozen(rel, pattern)


def main():
    payload = read_payload()
    if payload is None:
        emit_pretooluse("ask", "Test guard could not read the hook input, so this call was not checked. Review it manually.")
    tool = payload.get("tool_name", "")
    tin = payload.get("tool_input") or {}
    root = project_root(payload)
    patterns = load_frozen(root)

    if tool == "Bash":
        check_bash(tin.get("command", ""), root, patterns)
        return

    rel = rel_path(tin.get("file_path") or tin.get("notebook_path") or "", root)
    if not rel:
        return
    pattern = frozen_existing(rel, root, patterns)
    if pattern:
        deny_frozen(rel, pattern)

    old, new = before_after(tool, tin, root)
    reasons = []
    if TEST_PATH.search(rel):
        added = count(SKIP_MARKERS, new) - count(SKIP_MARKERS, old)
        if added > 0:
            reasons.append("adds {} skip or focus marker(s)".format(added))
        removed = count(TEST_DEFS, old) - count(TEST_DEFS, new)
        if removed > 0:
            reasons.append("removes {} test case(s)".format(removed))
    if TEST_CONFIG.search(rel):
        added = count(EXCLUDE_MARKERS, new) - count(EXCLUDE_MARKERS, old)
        if added > 0:
            reasons.append("adds {} test-selection exclude(s) to test runner config".format(added))
    if reasons:
        emit_pretooluse("ask", (
            "Test guard: this edit to {} {}. Skipping or deleting tests to get a green run hides "
            "failures. Approve only if you agree the test should change, and record why in the "
            "change's evidence.md."
        ).format(rel, " and ".join(reasons)))


if __name__ == "__main__":
    main()
