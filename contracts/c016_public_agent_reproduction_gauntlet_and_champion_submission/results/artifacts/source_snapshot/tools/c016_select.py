"""c016 §18 — apply the pre-registered lexicographic ranking and the competitive gate.

The ranking and every threshold are read from `evaluation_protocol.json`, which was written and
committed before any candidate was scored. Nothing here computes an unregistered composite.

§18's outcome is explicitly allowed to be "no candidate qualifies". §2 and §7 forbid uploading a
weak package merely to complete the contract, so a failing gate produces `PARTIAL` with the best
candidate and the exact failed condition named.
"""

from __future__ import annotations

import json
import math
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C16 = os.path.join(_REPO, "contracts",
                   "c016_public_agent_reproduction_gauntlet_and_champion_submission", "results")
ART = os.path.join(C16, "artifacts")
LOGD = os.path.join(C16, "test_logs")


def jload(p):
    p = p if os.path.isabs(p) else os.path.join(ART, p)
    return json.load(open(p)) if os.path.exists(p) else None


def wilson_lo(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - m) / d


def main():
    proto = jload("evaluation_protocol.json")
    fin = jload("final_gauntlet_results.json") or []
    conf = jload("confirmation_results.json") or {}
    fid = jload("reproduction_fidelity_summary.json") or {}
    screen = jload("screening_results.json") or []
    lat = jload("latency_report.json") or {}
    perms = jload("reuse_permission_matrix.json") or {}

    fid_by = {c["candidate_id"]: c["fidelity"] for c in fid.get("candidates", [])}
    scr_by = {r["candidate_id"]: r for r in screen}
    fin_by = {r["candidate_id"]: r for r in fin}
    conf_by = {r["candidate_id"]: r for r in conf.get("confirmation", [])}
    perm_by = {r["candidate_id"]: r["permission_class"] for r in perms.get("rows", [])}

    base = proto["base_conditions"]
    paths = proto["strength_paths"]
    rows = []
    for cid, f in fin_by.items():
        s = scr_by.get(cid, {})
        c = conf_by.get(cid, {})
        # all safe games: Stage A + the Stage B top-up
        safe_games = (s.get("safe_games") or 0) + (f.get("__safe___games") or 0)
        safe_score = ((s.get("safe_rate") or 0) * (s.get("safe_games") or 0)
                      + (f.get("__safe___rate") or 0) * (f.get("__safe___games") or 0))
        safe_rate = round(safe_score / safe_games, 4) if safe_games else None

        # confirmation numbers drive the ranking; Stage B is the fallback when absent
        d_rate = c.get("confirm_dragapult_rate", f.get("dragapult_rate"))
        d_games = c.get("confirm_dragapult_games", f.get("dragapult_games"))
        fld = c.get("confirm_field_mean", f.get("field_mean"))
        fld_games = c.get("confirm_field_games", 300)

        base_checks = {
            "fidelity_ok": fid_by.get(cid) in base["fidelity_in"],
            "safe_control_ge_0.90": (safe_rate or 0) >= base["safe_control_min"],
            "vs_c014_ge_0.65": (f.get("__c014___rate") or 0) >= base["vs_c014_min"]
            and (f.get("__c014___games") or 0) >= base["vs_c014_min_games"],
            "vs_c015_ge_0.65": (f.get("__c015___rate") or 0) >= base["vs_c015_min"]
            and (f.get("__c015___games") or 0) >= base["vs_c015_min_games"],
            "zero_reliability_violations": (f.get("violations") or 0) == 0
            and (s.get("violations") or 0) == 0,
        }

        # strength paths, each evaluated exactly as registered
        A = paths["A"]
        wlo = c.get("confirm_dragapult_wilson_lo")
        path_a = {
            "vs_dragapult": d_rate, "games": d_games, "wilson_lo": wlo,
            "needs": f">= {A['vs_dragapult_min']} over >= {A['min_games']} games, "
                     f"Wilson LB > {A['wilson_lb_above']}",
            "passes": bool(d_rate is not None and d_rate >= A["vs_dragapult_min"]
                           and (d_games or 0) >= A["min_games"]
                           and wlo is not None and wlo > A["wilson_lb_above"]),
        }
        B = paths["B"]
        ctrl = conf.get("dragapult_control_same_seeds") or {}
        deficits = []
        for opp, key in (("iono", "confirm_iono"), ("mega_lucario", "confirm_mega_lucario"),
                         ("mega_abomasnow", "confirm_mega_abomasnow")):
            mine = c.get(key)
            theirs = (ctrl.get(opp) or {}).get("score_rate")
            if mine is not None and theirs is not None:
                deficits.append({"opponent": opp, "candidate": mine, "dragapult": theirs,
                                 "deficit": round(theirs - mine, 4)})
        n_big_deficit = sum(1 for x in deficits
                            if x["deficit"] > B["max_deficit_vs_dragapult_on_two_opponents"])
        path_b = {
            "vs_dragapult": d_rate, "games": d_games, "field_mean": fld,
            "field_games": fld_games, "deficits": deficits,
            "needs": f">= {B['vs_dragapult_min']} vs Dragapult over >= {B['min_games']}, "
                     f"field mean >= {B['field_mean_min']} over >= {B['field_min_games']}, "
                     f"not worse than {B['max_deficit_vs_dragapult_on_two_opponents']} on two "
                     "official opponents",
            "passes": bool(d_rate is not None and d_rate >= B["vs_dragapult_min"]
                           and (d_games or 0) >= B["min_games"]
                           and fld is not None and fld >= B["field_mean_min"]
                           and (fld_games or 0) >= B["field_min_games"]
                           and n_big_deficit < 2),
        }
        # Path C requires a >=900-equivalent PUBLIC_CLAIM tied to THIS candidate plus an
        # explicit evidence-quality approval. The official samples carry no such published
        # score, so C is not available to them and is recorded as such rather than stretched.
        path_c = {
            "passes": False,
            "reason": "no >=900-equivalent published score or matchup benchmark exists for the "
                      "official sample agents; the LB-950 public claim belongs to a different, "
                      "LOCAL_BENCHMARK_ONLY notebook and cannot be transferred to this "
                      "candidate. Path C is not available rather than stretched to fit.",
        }
        rows.append({
            "candidate_id": cid,
            "fidelity": fid_by.get(cid),
            "permission_class": perm_by.get(cid),
            "safe_games_total": safe_games, "safe_rate_total": safe_rate,
            "stage_b": {k: f.get(k) for k in f if k != "candidate_id"},
            "confirmation": c,
            "base_conditions": base_checks,
            "base_conditions_pass": all(base_checks.values()),
            "path_A": path_a, "path_B": path_b, "path_C": path_c,
            "strength_path_passed": ("A" if path_a["passes"] else
                                     "B" if path_b["passes"] else
                                     "C" if path_c["passes"] else None),
            "p99_latency_ms": s.get("p99_latency_ms"),
        })

    # lexicographic ranking exactly as registered
    cross = conf.get("crossplay") or {}
    top2 = conf.get("top2") or []

    def crossplay_rate(cid):
        if not cross or len(top2) != 2:
            return 0.0
        return cross["score_rate"] if cid == top2[0] else (1 - (cross["score_rate"] or 0))

    def key(r):
        return (
            0 if r["fidelity"] in ("EXACT", "FAITHFUL_CLEAN_ROOM") else 1,
            0 if r["base_conditions"]["zero_reliability_violations"] else 1,
            -(r["confirmation"].get("confirm_dragapult_rate")
              or r["stage_b"].get("dragapult_rate") or 0),
            -(r["confirmation"].get("confirm_field_mean")
              or r["stage_b"].get("field_mean") or 0),
            -crossplay_rate(r["candidate_id"]),
            (r["p99_latency_ms"] or 999),
            0,
        )
    ranked = sorted(rows, key=key)
    qualified = [r for r in ranked
                 if r["base_conditions_pass"] and r["strength_path_passed"]]
    selected = qualified[0] if qualified else None
    best = ranked[0] if ranked else None

    failed = []
    if not selected and best:
        for k, v in best["base_conditions"].items():
            if not v:
                failed.append(f"base condition {k}")
        if not best["strength_path_passed"]:
            failed.append("no strength path passed (A, B, or C)")

    gate = {
        "competitive_gate": "PASS" if selected else "FAIL",
        "selected_candidate_id": selected["candidate_id"] if selected else None,
        "strength_path": selected["strength_path_passed"] if selected else None,
        "best_candidate_id": best["candidate_id"] if best else None,
        "exact_failed_gates": failed,
        "ranking_applied": proto["ranking_lexicographic"],
        "ranked_order": [r["candidate_id"] for r in ranked],
        "upload_authorised": bool(selected),
        "note": "§2/§7 forbid uploading a weak package merely to complete the contract; a "
                "failing competitive gate produces PARTIAL with the best candidate preserved",
    }
    json.dump({"rows": ranked, "gate": gate, "crossplay": cross, "top2": top2},
              open(os.path.join(ART, "selection_decision.json"), "w"), indent=2, default=str)
    json.dump(gate, open(os.path.join(ART, "competitive_gate.json"), "w"), indent=2,
              default=str)

    L = ["# Selection decision and competitive gate (§18)\n",
         f"**competitive_gate = {gate['competitive_gate']}**\n"]
    if selected:
        L.append(f"Selected **`{selected['candidate_id']}`** via strength path "
                 f"**{selected['strength_path_passed']}**.\n")
    else:
        L.append(f"**No candidate qualifies.** Best candidate: `{gate['best_candidate_id']}`. "
                 "No upload is performed — §2 and §7 forbid submitting a weak package merely to "
                 "complete the contract.\n")
        L.append("Exact failed gates:\n")
        for f_ in failed:
            L.append(f"- {f_}")
        L.append("")
    L.append("## Ranking (lexicographic, exactly as pre-registered)\n")
    for i, r in enumerate(proto["ranking_lexicographic"], 1):
        L.append(f"{r}")
    L.append("\n| rank | candidate | fidelity | vs Dragapult (confirm) | field mean | "
             "vs c014 | vs c015 | safe | base | path |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(ranked, 1):
        c = r["confirmation"]
        b = r["stage_b"]
        L.append(f"| {i} | `{r['candidate_id']}` | {r['fidelity']} | "
                 f"{c.get('confirm_dragapult_rate', b.get('dragapult_rate'))} | "
                 f"{c.get('confirm_field_mean', b.get('field_mean'))} | "
                 f"{b.get('__c014___rate')} | {b.get('__c015___rate')} | "
                 f"{r['safe_rate_total']} | "
                 f"{'yes' if r['base_conditions_pass'] else 'NO'} | "
                 f"{r['strength_path_passed'] or '—'} |")
    L.append("\n## Base conditions per candidate\n")
    for r in ranked:
        L.append(f"**`{r['candidate_id']}`** — " + ", ".join(
            f"{k}: {'pass' if v else '**FAIL**'}" for k, v in r["base_conditions"].items()))
        L.append("")
    L.append("## Strength paths\n")
    for r in ranked:
        L.append(f"### `{r['candidate_id']}`\n")
        L.append(f"- **A** ({r['path_A']['needs']}): vs Dragapult "
                 f"{r['path_A']['vs_dragapult']} over {r['path_A']['games']} games, Wilson LB "
                 f"{r['path_A']['wilson_lo']} → **{'PASS' if r['path_A']['passes'] else 'FAIL'}**")
        L.append(f"- **B** ({r['path_B']['needs']}): vs Dragapult "
                 f"{r['path_B']['vs_dragapult']}, field mean {r['path_B']['field_mean']} → "
                 f"**{'PASS' if r['path_B']['passes'] else 'FAIL'}**")
        L.append(f"- **C**: {r['path_C']['reason']} → **FAIL**")
        L.append("")
    if cross:
        L.append(f"## Cross-play\n\n`{top2[0]}` vs `{top2[1]}`: {cross.get('score_rate')} over "
                 f"{cross.get('games')} games (Wilson {cross.get('wilson95')}).\n")
    open(os.path.join(ART, "SELECTION_DECISION.md"), "w").write("\n".join(L) + "\n")
    with open(os.path.join(LOGD, "common_gauntlet.txt"), "a") as fh:
        fh.write("\nSELECTION\n" + json.dumps(gate, indent=2, default=str) + "\n")
    print(json.dumps(gate, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
