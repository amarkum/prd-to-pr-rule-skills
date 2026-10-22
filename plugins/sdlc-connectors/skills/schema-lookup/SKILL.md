---
name: schema-lookup
description: Looks up the shape of data a story touches - committed schema snapshots first, then read-only MCP (MongoDB collection-schema and indexes, the SQL schema database through DBHub) - records it with sources and without exposing records, and keeps snapshots current. Use when a PRD, spec or task mentions collections, tables, fields, indexes or data contracts, or when asked what the data looks like.
argument-hint: "<collection | table | field>"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/schema_snapshot.py *)
---

# Schema lookup

Paths: `${CLAUDE_PLUGIN_ROOT}` is this plugin's root (in Cursor: the folder two levels above this skill).

## Order of sources

1. **Committed snapshots** in `docs/schemas/**` (one JSON Schema per collection or table, with `x-snapshot` metadata).
   They are reviewed and diffable, so prefer them and cite the path.
2. **Live, read-only, local or dev only**, for what the snapshots don't cover:
   - **MongoDB MCP** (`mongodb` server, started with `--readOnly`): `list-collections`, `collection-schema`,
     `collection-indexes`, `count`, `explain`. Use `find` only with `limit` ≤ 5 and a projection that excludes personal
     fields, and only when the schema alone can't answer the question.
   - **Schema database** (DBHub `schema-db` server, `execute_sql` configured `readonly = true`): `search_objects` for tables
     and columns. Use `execute_sql` only for metadata (`information_schema`, catalog views, schema-registry tables).
     Never `SELECT *` from business tables.
3. If a server is not configured, ask the developer to set `MDB_MCP_CONNECTION_STRING` or `SCHEMA_DB_DSN` for a local or
   dev database with a **read-only** user. Never ask for production credentials.

## Record

In `context.md` or the spec: store, collection or table, the fields that matter (name, type, required, index), and the
source (snapshot path, or the MCP tool and time). Describe shapes. **Never paste documents or rows.**

## Keep snapshots current

When a story changes what a pipeline writes, refresh its snapshot in the same PR, sampling to a file so values stay out
of the conversation:

```bash
mongosh "$MDB_MCP_CONNECTION_STRING" --quiet --eval \
  'EJSON.stringify(db.getSiblingDB("payroll").payroll_run_status.aggregate([{$sample:{size:200}}]).toArray())' > /tmp/samples.json
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/schema_snapshot.py infer --in /tmp/samples.json \
  --name payroll.payroll_run_status --source "local sample" --out docs/schemas/mongo/payroll.payroll_run_status.json
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/schema_snapshot.py diff <old.json> docs/schemas/mongo/payroll.payroll_run_status.json
```

`diff` exits 1 on a breaking change (field removed, type narrowed, required to optional). A breaking change needs a
migration plan in the approved spec, and the consumers named in `.ai/repo.yaml` must be told.
