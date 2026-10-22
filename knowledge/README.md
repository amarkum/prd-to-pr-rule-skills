# Knowledge base (org and stack scope)

Reviewed lessons that make the next story better. Repo-specific lessons live in each repo's `docs/knowledge/`.
Lessons here apply across repos, organised by stack (`airflow/`, `frontend/`, `mfe/`) or `process/`.

- **Format**: the `learn` skill's `knowledge-entry.md` template. Front matter fields `id`, `title`, `scope`, `type`,
  `status`, `owner`, `provenance`, `created`, `review_by`, `promoted_to`.
- **How entries arrive**: the `learn` skill opens a PR (label `ai-knowledge`); the CODEOWNERS for the stack review it.
- **How agents use them**: `context-gather` searches here by stack and keyword, and cites entries by id.
- **Promotion ladder**: knowledge entry -> rule or skill text -> hook, lint or test. When a lesson recurs, promote it and
  set `promoted_to`.
- **Freshness**: `python3 tools/aisdlc.py knowledge-audit knowledge/` fails on entries past `review_by`. A weekly
  workflow runs it and opens an issue.

The three seed entries below illustrate each rung of the ladder. They come from the PAY-412 example scenario and
show the format; replace them with your own.
