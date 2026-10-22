---
name: verify
description: Produces verifiable evidence that a change meets its spec - runs the repo's checks, maps every acceptance criterion to passing tests, proves new tests fail without the change (fail-to-pass), and records hashes and the commit SHA - then fixes failures within a bounded number of rounds. Use before opening a PR, after build, or when asked "is this done", "run the checks", or "prove it works".
argument-hint: "[--base origin/main]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ac_coverage.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fail_to_pass.py *)
---

# Verify

Evidence is produced by scripts at a committed SHA, never asserted in prose.
Paths: `${CLAUDE_PLUGIN_ROOT}` is this plugin's root (in Cursor: the folder two levels above this skill).

## 1. Run

Commit first: a dirty tree can only produce an INCOMPLETE verdict. Then:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py run --manifest .ai/repo.yaml --base origin/<default-branch>
```

This runs, in order:
- every `checks` command from `.ai/repo.yaml`, with logs and SHA-256 hashes;
- `ac_coverage.py`, which links the JUnit test names to this repo's ACs from the spec's repo impact table;
- `fail_to_pass.py`, which runs new tests against the merge-base and requires at least one to fail there.

It writes `.ai/evidence/manifest.json` and `.ai/evidence/summary.md`. `PASS` is the only verdict that counts.

## 2. If it is not PASS, classify each failure before touching anything

| Failure | Meaning | Action |
|---|---|---|
| Check failed (lint, types, unit) | code is wrong | fix the code |
| AC `MISSING` | no test cites that AC | write the test (qualified name), see it fail, then pass |
| AC `FAILING` | the behaviour is wrong | fix the code; change the test only if it contradicts the spec, and say so |
| `PASS_TO_PASS` only | new tests don't prove the change | strengthen the assertions until they fail on base |
| `FAIL_ON_HEAD` | the test or code is broken | fix it |
| Environment problem (service down, flaky) | not the code | re-run once. If it fails again, report it; never mark it skipped |

**At most two repair rounds.** Then stop and report the remaining failures, what you tried, and what decision is needed.

## 3. Independent check

When `PASS`, ask the `qa-verifier` subagent to review the evidence and the tests themselves: do the AC tests assert the AC's
outcome, or just render without crashing? Are there tautologies? Is the unit under test mocked? Is the data synthetic?
Fix what it finds (that means a new commit and a re-run).

## 4. Report

The verdict, the HEAD SHA, the AC table, the fail-to-pass counts and any residual risk.
This local evidence is level 1. CI re-runs the same script on a clean runner (level 2) and attaches attested artifacts
(level 3). Reviewers trust the CI result.
