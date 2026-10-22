#!/usr/bin/env python3
"""prd_lint.py - deterministic completeness check for a PRD exported to Markdown.

This is the *floor* under the LLM review done by the prd-review skill: it finds
structural gaps the same way every time, so product owners get consistent,
explainable feedback. Semantic problems (contradictions, infeasible asks,
conflicts with production history) are left to the LLM review.

Usage:
  prd_lint.py PRD.md [--json OUT.json] [--md OUT.md] [--rubric RUBRIC.json] [--quiet]

Exit codes: 0 = READY, 1 = NEEDS_CLARIFICATION, 2 = usage or input error.
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VERSION = "1.0.0"

# Sections are matched in this order, most specific first ("non-functional"
# before "functional", "non-goals" before "goals"). A heading maps to the
# first section whose `match` prefix appears and whose `exclude` does not.
DEFAULT_RUBRIC = {
    "sections": [
        {"id": "open_questions", "title": "Open questions",
         "match": ["open question", "open issue", "unknowns", "questions"],
         "required": False, "allow_none": True,
         "question": "Please add an 'Open questions' section, even if it just says 'None'."},
        {"id": "acceptance", "title": "Acceptance criteria",
         "match": ["acceptance criteria", "acceptance"], "required": True,
         "question": "How will we know each requirement works? Please write acceptance criteria as Given / When / Then."},
        {"id": "nfr", "title": "Non-functional requirements",
         "match": ["non-functional", "non functional", "nonfunctional", "nfr", "quality attribute"],
         "required": True,
         "question": "What are the performance, availability, accessibility and data-freshness expectations? Please use numbers.",
         "suggested_default": "p95 page load < 2 s; WCAG 2.2 AA; data no older than 1 h; inherits the platform availability SLO."},
        {"id": "non_goals", "title": "Non-goals / out of scope",
         "match": ["non-goal", "non goal", "nongoal", "out of scope", "out-of-scope", "not in scope", "exclusion"],
         "required": True,
         "question": "What is explicitly out of scope for this release?"},
        {"id": "functional", "title": "Functional requirements",
         "match": ["functional requirement", "requirements", "user stor", "features", "scope of work"],
         "exclude": ["data", "security", "privacy", "compliance", "technical", "non-functional", "non functional"],
         "required": True,
         "question": "What must the system do? Please list each behaviour as a numbered requirement (FR-1, FR-2, ...)."},
        {"id": "goals", "title": "Goals", "match": ["goal", "objective"], "required": True,
         "question": "What outcomes define success for this feature?"},
        {"id": "problem", "title": "Problem / context",
         "match": ["problem", "context", "background", "motivation", "why"], "required": True,
         "question": "What user or business problem does this solve, and what evidence shows it is a problem?"},
        {"id": "summary", "title": "Summary",
         "match": ["summary", "overview", "tl;dr", "tldr", "introduction"], "required": True,
         "question": "In two or three sentences: what are we building, and for whom?"},
        {"id": "flow", "title": "User flow",
         "match": ["user flow", "user journey", "journey", "flow", "wireframe", "design", "ux"], "required": False},
        {"id": "users", "title": "Users and roles",
         "match": ["users", "persona", "roles", "audience", "actors", "stakeholder", "target user"],
         "required": True,
         "question": "Which user roles use this feature, and which roles must NOT have access?"},
        {"id": "data", "title": "Data", "match": ["data"], "required": False, "allow_none": True,
         "question": "Which data is shown, created or changed, and where does it come from?"},
        {"id": "security", "title": "Security / privacy",
         "match": ["security", "privacy", "compliance", "permission"], "required": False, "allow_none": True},
        {"id": "dependencies", "title": "Dependencies",
         "match": ["dependenc", "integration"], "required": False, "allow_none": True},
        {"id": "metrics", "title": "Success metrics",
         "match": ["success metric", "metric", "kpi", "success criteria", "measurement", "analytics"],
         "required": False,
         "question": "How will we measure success after launch?"},
        {"id": "rollout", "title": "Rollout",
         "match": ["rollout", "roll-out", "release", "launch"], "required": False,
         "question": "How should this be released (feature flag, pilot group, date constraints)?"},
    ],
    "vague_terms": [
        "fast", "quick", "quickly", "easy", "easily", "simple", "user-friendly", "user friendly",
        "intuitive", "seamless", "seamlessly", "robust", "scalable", "efficient", "efficiently",
        "flexible", "appropriate", "appropriately", "as needed", "as appropriate", "if possible",
        "where possible", "etc", "and/or", "various", "usually", "sufficient", "adequate",
        "reasonable", "optimal", "real-time", "near real-time", "high performance", "low latency",
    ],
    "vague_scan_sections": ["functional", "acceptance", "nfr"],
    "weights": {"blocking": 15, "advisory": 3, "info": 0},
}

PLACEHOLDER_RE = re.compile(
    r"\b(?:TBD|TBC|TBA|TODO|FIXME)\b|\?{3,}|\blorem ipsum\b"
    r"|\bto be (?:decided|defined|determined|confirmed|added|agreed)\b"
    r"|\[(?:insert|add|fill in|placeholder)[^\]]*\]"
    r"|<(?![!\s/])(?!https?:)(?!mailto:)[^<>\n]{1,60}(?<!\s)>",  # <name>, <KEY-123>; not comments, URLs or "a < b"
    re.IGNORECASE,
)
NONE_ONLY_RE = re.compile(
    r"^(?:none|n/?a|not applicable|nothing|no open questions?|no dependencies|-|—)\.?$", re.IGNORECASE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
BOLD_LINE_RE = re.compile(r"^\*\*(.+?)\*\*:?\s*$")
LIST_RE = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+(.*)$")
TABLE_RE = re.compile(r"^\s*\|(.+)\|\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}")
GWT_RE = re.compile(r"\bwhen\b.*\bthen\b", re.IGNORECASE | re.DOTALL)
EARS_RE = re.compile(r"\b(?:when|while|if|where)\b.*\bshall\b|\bthe \w+(?: \w+)? shall\b", re.IGNORECASE | re.DOTALL)
AC_ID_RE = re.compile(r"(?<![A-Za-z0-9])AC[-_ ]?(\d+)(?![0-9])", re.IGNORECASE)
FR_ID_RE = re.compile(r"(?<![A-Za-z0-9])FR[-_ ]?(\d+)(?![0-9])", re.IGNORECASE)
ERROR_STATE_RE = re.compile(
    r"error|fail|invalid|empty|no data|no results|unavailable|timeout|time out|denied|unauthori[sz]ed"
    r"|forbidden|not found|offline|retry|missing|ineligible|not eligible|no access", re.IGNORECASE)
NFR_KEYWORD_RE = re.compile(
    r"load|latency|response|throughput|availability|uptime|performance|concurren|scal|timeout"
    r"|freshness|fresh|delay|sla\b|slo\b|rpo\b|rto\b|accessib|wcag", re.IGNORECASE)
OWNER_RE = re.compile(r"(?:product owner|prd owner|owner|\bpo\b|author|driver)\s*(?:\*\*)?\s*[:|]\s*(?:\*\*)?\s*([^|\n]+)",
                      re.IGNORECASE)
RESOLVED_RE = re.compile(r"\b(?:resolved|answered|answer:|decision:|decided|closed|done)\b|~~.+~~|✅|\[x\]",
                         re.IGNORECASE)
NON_BLOCKING_RE = re.compile(r"[\[(]\s*(?:non[- ]?blocking|nb)\s*[\])]", re.IGNORECASE)
ID_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]{1,10}-\d+(?![0-9])")


def strip_marker(line: str) -> str:
    """Drop a leading list marker ("- ", "* ", "1. ") and emphasis so "- None." reads as "None."."""
    return re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", line).strip().strip("*_").strip()


def has_number(line: str) -> bool:
    """True if the line carries a quantity; IDs such as FR-2 or PAY-412 don't count."""
    return re.search(r"\d", ID_TOKEN_RE.sub("", line)) is not None


