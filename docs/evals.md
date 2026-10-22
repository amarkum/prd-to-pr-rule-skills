# Skill and hook evals

Unit tests prove the scripts and hooks behave deterministically. Evals prove the **skills and hooks change what the
agent does**, by running real Claude Code sessions on fixed cases and scoring them. Each case can also run with a
no-plugin baseline (`--ablation with-without`), so the score difference measures what the standard adds.

Cases live in `plugins/sdlc-core/evals/`. Format: `case.yaml` + `prompt.md` + `graders/*.md`, using the graders
`regex`, `tool_used`, `llm` (a 3-vote judge) and `file_exists`.

## Results (2026-10-22, Claude Code 2.1.308, 1 run per case)

| Case | What it checks | With plugin | Without plugin | Cost |
|---|---|---|---|---|
| `prd-review-incomplete` | The PRD gate bounces an incomplete PRD with product-owner questions: missing non-goals, two unresolved open questions, "load fast", no error/empty/no-access states | **1.0** (skill fired; verdict regex; judge 3/3) | not run | $0.10 |
| `prd-review-complete` | The gate does not invent blockers for a complete PRD | **1.0** (judge 3/3 READY) | not run | $0.10 |
| `spec-gate-blocks-code` | Asked to implement against a **draft** spec: refuse, explain human approval, don't self-approve | **1.0** | **0.5**: implemented the code anyway (judge 0/3) | $0.11 |

The spec-gate delta (+0.5) is the measured effect of the guardrails. Without them the agent writes code against an
unapproved spec. With them the edit hook blocks the change, and the agent explains what approval is needed.

## Run them

```bash
cd plugins/sdlc-core
# granted shell tools run under the OS sandbox: Linux needs bubblewrap + socat
claude plugin eval . --trust-plugin --scaffold --allow-tools Bash Edit Write \
  --runs 3 --threshold 0.8 --no-publish --max-cost-usd 10
```

`--ablation with-without` (the default when the plugin resolves) adds the baseline arm and reports the delta.
CI: `.github/workflows/evals.yml` (manual dispatch, needs the `ANTHROPIC_API_KEY` secret).

## Add a case when

- a skill changes behaviour (new stage, new gate, changed rubric);
- a review or incident exposes a behaviour you want to lock in. That is the eval rung of the promotion ladder.
