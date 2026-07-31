"""c022 A5 / M05-M09 — calibration, world disagreement, and the K comparison.

`MANDATORY_IMPLEMENTATION A5` requires, for every root decision: sampled-world outcomes, per-world
root action estimates, the aggregate estimate, the selected action, the actual game result, a
predicted-win-probability calibration bin, between-world disagreement, and action stability across
repeated runs. The runner records all of that per decision; this tool aggregates it and computes
the comparisons the probe matrix asks for.

It computes nothing it cannot recompute from raw files. Every number in the report comes from a
`*_calibration.jsonl`, a `*_games.jsonl`, a `*_traces.jsonl` or a `*_summary.json`, so `F03`
("all reported numbers recompute from raw data") is satisfied by construction rather than by a
later audit.

**A5 says the correction is not accepted merely because K>1 executes.** The validity gates below
run first, and an arm that fails one is reported as INVALID rather than as a result:

    equal total simulations across K        (M05, fixed_total only)
    equal simulations per world across K    (M06, fixed_per_world only)
    comparable abandonment across K         -- abandoned games are excluded from the field
                                               score, so a K-dependent abandonment rate makes
                                               the surviving subsample K-dependent too
    budget delivered                        -- an arm that did not run its simulations has not
                                               tested what it claims to test
    zero signature mismatches               -- otherwise action indices are not comparable and
                                               the aggregate summed different actions
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C22 = os.path.join(_REPO, "contracts",
                   "c022_mcgs_multideterminization_and_faithful_byterl_reproduction", "results")
MC = os.path.join(C22, "mcgs")

CALIBRATION_BINS = [(0.0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.4), (0.4, 0.5),
                    (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0001)]


def wilson(k: float, n: int, z: float = 1.96):
    if n <= 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def read_jsonl(path: str) -> List[Dict[str, Any]]:
    if not os.path.isfile(path):
        return []
    out = []
    with open(path) as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except Exception:  # noqa: BLE001
                    continue
    return out


def load_arm(directory: str, tag: str) -> Optional[Dict[str, Any]]:
    sp = os.path.join(directory, f"{tag}_summary.json")
    if not os.path.isfile(sp):
        return None
    with open(sp) as fh:
        summary = json.load(fh)
    return {
        "tag": tag, "dir": os.path.relpath(directory, _REPO), "summary": summary,
        "calibration": read_jsonl(os.path.join(directory, f"{tag}_calibration.jsonl")),
        "games": read_jsonl(os.path.join(directory, f"{tag}_games.jsonl")),
        "traces": read_jsonl(os.path.join(directory, f"{tag}_traces.jsonl")),
    }


# ============================================================================ calibration
def calibration(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Brier, log-loss and a reliability table over (predicted, realised) pairs.

    Only decisions from COMPLETED games contribute: a decision whose game was abandoned has no
    realised outcome, and scoring it as a loss would make every arm look better the more games
    it abandoned.
    """
    pairs = [(float(r["predicted_win_probability"]), float(r["realised"]))
             for r in rows
             if r.get("predicted_win_probability") is not None and r.get("realised") is not None]
    if not pairs:
        return {"n": 0}
    brier = statistics.fmean((p - y) ** 2 for p, y in pairs)
    eps = 1e-9
    logloss = -statistics.fmean(
        y * math.log(max(p, eps)) + (1 - y) * math.log(max(1 - p, eps)) for p, y in pairs)
    base = statistics.fmean(y for _p, y in pairs)
    # The reference every calibration claim needs: a CONSTANT predictor at the observed base
    # rate. A model whose Brier score is no better than this has learned nothing about which
    # decisions are good, however confident it sounds.
    brier_const = statistics.fmean((base - y) ** 2 for _p, y in pairs)
    logloss_const = -statistics.fmean(
        y * math.log(max(base, eps)) + (1 - y) * math.log(max(1 - base, eps)) for _p, y in pairs)

    table = []
    for lo, hi in CALIBRATION_BINS:
        sel = [(p, y) for p, y in pairs if lo <= p < hi]
        if not sel:
            table.append({"bin": f"[{lo:.1f},{min(hi,1.0):.1f})", "n": 0})
            continue
        mp = statistics.fmean(p for p, _ in sel)
        my = statistics.fmean(y for _, y in sel)
        table.append({"bin": f"[{lo:.1f},{min(hi,1.0):.1f})", "n": len(sel),
                      "mean_predicted": round(mp, 4), "observed": round(my, 4),
                      "gap_pp": round(100 * (mp - my), 1),
                      "observed_wilson95": wilson(sum(y for _, y in sel), len(sel))})
    # Expected calibration error: bin-count-weighted mean |predicted - observed|.
    ece = sum(b["n"] * abs(b["mean_predicted"] - b["observed"])
              for b in table if b["n"]) / len(pairs)
    return {
        "n": len(pairs),
        "mean_predicted": round(statistics.fmean(p for p, _ in pairs), 4),
        "observed_base_rate": round(base, 4),
        "overconfidence_pp": round(100 * (statistics.fmean(p for p, _ in pairs) - base), 1),
        "brier": round(brier, 5),
        "brier_constant_baseline": round(brier_const, 5),
        "brier_skill_vs_constant": round(1 - brier / brier_const, 4) if brier_const > 0 else None,
        "log_loss": round(logloss, 5),
        "log_loss_constant_baseline": round(logloss_const, 5),
        "expected_calibration_error": round(ece, 4),
        "reliability": table,
    }


