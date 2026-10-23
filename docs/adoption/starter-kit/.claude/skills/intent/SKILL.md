---
name: intent
description: Start a change. Turns a request, ticket or incident into a draft docs/changes/<id>/intent.md with a proposed change class and the questions the product owner must answer. Use when the builder types /intent or asks to start or scope a new change.
argument-hint: "<ticket key, link or one-line request>"
disable-model-invocation: true
---

# /intent: problem to intent.md

Request: $ARGUMENTS

1. **Pick the change id.** Use the ticket key plus a short slug, for example
   `PAY-1234-refund-rounding`. Without a ticket, use `CHG-<YYYYMMDD>-<slug>`. The artifacts live
   in `docs/changes/<id>/`.
2. **Gather the source.** If the request is a ticket key or URL and an issue-tracker MCP server is
   connected (Jira, Linear, GitHub), read the ticket, its comments and linked items. Otherwise use
   what the builder pasted. If you cannot read something, say so and ask. Never guess its content.
3. **Draft.** Delegate to the `intent-agent` subagent. Pass the source material, the id and the
   template path `docs/changes/_templates/intent.md`.
4. **Check the class** against `docs/changes/README.md`. If the change is trivial, tell the builder
   that no intent is needed and a clear PR description is enough, delete the draft, and stop.
5. **Present** the path, the class with its one-line reason, the numbered open questions, and which
   gate items are still unmet.
6. **Stop.** The product owner approves by setting `status: approved` and `approved: <date>`, or by
   approving the PR that adds the intent. Do not start `/spec` or `/plan-change` on your own.
