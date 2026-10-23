---
name: release-manifest
description: Assemble docs/changes/<id>/release-manifest.yaml from the change artifacts, git, CI results and the dev, QA and staging deployments, and summarise production readiness for the human or policy gate. Never deploys to production. Use when a merged change is moving through environments, or when the builder types /release-manifest.
argument-hint: "<change id> [version]"
disable-model-invocation: true
---

# /release-manifest: what ships, and under what risk

Arguments: $ARGUMENTS

1. **Preconditions.** `evidence.md` has `verdict: pass` and `review.md` has no open blocking
   findings. For significant and high-risk changes, the spec is approved. If anything is missing,
   stop and list it.
2. **Collect** the merge commit and PR URL (`gh pr view <n> --json url,mergeCommit,mergedAt`), the
   version or tag, the build artifact digests, the CI results (`gh pr checks <n>`) and the dev, QA
   and staging deployment results from the deploy tool. Ask the builder for anything you cannot
   read. Never invent a digest, a timestamp or a result.
3. **Fill** `docs/changes/_templates/release-manifest.yaml` as `docs/changes/<id>/release-manifest.yaml`.
   Take rollback from `plan.md` and say whether it was exercised in staging. Name the feature flag
   and the rollout steps.
4. **Production gate.** Leave `production_gate.decision: pending`. Use `type: policy` only when the
   change class has an approved auto-promotion policy and every required check passed. Otherwise use
   `type: human` and name the approver.
5. **Validate** that the file parses as YAML, for example with
   `python3 -c "import sys, yaml; yaml.safe_load(open(sys.argv[1]))" <file>` when PyYAML is
   installed.
6. **Reply** with the path and a go/no-go summary for the gate: checks, open risks and rollback
   readiness. Do not run production deployment commands. The production-boundary hook blocks them.
