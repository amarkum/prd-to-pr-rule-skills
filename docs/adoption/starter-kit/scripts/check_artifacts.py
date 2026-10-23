#!/usr/bin/env python3
"""Gate: every change folder touched on this branch has the artifacts its class requires.

For each docs/changes/<id>/ with files added or changed since the merge base (committed,
uncommitted or untracked), check:
  - intent.md exists and declares a class: trivial | standard | significant | high-risk
  - the files the class requires at this stage exist (see REQUIRED)
  - front matter: id matches the folder, owner is set, no <placeholders> left in key fields
  - when the branch also changes code outside docs/, intent.md and plan.md are approved
    (status: approved plus an approved date). Approval gates are code.
  - high-risk: spec.md names a security_approver
  - stage pr: evidence.md says verdict: pass
  - stage release: release-manifest.yaml has the required top-level keys

Stages: dev (default, used by `make verify` and the Stop hook), pr (CI on pull requests),
release (before promotion). A branch that changes code without a change folder passes with a note,
because that is only valid for trivial changes; set CHANGE_CLASS (for example from a PR label) to
enforce it. Set ARTIFACTS_MODE=warn to report without failing, which is useful in shadow mode.

Usage: python3 scripts/check_artifacts.py [--base origin/main] [--stage dev|pr|release]
Stdlib only, Python 3.8+.
"""
import argparse
import os
import re
import subprocess
import sys

CHANGES = "docs/changes/"
CLASSES = ("trivial", "standard", "significant", "high-risk")
REQUIRED = {
    "dev": {
        "trivial": [],
        "standard": ["intent.md", "plan.md"],
        "significant": ["intent.md", "spec.md", "plan.md"],
        "high-risk": ["intent.md", "spec.md", "plan.md"],
    },
    "pr": {
        "trivial": [],
        "standard": ["intent.md", "plan.md", "evidence.md"],
        "significant": ["intent.md", "spec.md", "plan.md", "evidence.md"],
        "high-risk": ["intent.md", "spec.md", "plan.md", "evidence.md"],
    },
    "release": {
        "trivial": [],
        "standard": ["intent.md", "plan.md", "evidence.md"],
        "significant": ["intent.md", "spec.md", "plan.md", "evidence.md", "release-manifest.yaml"],
        "high-risk": ["intent.md", "spec.md", "plan.md", "evidence.md", "release-manifest.yaml"],
    },
}
MANIFEST_KEYS = ("schema", "change_id", "version", "source", "checks", "risk", "production_gate")


def git(*args):
    proc = subprocess.run(["git"] + list(args), capture_output=True, text=True)
    return proc.returncode, proc.stdout


def resolve_base(preferred):
    for ref in [preferred, "origin/main", "main", "origin/master", "master"]:
        if ref and git("rev-parse", "--verify", "--quiet", ref + "^{commit}")[0] == 0:
            return ref
    return None


def changed_files(base):
    files = set()
    if base:
        code, merge_base = git("merge-base", base, "HEAD")
        if code == 0:
            files.update(git("diff", "--name-only", merge_base.strip())[1].splitlines())
    else:
        files.update(git("diff", "--name-only", "HEAD")[1].splitlines())
    files.update(git("ls-files", "--others", "--exclude-standard")[1].splitlines())
    return sorted(f for f in files if f)


