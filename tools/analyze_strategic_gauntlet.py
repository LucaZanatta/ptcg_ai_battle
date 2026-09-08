"""Analyze the c005 strategic gauntlet: matchup matrices, seat effects, pairwise
bootstrap intervals, regularized Bradley-Terry + 2000-resample bootstrap ranking,
worst matchups, reliability/latency, plus high-impact context coverage, action
entropy by context, and game-length/decision-count stats.

Reuses cg.gauntlet_stats. Reads strategic_gauntlet_games.jsonl.gz (game_terminal
+ decision records, phase=='gauntlet'). Produces strategic_* artifacts consumed
by tools/select_teacher.py.

Usage: .venv/bin/python tools/analyze_strategic_gauntlet.py --in-dir <artifacts> --out-dir <artifacts>
"""

import argparse
import csv
import json
import math
import os
import random
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.api import SelectContext
from cg.episode_compat import read_records
from cg.gauntlet_stats import (
    bootstrap_ranking, bradley_terry, seat_balanced_rate, stratified_bootstrap_ci, wilson_interval,
)

_BOOT = 2000
# High-impact contexts (§10.1), mapped to SelectContext members that exist.
_HIGH_IMPACT = {"MAIN", "ATTACK", "SWITCH", "EVOLVE", "TO_ACTIVE", "TO_BENCH", "TO_HAND",
                "DISCARD", "ACTIVATE"}
_NAME = {int(c): c.name for c in SelectContext}


def _pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else None


def _entropy(counter):
    total = sum(counter.values())
    if total == 0:
        return 0.0
    return -sum((n / total) * math.log2(n / total) for n in counter.values() if n)