def normalize_heading(text: str) -> str:
    text = re.sub(r"[*_`]", "", text).strip().lower()
    text = re.sub(r"^\d+(?:\.\d+)*[.)]?\s*", "", text)
    return re.sub(r"\s+", " ", text)


def phrase_in(phrase: str, text: str) -> bool:
    # Prefix match at a word start: "goal" matches "goals", not "subgoal".
    return re.search(r"(?<![a-z])" + re.escape(phrase), text) is not None


class Section:
    def __init__(self, heading: str, level: int, line: int):
        self.heading = heading
        self.level = level
        self.line = line              # 1-based line of the heading
        self.lines: list[tuple[int, str]] = []  # (line number, text) incl. subsections


def parse_sections(text: str, rubric: dict) -> list[Section]:
    """Split Markdown into heading-delimited sections; a section's content
    includes its subsections. Bold-only lines count as headings only when they
    name a rubric section (common in Confluence exports)."""
    known = [p for s in rubric["sections"] for p in s["match"]]
    sections: list[Section] = []
    open_stack: list[Section] = []
    in_fence = False
    for no, raw in enumerate(text.splitlines(), start=1):
        if raw.strip().startswith("```") or raw.strip().startswith("~~~"):
            in_fence = not in_fence
        heading = None
        if not in_fence:
            m = HEADING_RE.match(raw)
            if m:
                heading = (len(m.group(1)), m.group(2))
            else:
                b = BOLD_LINE_RE.match(raw.strip())
                if b and len(b.group(1)) < 60 and any(phrase_in(p, normalize_heading(b.group(1))) for p in known):
                    heading = (7, b.group(1))
        if heading:
            level, title = heading
            while open_stack and open_stack[-1].level >= level:
                open_stack.pop()
            sec = Section(title.strip(), level, no)
            sections.append(sec)
            open_stack.append(sec)
            continue
        for sec in open_stack:
            sec.lines.append((no, raw))
    return sections


