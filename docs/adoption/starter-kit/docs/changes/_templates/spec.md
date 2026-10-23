---
id: "<TICKET>-<short-slug>"
title: "<same as intent>"
class: significant                  # trivial | standard | significant | high-risk
status: draft                       # draft | approved | superseded
owner: "<builder handle>"
approver: "<tech lead or architect handle>"
security_approver: ""               # required for high-risk changes
approved: ""                        # YYYY-MM-DD
intent: "intent.md"
---

# Spec: <title>

What is being built and against which standards. Every requirement is numbered so tests, the plan
and reviewers can cite it.

## Functional requirements
- **FR-1** ...

## Non-functional requirements
- **NFR-1** Latency, throughput, availability, cost, accessibility ...

## Architecture and components affected
Components, boundaries crossed, sequence or data-flow notes. Link a diagram if it helps.

## API changes
Endpoints, events or contracts added or changed, with versioning and the error model.

## Data-model changes
Tables, fields, indexes, retention. Forward and backward compatibility.

## Security implications
Authentication, authorisation (object level), input handling, secrets, PII. Link the threat
model for high-risk changes.

## Observability requirements
Logs, metrics, traces, dashboards and alerts that prove this works in production.

## Failure scenarios
| Scenario | Expected behaviour | Detected by |
|---|---|---|
|  |  |  |

## Backward compatibility
Old clients, old data, mixed versions during rollout.

## Migration plan
Steps, ordering, reversibility, data backfill, dry run.

## Test strategy
Which layer proves which requirement: unit, integration, contract, end-to-end, performance,
security, accessibility.

## Rollout strategy
Feature flag, cohorts, percentages, kill switch, success and abort criteria.

## Open risks
| # | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| 1 |  |  |  |  |  |

## Specialist review log
| Reviewer | Verdict | Findings accepted | Findings rejected, with reason |
|---|---|---|---|
| architecture-reviewer |  |  |  |
| security-reviewer |  |  |  |

## Gate: do not proceed until
- [ ] Every requirement is testable and numbered.
- [ ] Policy packs that apply were checked, and exceptions are approved and recorded.
- [ ] Security review complete (named `security_approver` for high-risk).
- [ ] Approved (front matter `status: approved`, `approved: <date>`).