def front_matter(path):
    """Flat key: value pairs from YAML front matter (or a whole YAML file). No nesting."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    if path.endswith(".md"):
        match = re.match(r"^---\s*\n(.*?)\n---\s*(\n|$)", text, re.S)
        if not match:
            return {}
        text = match.group(1)
    data = {}
    for line in text.splitlines():
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not match:
            continue
        value = match.group(2).strip()
        if value[:1] in "\"'":
            value = value[1:value.find(value[0], 1)] if value.find(value[0], 1) > 0 else value[1:]
        else:
            value = value.split(" #", 1)[0].strip()
        data[match.group(1)] = value
    return data


def unfilled(value):
    return not value or ("<" in value and ">" in value) or "YYYY" in value


def check_folder(folder, stage, code_changed, problems):
    change_id = os.path.basename(folder.rstrip("/"))
    intent = front_matter(os.path.join(folder, "intent.md"))
    if intent is None:
        problems.append("{}: intent.md is missing".format(change_id))
        return
    change_class = intent.get("class", "")
    if change_class not in CLASSES:
        problems.append("{}: intent.md class must be one of {} (got '{}')".format(change_id, ", ".join(CLASSES), change_class))
        return
    for name in REQUIRED[stage][change_class]:
        if not os.path.exists(os.path.join(folder, name)):
            problems.append("{}: {} change needs {} at stage {}".format(change_id, change_class, name, stage))
    for name in ("intent.md", "spec.md", "plan.md", "evidence.md"):
        meta = front_matter(os.path.join(folder, name))
        if meta is None:
            continue
        if meta.get("id") != change_id:
            problems.append("{}: {} has id '{}', expected the folder name".format(change_id, name, meta.get("id", "")))
        if name != "evidence.md" and unfilled(meta.get("owner", "")):
            problems.append("{}: {} has no owner".format(change_id, name))
        if code_changed and name in ("intent.md", "plan.md", "spec.md") and name in REQUIRED[stage][change_class]:
            if meta.get("status") != "approved" or unfilled(meta.get("approved", "")):
                problems.append("{}: {} must be approved before code changes (status: approved, approved: <date>)".format(change_id, name))
    if change_class == "high-risk":
        spec = front_matter(os.path.join(folder, "spec.md")) or {}
        if unfilled(spec.get("security_approver", "")):
            problems.append("{}: high-risk change needs security_approver in spec.md".format(change_id))
    if stage in ("pr", "release"):
        evidence = front_matter(os.path.join(folder, "evidence.md"))
        if evidence is not None and evidence.get("verdict") != "pass":
            problems.append("{}: evidence.md verdict is '{}', expected pass".format(change_id, evidence.get("verdict", "")))
    manifest = os.path.join(folder, "release-manifest.yaml")
    if stage == "release" and os.path.exists(manifest):
        keys = front_matter(manifest) or {}
        missing = [k for k in MANIFEST_KEYS if k not in keys]
        if missing:
            problems.append("{}: release-manifest.yaml is missing {}".format(change_id, ", ".join(missing)))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default=os.environ.get("BASE_REF", "origin/main"))
    parser.add_argument("--stage", choices=sorted(REQUIRED), default="dev")
    args = parser.parse_args()

    base = resolve_base(args.base)
    files = changed_files(base)
    folders = sorted({CHANGES + f[len(CHANGES):].split("/", 1)[0] for f in files
                      if f.startswith(CHANGES) and f.count("/") >= 3 and not f[len(CHANGES):].startswith("_")})
    code_changed = any(not f.startswith("docs/") for f in files)
    problems = []
    for folder in folders:
        check_folder(folder, args.stage, code_changed, problems)

    declared = os.environ.get("CHANGE_CLASS", "").strip().lower()
    if code_changed and not folders:
        if declared and declared != "trivial":
            problems.append("CHANGE_CLASS is '{}' but the branch has no docs/changes/<id>/ folder".format(declared))
        else:
            print("verify-artifacts: code changed with no change folder; fine only for a trivial change")

    if not problems:
        print("verify-artifacts: OK ({} change folder(s), stage {}, base {})".format(len(folders), args.stage, base or "none"))
        return 0
    for problem in problems:
        print("verify-artifacts: " + problem)
    if os.environ.get("ARTIFACTS_MODE") == "warn":
        print("verify-artifacts: {} problem(s) reported; not failing because ARTIFACTS_MODE=warn".format(len(problems)))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