def classify(sections: list[Section], rubric: dict) -> dict[str, list[Section]]:
    found: dict[str, list[Section]] = {}
    for sec in sections:
        norm = normalize_heading(sec.heading)
        for spec in rubric["sections"]:
            if any(phrase_in(p, norm) for p in spec["match"]) and not any(
                    phrase_in(x, norm) for x in spec.get("exclude", [])):
                found.setdefault(spec["id"], []).append(sec)
                break
    return found


def merged_lines(secs: list[Section]) -> list[tuple[int, str]]:
    seen, out = set(), []
    for sec in secs:
        for no, line in sec.lines:
            if no not in seen:
                seen.add(no)
                out.append((no, line))
    return sorted(out)


def meaningful(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    text = "\n".join(f"{no}\x00{line}" for no, line in lines)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    out = []
    for row in text.split("\n"):
        if "\x00" not in row:
            continue
        no, line = row.split("\x00", 1)
        stripped = line.strip().strip("-*+|>").strip()
        if stripped and not TABLE_SEP_RE.match(line):
            out.append((int(no), line))
    return out


def extract_criteria(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Group acceptance-criteria content into individual criteria."""
    criteria: list[list] = []
    current = None
    base_indent = None
    table_header_seen = False
    for no, line in lines:
        if not line.strip():
            continue
        if HEADING_RE.match(line):
            current, base_indent = None, None
            continue
        t = TABLE_RE.match(line)
        if t:
            if TABLE_SEP_RE.match(line):
                continue
            if not table_header_seen:
                table_header_seen = True
                continue
            cells = [c.strip() for c in t.group(1).split("|")]
            criteria.append([no, " | ".join(c for c in cells if c)])
            current = None
            continue
        table_header_seen = False
        m = LIST_RE.match(line)
        if m:
            indent = len(m.group(1).replace("\t", "    "))
            if current is None or base_indent is None or indent <= base_indent:
                base_indent = indent if base_indent is None else min(base_indent, indent)
                current = [no, m.group(2).strip()]
                criteria.append(current)
            else:
                current[1] += " " + m.group(2).strip()
            continue
        text = line.strip()
        starts_scenario = re.match(r"^(?:\*\*)?(?:scenario|given)\b", text, re.IGNORECASE)
        if starts_scenario and (current is None or re.search(r"\bthen\b", current[1], re.IGNORECASE)):
            current = [no, text]
            criteria.append(current)
        elif current is not None:
            current[1] += " " + text
        elif not text.endswith(":"):
            current = [no, text]
            criteria.append(current)
    return [(no, txt) for no, txt in criteria if len(txt) >= 15]


def split_front_matter(text: str) -> tuple[dict, str]:
    """Return (meta, text) with a leading YAML front matter block blanked out (line numbers kept)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    for end in range(1, len(lines)):
        if lines[end].strip() == "---":
            meta = {}
            for line in lines[1:end]:
                m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
                if m:
                    meta[m.group(1)] = m.group(2).strip().strip("'\"")
            return meta, "\n".join([""] * (end + 1) + lines[end + 1:])
    return {}, text


class Linter:
    def __init__(self, text: str, rubric: dict, source: str):
        self.meta, self.text = split_front_matter(text)
        self.rubric = rubric
        self.source = source
        self.issues: list[dict] = []
        self.lines = self.text.splitlines()

    def add(self, severity, code, message, section=None, line=None, question=None, suggested_default=None):
        issue = {"code": code, "severity": severity, "section": section, "line": line, "message": message}
        if question:
            issue["question"] = question
        if suggested_default:
            issue["suggested_default"] = suggested_default
        self.issues.append(issue)

    def run(self) -> dict:
        sections = parse_sections(self.text, self.rubric)
        found = classify(sections, self.rubric)
        specs = {s["id"]: s for s in self.rubric["sections"]}
        content = {sid: meaningful(merged_lines(secs)) for sid, secs in found.items()}

        if not sections:
            self.add("blocking", "PRD-000", "No headings found; the PRD does not follow the template.",
                     question="Please restructure the PRD using the PRD template sections.")

        section_report = {}
        for spec in self.rubric["sections"]:
            sid = spec["id"]
            secs = found.get(sid, [])
            body = content.get(sid, [])
            body_text = " ".join(strip_marker(l) for _, l in body)
            state = "missing" if not secs else ("empty" if not body else (
                "none" if NONE_ONLY_RE.match(body_text) else "present"))
            section_report[sid] = {"title": spec["title"], "state": state,
                                   "heading": secs[0].heading if secs else None,
                                   "line": secs[0].line if secs else None}
            q, d = spec.get("question"), spec.get("suggested_default")
            if state == "missing":
                sev = "blocking" if spec.get("required") else "advisory"
                self.add(sev, "PRD-001", f"Missing section: {spec['title']}.", sid, None, q, d)
            elif state == "empty":
                sev = "blocking" if spec.get("required") else "advisory"
                self.add(sev, "PRD-002", f"Section '{secs[0].heading}' is empty.", sid, secs[0].line, q, d)
            elif state == "none" and spec.get("required") and not spec.get("allow_none"):
                self.add("advisory", "PRD-003", f"Section '{secs[0].heading}' says N/A; confirm that is intended.",
                         sid, secs[0].line, q, d)

        self._placeholders(found, specs)
        ac_report = self._acceptance(content.get("acceptance", []), content.get("functional", []))
        self._vague(content)
        self._nfr(content.get("nfr", []))
        self._states(content)
        self._open_questions(content.get("open_questions", []))
        owner = self._owner()

        weights = self.rubric["weights"]
        counts = {k: sum(1 for i in self.issues if i["severity"] == k) for k in ("blocking", "advisory", "info")}
        score = max(0, 100 - sum(weights[k] * v for k, v in counts.items()))
        status = "NEEDS_CLARIFICATION" if counts["blocking"] else "READY"
        order = {"blocking": 0, "advisory": 1, "info": 2}
        self.issues.sort(key=lambda i: (order[i["severity"]], i["line"] or 0))
        for n, issue in enumerate(self.issues, start=1):
            issue["id"] = f"Q{n}"
        return {"tool": "prd_lint", "version": VERSION, "source": self.source, "meta": self.meta, "status": status,
                "score": score, "counts": counts, "owner": owner, "sections": section_report,
                "acceptance": ac_report, "issues": self.issues}

    def _placeholders(self, found, specs):
        line_to_section = {}
        for sid, secs in found.items():
            for no, _ in merged_lines(secs):
                line_to_section.setdefault(no, sid)
        in_fence = False
        for no, line in enumerate(self.lines, start=1):
            if line.strip().startswith(("```", "~~~")):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            sid = line_to_section.get(no)
            if sid == "open_questions":
                continue
            m = PLACEHOLDER_RE.search(line)
            if m:
                required = bool(sid and specs[sid].get("required"))
                where = f"section '{specs[sid]['title']}'" if sid else "the document"
                self.add("blocking" if required else "advisory", "PRD-010",
                         f"Placeholder '{m.group(0)}' in {where}.", sid, no,
                         f"Line {no} still says '{m.group(0)}'. What should it say?")

    def _acceptance(self, ac_lines, fr_lines):
        criteria = extract_criteria(ac_lines)
        structured = [c for c in criteria if GWT_RE.search(c[1]) or EARS_RE.search(c[1])]
        with_ids = [c for c in criteria if AC_ID_RE.search(c[1])]
        if ac_lines and not criteria:
            self.add("blocking", "PRD-020", "Acceptance criteria section has no identifiable criteria.",
                     "acceptance", ac_lines[0][0],
                     "Please list each acceptance criterion as a separate Given / When / Then item.")
        elif criteria and not structured:
            self.add("blocking", "PRD-021", "No acceptance criterion is testable (none use Given/When/Then).",
                     "acceptance", criteria[0][0],
                     "Please rewrite the acceptance criteria as Given / When / Then so they can be tested automatically.")
        for no, txt in criteria:
            if (no, txt) not in structured and structured:
                snippet = (txt[:90] + "...") if len(txt) > 90 else txt
                self.add("advisory", "PRD-022", f"Acceptance criterion is not Given/When/Then: '{snippet}'",
                         "acceptance", no, f"Can '{snippet}' be rewritten as Given / When / Then?")
        frs = sorted({int(n) for _, l in fr_lines for n in FR_ID_RE.findall(l)})
        referenced = {int(n) for _, txt in criteria for n in FR_ID_RE.findall(txt)}
        if frs and referenced:
            for fr in frs:
                if fr not in referenced:
                    self.add("advisory", "PRD-023", f"FR-{fr} has no acceptance criterion referencing it.",
                             "functional", None, f"How do we verify FR-{fr}? Please add an acceptance criterion for it.")
        elif frs and criteria and not referenced:
            self.add("info", "PRD-024", "Acceptance criteria do not reference FR IDs; mapping will be inferred in the spec.",
                     "acceptance")
        return {"criteria": len(criteria), "structured": len(structured), "with_ids": len(with_ids),
                "functional_ids": [f"FR-{n}" for n in frs]}

    def _vague(self, content):
        hits: dict[str, list[int]] = {}
        for sid in self.rubric["vague_scan_sections"]:
            for no, line in content.get(sid, []):
                if has_number(line):
                    continue  # a number on the line usually means it is quantified
                for term in self.rubric["vague_terms"]:
                    if re.search(r"(?<![A-Za-z])" + re.escape(term) + r"(?![A-Za-z])", line, re.IGNORECASE):
                        hits.setdefault(term, []).append(no)
        for term, nos in sorted(hits.items(), key=lambda kv: kv[1][0]):
            also = f" (also line {', '.join(str(n) for n in nos[1:5])})" if len(nos) > 1 else ""
            self.add("advisory", "PRD-030", f"Vague term '{term}'{also}.", None, nos[0],
                     f"What does '{term}' mean in measurable terms (line {nos[0]})?")

    def _nfr(self, nfr_lines):
        for no, line in nfr_lines:
            if NFR_KEYWORD_RE.search(line) and not has_number(line):
                text = line.strip().lstrip("-*+ ").strip()
                self.add("advisory", "PRD-040", f"Unquantified non-functional requirement: '{text[:90]}'",
                         "nfr", no, f"Can you put a number on: '{text[:90]}'?",
                         "e.g. p95 < 2 s, availability 99.9%, data no older than 1 h, WCAG 2.2 AA")

    def _states(self, content):
        body = " ".join(l for sid in ("functional", "acceptance", "flow") for _, l in content.get(sid, []))
        if body and not ERROR_STATE_RE.search(body):
            self.add("advisory", "PRD-050", "No error, empty, or no-access states are described.", "acceptance", None,
                     "What should users see when data is empty, loading fails, or they lack access?",
                     "Empty: neutral message; failure: retry option; no access: guidance without confidential details.")

    def _open_questions(self, oq_lines):
        body = " ".join(strip_marker(l) for _, l in oq_lines)
        if not oq_lines or NONE_ONLY_RE.match(body):
            return
        for no, line in oq_lines:
            m = LIST_RE.match(line)
            text = (m.group(2) if m else line).strip()
            if not (m or "?" in text) or len(text) < 5 or NONE_ONLY_RE.match(strip_marker(text)):
                continue
            if RESOLVED_RE.search(text):
                continue
            if NON_BLOCKING_RE.search(text):
                self.add("advisory", "PRD-061", f"Open question (non-blocking): '{text[:100]}'", "open_questions", no)
            else:
                self.add("blocking", "PRD-060", f"Unresolved open question: '{text[:100]}'", "open_questions", no,
                         f"Please answer, or mark it [non-blocking]: '{text[:100]}'")

    def _owner(self):
        for line in self.lines[:60]:
            m = OWNER_RE.search(line)
            if m and m.group(1).strip(" *_"):
                return m.group(1).strip(" *_")
        if self.meta.get("page_owner"):
            return f"page owner {self.meta['page_owner']}"
        self.add("advisory", "PRD-070", "No product owner named in the PRD header; feedback goes to the page author.",
                 None, None, "Who is the accountable product owner for this PRD?")
        return None


def to_markdown(r: dict) -> str:
    icon = "READY" if r["status"] == "READY" else "NEEDS CLARIFICATION"
    out = [f"# PRD lint: {icon}", "",
           f"- Source: `{r['source']}`", f"- Score: **{r['score']}/100**",
           f"- Issues: {r['counts']['blocking']} blocking, {r['counts']['advisory']} advisory, {r['counts']['info']} info",
           f"- Product owner: {r['owner'] or 'not named'}",
           f"- Acceptance criteria: {r['acceptance']['criteria']} found, {r['acceptance']['structured']} testable "
           f"(Given/When/Then), {r['acceptance']['with_ids']} with IDs", "",
           "## Sections", "", "| Section | State | Heading |", "|---|---|---|"]
    for sid, s in r["sections"].items():
        out.append(f"| {s['title']} | {s['state']} | {s['heading'] or ''} |")
    for sev in ("blocking", "advisory", "info"):
        items = [i for i in r["issues"] if i["severity"] == sev]
        if not items:
            continue
        out += ["", f"## {sev.capitalize()} ({len(items)})", ""]
        for i in items:
            where = f" (line {i['line']})" if i["line"] else ""
            out.append(f"- **{i['id']}** [{i['code']}] {i['message']}{where}")
    questions = [i for i in r["issues"] if i.get("question") and i["severity"] != "info"]
    if questions:
        out += ["", "## Questions for the product owner", ""]
        for n, i in enumerate(questions, start=1):
            tag = "must answer" if i["severity"] == "blocking" else "please consider"
            line = f"{n}. ({tag}) {i['question']}"
            if i.get("suggested_default"):
                line += f" *Proposed default: {i['suggested_default']}*"
            out.append(line)
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("prd", help="PRD Markdown file")
    ap.add_argument("--json", dest="json_out", help="write the JSON report here")
    ap.add_argument("--md", dest="md_out", help="write the Markdown report here")
    ap.add_argument("--rubric", help="JSON rubric overriding the defaults")
    ap.add_argument("--quiet", action="store_true", help="no stdout report")
    args = ap.parse_args(argv)
    path = Path(args.prd)
    if not path.is_file():
        print(f"prd_lint: no such file: {path}", file=sys.stderr)
        return 2
    rubric = DEFAULT_RUBRIC
    if args.rubric:
        try:
            rubric = {**DEFAULT_RUBRIC, **json.loads(Path(args.rubric).read_text(encoding="utf-8"))}
        except (OSError, ValueError) as exc:
            print(f"prd_lint: bad rubric: {exc}", file=sys.stderr)
            return 2
    report = Linter(path.read_text(encoding="utf-8"), rubric, str(path)).run()
    md = to_markdown(report)
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.md_out:
        Path(args.md_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md_out).write_text(md, encoding="utf-8")
    if not args.quiet:
        print(md)
    return 0 if report["status"] == "READY" else 1


if __name__ == "__main__":
    sys.exit(main())
