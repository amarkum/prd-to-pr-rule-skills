# Agent evals

Regression tests for the agent's configuration. `CLAUDE.md`, `REVIEW.md`, `.claude/` and the ai-sdlc plugins steer
what Claude does here; when one of them changes, or a new model is adopted, these evals say whether Claude still does
this repo's work to the same standard. `ai-agent-evals.yml` runs them on PRs that touch that configuration and nightly,
and fails below an 80% pass rate.

## Add an eval

Take a real task from recent work with a known accepted outcome, ideally one where the agent once went wrong.
Every production incident gets one, written by the team that owned the incident. Aim for 20 to 50 over time.

`evals/<short-name>.json`:

```json
{
  "prompt": "PAY-499: the payroll status DAG marks a re-run as FAILED when the previous run succeeded. Fix it test-first.",
  "allowed_tools": "Read,Edit,Write,Grep,Glob,Bash(pytest *),Bash(ruff *)",
  "setup": ["git apply evals/fixtures/pay-499-bug.patch"],
  "checks": [
    "pytest tests/dags -q",
    "ruff check dags include tests",
    "git diff --quiet HEAD -- tests/dags/test_payroll_status.py"
  ],
  "timeout": 900,
  "max_turns": 40
}
```

`checks` define acceptable: tests pass, lint is clean, behaviour unchanged elsewhere, policy followed (the last check
above proves the agent fixed the code without editing the reproducing test). Each runs in the eval's own worktree.

Run locally: `python3 <ai-sdlc>/plugins/sdlc-core/scripts/agent_evals.py run --threshold 0.8` (it calls `claude -p`
once per eval and costs money). As models improve, retire evals that no longer discriminate and add new ones from
incidents and review findings.
