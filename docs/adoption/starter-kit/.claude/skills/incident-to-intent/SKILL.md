---
name: incident-to-intent
description: Convert a production incident or postmortem into durable controls - a new intent.md for the fix, a failing regression test to freeze, an agent eval case, a Known traps entry for CLAUDE.md, and a proposed hook, permission or CI rule when the failure was mechanically preventable. Use after an incident, or when the builder types /incident-to-intent.
argument-hint: "<incident id, postmortem link or pasted notes>"
disable-model-invocation: true
---

# /incident-to-intent: production back to intent

Incident: $ARGUMENTS

1. **Gather** the timeline, impact, detection, root-cause hypothesis and contributing factors. Find
   the triggering change: search `docs/changes/*/release-manifest.yaml`, `git log -S '<symbol>'` and
   `gh pr list --search '<keyword>' --state merged`. If an SRE diagnosis report exists, use its
   hypothesis and confidence. Read observability data only through read-only MCP tools.
2. **Rate confidence.** High means the root cause is reproduced or proven by evidence. If confidence
   is low, write down the open questions and stop. That is L2 (Recommend) on the autonomy ladder: a
   human diagnoses before anything is built.
3. **Produce five outputs:**
   1. **Intent.** Use the `intent-agent` to write `docs/changes/<INC-id>-<slug>/intent.md`. Sources
      include the incident id. The class is at least standard, and high-risk for data loss or
      security incidents.
   2. **Regression test.** Use the `test-engineer` to write a test that reproduces the failure and
      fails now. Ask the builder to freeze it in `.claude/frozen-tests.txt`.
   3. **Eval case.** Write `evals/cases/EVAL-<next>-<slug>/` (case.yaml, fixture and reference) as
      described in `evals/README.md`, so the agent system is tested against this failure from now on.
   4. **Known trap.** Propose a one-line entry for the Known traps section of `CLAUDE.md`: what goes
      wrong, why, and how to avoid it.
   5. **Control.** If a deterministic rule would have prevented it, propose the exact hook rule,
      permission deny rule, lint rule or CI check. Hooks and settings are owned by humans, so
      propose the snippet and do not edit them.
4. **Reply** with a table of the five outputs: artifact, path, status (written, proposed, or needs a
   human).
