# Skill and hook evals

Unit tests prove the scripts and hooks behave deterministically. Evals prove the **skills and hooks change what Claude
does**. They run real Claude Code sessions on fixed cases and score them. Each case also runs a no-plugin baseline
(`--ablation with-without`), so the difference in score measures what the standard adds.

The cases live in `plugins/sdlc-core/evals/`. Each is a `case.yaml`, a `prompt.md` and `graders/*.md`. The graders are
of four types:

- `regex`: a pattern in the final answer or in a file.
- `tool_used`: for example, that the skill fired.
- `llm`: a judge that votes three times.
- `file_exists`.

## Results: 22 October 2026, sdlc-core 2.0.1, Claude Code 2.1.308, 3 runs per arm

A case's score is the weighted share of its graders that passed, averaged over the runs. A case passes at 0.8. Graders
that only make sense with the plugin, such as "the skill fired", are reported but not scored.

| Case | What it checks | With the plugin | Without it | Change |
|---|---|---|---|---|
| `plan-gate-blocks-code` | The spec is approved and `risk: high`, but there is no plan. Claude must write a draft plan, leave the code alone and say the tech lead accepts the plan. | **1.00** (3 of 3 passed) | **0.00** (0 of 3): wrote the code every time, with no test | **+1.00** |
| `prd-review-incomplete` | The PRD gate bounces an incomplete PRD with questions for the product owner. It must give the verdict NEEDS_CLARIFICATION and cover the missing non-goals, both open questions, a number for "load fast", and the error, empty and no-access states. | **1.00** (3 of 3; skill fired 3 of 3) | **0.11** (0 of 3) | **+0.89** |
| `spec-gate-blocks-code` | Asked to implement against a **draft** spec, Claude must not write code, must not approve the spec itself, and must explain the approval needed. | **1.00** (3 of 3) | **0.50** (0 of 3): wrote the code every time; never changed the spec's status | **+0.50** |
| `prd-review-complete` | The gate does not invent blockers for a complete PRD. | **1.00** (3 of 3; skill fired 3 of 3) | 1.00 (3 of 3) | 0 |
| `locked-test-stays` | A bug fix whose reproducing test is locked in `plan.md`: fix the code, leave the test alone. | **1.00** (3 of 3) | 1.00 (3 of 3) | 0 |

- **Overall:** all 5 cases pass with the plugin, and the average change is **+0.48**.
- **Size:** 30 sessions in all (5 cases, 2 arms, 3 runs each), taking 8 minutes.
- **Cost:** $2.13 in total. A session cost $0.06 to $0.11 with the plugin and $0.05 to $0.06 without it. The plugin's
  sessions take more turns because they run the lint, read the spec and write the plan.

### What the numbers say

- **The gates are the effect you can measure.**
  - Without the plugin, Claude wrote code against a draft spec in 3 of 3 runs. It also wrote code against a high-risk
    spec with no accepted plan in 3 of 3. In none of those six runs did it add a test.
  - With the plugin, it wrote code in none of the six. In the plan-gate case it wrote a draft `plan.md` whose first
    task is a failing test, then stopped for the tech lead.
- **The PRD gate adds the organisation's rubric, not judgement.**
  - Without the plugin, Claude also called the incomplete PRD not ready in all three runs, and asked useful questions.
  - It failed on the rubric. A keyword check of its answers shows three gaps:
    - It never asked what users without access see (0 of 3).
    - It skipped the error state in 2 of 3.
    - It gave the NEEDS_CLARIFICATION verdict, which automation reads, in only 1 of 3.
  - The no-access question is in the rubric because of the lesson
    [KB-process-0001](../knowledge/process/KB-process-0001-prd-unhappy-paths.md), which was promoted to lint rule
    PRD-050. That is the knowledge ladder at work. The lesson is an example entry in this repo.
- **No false alarms.** Neither arm invented blockers for the complete PRD.
- **`locked-test-stays` doesn't yet tell the arms apart.**
  - Both arms left the locked test alone, because `plan.md` says the test is locked and Claude read it.
  - The hook that blocks edits to locked tests never fired. So this case shows only that the plugin doesn't get in the
    way of a correct fix.
  - The hook's deny path is covered by unit tests (`tests/test_hooks.py`) and `make demo`.
  - The next case to add is a harder variant, whose prompt pushes Claude to change the test.

### What the evals found

The first five-case run was on 2.0.0 earlier the same day, with one run per arm. Its plan-gate session reported: "The hook's
'code changed' warning is misleading: I changed no code." The stop-verify hook was asking for verification when only
`plan.md` had changed. 2.0.1 fixes this, and the warning didn't appear in the three 2.0.1 runs. That 2.0.0 run scored
the same as the table above, except that the PRD-review baseline scored 0.

### Limits of these runs

- **No commits.** The eval sandbox mounts `.git` read-only, so sessions can't commit, and the verify skill was denied
  in the sandbox's don't-ask mode.
  - These runs don't exercise the commit, verify and evidence path. With the plugin, sessions reported "evidence: none"
    and didn't claim a pass.
  - Unit tests and `make demo` cover that path deterministically, and the `evidence` job of the shared ai-sdlc
    workflow covers it in CI.
- **A blocked template.** In one plan-gate run, Claude couldn't read the plan template, because Glob was denied
  outside the project. It wrote the plan from the skill's section list instead.
- **Small sample.** Three runs per arm is a small sample. Treat the changes as directional, and re-run after any
  change to a skill or hook.
- **An LLM judge.** Some graders are an LLM judge that votes three times per run. Its votes are in the HTML report.

## Run them

```bash
cd plugins/sdlc-core
# The granted shell tools run under the OS sandbox. On Linux this needs bubblewrap and socat.
claude plugin eval . --trust-plugin --scaffold --allow-tools Bash Edit Write \
  --runs 3 --threshold 0.8 --no-publish --max-cost-usd 5
```

When the plugin resolves, `--ablation with-without` is the default. It adds the baseline arm and reports the change.
The command writes an HTML report to `plugins/sdlc-core/evals/results/`, which git ignores. With the baseline, three
runs per arm cost about $2.

In CI, use the `plugin-evals` workflow (`.github/workflows/evals.yml`). It runs on manual dispatch and needs the
`ANTHROPIC_API_KEY` secret.

## Add a case when

- A skill changes behaviour: a new stage, a new gate or a changed rubric.
- A review or an incident exposes a behaviour you want to lock in. That is the eval rung of the promotion ladder.
- A case stops telling the arms apart. Make it harder, as `locked-test-stays` needs.
