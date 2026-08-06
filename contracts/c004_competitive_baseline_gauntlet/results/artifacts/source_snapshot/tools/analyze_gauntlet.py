"""Analyze a captured c004 gauntlet: matchup matrices, seat effects, pairwise
bootstrap intervals, regularized Bradley-Terry + bootstrap ranking, worst
matchups, reliability/latency/fallback, and the deterministic baseline selection.

Reads gauntlet_games.jsonl.gz (game_terminal records, phase=='gauntlet'). The
selection rule (§8) is applied as code, so it is fixed before results are seen.

Usage (from repo root):
  .venv/bin/python tools/analyze_gauntlet.py --in-dir <artifacts> --out-dir <artifacts>
"""

import argparse
import csv
import json
import os
import random
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.episode_compat import read_records
from cg.gauntlet_stats import (
    bootstrap_ranking, bradley_terry, seat_balanced_rate, stratified_bootstrap_ci, wilson_interval,
)

_BOOT = 2000


def _pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else None


def load_terminals(path, phase="gauntlet"):
    terms = []
    for _ln, _v, rec in read_records(path):
        if rec.get("record_type") == "game_terminal" and rec.get("phase") == phase:
            terms.append(rec)
    return terms


def analyze(in_dir, out_dir):
    path = os.path.join(in_dir, "gauntlet_games.jsonl.gz")
    terms = load_terminals(path)
    cands = sorted({rec["seat_candidate_ids"][s] for rec in terms for s in ("0", "1")})

    # ---- collect per-pair (unordered) seat-split results for candidate `a` (min id) ----
    pair_seat = {}          # (a,b) -> {"a0":[], "a1":[]}
    ordered = {}            # (seat0_cand, seat1_cand) -> [games, seat0_wins, draws]
    seat0_wins = seat0_games = 0
    per_cand_seat = {c: {"s0_w": 0, "s0_n": 0, "s1_w": 0, "s1_n": 0} for c in cands}
    reliability = {c: {"invalid_selections": 0, "agent_errors": 0, "timeouts": 0,
                       "env_errors": 0, "games": 0} for c in cands}
    latency = {c: {"latency_ns": [], "calls": 0} for c in cands}
    fallback = {c: {"fallback": 0, "calls": 0} for c in cands}
    bt_games = []

    for rec in terms:
        c0, c1 = rec["seat_candidate_ids"]["0"], rec["seat_candidate_ids"]["1"]
        w = rec.get("winner_candidate")
        wseat = rec.get("winner_seat")
        draw = (w == "draw")
        seat0_games += 1
        if wseat == 0:
            seat0_wins += 1
        # per-candidate seat records
        per_cand_seat[c0]["s0_n"] += 1
        per_cand_seat[c1]["s1_n"] += 1
        if not draw and wseat == 0:
            per_cand_seat[c0]["s0_w"] += 1
        if not draw and wseat == 1:
            per_cand_seat[c1]["s1_w"] += 1
        # ordered matrix
        ok = (c0, c1)
        o = ordered.setdefault(ok, [0, 0, 0])
        o[0] += 1
        if draw:
            o[2] += 1
        elif wseat == 0:
            o[1] += 1
        # unordered pair seat split for a = min
        a, b = sorted([c0, c1])
        ps = pair_seat.setdefault((a, b), {"a0": [], "a1": []})
        a_seat = 0 if c0 == a else 1
        ar = 0.5 if draw else (1.0 if w == a else 0.0)
        ps["a0" if a_seat == 0 else "a1"].append(ar)
        bt_games.append({"a": a, "b": b, "a_result": ar})
        # reliability / latency / fallback from terminal
        for s in ("0", "1"):
            cid = rec["seat_candidate_ids"][s]
            rel = rec["reliability"][s]
            reliability[cid]["invalid_selections"] += rel["invalid_selections"]
            reliability[cid]["agent_errors"] += int(rel["agent_error"])
            reliability[cid]["timeouts"] += int(rel["timeout"])
            reliability[cid]["games"] += 1
            if rec.get("env_exception"):
                reliability[cid]["env_errors"] += 1
            latency[cid]["latency_ns"].extend(rec.get("latency_ns_by_seat", {}).get(s, []))
            latency[cid]["calls"] += rec.get("decisions_by_seat", {}).get(s, 0)
            fallback[cid]["fallback"] += rec.get("fallback_by_seat", {}).get(s, 0)
            fallback[cid]["calls"] += rec.get("decisions_by_seat", {}).get(s, 0)

    # ---- pairwise intervals (stratified bootstrap for balanced; Wilson per seat) ----
    rng = random.Random(1234567)
    pairwise = {}
    pair_wins, pair_games = {}, {}
    for (a, b), ps in pair_seat.items():
        lo, hi, point = stratified_bootstrap_ci(ps["a0"], ps["a1"], n_boot=_BOOT, rng=rng)
        a0w = sum(ps["a0"]); a1w = sum(ps["a1"])
        pairwise[f"{a}__vs__{b}"] = {
            "a": a, "b": b, "games": len(ps["a0"]) + len(ps["a1"]),
            "a_seat0": {"games": len(ps["a0"]), "wins": a0w,
                        "rate": seat_balanced_rate(ps["a0"], []), "wilson": wilson_interval(a0w, len(ps["a0"]))[:2]},
            "a_seat1": {"games": len(ps["a1"]), "wins": a1w,
                        "rate": seat_balanced_rate([], ps["a1"]), "wilson": wilson_interval(a1w, len(ps["a1"]))[:2]},
            "seat_balanced_a_rate": point, "ci95_bootstrap": [lo, hi],
            "interval_method": "stratified_percentile_bootstrap_2000",
        }
        pair_wins[(a, b)] = a0w + a1w
        pair_wins[(b, a)] = (len(ps["a0"]) + len(ps["a1"])) - (a0w + a1w)
        pair_games[(a, b)] = len(ps["a0"]) + len(ps["a1"])

    # ---- Bradley-Terry + bootstrap ranking ----
    bt = bradley_terry(cands, pair_wins, pair_games, pseudocount=1.0)
    bt_order = sorted(cands, key=lambda c: bt[c], reverse=True)
    boot = bootstrap_ranking(cands, bt_games, n_boot=_BOOT, rng=random.Random(987654), pseudocount=1.0)

    # ---- worst matchups (min conservative lower bound of C's balanced rate) ----
    worst = {}
    for c in cands:
        opp_bounds = []
        for (a, b), ps in pair_seat.items():
            if c not in (a, b):
                continue
            if c == a:
                c0, c1 = ps["a0"], ps["a1"]
            else:  # c is b: invert results
                c0 = [1 - x for x in ps["a1"]]  # c as seat0 corresponds to a as seat1
                c1 = [1 - x for x in ps["a0"]]
            lo, hi, point = stratified_bootstrap_ci(c0, c1, n_boot=_BOOT, rng=random.Random(hash((c, a, b)) & 0xffffffff))
            opp = b if c == a else a
            opp_bounds.append({"opponent": opp, "balanced_rate": point, "lower_bound_95": lo,
                               "upper_bound_95": hi})
        opp_bounds.sort(key=lambda x: x["lower_bound_95"])
        worst[c] = {"opponents": opp_bounds, "worst": (opp_bounds[0] if opp_bounds else None)}

    # ---- reliability / latency / fallback reports ----
    for c in cands:
        L = sorted(x / 1e6 for x in latency[c]["latency_ns"])
        latency[c]["latency_ms"] = {"p50": _pct(L, 0.50), "p95": _pct(L, 0.95),
                                    "p99": _pct(L, 0.99), "max": (L[-1] if L else None),
                                    "count": len(L)}
        del latency[c]["latency_ns"]
        reliability[c]["reliability_defects"] = (reliability[c]["invalid_selections"]
                                                 + reliability[c]["agent_errors"] + reliability[c]["timeouts"])
        reliability[c]["eligible"] = reliability[c]["reliability_defects"] == 0
        fallback[c]["fallback_rate"] = (fallback[c]["fallback"] / fallback[c]["calls"]
                                        if fallback[c]["calls"] else 0.0)

    # ---- seat effects ----
    seat_rows = []
    for c in cands:
        d = per_cand_seat[c]
        s0 = d["s0_w"] / d["s0_n"] if d["s0_n"] else None
        s1 = d["s1_w"] / d["s1_n"] if d["s1_n"] else None
        bal = seat_balanced_rate([1] * d["s0_w"] + [0] * (d["s0_n"] - d["s0_w"]) if d["s0_n"] else [],
                                 [1] * d["s1_w"] + [0] * (d["s1_n"] - d["s1_w"]) if d["s1_n"] else [])
        seat_rows.append({"candidate": c, "seat0_winrate": s0, "seat1_winrate": s1, "seat_balanced": bal,
                          "seat0_games": d["s0_n"], "seat1_games": d["s1_n"]})

    # ---- deterministic selection rule (§8), applied as code ----
    decision = select_baselines(cands, bt, worst, latency, reliability, boot)

    # ---- write artifacts ----
    def w(name, obj):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2)

    # matchup matrices (CSV)
    _write_matrix_csv(os.path.join(out_dir, "matchup_matrix.csv"), cands, pairwise, ordered, unordered=True)
    _write_matrix_csv(os.path.join(out_dir, "ordered_matchup_matrix.csv"), cands, pairwise, ordered, unordered=False)
    with open(os.path.join(out_dir, "seat_effects.csv"), "w", newline="", encoding="utf-8") as fh:
        wtr = csv.DictWriter(fh, fieldnames=["candidate", "seat0_winrate", "seat1_winrate",
                                             "seat_balanced", "seat0_games", "seat1_games"])
        wtr.writeheader()
        wtr.writerows(seat_rows)
    w("pairwise_intervals.json", {"overall_seat0_winrate": seat0_wins / seat0_games if seat0_games else None,
                                  "pairs": pairwise})
    w("bradley_terry_ranking.json", {"strengths": bt, "ranking": bt_order,
                                     "log_strengths": {c: __import__("math").log(bt[c]) for c in cands},
                                     "regularization": "symmetric pseudo-count=1.0 per unordered pair"})
    w("bootstrap_ranking.json", {"n_boot": _BOOT, "candidates": boot,
                                 "method": "resample gauntlet games, refit regularized Bradley-Terry"})
    w("worst_matchups.json", worst)
    w("reliability_report.json", {"candidates": reliability})
    w("latency_report.json", {"candidates": latency})
    w("fallback_report.json", {"candidates": fallback})
    w("competitive_decision.json", decision)

    print(json.dumps({"candidates": cands, "gauntlet_games": len(terms),
                      "bt_ranking": bt_order, "primary": decision["primary_baseline"],
                      "backup": decision["backup_baseline"],
                      "eligible": [c for c in cands if reliability[c]["eligible"]]}, indent=2))
    return decision, {"reliability": reliability, "latency": latency, "worst": worst, "bt": bt, "boot": boot}


