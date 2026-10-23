# Change artifacts

Every change that is not trivial gets a folder here: `docs/changes/<id>/`. The files in it are the
workflow state and the audit trail. Anyone can walk back from a release to the original problem:

release-manifest.yaml → review.md → evidence.md → plan.md → spec.md → intent.md → the ticket, incident or customer problem

`<id>` is the ticket key plus a short slug, for example `PAY-1234-refund-rounding`, or
`CHG-<YYYYMMDD>-<slug>` when there is no ticket. Templates are in `_templates/`.

## Change classes

Apply the full chain only where the risk pays for it. The class is proposed in `intent.md`, set by
the builder, and checked by `make verify-artifacts` (`scripts/check_artifacts.py`).

| Class | Typical changes | Required artifacts | Human approvals |
|---|---|---|---|
| **trivial** | Copy or typo, config value, dependency patch bump with green CI, docs | None. A clear PR description is the record. | One PR reviewer |
| **standard** | Small feature or defect fix inside one service, behind a flag, no schema, auth, payment or PII change | intent.md (short), plan.md, evidence.md | Product owner approves intent; builder approves plan; PR review focuses on judgement |
| **significant** | Cross-service feature, API contract change, backward-compatible migration, new dependency | intent, spec, plan, evidence, release-manifest.yaml | Product owner (intent), tech lead (spec), builder (plan), PR reviewer, production gate |
| **high-risk** | Authentication or authorisation, payments, PII, irreversible data change, infrastructure or network policy | Everything in significant, plus `security_approver` on the spec | All of the above plus a security reviewer; production gate is always human |

When unsure, pick the higher class. A change can be re-classed upward at any time. Downward
re-classing needs the approver of the higher class.

## Lifecycle

| Phase | Skill | Agent roles | Artifact | Gate |
|---|---|---|---|---|
| Plan | `/intent` | intent-agent | intent.md | Product owner approves |
| Design | `/spec` | architecture-reviewer, security-reviewer, others by policy pack | spec.md | Tech lead approves (security for high-risk) |
| Build | `/plan-change`, then implement | coding agent, test-engineer | plan.md + code | Builder approves the plan in plan mode |
| Test | `/verify-change` | verifier, reviewers, review-synthesizer | evidence.md, review.md | `make verify` passes; no open blockers |
| Deploy | `/release-manifest` | release pipeline | release-manifest.yaml | Human or policy gate at the production boundary |
| Maintain | `/incident-to-intent` | SRE diagnosis, incident agent | new intent.md, regression test, eval case | High-confidence findings become intents; low-confidence go to a human |

## Front matter

Every artifact starts with YAML front matter. Scripts and dashboards read it, so keep the keys:
`id`, `class`, `status`, `owner`, `approver`, `approved`. Dates are `YYYY-MM-DD`; timestamps are
ISO 8601 in UTC. The intent's `received` date and each artifact's `approved` date feed the flow
metrics (idea to approved intent, intent to spec, spec to PR).
