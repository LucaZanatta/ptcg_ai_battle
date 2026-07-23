"""Generate a SelectContext coverage + latency report from captured episodes.

Distinguishes ENUM coverage (all SelectContext members, including zero-count)
from RUNTIME coverage (contexts actually observed in the captured games). Reports
per-context observed counts, per-seat decision counts, fallback usage, invalid
selections, and P50/P95/P99/max policy latency.

Outputs (paths given on the CLI):
  context_coverage.json, context_coverage.csv, CONTEXT_COVERAGE.md

Usage (from repo root):
  .venv/bin/python tools/context_coverage_report.py <episodes.jsonl> \
      --json  .../context_coverage.json \
      --csv   .../context_coverage.csv \
      --md    .../CONTEXT_COVERAGE.md
"""

import argparse
import csv
import json
import math
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.api import SelectContext  # noqa: E402


def _pct(sorted_vals, p):
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return round(sorted_vals[0], 6)
    k = (len(sorted_vals) - 1) * (p / 100.0)
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return round(sorted_vals[int(k)], 6)
    return round(sorted_vals[lo] * (hi - k) + sorted_vals[hi] * (k - lo), 6)


def build_report(path):
    per_ctx = {}          # value -> stats
    decisions_by_seat = {}
    total_decisions = 0

    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            rec = json.loads(raw)
            if rec.get("record_type") != "decision":
                continue
            total_decisions += 1
            v = rec.get("context_value")
            seat = rec.get("seat")
            decisions_by_seat[seat] = decisions_by_seat.get(seat, 0) + 1
            st = per_ctx.setdefault(v, {
                "value": v, "name": rec.get("context_name"),
                "observed_count": 0, "by_seat": {}, "fallback_count": 0,
                "invalid_count": 0, "latencies_ms": [],
            })
            st["observed_count"] += 1
            st["by_seat"][seat] = st["by_seat"].get(seat, 0) + 1
            if rec.get("used_fallback"):
                st["fallback_count"] += 1
            if not str(rec.get("validation_status", "valid")).startswith("valid"):
                st["invalid_count"] += 1
            lat = rec.get("policy_latency_ns")
            if isinstance(lat, (int, float)):
                st["latencies_ms"].append(lat / 1e6)

    enum_members = list(SelectContext)
    enum_values = {int(c) for c in enum_members}
    observed_values = set(per_ctx)

    contexts = []
    for c in enum_members:
        v = int(c)
        st = per_ctx.get(v)
        contexts.append(_ctx_row(c.name, v, st, observed=v in observed_values, in_enum=True))
    # Any observed context not defined in the enum (engine appended a new value).
    for v in sorted(observed_values - enum_values):
        st = per_ctx[v]
        contexts.append(_ctx_row(st.get("name") or f"UNKNOWN_{v}", v, st, observed=True, in_enum=False))

    runtime_observed = len(observed_values & enum_values)
    report = {
        "description": "SelectContext coverage. 'enum' coverage = every defined "
                       "SelectContext member; 'runtime' coverage = contexts actually "
                       "observed in captured games. These are intentionally distinct.",
        "enum_contexts_total": len(enum_members),
        "runtime_contexts_observed": runtime_observed,
        "runtime_observed_percentage": round(100.0 * runtime_observed / len(enum_members), 2),
        "total_decisions": total_decisions,
        "decisions_by_seat": {str(k): v for k, v in sorted(decisions_by_seat.items(), key=lambda x: (x[0] is None, x[0]))},
        "contexts": contexts,
        "not_observed": [c.name for c in enum_members if int(c) not in observed_values],
    }
    return report


def _ctx_row(name, value, st, observed, in_enum):
    if st:
        lat = sorted(st["latencies_ms"])
        latency = {"count": len(lat), "p50": _pct(lat, 50), "p95": _pct(lat, 95),
                   "p99": _pct(lat, 99), "max": (round(lat[-1], 6) if lat else None)}
        by_seat = {str(k): v for k, v in sorted(st["by_seat"].items(), key=lambda x: (x[0] is None, x[0]))}
        return {"name": name, "value": value, "in_enum": in_enum, "observed": observed,
                "observed_count": st["observed_count"], "by_seat": by_seat,
                "fallback_count": st["fallback_count"], "invalid_count": st["invalid_count"],
                "latency_ms": latency}
    return {"name": name, "value": value, "in_enum": in_enum, "observed": False,
            "observed_count": 0, "by_seat": {}, "fallback_count": 0, "invalid_count": 0,
            "latency_ms": {"count": 0, "p50": None, "p95": None, "p99": None, "max": None}}


def write_csv(report, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["context_name", "context_value", "in_enum", "observed", "observed_count",
                    "seat0_count", "seat1_count", "fallback_count", "invalid_count",
                    "p50_ms", "p95_ms", "p99_ms", "max_ms"])
        for c in report["contexts"]:
            lat = c["latency_ms"]
            w.writerow([c["name"], c["value"], c["in_enum"], c["observed"], c["observed_count"],
                        c["by_seat"].get("0", 0), c["by_seat"].get("1", 0),
                        c["fallback_count"], c["invalid_count"],
                        lat["p50"], lat["p95"], lat["p99"], lat["max"]])


def write_md(report, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    lines = []
    lines.append("# SelectContext Coverage & Latency\n")
    lines.append(f"- **Enum-defined contexts:** {report['enum_contexts_total']} "
                 "(every `SelectContext` member, including zero-count).")
    lines.append(f"- **Runtime-observed contexts:** {report['runtime_contexts_observed']} "
                 f"({report['runtime_observed_percentage']}% of enum).")
    lines.append(f"- **Total decisions:** {report['total_decisions']}; "
                 f"by seat: {report['decisions_by_seat']}.")
    lines.append("\n> Enum coverage and runtime coverage are distinct: the selector is "
                 "compatible with every enum context, but only a subset arises in sampled games.\n")
    lines.append("| context | value | observed | count | seat0 | seat1 | fallback | invalid | p50 ms | p95 ms | p99 ms | max ms |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for c in report["contexts"]:
        lat = c["latency_ms"]
        def f(x):
            return "" if x is None else f"{x:.4f}"
        lines.append(f"| {c['name']} | {c['value']} | {'yes' if c['observed'] else 'no'} "
                     f"| {c['observed_count']} | {c['by_seat'].get('0', 0)} | {c['by_seat'].get('1', 0)} "
                     f"| {c['fallback_count']} | {c['invalid_count']} "
                     f"| {f(lat['p50'])} | {f(lat['p95'])} | {f(lat['p99'])} | {f(lat['max'])} |")
    lines.append(f"\n**Not observed ({len(report['not_observed'])}):** "
                 + ", ".join(report["not_observed"]) + "\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Context coverage report")
    parser.add_argument("path")
    parser.add_argument("--json", required=True)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--md", required=True)
    args = parser.parse_args(argv)

    report = build_report(args.path)
    os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    write_csv(report, args.csv)
    write_md(report, args.md)
    print(f"enum contexts: {report['enum_contexts_total']}; "
          f"runtime observed: {report['runtime_contexts_observed']} "
          f"({report['runtime_observed_percentage']}%)")
    print(f"total decisions: {report['total_decisions']} by seat {report['decisions_by_seat']}")
    print(f"wrote: {args.json}, {args.csv}, {args.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
