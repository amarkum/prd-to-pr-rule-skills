#!/usr/bin/env python3
"""schema_snapshot.py - committed data-contract snapshots for MongoDB collections (or any JSON documents).

  infer  sample documents (JSON array, JSON lines or MongoDB Extended JSON) -> JSON Schema snapshot.
         Only types and field presence are kept, never values.
  diff   compare two snapshots and classify every change as additive or BREAKING (exit 1 if breaking),
         so "don't break consumers" becomes a CI check rather than a review comment.

Keep record values out of the model's context: sample to a file in a shell pipeline, then infer from the file, e.g.
  mongosh "$MDB_URI" --quiet --eval 'EJSON.stringify(db.payroll_run_status.aggregate([{$sample:{size:200}}]).toArray())' \
    > /tmp/samples.json
  schema_snapshot.py infer --in /tmp/samples.json --name payroll.payroll_run_status \
    --out docs/schemas/mongo/payroll.payroll_run_status.json

Usage:
  schema_snapshot.py infer --in FILE --name DB.COLLECTION [--source TEXT] [--out FILE]
  schema_snapshot.py diff OLD.json NEW.json [--json]
Standard library only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

EJSON = {"$oid": ("string", "objectid"), "$date": ("string", "date-time"), "$numberLong": ("integer", None),
         "$numberInt": ("integer", None), "$numberDouble": ("number", None), "$numberDecimal": ("number", None),
         "$binary": ("string", "binary"), "$uuid": ("string", "uuid"), "$timestamp": ("string", "timestamp")}
WIDENING = {("integer", "number")}


def json_type(value):
    if isinstance(value, dict) and len(value) == 1 and next(iter(value)) in EJSON:
        return EJSON[next(iter(value))]
    if value is None:
        return "null", None
    if isinstance(value, bool):
        return "boolean", None
    if isinstance(value, int):
        return "integer", None
    if isinstance(value, float):
        return "number", None
    if isinstance(value, str):
        return "string", None
    if isinstance(value, list):
        return "array", None
    return "object", None


def merge(schema: dict, value) -> dict:
    """Fold one value into a schema node: {"types": set, "formats": set, "props": {}, "seen": n, "present": {k: n}}."""
    t, fmt = json_type(value)
    schema.setdefault("types", set()).add(t)
    if fmt:
        schema.setdefault("formats", set()).add(fmt)
    if t == "object":
        schema["objects"] = schema.get("objects", 0) + 1
        props = schema.setdefault("props", {})
        present = schema.setdefault("present", {})
        for k, v in value.items():
            merge(props.setdefault(k, {}), v)
            if v is not None:
                present[k] = present.get(k, 0) + 1
    elif t == "array":
        items = schema.setdefault("items", {})
        for v in value:
            merge(items, v)
    return schema


def to_json_schema(node: dict) -> dict:
    types = sorted(node.get("types", set()))
    if "integer" in types and "number" in types:
        types.remove("integer")
    out: dict = {"type": types[0] if len(types) == 1 else types}
    if node.get("formats"):
        fmts = sorted(node["formats"])
        out["format"] = fmts[0] if len(fmts) == 1 else fmts
    if "object" in types:
        out["properties"] = {k: to_json_schema(v) for k, v in sorted(node.get("props", {}).items())}
        required = [k for k, n in sorted(node.get("present", {}).items()) if n == node.get("objects", 0)]
        if required:
            out["required"] = required
    if "array" in types and node.get("items"):
        out["items"] = to_json_schema(node["items"])
    return out


def load_docs(path: Path) -> list:
    text = path.read_text(encoding="utf-8").strip()
    if text.startswith("["):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def infer(docs: list, name: str, source: str) -> dict:
    root: dict = {}
    for d in docs:
        if not isinstance(d, dict):
            raise ValueError("every sample must be a JSON object (document)")
        merge(root, d)
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": name, **to_json_schema(root)}
    schema["x-snapshot"] = {"name": name, "source": source, "samples": len(docs),
                            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    return schema


def flatten(schema: dict, prefix: str = "", required: bool = True) -> dict:
    """{path: {"type": set, "required": bool}} for every field, arrays as `field[]`."""
    out = {}
    types = schema.get("type")
    types = set(types if isinstance(types, list) else [types]) if types else set()
    if prefix:
        out[prefix] = {"type": types, "required": required}
    if "object" in types:
        req = set(schema.get("required", []))
        for k, sub in schema.get("properties", {}).items():
            out.update(flatten(sub, f"{prefix}.{k}" if prefix else k, k in req))
    if "array" in types and isinstance(schema.get("items"), dict):
        out.update(flatten(schema["items"], f"{prefix}[]", True))
    return out


def diff(old: dict, new: dict) -> list[dict]:
    a, b = flatten(old), flatten(new)
    changes = []
    for path in sorted(set(a) | set(b)):
        if path not in b:
            changes.append({"path": path, "change": "removed", "breaking": True})
        elif path not in a:
            changes.append({"path": path, "change": "added", "breaking": False})
        else:
            ta, tb = a[path]["type"], b[path]["type"]
            if ta != tb:
                widened = all(any(x == y or (x, y) in WIDENING for y in tb) for x in ta)
                changes.append({"path": path, "change": f"type {sorted(ta)} -> {sorted(tb)}", "breaking": not widened})
            if a[path]["required"] and not b[path]["required"]:
                changes.append({"path": path, "change": "required -> optional", "breaking": True})
            elif not a[path]["required"] and b[path]["required"]:
                changes.append({"path": path, "change": "optional -> required", "breaking": False})
    return changes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("infer")
    i.add_argument("--in", dest="inp", required=True)
    i.add_argument("--name", required=True)
    i.add_argument("--source", default="sampled documents")
    i.add_argument("--out")
    d = sub.add_parser("diff")
    d.add_argument("old")
    d.add_argument("new")
    d.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "infer":
            schema = infer(load_docs(Path(a.inp)), a.name, a.source)
            text = json.dumps(schema, indent=2) + "\n"
            if a.out:
                Path(a.out).parent.mkdir(parents=True, exist_ok=True)
                Path(a.out).write_text(text, encoding="utf-8")
                print(f"wrote {a.out} ({schema['x-snapshot']['samples']} samples)")
            else:
                print(text, end="")
            return 0
        changes = diff(json.loads(Path(a.old).read_text()), json.loads(Path(a.new).read_text()))
        breaking = [c for c in changes if c["breaking"]]
        if a.json:
            print(json.dumps({"breaking": bool(breaking), "changes": changes}, indent=2))
        else:
            for c in changes:
                print(f"{'BREAKING' if c['breaking'] else 'additive'}  {c['path']}: {c['change']}")
            print(f"{len(changes)} change(s), {len(breaking)} breaking")
        return 1 if breaking else 0
    except (OSError, ValueError) as exc:
        print(f"schema_snapshot: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
