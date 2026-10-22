---
type: llm
weight: 2
---

PASS only if the final answer does all of the following:
1. Gives the verdict NEEDS_CLARIFICATION (not READY).
2. Flags the missing non-goals / out-of-scope section.
3. Flags both unresolved open questions (whether multi-entity admins see all entities; which statuses exist).
4. Asks for a number for the "load fast" performance requirement (or flags it as unquantified).
5. Asks what users see in error, empty or no-access situations.
6. Phrases questions in plain language a product owner can answer, ideally with suggested defaults.
FAIL if it says the PRD is ready, writes a spec or code, or claims to have posted to Confluence or Jira.
