---
id: "<TICKET>-<short-slug>"        # folder name under docs/changes/, e.g. PAY-1234-refund-rounding
title: "<one line, from the user's side>"
class: standard                     # trivial | standard | significant | high-risk (docs/changes/README.md)
status: draft                       # draft | approved | superseded
owner: "<builder handle>"           # the single accountable builder
approver: "<product owner handle>"
received: "YYYY-MM-DD"              # when the idea or request first arrived (feeds idea-to-impact time)
approved: ""                        # YYYY-MM-DD, set by the approver only
sources:                            # where the problem came from: tickets, support, incidents, analytics
  - "<jira:PAY-1234>"
---

# Intent: <title>

Why this change exists. Written before design, approved by the product owner. One page for a
standard change, two at most for significant or high-risk ones.

## Problem
What is wrong or missing, for whom, and how we know. Link the evidence.

## Business outcome
What gets better for the business when this is solved. One or two sentences.

## Users affected
Who, how many, which segments, tenants or regions.

## Current behavior
What happens today. Include a reproduction for defects.

## Desired behavior
Observable outcomes, not an implementation.

## Scope
-

## Out of scope
-

## Constraints
Security, privacy and PII, compliance, performance, deadlines, platform limits.

## Dependencies
Teams, services, vendors, feature flags, data.

## Success metrics
| Metric | Baseline | Target | How measured | Checked on |
|---|---|---|---|---|
|  |  |  |  |  |

## Risks and open questions
| # | Question or risk | Owner | Status |
|---|---|---|---|
| 1 |  |  | open |

## Gate: do not proceed until
- [ ] The problem is clearly stated.
- [ ] A measurable outcome is defined (at least one success metric with a target).
- [ ] Scope and out of scope are agreed.
- [ ] Security and compliance constraints are captured.
- [ ] A named owner is assigned.
- [ ] Approved by the product owner (front matter `status: approved`, `approved: <date>`).
