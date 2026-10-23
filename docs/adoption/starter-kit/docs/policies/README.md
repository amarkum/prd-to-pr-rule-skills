# Policy packs

A policy pack is one version-controlled file per area that both people and agents apply while a
spec is being written, not weeks later in review. Reviewer subagents cite rule ids in findings
(`policy: security.SEC-003`), which makes findings checkable and lets you count which rules fire.

Planned packs (write them as the pilot needs them, one area at a time):
architecture, api, security, authz, privacy (PII), logging, observability, data, frontend,
accessibility, cloud, performance, compliance, testing.

## Format

Each rule has an id, one imperative sentence, the reason, how to check it, and a short example.
Keep a pack under about 150 lines. A pack that agents skim and skip is worse than five sharp rules.

```markdown
### SEC-001 Check object-level authorisation on every read and write
Why: tenant data leaks come from endpoints that check the role but not the object's owner.
Check: every handler that loads a record by id compares its tenant or owner with the caller.
Example: `invoice = repo.get(id); authorize(caller, "read", invoice)`, not `repo.get(id)` alone.
```

Rules change like code: in a PR, with an owner, and with an eval case when a rule changes agent
behaviour. When an agent repeats a mistake, the fix lands here, in `CLAUDE.md`, or in a test,
never only in someone's head.

`security.md` in this folder is a short starting example.
