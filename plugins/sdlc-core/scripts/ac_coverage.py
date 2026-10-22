#!/usr/bin/env python3
"""ac_coverage.py - acceptance-criteria traceability from a spec to JUnit results.

Reads the AC IDs defined in a spec (specs/<KEY>/spec.md) and JUnit XML files,
links test cases to ACs by name, classname or property, and fails when an AC has
no passing test and no documented manual verification.

Tests cite ACs qualified with the Jira key, so IDs never collide across specs:
  pytest      def test_pay_412_ac_2_upserts_status(): ...
              (or record_property("ac", "PAY-412/AC-2"))
  jest/vitest it("PAY-412 AC-1: renders one card per run", ...)
  playwright  test("PAY-412 AC-5: shows access-unavailable state", ...)
One name may cite several ACs after a single key: "PAY-412 AC-1 AC-3: ...".

Usage:
  ac_coverage.py --spec specs/PAY-412/spec.md --junit 'reports/**/*.xml' [--junit more.xml]
                 [--key PAY-412] [--only AC-1,AC-3] [--allow-unqualified] [--no-manual]
                 [--json OUT.json] [--md OUT.md] [--quiet]

Exit codes: 0 every in-scope AC covered, 1 gaps or failing tests, 2 usage/input error.
Standard library only.
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

VERSION = "1.0.0"

QUALIFIED_RE = re.compile(
    r"(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9]*)[-_ ](\d+)[-_ /:.]*AC[-_ ]?(\d+)(?![0-9])", re.IGNORECASE)
BARE_AC_RE = re.compile(r"(?<![A-Za-z0-9])AC[-_ ]?(\d+)(?![0-9])", re.IGNORECASE)
DEF_RE = re.compile(
    r"^\s*(?:[-*+]|\d+[.)])?\s*(?:\|\s*)?(?:#{1,6}\s*)?(?:\*\*|__)?\s*(AC-\d+)\b", re.IGNORECASE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def parse_frontmatter(text: str) -> dict:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    meta = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if m:
            meta[m.group(1).lower()] = m.group(2).strip().strip("'\"")
    return meta


def section_lines(text: str, keyword: str) -> list[str] | None:
    """Lines under the first heading containing `keyword`, up to the next heading of the same or higher level."""
    out, level = None, None
    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            if out is not None and len(m.group(1)) <= level:
                break
            if out is None and keyword in m.group(2).lower():
                out, level = [], len(m.group(1))
                continue
        if out is not None:
            out.append(line)
    return out


def clean(text: str) -> str:
    text = re.sub(r"[*_`|]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_spec(path: Path) -> tuple[dict, dict, dict]:
    text = path.read_text(encoding="utf-8")
    meta = parse_frontmatter(text)
    lines = section_lines(text, "acceptance criteria")
    if lines is None:
        lines = text.splitlines()
    acs: dict[str, str] = {}
    for line in lines:
        m = DEF_RE.match(line)
        if m:
            ac = m.group(1).upper()
            rest = clean(line[m.end():]).lstrip(":.)-] ").strip()
            acs.setdefault(ac, rest[:160])
    manual: dict[str, str] = {}
    for line in section_lines(text, "manual verification") or []:
        for n in BARE_AC_RE.findall(line):
            manual.setdefault(f"AC-{int(n)}", clean(line)[:200])
    return meta, acs, manual


def links_for(text: str, key: str, allow_unqualified: bool) -> set[tuple[str, bool]]:
    """Return {(AC-n, qualified)} cited by this text for `key`."""
    found: set[tuple[str, bool]] = set()
    keys = set()
    for m in QUALIFIED_RE.finditer(text):
        k = f"{m.group(1).upper()}-{int(m.group(2))}"
        keys.add(k)
        if k == key:
            found.add((f"AC-{int(m.group(3))}", True))
    bare = {f"AC-{int(n)}" for n in BARE_AC_RE.findall(text)}
    if keys == {key}:
        found |= {(ac, True) for ac in bare}
    elif not keys and allow_unqualified:
        found |= {(ac, False) for ac in bare}
    return found


def parse_junit(paths: list[str]) -> tuple[list[dict], list[str]]:
    cases, errors = [], []
    for p in paths:
        try:
            root = ET.parse(p).getroot()
        except (ET.ParseError, OSError) as exc:
            errors.append(f"{p}: {exc}")
            continue
        for tc in root.iter("testcase"):
            props = [f"{pr.get('name', '')} {pr.get('value', '')}" for pr in tc.iter("property")]
            if tc.find("failure") is not None:
                status = "failed"
            elif tc.find("error") is not None:
                status = "error"
            elif tc.find("skipped") is not None:
                status = "skipped"
            else:
                status = "passed"
            cases.append({"name": tc.get("name", ""), "classname": tc.get("classname", ""),
                          "file": tc.get("file", ""), "status": status, "props": props, "source": p})
    return cases, errors


def expand(patterns: list[str]) -> list[str]:
    files: list[str] = []
    for pat in patterns:
        hits = sorted(glob.glob(pat, recursive=True)) if any(c in pat for c in "*?[") else [pat]
        files += [h for h in hits if Path(h).is_file() and h not in files]
    return files


def evaluate(spec: Path, junit_patterns: list[str], key: str | None = None, only: list[str] | None = None,
             allow_unqualified: bool = False, allow_manual: bool = True) -> dict:
    meta, acs, manual = parse_spec(spec)
    key = (key or meta.get("jira") or "").upper()
    if not key:
        raise ValueError("no Jira key: add `jira: KEY-123` to the spec frontmatter or pass --key")
    if not acs:
        raise ValueError(f"no acceptance criteria (AC-n) found in {spec}")
    files = expand(junit_patterns)
    cases, errors = parse_junit(files)
    scope = [a.upper() for a in only] if only else sorted(acs, key=lambda a: int(a.split("-")[1]))
    per_ac = {ac: [] for ac in scope}
    orphans, unqualified = [], 0
    for case in cases:
        text = " ".join([case["name"], case["classname"], *case["props"]])
        for ac, qualified in sorted(links_for(text, key, allow_unqualified)):
            unqualified += 0 if qualified else 1
            entry = {"test": case["name"], "classname": case["classname"], "status": case["status"],
                     "source": case["source"], "qualified": qualified}
            if ac in per_ac:
                per_ac[ac].append(entry)
            elif ac not in acs:
                orphans.append({"ac": ac, **entry})
    results, gaps = [], []
    for ac in scope:
        tests = per_ac[ac]
        statuses = {t["status"] for t in tests}
        if statuses & {"failed", "error"}:
            status = "FAILING"
        elif "passed" in statuses:
            status = "COVERED"
        elif ac in manual and allow_manual:
            status = "MANUAL"
        else:
            status = "MISSING"
        if ac not in acs:
            status = "UNKNOWN_AC"
        if status not in ("COVERED", "MANUAL"):
            gaps.append(ac)
        results.append({"ac": ac, "text": acs.get(ac, ""), "status": status, "tests": tests,
                        "manual": manual.get(ac)})
    return {"tool": "ac_coverage", "version": VERSION, "spec": str(spec), "key": key,
            "junit_files": files, "junit_errors": errors, "testcases": len(cases),
            "verdict": "pass" if not gaps and files else "fail", "gaps": gaps,
            "unqualified_links": unqualified, "orphans": orphans, "acs": results}


def to_markdown(r: dict) -> str:
    mark = {"COVERED": "covered", "MANUAL": "manual", "FAILING": "FAILING", "MISSING": "MISSING",
            "UNKNOWN_AC": "unknown AC"}
    out = [f"### Acceptance-criteria coverage: {r['key']} ({'PASS' if r['verdict'] == 'pass' else 'FAIL'})", "",
           f"{len(r['junit_files'])} JUnit file(s), {r['testcases']} test cases.", "",
           "| AC | Status | Tests (status) | Criterion |", "|---|---|---|---|"]
    for a in r["acs"]:
        tests = "<br>".join(f"`{t['test'][:70]}` ({t['status']})" for t in a["tests"][:4]) or (a["manual"] or "-")
        more = f"<br>+{len(a['tests']) - 4} more" if len(a["tests"]) > 4 else ""
        out.append(f"| {a['ac']} | {mark[a['status']]} | {tests}{more} | {a['text'][:90]} |")
    if not r["junit_files"]:
        out += ["", "No JUnit files matched; nothing can be counted as covered."]
    if r["orphans"]:
        out += ["", "Tests cite ACs that the spec does not define: " +
                ", ".join(sorted({o['ac'] for o in r['orphans']}))]
    if r["unqualified_links"]:
        out += ["", f"{r['unqualified_links']} link(s) used bare AC IDs without the Jira key (--allow-unqualified)."]
    for e in r["junit_errors"]:
        out.append(f"\nUnreadable JUnit file: {e}")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--spec", required=True)
    ap.add_argument("--junit", action="append", required=True, help="JUnit file or glob; repeatable")
    ap.add_argument("--key", help="Jira key; default: spec frontmatter `jira`")
    ap.add_argument("--only", help="comma-separated AC IDs in scope for this repo/PR")
    ap.add_argument("--allow-unqualified", action="store_true", help="accept bare AC-n without the Jira key")
    ap.add_argument("--no-manual", action="store_true", help="manual verification does not count as covered")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--md", dest="md_out")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    spec = Path(args.spec)
    if not spec.is_file():
        print(f"ac_coverage: no such spec: {spec}", file=sys.stderr)
        return 2
    try:
        report = evaluate(spec, args.junit, args.key, args.only.split(",") if args.only else None,
                          args.allow_unqualified, not args.no_manual)
    except ValueError as exc:
        print(f"ac_coverage: {exc}", file=sys.stderr)
        return 2
    md = to_markdown(report)
    for dest, content in ((args.json_out, json.dumps(report, indent=2) + "\n"), (args.md_out, md)):
        if dest:
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_text(content, encoding="utf-8")
    if not args.quiet:
        print(md)
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
