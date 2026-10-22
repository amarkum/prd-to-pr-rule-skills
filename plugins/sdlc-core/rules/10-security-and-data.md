---
description: Security and data handling rules for coding agents
---
# Security and data (always on)

- Never read, print or write secrets (.env, keys, tokens, credential files). Reference environment variables.
- Data stores are read-only for agents. Prefer schemas, counts and indexes; samples at most 5 documents,
  redacted, never copied into prompts, tests, fixtures or PR text. Tests use synthetic data.
- Local or dev data stores only. Never connect to production.
- No new network destinations, no `curl | sh`. A new dependency needs its name, version, license and reason
  in the PR.
- Authorization is enforced server-side; UI checks are cosmetic.
- Changes to auth, PII handling, migrations, infrastructure, CI workflows or CODEOWNERS need explicit human
  approval. Never weaken the agent's own guardrails (`.claude/settings*.json`, hooks, CI gates).