def analyze(in_dir, out_dir):
    path = os.path.join(in_dir, "strategic_gauntlet_games.jsonl.gz")
    terms, decisions = [], 0
    per_cand_ctx = {}          # cand -> {ctx: count}
    per_cand_ctx_entropy = {}  # cand -> {ctx: Counter(selected_index)}
    per_cand_decisions = {}
    for _ln, _v, rec in read_records(path):
        rt = rec.get("record_type")
        if rt == "game_terminal" and rec.get("phase") == "gauntlet":
            terms.append(rec)
        elif rt == "decision" and rec.get("phase") == "gauntlet":
            decisions += 1
            c = rec.get("candidate_id"); cv = rec.get("select_context")
            per_cand_ctx.setdefault(c, {}).setdefault(cv, 0)
            per_cand_ctx[c][cv] += 1
            per_cand_decisions[c] = per_cand_decisions.get(c, 0) + 1
            sel = rec.get("selected_indices") or []
            key = sel[0] if sel else -1
            per_cand_ctx_entropy.setdefault(c, {}).setdefault(cv, {})
            per_cand_ctx_entropy[c][cv][key] = per_cand_ctx_entropy[c][cv].get(key, 0) + 1

    cands = sorted({rec["seat_candidate_ids"][s] for rec in terms for s in ("0", "1")})
    pair_seat, ordered = {}, {}
    seat0_w = seat0_n = 0
    per_seat = {c: {"s0w": 0, "s0n": 0, "s1w": 0, "s1n": 0} for c in cands}
    reliability = {c: {"invalid_selections": 0, "agent_errors": 0, "timeouts": 0, "games": 0} for c in cands}
    latency = {c: {"latency_ns": [], "calls": 0} for c in cands}
    lengths = []
    pair_wins, pair_games, bt_games = {}, {}, []

    for rec in terms:
        c0, c1 = rec["seat_candidate_ids"]["0"], rec["seat_candidate_ids"]["1"]
        w, wseat = rec.get("winner_candidate"), rec.get("winner_seat")
        draw = w == "draw"
        seat0_n += 1
        if wseat == 0:
            seat0_w += 1
        per_seat[c0]["s0n"] += 1; per_seat[c1]["s1n"] += 1
        if not draw and wseat == 0:
            per_seat[c0]["s0w"] += 1
        if not draw and wseat == 1:
            per_seat[c1]["s1w"] += 1
        o = ordered.setdefault((c0, c1), [0, 0, 0])  # [games, seat0_wins, draws]
        o[0] += 1
        if draw:
            o[2] += 1
        elif wseat == 0:
            o[1] += 1
        a, b = sorted([c0, c1])
        ps = pair_seat.setdefault((a, b), {"a0": [], "a1": []})
        ar = 0.5 if draw else (1.0 if w == a else 0.0)
        ps["a0" if c0 == a else "a1"].append(ar)
        bt_games.append({"a": a, "b": b, "a_result": ar})
        if rec.get("game_length_steps"):
            lengths.append(rec["game_length_steps"])
        for s in ("0", "1"):
            cid = rec["seat_candidate_ids"][s]; rel = rec["reliability"][s]
            reliability[cid]["invalid_selections"] += rel["invalid_selections"]
            reliability[cid]["agent_errors"] += int(rel["agent_error"])
            reliability[cid]["timeouts"] += int(rel["timeout"])
            reliability[cid]["games"] += 1
            latency[cid]["latency_ns"].extend(rec.get("latency_ns_by_seat", {}).get(s, []))
            latency[cid]["calls"] += rec.get("decisions_by_seat", {}).get(s, 0)

    rng = random.Random(24680)
    pairwise = {}
    for (a, b), ps in pair_seat.items():
        lo, hi, point = stratified_bootstrap_ci(ps["a0"], ps["a1"], n_boot=_BOOT, rng=rng)
        a0w, a1w = sum(ps["a0"]), sum(ps["a1"])
        pairwise[f"{a}__vs__{b}"] = {"a": a, "b": b, "games": len(ps["a0"]) + len(ps["a1"]),
                                     "a_seat0": {"games": len(ps["a0"]), "wins": a0w, "wilson": wilson_interval(a0w, len(ps["a0"]))[:2]},
                                     "a_seat1": {"games": len(ps["a1"]), "wins": a1w, "wilson": wilson_interval(a1w, len(ps["a1"]))[:2]},
                                     "seat_balanced_a_rate": point, "ci95_bootstrap": [lo, hi],
                                     "interval_method": "stratified_percentile_bootstrap_2000"}
        pair_wins[(a, b)] = a0w + a1w
        pair_wins[(b, a)] = (len(ps["a0"]) + len(ps["a1"])) - (a0w + a1w)
        pair_games[(a, b)] = len(ps["a0"]) + len(ps["a1"])

    bt = bradley_terry(cands, pair_wins, pair_games, pseudocount=1.0)
    bt_order = sorted(cands, key=lambda c: bt[c], reverse=True)
    boot = bootstrap_ranking(cands, bt_games, n_boot=_BOOT, rng=random.Random(13579), pseudocount=1.0)

    worst = {}
    for c in cands:
        bounds = []
        for (a, b), ps in pair_seat.items():
            if c not in (a, b):
                continue
            if c == a:
                c0l, c1l = ps["a0"], ps["a1"]
            else:
                c0l = [1 - x for x in ps["a1"]]; c1l = [1 - x for x in ps["a0"]]
            lo, hi, point = stratified_bootstrap_ci(c0l, c1l, n_boot=_BOOT, rng=random.Random(hash((c, a, b)) & 0xffffffff))
            bounds.append({"opponent": (b if c == a else a), "balanced_rate": point, "lower_bound_95": lo})
        bounds.sort(key=lambda x: x["lower_bound_95"])
        worst[c] = {"opponents": bounds, "worst": bounds[0] if bounds else None}

    for c in cands:
        L = sorted(x / 1e6 for x in latency[c]["latency_ns"])
        latency[c]["latency_ms"] = {"p50": _pct(L, .5), "p95": _pct(L, .95), "p99": _pct(L, .99),
                                    "max": (L[-1] if L else None), "count": len(L)}
        del latency[c]["latency_ns"]
        reliability[c]["reliability_defects"] = (reliability[c]["invalid_selections"]
                                                 + reliability[c]["agent_errors"] + reliability[c]["timeouts"])
        reliability[c]["eligible"] = reliability[c]["reliability_defects"] == 0

    # context coverage + entropy
    ctx_report = {}
    for c in cands:
        ctxs = per_cand_ctx.get(c, {})
        named = {_NAME.get(k, f"UNKNOWN_{k}"): v for k, v in ctxs.items()}
        high = {n: v for n, v in named.items() if n in _HIGH_IMPACT}
        ent = {}
        for cv, counter in per_cand_ctx_entropy.get(c, {}).items():
            ent[_NAME.get(cv, f"UNKNOWN_{cv}")] = round(_entropy(counter), 4)
        ctx_report[c] = {"context_counts": named, "high_impact_contexts": high,
                         "high_impact_context_count": len(high),
                         "total_decisions": per_cand_decisions.get(c, 0),
                         "action_entropy_by_context": ent,
                         "mean_action_entropy": round(sum(ent.values()) / len(ent), 4) if ent else 0.0}

    os.makedirs(out_dir, exist_ok=True)

    def wj(name, obj):
        json.dump(obj, open(os.path.join(out_dir, name), "w"), indent=2)

    _matrix(os.path.join(out_dir, "strategic_matchup_matrix.csv"), cands, pairwise, ordered, True)
    _matrix(os.path.join(out_dir, "strategic_ordered_matchup_matrix.csv"), cands, pairwise, ordered, False)
    with open(os.path.join(out_dir, "strategic_seat_effects.csv"), "w", newline="") as fh:
        wr = csv.writer(fh); wr.writerow(["candidate", "seat0_winrate", "seat1_winrate", "seat0_games", "seat1_games"])
        for c in cands:
            d = per_seat[c]
            wr.writerow([c, (d["s0w"] / d["s0n"] if d["s0n"] else ""), (d["s1w"] / d["s1n"] if d["s1n"] else ""),
                         d["s0n"], d["s1n"]])
    wj("strategic_pairwise_intervals.json", {"overall_seat0_winrate": (seat0_w / seat0_n if seat0_n else None), "pairs": pairwise})
    wj("strategic_ranking.json", {"strengths": bt, "ranking": bt_order,
                                  "log_strengths": {c: math.log(bt[c]) for c in cands},
                                  "regularization": "symmetric pseudo-count=1.0"})
    wj("strategic_bootstrap.json", {"n_boot": _BOOT, "candidates": boot})
    wj("strategic_worst_matchups.json", worst)
    wj("strategic_reliability.json", {"candidates": reliability})
    wj("strategic_latency.json", {"candidates": latency})
    wj("strategic_context_coverage.json", {"candidates": ctx_report,
       "game_length_steps": {"count": len(lengths), "mean": (sum(lengths) / len(lengths) if lengths else None),
                             "p50": _pct(lengths, .5), "max": (max(lengths) if lengths else None)},
       "total_gauntlet_decisions": decisions})

    print(json.dumps({"gauntlet_games": len(terms), "decisions": decisions, "bt_ranking": bt_order,
                      "eligible": [c for c in cands if reliability[c]["eligible"]],
                      "high_impact_ctx": {c: ctx_report[c]["high_impact_context_count"] for c in cands}}, indent=2))
    return {"bt": bt, "boot": boot, "worst": worst, "latency": latency, "reliability": reliability,
            "ctx": ctx_report, "ranking": bt_order}


def _matrix(path, cands, pairwise, ordered, unordered):
    with open(path, "w", newline="") as fh:
        wr = csv.writer(fh); wr.writerow(["row\\col"] + cands)
        for r in cands:
            row = [r]
            for c in cands:
                if r == c:
                    row.append(""); continue
                if unordered:
                    a, b = sorted([r, c]); p = pairwise.get(f"{a}__vs__{b}")
                    rate = "" if not p else (p["seat_balanced_a_rate"] if a == r else 1 - p["seat_balanced_a_rate"])
                    row.append(f"{rate:.3f}" if rate != "" else "")
                else:
                    o = ordered.get((r, c))
                    row.append(f"{(o[1] + 0.5 * o[2]) / o[0]:.3f}" if o and o[0] else "")
            wr.writerow(row)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--in-dir", required=True)
    p.add_argument("--out-dir", required=True)
    a = p.parse_args(argv)
    analyze(a.in_dir, a.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
