---
type: llm
weight: 2
---

PASS if the final answer gives the verdict READY, or says the PRD is ready for engineering, with at most advisory
(non-blocking) suggestions.
FAIL if it returns NEEDS_CLARIFICATION, or presents any finding as blocking that the PRD already answers (non-goals,
roles, error/empty/no-access states, quantified NFRs, and resolved open questions are all present in this PRD).
