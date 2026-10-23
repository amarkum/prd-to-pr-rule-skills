# Agent evals

Normal tests answer "does the software still work?". Agent evals answer "does the AI engineering
system still behave correctly?". The system under test is the agent configuration: `CLAUDE.md`,
`.claude/agents`, `.claude/skills`, `.claude/hooks`, `.claude/settings.json`, the policy packs and
the model. Run the suite whenever any of them change (`ci/github/agent-evals.yml` does this).

```bash
python3 evals/run_evals.py --self-test           # free: each case passes with its reference, fails without
python3 evals/run_evals.py --case EVAL-0001 --runs 1
python3 evals/run_evals.py                       # the whole suite, real runs (costs money)
```

The harness copies the agent configuration and the case fixture into a throwaway git repository,
runs headless Claude Code (`claude -p ... --output-format json`) with the case's turn and budget
limits, then grades the workspace. It needs `claude` on PATH and PyYAML for `case.yaml`.

Fixtures contain deliberately failing tests. `evals/conftest.py` keeps pytest from collecting them;
exclude `evals/cases/` in any other test runner or linter your repository uses.

## A case

```
evals/cases/EVAL-0001-frozen-test-defect-fix/
  case.yaml        task, expected and forbidden behaviour, graders, limits
  fixture/         the starting repository (with its own .claude/frozen-tests.txt and Makefile)
  reference/       files a correct agent would produce; used by --self-test
```

Each case defines what the operating model asks for: input task, expected behaviour, expected
files or patterns, forbidden behaviour, tests that must pass, policy checks and a scoring rubric.

| Grader | Passes when |
|---|---|
| `must_pass` | every command exits 0 in the workspace afterwards |
| `files_unchanged` | the listed files are byte-for-byte unchanged |
| `files_changed` | the listed files changed |
| `allowed_paths` | every changed or new file matches one of the globs |
| `expected_patterns` | each regex is found in the named file |
| `forbidden_patterns` | no regex matches an added line in the diff or a new file |

Each grader has a weight. A run's score is the weighted share of graders that passed. A run passes at
`threshold` (default 1.0) with no policy violation (cost or turn limits). A case passes when its pass
rate reaches `min_pass_rate` across `runs` attempts, because LLM output varies.

## Growing the suite
- Seed 20 to 30 cases from representative historical PRs: API security fixes, authentication
  changes, data migrations, UI components and incident fixes. Take the parent commit as the fixture
  and the merged change as the reference. Strip anything confidential.
- Every production incident adds a case (`/incident-to-intent` drafts it).
- Every time an agent repeats a mistake, add a case before you fix CLAUDE.md, so you can see the fix work.
- Run `--self-test` on every new case: a case that passes without the fix measures nothing.

Agent eval pass rate is an executive metric. Lines of AI-generated code are not.

Once the skills ship as a plugin, `claude plugin eval` can also score them (prompt.md plus grader
files per case, with a no-plugin baseline arm). Start one with `claude plugin eval init`.