def disagreement(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """M09 — between-world disagreement, from the per-decision records."""
    ma = [r["modal_agreement"] for r in rows if r.get("modal_agreement") is not None]
    db = [r["distinct_best_actions"] for r in rows if r.get("distinct_best_actions") is not None]
    sd = [r["selected_value_sd"] for r in rows if r.get("selected_value_sd") is not None]
    multi = [r for r in rows if int(r.get("k") or 1) > 1]
    return {
        "decisions": len(rows),
        "decisions_with_k_gt_1": len(multi),
        "mean_modal_agreement": round(statistics.fmean(ma), 4) if ma else None,
        "unanimous_fraction": round(sum(1 for x in db if x == 1) / len(db), 4) if db else None,
        "mean_distinct_best_actions": round(statistics.fmean(db), 4) if db else None,
        "max_distinct_best_actions": max(db) if db else None,
        "mean_selected_value_sd": round(statistics.fmean(sd), 4) if sd else None,
        "n_with_sd": len(sd),
    }


def starvation(arm: Dict[str, Any]) -> Dict[str, Any]:
    """Per-world starvation, so a fixed-total K=8 result is attributable.

    Under fixed_total, K=8 gives each world one eighth of the simulations. If K=8 is worse, that
    could be world diversity failing to help OR each world being too starved to search at all.
    Per-world simulations and expanded actions separate the two.
    """
    # SAMPLE SIZE CAVEAT: the agent caps its trace buffer and the runner keeps only the first
    # two traces per game, so this is a sample of roughly 2 x games decisions -- about 120 at 60
    # games, out of thousands. It is a diagnostic that distinguishes "world diversity did not
    # help" from "each world was too starved to search", not a census of the arm's per-world
    # behaviour, and the report says so.
    sims, expanded, edges = [], [], []
    for t in arm["traces"]:
        for ws in t.get("world_stats", []):
            sims.append(ws.get("simulations", 0))
            expanded.append(ws.get("expanded_actions", 0))
            edges.append(ws.get("root_edges", 0))
    if not sims:
        return {"n_world_records": 0}
    return {
        "n_world_records": len(sims),
        "sampled_from_traces_per_game": 2,
        "is_a_sample_not_a_census": True,
        "mean_simulations_per_world": round(statistics.fmean(sims), 2),
        "min_simulations_per_world": min(sims),
        "mean_expanded_actions_per_world": round(statistics.fmean(expanded), 2),
        "mean_root_edges_per_world": round(statistics.fmean(edges), 2),
        "fraction_of_worlds_expanding_le_1_action": round(
            sum(1 for x in expanded if x <= 1) / len(expanded), 4),
    }


def validity(arms: List[Dict[str, Any]], protocol: str) -> Dict[str, Any]:
    """Gates that must hold before any K comparison means anything."""
    if not arms:
        return {"valid": False, "reasons": ["no arms"]}
    reasons = []
    totals = {a["tag"]: a["summary"].get("total_simulations") for a in arms}
    per_dec = {a["tag"]: a["summary"].get("sims_per_decision") for a in arms}
    if protocol == "fixed_total":
        vals = [v for v in per_dec.values() if v is not None]
        if vals and (max(vals) - min(vals)) > 1.0:
            reasons.append(
                f"M05 FAILED: fixed_total arms must use equal simulations per decision, got "
                f"{per_dec}")
    else:
        # per world = total / K must be constant
        pw = {}
        for a in arms:
            k = a["summary"]["config"]["k_worlds"]
            s = a["summary"].get("sims_per_decision")
            pw[a["tag"]] = round(s / k, 2) if s else None
        vals = [v for v in pw.values() if v is not None]
        if vals and (max(vals) - min(vals)) > 1.0:
            reasons.append(
                f"M06 FAILED: fixed_per_world arms must give each world equal simulations, got "
                f"{pw}")

    # Every game that does not produce a score is excluded from the field score, whatever the
    # reason -- abandoned on the wall-clock guard, errored, or finished without both seats DONE.
    # It is the TOTAL exclusion rate that must be comparable across K, not just abandonment:
    # an arm excluding 30% of its games has a field score computed on a different population
    # from one excluding 5%.
    ab = {a["tag"]: (a["summary"].get("abandoned", 0) + a["summary"].get("unscored", 0)
                     + a["summary"].get("errored", 0),
                     a["summary"].get("games", 0))
          for a in arms}
    rates = {t: (n / g if g else 0.0) for t, (n, g) in ab.items()}
    # 8 points, not 15. results/hardware/contention_tests.json measured a 6.7-point exclusion
    # difference moving a field score by 10 points, so a 15-point gate would admit a spread
    # capable of moving a score by more than any K effect this contract could detect.
    if rates and (max(rates.values()) - min(rates.values())) > 0.08:
        reasons.append(
            f"EXCLUSION SPREAD > 8pp across K: {({t: round(r,3) for t,r in rates.items()})}. "
            "Excluded games (abandoned, errored, or finished without both seats DONE) do not "
            "enter the field score, so the surviving subsample is K-dependent and the "
            "comparison is confounded. Reported as INVALID_BY_EXCLUSION per "
            "results/hardware/contention_tests.json; the protocol is re-run with a decision "
            "budget lowered UNIFORMLY across its arms.")
    for a in arms:
        s = a["summary"]
        if not s.get("budget_delivered", True):
            reasons.append(f"{a['tag']}: budget NOT delivered "
                           f"(decision_deadline_stops={s.get('decision_deadline_stops')})")
        if s.get("signature_mismatches"):
            reasons.append(f"{a['tag']}: {s['signature_mismatches']} option-signature mismatches "
                           "-- action indices are not comparable across worlds")
        # opponent_flag_conflicts is NOT a validity failure. D16 established that in PTCG an
        # action's resolution can depend on hidden information, so the same action can end the
        # turn in one sampled world and not in another -- with the option signature matching,
        # i.e. with the indices perfectly aligned. The aggregate handles it by converting each
        # world's contribution to the root player's frame before summing. The count is reported
        # because it quantifies how often that adapter does real work, and because a rise
        # UNACCOMPANIED by a signature mismatch would still be worth explaining.
        if s.get("mixed_terminal_scale_decisions"):
            reasons.append(f"{a['tag']}: {s['mixed_terminal_scale_decisions']} decisions reached "
                           "a terminal leaf, mixing the +/-10 scale into the aggregate")
        if s.get("world_errors"):
            reasons.append(f"{a['tag']}: {s['world_errors']} world errors")
    return {"valid": not reasons, "reasons": reasons,
            "exclusion_rate": {t: round(r, 4) for t, r in rates.items()},
            "total_simulations": totals, "sims_per_decision": per_dec}


def analyse_protocol(directory: str, tags: List[str], protocol: str) -> Dict[str, Any]:
    arms = [a for a in (load_arm(directory, t) for t in tags) if a]
    out = {"protocol": protocol, "dir": os.path.relpath(directory, _REPO),
           "arms_found": [a["tag"] for a in arms],
           "arms_missing": [t for t in tags if not any(a["tag"] == t for a in arms)],
           "validity": validity(arms, protocol), "arms": {}}
    for a in arms:
        s = a["summary"]
        out["arms"][a["tag"]] = {
            "k": s["config"]["k_worlds"],
            "games": s.get("games"), "completed": s.get("completed"),
            "abandoned": s.get("abandoned"), "unscored": s.get("unscored"),
            "errored": s.get("errored"),
            "excluded_fraction": s.get("excluded_fraction"),
            "all_games_accounted": s.get("all_games_accounted"),
            "field_score": s.get("field_score"), "wilson95": s.get("wilson95"),
            "field_score_bounds_if_unscored_counted": s.get(
                "field_score_bounds_if_unscored_counted"),
            "sims_per_decision": s.get("sims_per_decision"),
            "opponent_flag_conflicts": s.get("opponent_flag_conflicts"),
            "searched_decisions": s.get("searched_decisions"),
            "decision_budget_exhausted_decisions": s.get(
                "decision_budget_exhausted_decisions"),
            "wall_clock_s": s.get("wall_clock_s"),
            "term_root_win": s.get("term_root_win"),
            "term_root_loss": s.get("term_root_loss"),
            "term_undecided": s.get("term_undecided"),
            "predicted_over_decided": round(
                s["term_root_win"] / (s["term_root_win"] + s["term_root_loss"]), 4)
            if (s.get("term_root_win") is not None and
                (s.get("term_root_win", 0) + s.get("term_root_loss", 0)) > 0) else None,
            "calibration": calibration(a["calibration"]),
            "disagreement": disagreement(a["calibration"]),
            "starvation": starvation(a),
        }
    # K comparison against the arm's own K=1 control
    k1 = next((t for t in out["arms"] if out["arms"][t]["k"] == 1), None)
    if k1:
        base = out["arms"][k1]
        for t, row in out["arms"].items():
            if t == k1:
                continue
            row["vs_k1"] = {
                "field_score_delta_pp": round(
                    100 * (row["field_score"] - base["field_score"]), 2)
                if (row["field_score"] is not None and base["field_score"] is not None) else None,
                "intervals_overlap": (
                    None if not (row["wilson95"] and base["wilson95"]
                                 and row["wilson95"][0] is not None
                                 and base["wilson95"][0] is not None)
                    else not (row["wilson95"][0] > base["wilson95"][1]
                              or base["wilson95"][0] > row["wilson95"][1])),
                "brier_delta": round(
                    row["calibration"]["brier"] - base["calibration"]["brier"], 5)
                if (row["calibration"].get("brier") is not None
                    and base["calibration"].get("brier") is not None) else None,
                "log_loss_delta": round(
                    row["calibration"]["log_loss"] - base["calibration"]["log_loss"], 5)
                if (row["calibration"].get("log_loss") is not None
                    and base["calibration"].get("log_loss") is not None) else None,
                "overconfidence_delta_pp": round(
                    row["calibration"]["overconfidence_pp"]
                    - base["calibration"]["overconfidence_pp"], 2)
                if (row["calibration"].get("overconfidence_pp") is not None
                    and base["calibration"].get("overconfidence_pp") is not None) else None,
            }
    out["k1_control_tag"] = k1
    return out


def render(report: Dict[str, Any]) -> str:
    L = []
    A = L.append
    A("# MCGS multi-determinization: calibration and the K comparison")
    A("")
    A("Generated by `tools/c022_mcgs_analyze.py` from raw per-decision and per-game records. "
      "Every number recomputes from `*_calibration.jsonl`, `*_games.jsonl`, `*_traces.jsonl` and "
      "`*_summary.json`.")
    A("")
    A("`MANDATORY_IMPLEMENTATION A5`: \"The correction is not accepted merely because K>1 "
      "executes.\" The validity gates run first; an arm that fails one is not a result.")
    A("")

    for key in ("fixed_total", "fixed_per_world"):
        p = report.get(key)
        if not p:
            continue
        A(f"## {key}")
        A("")
        v = p["validity"]
        A(f"**Validity: {'PASS' if v['valid'] else 'FAILED'}**")
        if v["reasons"]:
            A("")
            for r in v["reasons"]:
                A(f"- {r}")
        A("")
        if p["arms_missing"]:
            A(f"Arms not present: `{'`, `'.join(p['arms_missing'])}`")
            A("")
        A("| arm | K | games | scored | aband | unscored | excl. | field | 95% CI | "
          "bounds if counted | sims/dec | Brier | log-loss | mean pred | observed | over (pp) |")
        A("|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|")
        for t, r in sorted(p["arms"].items(), key=lambda kv: kv[1]["k"]):
            c = r["calibration"]
            A(f"| `{t}` | {r['k']} | {r['games']} | {r['completed']} | {r['abandoned']} | "
              f"{r.get('unscored')} | {r.get('excluded_fraction')} | "
              f"{r['field_score']} | {r['wilson95']} | "
              f"{r.get('field_score_bounds_if_unscored_counted')} | "
              f"{r['sims_per_decision']} | "
              f"{c.get('brier')} | {c.get('log_loss')} | {c.get('mean_predicted')} | "
              f"{c.get('observed_base_rate')} | {c.get('overconfidence_pp')} |")
        A("")
        A("### Against the K=1 control")
        A("")
        A("| arm | Δfield (pp) | CIs overlap | ΔBrier | Δlog-loss | Δoverconfidence (pp) |")
        A("|---|---:|---|---:|---:|---:|")
        for t, r in sorted(p["arms"].items(), key=lambda kv: kv[1]["k"]):
            d = r.get("vs_k1")
            if not d:
                continue
            A(f"| `{t}` | {d['field_score_delta_pp']} | {d['intervals_overlap']} | "
              f"{d['brier_delta']} | {d['log_loss_delta']} | {d['overconfidence_delta_pp']} |")
        A("")
        A("A **negative** ΔBrier and Δlog-loss means K>1 is better calibrated than K=1, which is "
          "M08's pass condition. Field-score deltas at these game counts are shortlist evidence "
          "only — `TRAINING_AND_EVALUATION §5` requires at least 200 paired games before "
          "claiming a six-point effect.")
        A("")
        A("### World disagreement (M09) and per-world starvation")
        A("")
        A("| arm | K | modal agreement | unanimous | mean distinct best | sel. value sd | "
          "sims/world | worlds expanding ≤1 action |")
        A("|---|---:|---:|---:|---:|---:|---:|---:|")
        for t, r in sorted(p["arms"].items(), key=lambda kv: kv[1]["k"]):
            g, s = r["disagreement"], r["starvation"]
            A(f"| `{t}` | {r['k']} | {g['mean_modal_agreement']} | {g['unanimous_fraction']} | "
              f"{g['mean_distinct_best_actions']} | {g['mean_selected_value_sd']} | "
              f"{s.get('mean_simulations_per_world')} | "
              f"{s.get('fraction_of_worlds_expanding_le_1_action')} |")
        A("")
        A("Starvation matters for attribution. Under `fixed_total` a K=8 arm gives each world one "
          "eighth of the simulations, so a worse result could be world diversity failing to help "
          "OR each world being too starved to search. The last two columns separate them.")
        A("")
        n_world = {t: r["starvation"].get("n_world_records")
                   for t, r in p["arms"].items()}
        A(f"**These two columns are a SAMPLE, not a census.** The runner keeps two traces per "
          f"game, so the per-world records number {n_world} out of many thousands of decisions "
          "per arm. They are sufficient to tell starvation from diversity — a starved world "
          "expands one action whatever decision it faces — and are not a per-world profile of "
          "the arm.")
        A("")

    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-json", default=os.path.join(MC, "calibration",
                                                       "k_comparison.json"))
    ap.add_argument("--out-md", default=os.path.join(MC, "calibration",
                                                     "K_COMPARISON.md"))
    a = ap.parse_args(argv)

    report = {
        "fixed_total": analyse_protocol(
            os.path.join(MC, "fixed_total_simulations"),
            ["ft_k1", "ft_k2", "ft_k4", "ft_k8"], "fixed_total"),
        "fixed_per_world": analyse_protocol(
            os.path.join(MC, "fixed_simulations_per_world"),
            ["fpw_k1", "fpw_k2", "fpw_k4", "fpw_k8"], "fixed_per_world"),
    }
    m04 = load_arm(os.path.join(MC, "k1_control"), "m04_k1_reuse")
    if m04:
        report["m04_identity"] = {
            "summary": m04["summary"],
            "calibration": calibration(m04["calibration"]),
        }
    for p in (a.out_json, a.out_md):
        os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(a.out_json, "w") as fh:
        json.dump(report, fh, indent=2)
    with open(a.out_md, "w") as fh:
        fh.write(render(report))
    for key in ("fixed_total", "fixed_per_world"):
        p = report[key]
        print(f"{key}: arms={p['arms_found']} missing={p['arms_missing']} "
              f"valid={p['validity']['valid']}")
        for r in p["validity"]["reasons"]:
            print(f"   ! {r}")
    print(f"wrote {a.out_json}\nwrote {a.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
