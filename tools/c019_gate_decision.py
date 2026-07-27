"""c019 — evaluate a candidate against the registered DECISION_RULES credibility gate.

Both branches must be judged by the SAME rule, computed the same way, from the same panel
artefact. Writing one branch's verdict by hand and the other's by tool is how two methods end up
being held to two standards, so this reads a `final_panel/<tag>_aggregates.json` and emits the
gate decision for any candidate in it.

Gate (DECISION_RULES.md):
  (a) field score at least +3 points over the frozen baseline, OR
  (b) any single matchup at least +5 points without a field regression worse than -2 points.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C19 = os.path.join(_REPO, "contracts", "c019_dual_method_campaign_ptcg_mcts_and_byterl",
                   "results")
OPPONENTS = ["dragapult", "mega_lucario", "iono", "mega_abomasnow"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel-tag", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--baseline", default="baseline_official_mega_lucario")
    ap.add_argument("--out", required=True, help="path relative to results/")
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)

    agg = json.load(open(os.path.join(C19, "final_panel",
                                      f"{a.panel_tag}_aggregates.json")))
    rows = {r["candidate_id"]: r for r in agg["results"]}
    if a.candidate not in rows or a.baseline not in rows:
        raise SystemExit(f"panel {a.panel_tag} lacks {a.candidate} or {a.baseline}; "
                         f"has {sorted(rows)}")
    c, b = rows[a.candidate], rows[a.baseline]

    delta_field = round(c["field_score"] - b["field_score"], 4)
    per = {o: round(c[f"{o}_rate"] - b[f"{o}_rate"], 4) for o in OPPONENTS}
    clause_a = delta_field >= 0.03
    clause_b = any(v >= 0.05 for v in per.values()) and delta_field >= -0.02
    eligible = bool(clause_a or clause_b)

    out = {
        "rule": f"DECISION_RULES.md -- {a.label or a.candidate} credibility",
        "panel_tag": a.panel_tag,
        "candidate": a.candidate,
        "baseline_field": b["field_score"],
        "candidate_field": c["field_score"],
        "baseline_field_ci": b.get("field_ci"),
        "candidate_field_ci": c.get("field_ci"),
        "delta_field_points": delta_field,
        "per_matchup_delta": per,
        "clause_a_field_plus_3pts": clause_a,
        "clause_b_matchup_plus_5pts_without_2pt_field_regression": clause_b,
        "eligible_for_submission": eligible,
        "games": c["games"] + b["games"],
        "incomplete_games": agg.get("incomplete_games"),
        "latency": {"baseline_max_game_s": b.get("max_game_seconds"),
                    "candidate_max_game_s": c.get("max_game_seconds"),
                    "candidate_mean_search_match_ms": c.get("mean_search_match_ms"),
                    "candidate_max_search_match_ms": c.get("max_search_match_ms")},
        "verdict": (
            f"ELIGIBLE -- {a.candidate} clears the registered gate at "
            f"{delta_field * 100:+.1f} field points over the frozen baseline."
            if eligible else
            f"NOT ELIGIBLE -- {a.candidate} scores {delta_field * 100:+.1f} field points "
            f"against the frozen baseline on {c['games'] + b['games']} identity-safe games "
            f"({agg.get('incomplete_games')} incomplete). The gate requires +3, or +5 on a "
            f"single matchup without a -2 field regression; its best matchup delta is "
            f"{max(per.values()) * 100:+.1f}."),
    }
    p = os.path.join(C19, a.out)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(out, open(p, "w"), indent=2)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
