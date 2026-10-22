---
name: verify
description: The Test stage: runs the repo's checks, maps each acceptance criterion to passing tests, proves new tests fail without the change, checks the diff against plan.md and its locked tests, and records it all at the commit SHA; fixes failures in at most two rounds. Use before a PR, after build, or for "is this done" or "prove it works".
argument-hint: "[--base origin/main]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ac_coverage.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fail_to_pass.py *)
---

# Verify

Evidence is produced by scripts at a committed SHA, never asserted in prose.
Paths: `${CLAUDE_PLUGIN_ROOT}` is this plugin's root.

## 1. Run

Commit first: a dirty tree can only produce an INCOMPLETE verdict. Then:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py run --manifest .ai/repo.yaml --base origin/<default-branch>
```

This runs, in order:
- every `checks` command from `.ai/repo.yaml`, with logs and SHA-256 hashes;
- `ac_coverage.py`, which links the JUnit test names to this repo's ACs from the spec's repo impact table;
- `fail_to_pass.py`, which runs new tests against the merge-base and requires at least one to fail there;
- the plan checks: `plan.md` is accepted, lists every changed file, and its locked tests are byte-for-byte unchanged.

It writes `.ai/evidence/manifest.json` and `.ai/evidence/summary.md`. `PASS` is the only verdict that counts.

## 2. If it is not PASS, classify each failure before touching anything

| Failure | Meaning | Action |
|---|---|---|
| Check failed (lint, types, unit) | code is wrong | fix the code |
| AC `MISSING` | no test cites that AC | write the test (qualified name), see it fail, then pass |
| AC `FAILING` | the behaviour is wrong | fix the code; change the test only if it contradicts the spec, and say so |
| `PASS_TO_PASS` only | new tests don't prove the change | strengthen the assertions until they fail on base |
| `FAIL_ON_HEAD` | the test or code is broken | fix it |
| plan.md does not list a changed file | the work departed from the plan | intended: add the file to "Files that change" with the reason, in a new commit; not intended: revert it |
| locked test changed | the proof was edited | restore the locked test exactly and fix the code; only a human changes a lock |
| plan or spec not accepted | a gate is open | stop: this is a human decision, not a repair |
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
