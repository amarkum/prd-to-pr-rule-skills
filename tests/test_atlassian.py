import importlib.util
import io
import json
import unittest

from helpers import SCRIPTS

spec = importlib.util.spec_from_file_location("atlassian", SCRIPTS / "atlassian.py")
atl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(atl)

STORAGE = """
<h2>Summary</h2><p>Admins see <strong>run status</strong> per pay period. See <a href="https://x.test/a">spec</a>.</p>
<ac:structured-macro ac:name="info"><ac:rich-text-body><p>Pilot with 5 employers.</p></ac:rich-text-body></ac:structured-macro>
<h2>Acceptance criteria</h2>
<ul><li>AC-1: Given an admin, when they open the dashboard, then they see cards.</li>
<li>AC-2: Given a failure, when loading, then a retry button shows.<ul><li>nested detail</li></ul></li></ul>
<table><tbody><tr><th>Field</th><th>Value</th></tr><tr><td>Product owner</td><td><ac:link><ri:user ri:account-id="5b10abc"/></ac:link></td></tr></tbody></table>
<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">json</ac:parameter><ac:plain-text-body><![CDATA[{"status": "COMPLETED"}]]></ac:plain-text-body></ac:structured-macro>
<ac:task-list><ac:task><ac:task-status>complete</ac:task-status><ac:task-body>Legal review</ac:task-body></ac:task><ac:task><ac:task-status>incomplete</ac:task-status><ac:task-body>Security review</ac:task-body></ac:task></ac:task-list>
<p>Status: <ac:structured-macro ac:name="status"><ac:parameter ac:name="title">Ready</ac:parameter></ac:structured-macro></p>
"""


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Recorder:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, req, timeout=30):
        body = json.loads(req.data.decode()) if req.data else None
        self.requests.append((req.get_method(), req.full_url, body, dict(req.header_items())))
        return FakeResponse(json.dumps(self.responses.pop(0)).encode())


CLOUD_ENV = {"ATLASSIAN_SITE": "https://acme.atlassian.net", "ATLASSIAN_EMAIL": "bot@acme.test",
             "ATLASSIAN_API_TOKEN": "t0ken"}


class ConversionTests(unittest.TestCase):
    def test_storage_to_markdown(self):
        md = atl.storage_to_md(STORAGE)
        self.assertIn("## Summary", md)
        self.assertIn("**run status**", md)
        self.assertIn("[spec](https://x.test/a)", md)
        self.assertIn("> **Info:** Pilot with 5 employers.", md)
        self.assertIn("- AC-1: Given an admin, when they open the dashboard, then they see cards.", md)
        self.assertIn("  - nested detail", md)
        self.assertIn("| Field | Value |", md)
        self.assertIn("| Product owner | @user:5b10abc |", md)
        self.assertIn('```json\n{"status": "COMPLETED"}\n```', md)
        self.assertIn("- [x] Legal review", md)
        self.assertIn("- [ ] Security review", md)
        self.assertIn("[READY]", md)

    def test_markdown_to_storage_and_adf(self):
        md = "## PRD needs clarification\n\n1. **Must answer:** what is out of scope?\n2. Use `p95`\n\nThanks"
        storage = atl.md_to_storage(md)
        self.assertIn("<h2>PRD needs clarification</h2>", storage)
        self.assertIn("<ol><li><strong>Must answer:</strong> what is out of scope?</li>", storage)
        adf = atl.md_to_adf(md)
        self.assertEqual(adf["type"], "doc")
        self.assertEqual([n["type"] for n in adf["content"]], ["heading", "orderedList", "paragraph"])
        first = adf["content"][1]["content"][0]["content"][0]["content"][0]
        self.assertEqual(first, {"type": "text", "text": "Must answer:", "marks": [{"type": "strong"}]})

    def test_html_is_escaped_in_comments(self):
        self.assertIn("&lt;script&gt;", atl.md_to_storage("<script>alert(1)</script>"))

    def test_page_id_parsing(self):
        self.assertEqual(atl.parse_page_id("https://acme.atlassian.net/wiki/spaces/PAY/pages/123456789/PRD"), "123456789")
        self.assertEqual(atl.parse_page_id("https://wiki.acme.com/pages/viewpage.action?pageId=42"), "42")
        self.assertEqual(atl.parse_page_id("987"), "987")
        with self.assertRaises(ValueError):
            atl.parse_page_id("https://acme.atlassian.net/wiki/x/AbCd")


