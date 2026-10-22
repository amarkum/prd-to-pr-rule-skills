---
jira: <KEY>
title: <title>
type: feature            # feature | bug | incident | improvement
source: confluence:<page-id>@v<version>   # or jira:<KEY>, sentry:<issue-id>, alert:<metric>@<date>, conversation
author: <originator>
status: draft            # draft | accepted | rejected  (the product owner or service owner decides)
accepted_by:
accepted_at:
---

# Intent: <title>

## Problem

<What people can't do today, who is affected, in the originator's own words. Evidence: numbers, tickets, incidents.>

## Proposed outcome

<What better looks like, observable from outside the code.>

## Affected users and systems

<Roles and personas; repos and services, using the names in each repo's .ai/repo.yaml.>

## Constraints

<Policy, data and privacy, compatibility, performance, dates. Non-goals.>

## Open questions

<Carried into the spec, or "None.">
