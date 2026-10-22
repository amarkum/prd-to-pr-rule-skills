#!/usr/bin/env python3
"""bands.py - deterministic control bands that decide when Claude is invoked on a production or process metric.

Detection stays deterministic: a rolling baseline (mean and standard deviation) and the Western Electric
rules decide the tier; the tier decides what the agent may do (bands.yaml):

  metric: ci_test_failure_rate
  direction: up            # up | down | both: which side of the baseline is bad
  baseline: rolling_30d    # rolling_<N>d (days, by timestamp) or rolling_<N> (points)
  min_sd: 0.01             # floor for the standard deviation of a very flat baseline
  tiers:
    1sigma: {action: log}
    2sigma: {action: diagnose, tools: "Read,Grep,Bash(gh run view *)"}
    3sigma: {action: propose, routes: [pull_request, "runbook:rollback-deploy"]}

Rules, evaluated on the newest points against the baseline before them:
  R1  the newest point beyond 3 sigma                          -> 3sigma
  R2  2 of the newest 3 points beyond 2 sigma, same side       -> 2sigma
  R3  4 of the newest 5 points beyond 1 sigma, same side       -> 1sigma
  R4  the newest 8 points on the same side of the mean (drift) -> 1sigma

Usage:
  bands.py check --config .ai/bands.yaml --series series.json [--json out.json] [--github-output $GITHUB_OUTPUT]
  bands.py series-gh-runs --runs runs.json [--out series.json]
      turns `gh run list --json conclusion,createdAt --limit 500` into a daily failure-rate series

A series is a JSON list of {"t": "2026-10-01" or ISO timestamp, "value": number}.
Exit codes: 0 evaluated (the tier is in the output), 2 usage or input error.
Standard library only; YAML configs need PyYAML (a .json config works without it).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import sys
from pathlib import Path

TIERS = ["none", "1sigma", "2sigma", "3sigma"]
TEST_WINDOW = 8   # R4 needs the newest 8 points


def load_config(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    try:
        import yaml  # type: ignore
    except ImportError:
        raise ValueError("YAML config needs PyYAML (pip install pyyaml), or use a .json config")
    return yaml.safe_load(text) or {}


def parse_time(t: str) -> dt.datetime:
    t = str(t).replace("Z", "+00:00")
    value = dt.datetime.fromisoformat(t) if "T" in t else dt.datetime.fromisoformat(t + "T00:00:00+00:00")
    return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)


def baseline_points(points: list[dict], spec: str) -> tuple[list[dict], list[dict]]:
    """(baseline, recent): recent is the newest TEST_WINDOW points; baseline is the window before them."""
    recent = points[-TEST_WINDOW:]
    earlier = points[:-TEST_WINDOW]
    m = re.fullmatch(r"rolling_(\d+)(d?)", spec or "rolling_30d")
    if not m:
        raise ValueError(f"baseline must look like rolling_30d or rolling_60, not {spec!r}")
    n, days = int(m.group(1)), m.group(2) == "d"
    if days and recent:
        start = parse_time(recent[0]["t"]) - dt.timedelta(days=n)
        return [p for p in earlier if parse_time(p["t"]) >= start], recent
    return earlier[-n:], recent


def evaluate(points: list[dict], cfg: dict) -> dict:
    points = sorted(points, key=lambda p: parse_time(p["t"]))
    base, recent = baseline_points(points, cfg.get("baseline", "rolling_30d"))
    if len(base) < 5 or not recent:
        return {"tier": "none", "rules_fired": [], "reason": f"not enough history ({len(base)} baseline points, need 5)"}
    values = [float(p["value"]) for p in base]
    mean = sum(values) / len(values)
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))
    sd = max(sd, float(cfg.get("min_sd", 0)) or 1e-12)
    direction = cfg.get("direction", "both")
    zs = [(float(p["value"]) - mean) / sd for p in recent]

    def bad(z: float, k: float) -> bool:
        return (z > k and direction in ("up", "both")) or (z < -k and direction in ("down", "both"))

    def same_side(zs_: list[float], k: float, need: int) -> bool:
        ups = sum(1 for z in zs_ if z > k and direction in ("up", "both"))
        downs = sum(1 for z in zs_ if z < -k and direction in ("down", "both"))
        return ups >= need or downs >= need

    fired = []
    if bad(zs[-1], 3):
        fired.append(("R1", "3sigma", "newest point beyond 3 sigma"))
    if len(zs) >= 3 and same_side(zs[-3:], 2, 2):
        fired.append(("R2", "2sigma", "2 of the newest 3 points beyond 2 sigma"))
    if len(zs) >= 5 and same_side(zs[-5:], 1, 4):
        fired.append(("R3", "1sigma", "4 of the newest 5 points beyond 1 sigma"))
    if len(zs) >= 8 and same_side(zs[-8:], 0, 8):
        fired.append(("R4", "1sigma", "the newest 8 points on one side of the mean"))
    tier = max((f[1] for f in fired), key=TIERS.index, default="none")
    return {"tier": tier, "rules_fired": [{"rule": r, "tier": t, "meaning": m} for r, t, m in fired],
            "baseline": {"mean": round(mean, 6), "sd": round(sd, 6), "points": len(base)},
            "latest": {"t": recent[-1]["t"], "value": recent[-1]["value"], "z": round(zs[-1], 3)},
            "recent_z": [round(z, 3) for z in zs]}


def cmd_check(a) -> int:
    cfg = load_config(Path(a.config))
    series = json.loads(Path(a.series).read_text(encoding="utf-8"))
    result = evaluate(series, cfg)
    tier_cfg = (cfg.get("tiers") or {}).get(result["tier"], {}) if result["tier"] != "none" else {}
    result = {"metric": cfg.get("metric"), "direction": cfg.get("direction", "both"), **result,
              "action": tier_cfg.get("action", "none"), "tools": tier_cfg.get("tools"),
              "routes": tier_cfg.get("routes", [])}
    text = json.dumps(result, indent=2)
    if a.json:
        Path(a.json).write_text(text + "\n", encoding="utf-8")
    if a.github_output:
        with open(a.github_output, "a", encoding="utf-8") as fh:
            fh.write(f"tier={result['tier']}\naction={result['action']}\ntools={result.get('tools') or ''}\n")
    print(text)
    return 0


def cmd_series_gh_runs(a) -> int:
    runs = json.loads(Path(a.runs).read_text(encoding="utf-8"))
    days: dict[str, list[int]] = {}
    for run in runs:
        if run.get("conclusion") not in ("success", "failure", "timed_out"):
            continue  # cancelled, skipped and in-progress runs say nothing about test health
        day = parse_time(run["createdAt"]).date().isoformat()
        total_fail = days.setdefault(day, [0, 0])
        total_fail[0] += 1
        total_fail[1] += run["conclusion"] != "success"
    series = [{"t": d, "value": round(f / n, 4), "n": n} for d, (n, f) in sorted(days.items())]
    text = json.dumps(series, indent=1)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--config", required=True)
    c.add_argument("--series", required=True)
    c.add_argument("--json")
    c.add_argument("--github-output")
    g = sub.add_parser("series-gh-runs")
    g.add_argument("--runs", required=True)
    g.add_argument("--out")
    a = ap.parse_args(argv)
    try:
        return {"check": cmd_check, "series-gh-runs": cmd_series_gh_runs}[a.cmd](a)
    except (ValueError, KeyError, OSError) as exc:
        print(f"bands: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