class ApiTests(unittest.TestCase):
    def test_cloud_page_and_comment_requests(self):
        rec = Recorder([{"id": "123", "title": "PRD", "version": {"number": 9}, "ownerId": "abc",
                         "body": {"storage": {"value": "<p>x</p>"}}, "_links": {"webui": "/spaces/PAY/pages/123"}},
                        {"id": "c1"}])
        api = atl.Api(opener=rec, env=CLOUD_ENV)
        page = api.page("123")
        self.assertEqual(page["url"], "https://acme.atlassian.net/wiki/spaces/PAY/pages/123")
        api.page_comment("123", "Hello **PO**")
        (m1, u1, _, h1), (m2, u2, b2, _) = rec.requests
        self.assertEqual((m1, u1), ("GET", "https://acme.atlassian.net/wiki/api/v2/pages/123?body-format=storage"))
        self.assertTrue(h1["Authorization"].startswith("Basic "))
        self.assertEqual((m2, u2), ("POST", "https://acme.atlassian.net/wiki/api/v2/footer-comments"))
        self.assertEqual(b2["body"], {"representation": "storage", "value": "<p>Hello <strong>PO</strong></p>"})

    def test_cloud_jira_create_transition_search(self):
        rec = Recorder([{"key": "PAY-413"},
                        {"transitions": [{"id": "31", "name": "Ask PO", "to": {"name": "Needs Clarification"}}]},
                        {},
                        {"issues": []}])
        api = atl.Api(opener=rec, env=CLOUD_ENV)
        api.jira_create("PAY", "Clarify PRD", description="1. What is out of scope?", parent="PAY-412",
                        labels=["prd-clarification"], assignee="acc-1")
        self.assertEqual(api.jira_transition("PAY-412", "needs clarification")["to"], "Needs Clarification")
        api.jira_search("project = PAY AND type = Bug", "summary,status", 5)
        create, _, transition, search = rec.requests
        self.assertEqual(create[1], "https://acme.atlassian.net/rest/api/3/issue")
        self.assertEqual(create[2]["fields"]["description"]["type"], "doc")
        self.assertEqual(create[2]["fields"]["assignee"], {"accountId": "acc-1"})
        self.assertEqual(transition[2], {"transition": {"id": "31"}})
        self.assertTrue(search[1].startswith("https://acme.atlassian.net/rest/api/3/search/jql?jql=project"))

    def test_data_center_flavor(self):
        rec = Recorder([{"id": "42", "title": "PRD", "version": {"number": 3, "by": {"displayName": "Priya"}},
                         "body": {"storage": {"value": "<p>x</p>"}}, "_links": {"webui": "/display/PAY/PRD"}},
                        {"key": "PAY-9"}])
        api = atl.Api(opener=rec, env={"ATLASSIAN_SITE": "https://wiki.acme.com", "ATLASSIAN_PAT": "pat",
                                       "ATLASSIAN_FLAVOR": "dc", "JIRA_SITE": "https://jira.acme.com"})
        self.assertEqual(api.page("42")["author"], "Priya")
        api.jira_create("PAY", "Clarify", description="plain text")
        (_, u1, _, h1), (_, u2, b2, _) = rec.requests
        self.assertEqual(u1, "https://wiki.acme.com/rest/api/content/42?expand=body.storage,version,space")
        self.assertEqual(h1["Authorization"], "Bearer pat")
        self.assertEqual(u2, "https://jira.acme.com/rest/api/2/issue")
        self.assertEqual(b2["fields"]["description"], "plain text")

    def test_unknown_transition_lists_options(self):
        rec = Recorder([{"transitions": [{"id": "1", "name": "Start", "to": {"name": "In Progress"}}]}])
        with self.assertRaises(RuntimeError) as ctx:
            atl.Api(opener=rec, env=CLOUD_ENV).jira_transition("PAY-1", "Done")
        self.assertIn("Start -> In Progress", str(ctx.exception))

    def test_missing_credentials(self):
        with self.assertRaises(ValueError):
            atl.Api(env={"ATLASSIAN_SITE": "https://acme.atlassian.net"})


if __name__ == "__main__":
    unittest.main()
