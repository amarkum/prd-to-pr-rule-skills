#!/usr/bin/env python3
"""atlassian.py - minimal Confluence/Jira REST client for headless (CI) runs.

Interactive sessions use the Atlassian MCP server. CI cannot complete an OAuth
browser flow, so the intake workflow uses this dependency-free client instead.

  page-md          Confluence page -> Markdown with front matter (for prd_lint + the LLM review)
  page-comment     add a footer comment (Markdown body) to a Confluence page
  jira-create      create an issue (e.g. the PRD clarification task for the product owner)
  jira-comment     comment on an issue
  jira-transition  move an issue by transition or target-status name
  jira-search      JQL search, prints JSON lines (key, summary, status, ...)

Environment:
  ATLASSIAN_SITE        https://acme.atlassian.net (Cloud) or https://confluence.acme.com (DC)
  ATLASSIAN_EMAIL + ATLASSIAN_API_TOKEN   Cloud (basic auth)
  ATLASSIAN_PAT         Data Center / Server personal access token (bearer)
  ATLASSIAN_FLAVOR      cloud (default) | dc
  JIRA_SITE             optional, when Jira lives on a different host than Confluence

Standard library only. Exit codes: 0 ok, 1 HTTP/API error, 2 usage error.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

# ------------------------------------------------------------ storage -> markdown


class _StorageToMd(HTMLParser):
    """Confluence storage format (XHTML + ac:/ri: macros) to readable Markdown."""
    BLOCKS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "table", "pre", "blockquote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.lists: list[str] = []          # stack of "ul"/"ol"
        self.ol_counters: list[int] = []
        self.table: list[list[str]] | None = None
        self.cell: list[str] | None = None
        self.link_href: str | None = None
        self.macro: list[dict] = []         # stack of open ac:structured-macro
        self.param: str | None = None
        self.capture_plain = False
        self.task_done = False
        self.in_task_status = False
        self.quote = 0                      # depth of open info/note/warning/tip/panel macros
        self.quote_fresh = False            # first paragraph of a panel continues the label line

    # -- helpers
    def emit(self, text: str):
        if self.cell is not None:
            self.cell.append(text)
        else:
            self.out.append(text)

    def newline(self, n: int = 1):
        if self.cell is not None:
            self.cell.append(" ")
            return
        joined = "".join(self.out)
        trailing = len(joined) - len(joined.rstrip("\n"))
        if joined and trailing < n:
            self.out.append("\n" * (n - trailing))

    # -- parser callbacks
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.newline(2)
            self.emit("#" * int(tag[1]) + " ")
        elif tag == "p":
            if self.quote:
                if not self.quote_fresh:
                    self.newline(1)
                    self.emit("> ")
                self.quote_fresh = False
            else:
                self.newline(2 if not self.lists else 1)
        elif tag == "br":
            self.emit("\n" if self.cell is None else " ")
        elif tag in ("strong", "b"):
            self.emit("**")
        elif tag in ("em", "i"):
            self.emit("_")
        elif tag == "code" and not self.capture_plain:
            self.emit("`")
        elif tag in ("ul", "ol"):
            self.newline(1)
            self.lists.append(tag)
            self.ol_counters.append(0)
        elif tag == "li":
            self.newline(1)
            depth = len(self.lists) - 1
            if self.lists and self.lists[-1] == "ol":
                self.ol_counters[-1] += 1
                self.emit("   " * depth + f"{self.ol_counters[-1]}. ")
            else:
                self.emit("  " * depth + "- ")
        elif tag == "table":
            self.newline(2)
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.table.append([])
        elif tag in ("td", "th") and self.table is not None:
            self.cell = []
        elif tag == "a":
            self.link_href = a.get("href")
            self.emit("[")
        elif tag == "ac:structured-macro":
            name = a.get("ac:name", "")
            self.macro.append({"name": name, "params": {}})
            if name in ("info", "note", "warning", "tip", "panel"):
                self.newline(2)
                self.emit(f"> **{name.capitalize()}:** ")
                self.quote += 1
                self.quote_fresh = True
        elif tag == "ac:parameter":
            self.param = a.get("ac:name", "")
        elif tag == "ac:plain-text-body":
            self.capture_plain = True
        elif tag == "ac:task":
            self.task_done = False
        elif tag == "ac:task-status":
            self.in_task_status = True
        elif tag == "ac:task-body":
            self.newline(1)
            self.emit("- [x] " if self.task_done else "- [ ] ")
        elif tag == "ri:user":
            self.emit(f"@user:{a.get('ri:account-id') or a.get('ri:userkey') or a.get('ri:username') or '?'}")
        elif tag == "ri:page":
            self.emit(f"[[{a.get('ri:content-title', 'page')}]]")
        elif tag == "ri:attachment":
            self.emit(f"[attachment: {a.get('ri:filename', '?')}]")
        elif tag == "time":
            self.emit(a.get("datetime", ""))

    def handle_endtag(self, tag):
        if tag == "p" and self.quote:
            pass
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "pre", "blockquote"):
            self.newline(2 if not self.lists else 1)
        elif tag in ("strong", "b"):
            self.emit("**")
        elif tag in ("em", "i"):
            self.emit("_")
        elif tag == "code" and not self.capture_plain:
            self.emit("`")
        elif tag in ("ul", "ol"):
            if self.lists:
                self.lists.pop()
                self.ol_counters.pop()
            self.newline(2 if not self.lists else 1)
        elif tag in ("td", "th") and self.table is not None and self.cell is not None:
            text = re.sub(r"\s+", " ", "".join(self.cell)).strip().replace("|", "\\|")
            if self.table:
                self.table[-1].append(text)
            self.cell = None
        elif tag == "table" and self.table is not None:
            rows = [r for r in self.table if r]
            self.table = None
            if rows:
                width = max(len(r) for r in rows)
                rows = [r + [""] * (width - len(r)) for r in rows]
                self.out.append("| " + " | ".join(rows[0]) + " |\n")
                self.out.append("|" + "---|" * width + "\n")
                for r in rows[1:]:
                    self.out.append("| " + " | ".join(r) + " |\n")
                self.out.append("\n")
        elif tag == "a":
            self.emit(f"]({self.link_href})" if self.link_href else "]")
            self.link_href = None
        elif tag == "ac:parameter":
            self.param = None
        elif tag == "ac:plain-text-body":
            self.capture_plain = False
        elif tag == "ac:task-status":
            self.in_task_status = False
        elif tag == "ac:structured-macro" and self.macro:
            m = self.macro.pop()
            if m["name"] == "status":
                self.emit(f"[{m['params'].get('title', 'status').upper()}]")
            elif m["name"] == "jira" and m["params"].get("key"):
                self.emit(f"[Jira {m['params']['key']}]")
            elif m["name"] in ("info", "note", "warning", "tip", "panel"):
                self.quote = max(0, self.quote - 1)
                self.newline(2)

    def handle_data(self, data):
        if self.in_task_status:
            self.task_done = data.strip().lower() == "complete"
            return
        if self.param is not None and self.macro:
            self.macro[-1]["params"][self.param] = data
            return
        if self.capture_plain:
            return  # code bodies arrive via CDATA (unknown_decl)
        if self.cell is None and not data.strip() and "\n" in data:
            return
        self.emit(data)

    def unknown_decl(self, data):
        if data.startswith("CDATA[") and self.capture_plain:
            lang = self.macro[-1]["params"].get("language", "") if self.macro else ""
            self.newline(2)
            self.emit(f"```{lang}\n{data[6:]}\n```")
            self.newline(2)


def storage_to_md(storage: str) -> str:
    parser = _StorageToMd()
    parser.feed(storage)
    parser.close()
    text = "".join(parser.out)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


# ------------------------------------------------------------ markdown -> storage / ADF

def _inline_html(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"(?<![\w*])_(.+?)_(?![\w*])", r"<em>\1</em>", text)
    return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', text)


def md_blocks(md: str):
    """Yield (kind, payload) blocks: heading(level,text) | ul(items) | ol(items) | code(text) | p(text)."""
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith("```"):
            body = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1
            yield "code", "\n".join(body)
        elif re.match(r"^#{1,6}\s", line):
            level = len(line) - len(line.lstrip("#"))
            yield "heading", (level, line[level:].strip())
            i += 1
        elif re.match(r"^\s*[-*]\s+", line) or re.match(r"^\s*\d+[.)]\s+", line):
            kind = "ol" if re.match(r"^\s*\d+[.)]\s+", line) else "ul"
            items = []
            while i < len(lines) and (re.match(r"^\s*(?:[-*]|\d+[.)])\s+", lines[i])
                                      or (lines[i].startswith("  ") and items)):
                if re.match(r"^\s*(?:[-*]|\d+[.)])\s+", lines[i]):
                    items.append(re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", lines[i]))
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            yield kind, items
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not re.match(r"^(?:#{1,6}\s|```|\s*[-*]\s|\s*\d+[.)]\s)", lines[i]):
                para.append(lines[i].strip())
                i += 1
            yield "p", " ".join(para)


def md_to_storage(md: str) -> str:
    parts = []
    for kind, payload in md_blocks(md):
        if kind == "heading":
            parts.append(f"<h{payload[0]}>{_inline_html(payload[1])}</h{payload[0]}>")
        elif kind in ("ul", "ol"):
            parts.append(f"<{kind}>" + "".join(f"<li>{_inline_html(t)}</li>" for t in payload) + f"</{kind}>")
        elif kind == "code":
            parts.append('<ac:structured-macro ac:name="code"><ac:plain-text-body><![CDATA['
                         + payload.replace("]]>", "]]]]><![CDATA[>") + "]]></ac:plain-text-body></ac:structured-macro>")
        else:
            parts.append(f"<p>{_inline_html(payload)}</p>")
    return "".join(parts)


def _adf_inline(text: str) -> list[dict]:
    nodes, pos = [], 0
    for m in re.finditer(r"\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\((https?://[^)\s]+)\)", text):
        if m.start() > pos:
            nodes.append({"type": "text", "text": text[pos:m.start()]})
        if m.group(1):
            nodes.append({"type": "text", "text": m.group(1), "marks": [{"type": "strong"}]})
        elif m.group(2):
            nodes.append({"type": "text", "text": m.group(2), "marks": [{"type": "code"}]})
        else:
            nodes.append({"type": "text", "text": m.group(3), "marks": [{"type": "link", "attrs": {"href": m.group(4)}}]})
        pos = m.end()
    if pos < len(text):
        nodes.append({"type": "text", "text": text[pos:]})
    return nodes or [{"type": "text", "text": " "}]


def md_to_adf(md: str) -> dict:
    content = []
    for kind, payload in md_blocks(md):
        if kind == "heading":
            content.append({"type": "heading", "attrs": {"level": min(payload[0], 6)}, "content": _adf_inline(payload[1])})
        elif kind in ("ul", "ol"):
            content.append({"type": "bulletList" if kind == "ul" else "orderedList",
                            "content": [{"type": "listItem", "content": [{"type": "paragraph", "content": _adf_inline(t)}]}
                                        for t in payload]})
        elif kind == "code":
            content.append({"type": "codeBlock", "content": [{"type": "text", "text": payload or " "}]})
        else:
            content.append({"type": "paragraph", "content": _adf_inline(payload)})
    return {"type": "doc", "version": 1, "content": content}


# ------------------------------------------------------------ HTTP client

def parse_page_id(value: str) -> str:
    if value.isdigit():
        return value
    m = re.search(r"/pages/(\d+)", value) or re.search(r"[?&]pageId=(\d+)", value)
    if not m:
        raise ValueError(f"cannot find a page id in {value!r} (tiny /x/ links are not supported; use the full URL)")
    return m.group(1)


class Api:
    def __init__(self, site: str | None = None, flavor: str | None = None, opener=None, env=os.environ):
        self.site = (site or env.get("ATLASSIAN_SITE", "")).rstrip("/")
        self.jira_site = (env.get("JIRA_SITE") or self.site).rstrip("/")
        self.flavor = flavor or env.get("ATLASSIAN_FLAVOR", "cloud")
        if not self.site:
            raise ValueError("set ATLASSIAN_SITE")
        if env.get("ATLASSIAN_PAT"):
            self.auth = f"Bearer {env['ATLASSIAN_PAT']}"
        elif env.get("ATLASSIAN_EMAIL") and env.get("ATLASSIAN_API_TOKEN"):
            token = base64.b64encode(f"{env['ATLASSIAN_EMAIL']}:{env['ATLASSIAN_API_TOKEN']}".encode()).decode()
            self.auth = f"Basic {token}"
        else:
            raise ValueError("set ATLASSIAN_EMAIL + ATLASSIAN_API_TOKEN (Cloud) or ATLASSIAN_PAT (Data Center)")
        self.opener = opener or urllib.request.urlopen

    def call(self, method: str, url: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": self.auth, "Accept": "application/json",
            **({"Content-Type": "application/json"} if data else {})})
        try:
            with self.opener(req, timeout=30) as resp:
                raw = resp.read().decode() or "{}"
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:500]
            raise RuntimeError(f"{method} {url} -> HTTP {exc.code}: {detail}") from None
        return json.loads(raw)

    # Confluence
    def page(self, page_id: str) -> dict:
        if self.flavor == "dc":
            d = self.call("GET", f"{self.site}/rest/api/content/{page_id}?expand=body.storage,version,space")
            return {"id": d["id"], "title": d["title"], "version": d.get("version", {}).get("number"),
                    "storage": d["body"]["storage"]["value"],
                    "url": self.site + d.get("_links", {}).get("webui", f"/pages/viewpage.action?pageId={page_id}"),
                    "author": d.get("version", {}).get("by", {}).get("displayName")}
        d = self.call("GET", f"{self.site}/wiki/api/v2/pages/{page_id}?body-format=storage")
        return {"id": d["id"], "title": d["title"], "version": d.get("version", {}).get("number"),
                "storage": d["body"]["storage"]["value"],
                "url": f"{self.site}/wiki" + d.get("_links", {}).get("webui", f"/pages/{page_id}"),
                "author": d.get("ownerId") or d.get("authorId")}

    def page_comment(self, page_id: str, markdown: str) -> dict:
        storage = md_to_storage(markdown)
        if self.flavor == "dc":
            return self.call("POST", f"{self.site}/rest/api/content", {
                "type": "comment", "container": {"id": page_id, "type": "page"},
                "body": {"storage": {"value": storage, "representation": "storage"}}})
        return self.call("POST", f"{self.site}/wiki/api/v2/footer-comments",
                         {"pageId": page_id, "body": {"representation": "storage", "value": storage}})

    # Jira
    def _jira(self, path: str) -> str:
        return f"{self.jira_site}/rest/api/{'2' if self.flavor == 'dc' else '3'}/{path}"

    def _doc(self, markdown: str):
        return markdown if self.flavor == "dc" else md_to_adf(markdown)

    def jira_create(self, project: str, summary: str, issue_type: str = "Task", description: str = "",
                    parent: str | None = None, labels: list[str] | None = None, assignee: str | None = None) -> dict:
        fields = {"project": {"key": project}, "summary": summary, "issuetype": {"name": issue_type}}
        if description:
            fields["description"] = self._doc(description)
        if parent:
            fields["parent"] = {"key": parent}
        if labels:
            fields["labels"] = labels
        if assignee:
            fields["assignee"] = {"name": assignee} if self.flavor == "dc" else {"accountId": assignee}
        return self.call("POST", self._jira("issue"), {"fields": fields})

    def jira_comment(self, issue: str, markdown: str) -> dict:
        return self.call("POST", self._jira(f"issue/{issue}/comment"), {"body": self._doc(markdown)})

    def jira_transition(self, issue: str, target: str) -> dict:
        options = self.call("GET", self._jira(f"issue/{issue}/transitions")).get("transitions", [])
        want = target.strip().lower()
        match = next((t for t in options if t.get("name", "").lower() == want
                      or t.get("to", {}).get("name", "").lower() == want), None)
        if not match:
            names = ", ".join(f"{t.get('name')} -> {t.get('to', {}).get('name')}" for t in options)
            raise RuntimeError(f"no transition to '{target}' from the current status; available: {names}")
        self.call("POST", self._jira(f"issue/{issue}/transitions"), {"transition": {"id": match["id"]}})
        return {"issue": issue, "transition": match.get("name"), "to": match.get("to", {}).get("name")}

    def jira_search(self, jql: str, fields: str, limit: int) -> list[dict]:
        q = urllib.parse.urlencode({"jql": jql, "fields": fields, "maxResults": limit})
        path = f"search?{q}" if self.flavor == "dc" else f"search/jql?{q}"
        return self.call("GET", self._jira(path)).get("issues", [])


# ------------------------------------------------------------ CLI

def front_matter(meta: dict) -> str:
    lines = ["---"] + [f"{k}: {json.dumps(v) if isinstance(v, str) else v}" for k, v in meta.items() if v is not None]
    return "\n".join(lines + ["---", ""])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("page-md")
    p.add_argument("--page", required=True, help="page id or URL")
    p.add_argument("--out")
    c = sub.add_parser("page-comment")
    c.add_argument("--page", required=True)
    c.add_argument("--body-file", required=True)
    j = sub.add_parser("jira-create")
    j.add_argument("--project", required=True)
    j.add_argument("--summary", required=True)
    j.add_argument("--type", default="Task")
    j.add_argument("--description-file")
    j.add_argument("--parent")
    j.add_argument("--labels", help="comma-separated")
    j.add_argument("--assignee", help="account id (Cloud) or username (DC)")
    jc = sub.add_parser("jira-comment")
    jc.add_argument("--issue", required=True)
    jc.add_argument("--body-file", required=True)
    t = sub.add_parser("jira-transition")
    t.add_argument("--issue", required=True)
    t.add_argument("--to", required=True, help="transition name or target status name")
    s = sub.add_parser("jira-search")
    s.add_argument("--jql", required=True)
    s.add_argument("--fields", default="summary,status,issuetype,priority,created,resolutiondate,labels,components")
    s.add_argument("--max", type=int, default=20)
    a = ap.parse_args(argv)
    try:
        api = Api()
        if a.cmd == "page-md":
            page = api.page(parse_page_id(a.page))
            md = front_matter({"source": "confluence", "page_id": str(page["id"]), "title": page["title"],
                               "version": page["version"], "url": page["url"], "page_owner": page["author"],
                               "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
            md += f"\n# {page['title']}\n\n" + storage_to_md(page["storage"])
            if a.out:
                Path(a.out).parent.mkdir(parents=True, exist_ok=True)
                Path(a.out).write_text(md, encoding="utf-8")
                print(json.dumps({"out": a.out, "page_id": page["id"], "version": page["version"]}))
            else:
                print(md)
        elif a.cmd == "page-comment":
            print(json.dumps(api.page_comment(parse_page_id(a.page), Path(a.body_file).read_text(encoding="utf-8"))))
        elif a.cmd == "jira-create":
            desc = Path(a.description_file).read_text(encoding="utf-8") if a.description_file else ""
            print(json.dumps(api.jira_create(a.project, a.summary, a.type, desc, a.parent,
                                             a.labels.split(",") if a.labels else None, a.assignee)))
        elif a.cmd == "jira-comment":
            print(json.dumps(api.jira_comment(a.issue, Path(a.body_file).read_text(encoding="utf-8"))))
        elif a.cmd == "jira-transition":
            print(json.dumps(api.jira_transition(a.issue, a.to)))
        elif a.cmd == "jira-search":
            for issue in api.jira_search(a.jql, a.fields, a.max):
                f = issue.get("fields", {})
                print(json.dumps({"key": issue.get("key"), "summary": f.get("summary"),
                                  "status": (f.get("status") or {}).get("name"),
                                  "type": (f.get("issuetype") or {}).get("name"),
                                  "created": f.get("created"), "resolved": f.get("resolutiondate"),
                                  "labels": f.get("labels"),
                                  "components": [c.get("name") for c in f.get("components") or []]}))
    except ValueError as exc:
        print(f"atlassian: {exc}", file=sys.stderr)
        return 2
    except (RuntimeError, OSError, KeyError) as exc:
        print(f"atlassian: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
