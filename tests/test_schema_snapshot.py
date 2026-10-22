import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, run

SCRIPT = ROOT / "plugins" / "sdlc-connectors" / "scripts" / "schema_snapshot.py"
spec = importlib.util.spec_from_file_location("schema_snapshot", SCRIPT)
ss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ss)

DOCS = [
    {"_id": {"$oid": "65f0c0ffee"}, "run_id": "R-1", "status": "COMPLETED", "updated_at": {"$date": "2026-10-01T06:00:00Z"},
     "employer": {"id": "E-1", "name": "Acme"}, "tags": ["pilot"], "attempts": 1},
    {"_id": {"$oid": "65f0c0ffef"}, "run_id": "R-2", "status": "FAILED", "updated_at": {"$date": "2026-10-01T07:00:00Z"},
     "employer": {"id": "E-2"}, "tags": [], "attempts": 2.5, "error": None},
]


class SchemaSnapshotTests(unittest.TestCase):
    def test_infer_types_formats_and_required(self):
        s = ss.infer(DOCS, "payroll.payroll_run_status", "test")
        props = s["properties"]
        self.assertEqual(props["_id"], {"type": "string", "format": "objectid"})
        self.assertEqual(props["updated_at"]["format"], "date-time")
        self.assertEqual(props["attempts"]["type"], "number")            # integer + number widens to number
        self.assertEqual(props["employer"]["required"], ["id"])          # name only in one sample
        self.assertEqual(props["tags"]["items"]["type"], "string")
        self.assertNotIn("error", s["required"])                         # null in the only sample that has it
        self.assertIn("run_id", s["required"])
        self.assertNotIn("Acme", json.dumps(s))                          # values never stored

    def test_diff_classifies_changes(self):
        old = ss.infer(DOCS, "x", "t")
        new_docs = [dict(d) for d in DOCS]
        for d in new_docs:
            d.pop("status")                                              # removed -> breaking
            d["entity_id"] = "N-1"                                       # added -> additive
            d["run_id"] = 1                                              # type change -> breaking
        changes = {c["path"]: c for c in ss.diff(old, ss.infer(new_docs, "x", "t"))}
        self.assertTrue(changes["status"]["breaking"])
        self.assertFalse(changes["entity_id"]["breaking"])
        self.assertTrue(changes["run_id"]["breaking"])

    def test_widening_and_optional(self):
        old = {"type": "object", "properties": {"n": {"type": "integer"}, "f": {"type": "string"}}, "required": ["n", "f"]}
        new = {"type": "object", "properties": {"n": {"type": "number"}, "f": {"type": "string"}}, "required": ["n"]}
        changes = {c["path"]: c for c in ss.diff(old, new)}
        self.assertFalse(changes["n"]["breaking"])                        # integer -> number is a widening
        self.assertTrue(changes["f"]["breaking"])                         # required -> optional breaks readers

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            samples = Path(d) / "s.jsonl"
            samples.write_text("\n".join(json.dumps(x) for x in DOCS))
            old, new = Path(d) / "old.json", Path(d) / "new.json"
            self.assertEqual(run(["python3", str(SCRIPT), "infer", "--in", str(samples), "--name", "x",
                                  "--out", str(old)]).returncode, 0)
            self.assertEqual(run(["python3", str(SCRIPT), "diff", str(old), str(old)]).returncode, 0)
            data = json.loads(old.read_text())
            del data["properties"]["status"]
            new.write_text(json.dumps(data))
            res = run(["python3", str(SCRIPT), "diff", str(old), str(new)])
            self.assertEqual(res.returncode, 1)
            self.assertIn("BREAKING  status: removed", res.stdout)


if __name__ == "__main__":
    unittest.main()
