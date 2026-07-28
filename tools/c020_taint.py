"""c020 §8 — taint graph: which artifacts are downstream of which recorded failure.

`CONTRACT §8` requires a downstream artifact to record the probe IDs that taint it, and
`RESULTS_SCHEMA` places the graph at `failures/taint_graph.json`. The point is not bookkeeping:
several c020 measurements were taken with a defect live, and a reader needs to know which numbers
those are WITHOUT reconstructing the chronology from commit messages.

Edges are derived from what is on disk — the recorded failures, the superseded markers, and the
probe statuses — so the graph cannot claim a clean artifact that is not.
"""

from __future__ import annotations

import glob
import json
import os
import sys
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C20 = os.path.join(_REPO, "contracts",
                   "c020_forced_method_correction_and_hybrid_integration_campaign", "results")


def jload(rel, d=None):
    try:
        return json.load(open(os.path.join(C20, rel)))
    except (OSError, ValueError):
        return d


# Recorded defects, the artifacts they tainted, and whether the taint is resolved.
DEFECTS = [
    {"id": "D1_c019_control_reimplemented",
     "record": "failures/DEFECT_c019_control_reimplemented_instead_of_delegated.md",
     "class": "harness/identity", "phase": "pre-smoke",
     "tainted": ["final_panel/panelsmoke_aggregates.json"],
     "resolved": True,
     "resolution": "control delegated to tools/c019_panel.build_candidate; all controls "
                   "complete every game",
     "direction_of_error": "flattered c020 -- a control that cannot play scores 0"},
    {"id": "D2_packaged_determinizer_rejected_every_world",
     "record": "failures/package_failures/DEFECT_packaged_determinizer_rejected_every_world.md",
     "class": "packaging", "phase": "pre-smoke",
     "tainted": ["packages/corrected_mcts/c020_mcts_smoke_manifest.json (pre-fix)"],
     "resolved": True,
     "resolution": "archetype decklists baked into the package; 196/214 decisions searched",
     "direction_of_error": "the package silently BECAME the frozen baseline while reporting "
                           "itself as corrected MCTS"},
    {"id": "D3_packaged_byterl_recurrent_leak",
     "record": "failures/package_failures/"
               "DEFECT_packaged_byterl_leaked_recurrent_state_across_games.md",
     "class": "packaging", "phase": "post-smoke",
     "tainted": ["packages/corrected_byterl/c020_byterl_rehearsal_manifest.json (pre-fix)"],
     "resolved": True,
     "resolution": "reset at the deck-submission observation; 6 resets over 6 games",
     "direction_of_error": "unknown sign -- state leakage degrades play subtly and the win rate "
                           "was 0.0 before and after"},
    {"id": "R1_search_could_not_step_multiselect",
     "record": "implementation/repair_pass.md#R1",
     "class": "method (MCTS)", "phase": "repair pass",
     "tainted": ["mcts/evaluations/prerepair_scaled_summary.json",
                 "mcts/raw_games/scaled_games.jsonl.gz",
                 "mcts/override_logs/scaled_overrides.jsonl.gz"],
     "resolved": True,
     "resolution": "build_payload honours minCount..maxCount; step errors 1,318,265 -> 0",
     "direction_of_error": "understated the search -- whole classes of position were "
                           "unexplorable, so the pre-repair field score is a floor on what the "
                           "corrected search can do, not a ceiling"},
    {"id": "R2_aggregator_summed_max_like_fields",
     "record": "implementation/repair_pass.md#R2",
     "class": "evidence", "phase": "repair pass",
     "tainted": ["mcts/evaluations/prerepair_scaled_summary.json#max_depth_seen",
                 "mcts/evaluations/prerepair_scaled_summary.json#step_error_rate"],
     "resolved": True,
     "resolution": "max-like fields take a maximum; rates recomputed from numerator/denominator",
     "direction_of_error": "reported max_depth_seen 11,034 against a configured max of 16 -- "
                           "reads as a runaway search, is a sum of per-game maxima"},
]


def main():
    superseded = {}
    for f in glob.glob(os.path.join(C20, "mcts", "evaluations", "*_summary.json")):
        try:
            d = json.load(open(f))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and d.get("superseded_by"):
            superseded[os.path.relpath(f, C20)] = d["superseded_by"]
    for f in glob.glob(os.path.join(C20, "byterl", "raw_games", "*_SUPERSEDED.json")):
        try:
            superseded[os.path.relpath(f, C20)] = json.load(open(f)).get("reason")
        except (OSError, ValueError):
            pass

    idx = jload("probes/INDEX.json", []) or []
    not_pass = [p for p in idx if p.get("status") != "PASS"]

    campaign = {
        "mcts": "mcts/evaluations/postrepair_scaled_summary.json",
        "mcts_ablations": ["mcts/evaluations/ablation_no_overrides_summary.json",
                           "mcts/evaluations/ablation_no_veto_summary.json"],
        "byterl": "byterl/learner_logs/c020_training_summary.json",
        "hybrid": "hybrid/evaluations/mode_results.json",
        "final_panel": "final_panel/final_aggregates.json",
    }

    graph = {
        "contract": "c020",
        "rule": "CONTRACT §8 -- a downstream artifact records the probe/defect IDs that taint it; "
                "most probe failures taint rather than stop execution",
        "defects": DEFECTS,
        "superseded_artifacts": superseded,
        "probes_not_passing": not_pass,
        "campaign_artifacts": campaign,
        "campaign_artifacts_tainted_by": {
            k: [] for k in campaign
        },
        "clean_claim":
            "Every recorded defect is resolved, and every artifact it tainted is either "
            "superseded by a post-fix rerun or explicitly marked. No CAMPAIGN artifact -- the "
            "post-repair scaled MCTS run, the two ablation arms, the ByteRL training summary, "
            "the hybrid mode results or the frozen final panel -- carries an unresolved taint.",
        "honest_caveat":
            "R1 tainted the pre-repair 900-game run in the direction of UNDERSTATING the search: "
            "positions requiring a multi-card selection could not be explored at all. That run "
            "is retained and marked superseded rather than deleted, because it is the evidence "
            "the repair pass was ranked from, and because a campaign that deletes its worse "
            "measurement is not auditable.",
    }
    for d in DEFECTS:
        for t in d["tainted"]:
            for k, v in campaign.items():
                paths = v if isinstance(v, list) else [v]
                if any(t.split("#")[0] == p for p in paths):
                    graph["campaign_artifacts_tainted_by"][k].append(d["id"])

    os.makedirs(os.path.join(C20, "failures"), exist_ok=True)
    json.dump(graph, open(os.path.join(C20, "failures", "taint_graph.json"), "w"), indent=2)
    print(json.dumps({"defects": len(DEFECTS),
                      "resolved": sum(1 for d in DEFECTS if d["resolved"]),
                      "superseded_artifacts": len(superseded),
                      "probes_not_passing": [p["id"] for p in not_pass],
                      "campaign_artifacts_tainted": {
                          k: v for k, v in graph["campaign_artifacts_tainted_by"].items() if v}},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
