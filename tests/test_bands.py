import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from helpers import script

CONFIG = {"metric": "ci_test_failure_rate", "direction": "up", "baseline": "rolling_30d", "min_sd": 0.01,
          "tiers": {"1sigma": {"action": "log"},
                    "2sigma": {"action": "diagnose", "tools": "Read,Grep,Bash(gh run view *)"},
                    "3sigma": {"action": "propose", "routes": ["pull_request", "runbook:rollback-deploy"]}}}
BASE = [0.10, 0.12, 0.09, 0.11, 0.10, 0.13, 0.08, 0.11, 0.10, 0.12, 0.09, 0.10, 0.11, 0.10, 0.12,
        0.09, 0.11, 0.10, 0.12, 0.10]   # mean ~0.105, sd ~0.013


def series(values):
    start = dt.date(2026, 9, 1)
    return [{"t": (start + dt.timedelta(days=i)).isoformat(), "value": v} for i, v in enumerate(values)]


class BandsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "bands.json").write_text(json.dumps(CONFIG))

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, recent, config="bands.json"):
        (self.dir / "series.json").write_text(json.dumps(series(BASE + recent)))
        res = script("bands.py", "check", "--config", str(self.dir / config), "--series", str(self.dir / "series.json"),
                     "--github-output", str(self.dir / "gh_out"))
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout)

    def test_quiet_metric_is_none(self):
        out = self.check([0.11, 0.09, 0.10, 0.12, 0.10, 0.11, 0.09, 0.10])
        self.assertEqual(out["tier"], "none")
        self.assertEqual(out["action"], "none")

    def test_spike_is_3_sigma_and_may_propose(self):
        out = self.check([0.10, 0.11, 0.09, 0.10, 0.12, 0.10, 0.11, 0.40])
        self.assertEqual(out["tier"], "3sigma")
        self.assertEqual(out["action"], "propose")
        self.assertIn("runbook:rollback-deploy", out["routes"])
        self.assertIn("R1", [r["rule"] for r in out["rules_fired"]])
        self.assertIn("tier=3sigma\naction=propose\n", (self.dir / "gh_out").read_text())

    def test_two_of_three_beyond_2_sigma_diagnoses_read_only(self):
        out = self.check([0.10, 0.11, 0.09, 0.10, 0.12, 0.14, 0.10, 0.14])
        self.assertEqual(out["tier"], "2sigma")
        self.assertEqual(out["tools"], "Read,Grep,Bash(gh run view *)")

    def test_slow_drift_is_1_sigma(self):
        out = self.check([0.11, 0.115, 0.11, 0.112, 0.113, 0.111, 0.114, 0.112])
        self.assertEqual(out["tier"], "1sigma")
        self.assertIn("R4", [r["rule"] for r in out["rules_fired"]])

    def test_direction_up_ignores_improvements(self):
        out = self.check([0.10, 0.11, 0.09, 0.10, 0.12, 0.10, 0.11, 0.0])
        self.assertEqual(out["tier"], "none")

    def test_not_enough_history(self):
        (self.dir / "series.json").write_text(json.dumps(series([0.1, 0.2, 0.3])))
        res = script("bands.py", "check", "--config", str(self.dir / "bands.json"), "--series", str(self.dir / "series.json"))
        self.assertEqual(json.loads(res.stdout)["tier"], "none")

    def test_yaml_config(self):
        (self.dir / "bands.yaml").write_text("metric: m\ndirection: up\nbaseline: rolling_20\ntiers:\n"
                                             "  3sigma: {action: propose}\n")
        self.assertEqual(self.check([0.1] * 7 + [0.5], config="bands.yaml")["tier"], "3sigma")

    def test_series_from_github_runs(self):
        runs = [{"conclusion": "success", "createdAt": "2026-10-01T09:00:00Z"},
                {"conclusion": "failure", "createdAt": "2026-10-01T10:00:00Z"},
                {"conclusion": "cancelled", "createdAt": "2026-10-01T11:00:00Z"},
                {"conclusion": "success", "createdAt": "2026-10-02T09:00:00Z"}]
        (self.dir / "runs.json").write_text(json.dumps(runs))
        res = script("bands.py", "series-gh-runs", "--runs", str(self.dir / "runs.json"))
        self.assertEqual(json.loads(res.stdout), [{"t": "2026-10-01", "value": 0.5, "n": 2},
                                                  {"t": "2026-10-02", "value": 0.0, "n": 1}])


if __name__ == "__main__":
    unittest.main()
