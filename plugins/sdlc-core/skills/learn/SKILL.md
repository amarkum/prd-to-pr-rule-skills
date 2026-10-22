---
name: learn
description: Turns what a story taught the team (review comments, CI failures, rework, PRD clarifications, incidents) into reviewed knowledge entries, CLAUDE.md lines, rules, checks or evals. Use after review feedback or a merge, after an incident, or for "capture lessons" or "run a retro".
argument-hint: "<PR-number | JIRA-KEY>"
---

# Learn (the compounding step)

The aim is for the next agent and the next developer to avoid this story's mistakes automatically.
Knowledge enters the standard only through a reviewed PR. Never edit rules or skills in place without review.

## 1. Collect what happened (facts, with links)

- Review comments: `gh pr view <n> --comments` and `gh api repos/{owner}/{repo}/pulls/<n>/comments`.
- Rework: commits after the first review, and why they were needed.
- CI: failed runs on the branch (`gh run list --branch <branch>`) and their causes.
- PRD: clarification rounds and what was missing (`specs/<KEY>/prd-review.json` history).
- Production: incidents or bugs later linked to the change.

## 2. Classify each lesson and choose where it lives

| Lesson type | Destination | Owner |
|---|---|---|
| Fact about this repo | `CLAUDE.md` or `docs/knowledge/` in this repo | repo CODEOWNERS |
| Stack convention or pitfall | stack skill or knowledge entry in the standard repo (`knowledge/<stack>/`) | stack guild |
| Workflow gap | `sdlc-core` skill or rubric | platform team |
| PRD template or rubric gap | `standards/prd-template.md`, prd-review rubric | product ops |
| Repeated mistake | promote it (below) | |

**Promotion ladder.** Each recurrence moves the lesson up one rung, and each rung is enforced more strictly:
knowledge entry (found when relevant) -> `CLAUDE.md` "Things Claude gets wrong" (the second time Claude makes the
mistake) -> rule or skill text (always or path-loaded) -> hook, lint or test (deterministic). A skill makes a violation
rare; a hook makes it close to impossible. If a reviewer has had to say the same thing twice, it belongs in a check.
Every production incident also gets an agent eval (`evals/`), so the configuration can't regress on it.

## 3. Write

- **Knowledge entries** use `templates/knowledge-entry.md`: symptom, cause, do/don't, the test that guards it, provenance links,
  owner, and a `review_by` date (about six months out). Keep them short; one lesson per file.
- **Retro line**: append `specs/<KEY>/retro.md` with stage timestamps, review cycles, CI failures, PRD clarification
  rounds, and the lessons with their destinations. These feed the team metrics.

## 4. Propose

Open a PR to the destination repo, labelled `ai-knowledge`, and tag its owner. Report what you proposed and where.
If nothing is worth keeping, write "no new lessons" in `retro.md`. That is a valid outcome.
