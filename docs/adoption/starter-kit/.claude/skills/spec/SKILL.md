---
name: spec
description: Turn an approved intent.md into docs/changes/<id>/spec.md by running specialist reviewer subagents in parallel and synthesising their findings. Required for significant and high-risk changes, optional for standard ones. Use when the builder types /spec.
argument-hint: "<change id>"
disable-model-invocation: true
---

# /spec: intent to executable specification

Change id: $ARGUMENTS

1. **Preconditions.** `docs/changes/<id>/intent.md` exists with `status: approved`. If not, stop and
   say what is missing. Trivial changes never get a spec. For a standard change, ask whether the
   builder wants a light spec or wants to go straight to `/plan-change`.
2. **Read** the intent, `CLAUDE.md`, the relevant policy packs in `docs/policies/`, and the code
   areas involved. For blast radius, use Grep for callers. If `kompactor` is installed, also run
   `kompactor graph impact <file|symbol>` on the main entry points.
3. **Draft** from `docs/changes/_templates/spec.md`. Number every functional and non-functional
   requirement (FR-1, NFR-1) so tests and the plan can cite them.
4. **Specialist review, in parallel.** In one message, start the `architecture-reviewer` and
   `security-reviewer` subagents on the draft. For significant and high-risk changes, also ask the
   `test-engineer` for a read-only critique of the test strategy. If the change has data, API, UX,
   performance or compliance aspects and a matching policy pack exists, add a general-purpose
   subagent briefed with that pack.
5. **Synthesise.** Fix the spec for each finding you accept. Record every reviewer's verdict, and
   each finding you rejected with the reason, in the Specialist review log table.
6. **Write** `docs/changes/<id>/spec.md` with `status: draft`. Reply with the path, the open risks
   and the decisions the approver must make.
7. **Stop for approval.** A tech lead or architect approves significant changes. High-risk changes
   also need `security_approver` filled in by a security reviewer.