def select_baselines(cands, bt, worst, latency, reliability, boot):
    eligible = [c for c in cands if reliability[c]["eligible"]]
    status = "ok" if eligible else "no_eligible_candidate"
    ranked = sorted(eligible, key=lambda c: bt[c], reverse=True)

    def worst_lb(c):
        wm = worst[c]["worst"]
        return wm["lower_bound_95"] if wm else 0.0

    def p99(c):
        return latency[c]["latency_ms"]["p99"] or 0.0

    primary = backup = None
    rejections = {}
    tiebreak_used = None
    if ranked:
        top = ranked[0]
        top_lo = boot[top]["strength_ci95"][0]
        # contenders: BT-strength 95% interval overlaps the leader's interval.
        contenders = [c for c in ranked if boot[c]["strength_ci95"][1] >= top_lo]
        if len(contenders) > 1:
            tiebreak_used = "worst_matchup_lower_bound -> p99_latency -> deterministic_simplicity"
            primary = sorted(contenders,
                             key=lambda c: (-worst_lb(c), p99(c), 0 if _is_det(c) else 1, c))[0]
        else:
            primary = top
        remaining = [c for c in ranked if c != primary]
        backup = remaining[0] if remaining else None

    for c in cands:
        if c == primary or c == backup:
            continue
        if not reliability[c]["eligible"]:
            rejections[c] = "REJECTED_RELIABILITY"
        else:
            rejections[c] = "REJECTED_STRENGTH"

    return {
        "status": status,
        "selection_rule": ["highest Bradley-Terry strength",
                           "if top intervals substantially overlap: higher worst-matchup lower bound",
                           "then lower P99 latency", "then simpler/more reproducible (deterministic)"],
        "reliability_gate": {c: reliability[c]["eligible"] for c in cands},
        "bradley_terry_strength": bt,
        "primary_baseline": primary,
        "backup_baseline": backup,
        "tiebreak_used": tiebreak_used,
        "candidate_rankings": ranked,
        "worst_matchup": {c: worst[c]["worst"] for c in cands},
        "p99_latency_ms": {c: latency[c]["latency_ms"]["p99"] for c in cands},
        "rejections": rejections,
    }


def _is_det(c):
    return c.startswith("det_")


def _write_matrix_csv(path, cands, pairwise, ordered, unordered):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        wtr = csv.writer(fh)
        wtr.writerow(["row\\col"] + cands)
        for r in cands:
            row = [r]
            for c in cands:
                if r == c:
                    row.append("")
                    continue
                if unordered:
                    a, b = sorted([r, c])
                    key = f"{a}__vs__{b}"
                    p = pairwise.get(key)
                    if not p:
                        row.append("")
                    else:
                        rate = p["seat_balanced_a_rate"] if a == r else (1 - p["seat_balanced_a_rate"])
                        row.append(f"{rate:.3f}")
                else:  # ordered: r as seat0 vs c as seat1
                    o = ordered.get((r, c))
                    row.append(f"{(o[1] + 0.5 * o[2]) / o[0]:.3f}" if o and o[0] else "")
            wtr.writerow(row)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Analyze c004 gauntlet")
    parser.add_argument("--in-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    analyze(args.in_dir, args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
