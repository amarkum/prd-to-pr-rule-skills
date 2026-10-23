#!/usr/bin/env python3
"""Gate: fail if a test that was frozen on the base branch has changed or been deleted.

Reads .claude/frozen-tests.txt as it was at the merge base, so a branch cannot unfreeze its own
tests. Compares the merge base with the working tree (committed and uncommitted changes) and fails
on any modified, deleted or renamed frozen file. New files inside a frozen directory are fine.

A human can approve an exception by setting ALLOW_FROZEN_CHANGE=1, for example when CI sees an
"unfreeze-approved" label that only code owners can apply.

Usage: python3 scripts/check_frozen_tests.py [--base origin/main] [--strict]
Stdlib only, Python 3.8+.
"""
import argparse
import fnmatch
import os
import subprocess
import sys

FROZEN_LIST = ".claude/frozen-tests.txt"


def git(*args):
    proc = subprocess.run(["git"] + list(args), capture_output=True, text=True)
    return proc.returncode, proc.stdout


def resolve_base(preferred):
    for ref in [preferred, "origin/main", "main", "origin/master", "master"]:
        if ref and git("rev-parse", "--verify", "--quiet", ref + "^{commit}")[0] == 0:
            return ref
    return None


def patterns_from(text):
    out = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line.startswith("./"):
            line = line[2:]
        if line:
            out.append(line)
    return out


def frozen_match(path, patterns):
    for pat in patterns:
        if pat.endswith("/"):
            if path.startswith(pat):
                return pat
        elif fnmatch.fnmatchcase(path, pat) or fnmatch.fnmatchcase(path, pat.replace("**/", "")):
            return pat
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default=os.environ.get("BASE_REF", "origin/main"))
    parser.add_argument("--strict", action="store_true", help="fail when no base ref can be found")
    args = parser.parse_args()

    base = resolve_base(args.base)
    if not base:
        print("verify-frozen: no base ref found (tried {} and main/master); skipped".format(args.base))
        return 1 if args.strict else 0
    code, merge_base = git("merge-base", base, "HEAD")
    if code != 0:
        print("verify-frozen: no merge base between {} and HEAD; skipped".format(base))
        return 1 if args.strict else 0
    merge_base = merge_base.strip()

    code, listing = git("show", "{}:{}".format(merge_base, FROZEN_LIST))
    patterns = patterns_from(listing) if code == 0 else []
    if not patterns:
        print("verify-frozen: no frozen tests on {}; nothing to check".format(base))
        return 0

    code, status = git("diff", "--name-status", "-M", "--diff-filter=MDR", merge_base)
    hits = []
    for line in status.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            pattern = frozen_match(parts[1], patterns)  # for renames, parts[1] is the old path
            if pattern:
                hits.append((parts[0][0], parts[1], pattern))

    if not hits:
        print("verify-frozen: OK ({} frozen pattern(s) on {})".format(len(patterns), base))
        return 0
    kind = {"M": "modified", "D": "deleted", "R": "renamed"}
    for status_code, path, pattern in hits:
        print("verify-frozen: {} was {} (frozen by '{}')".format(path, kind.get(status_code, "changed"), pattern))
    if os.environ.get("ALLOW_FROZEN_CHANGE") == "1":
        print("verify-frozen: allowed by ALLOW_FROZEN_CHANGE=1 (human-approved exception)")
        return 0
    print("verify-frozen: FAILED. Frozen tests encode agreed behaviour; change the implementation, "
          "or get a human-approved exception.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
