"""c007 pre-registration census: measure semantic-context frequency on the existing
c006 sequence dataset (19,050 ordered decisions, 240 games) so the residual-context
candidates and admission targets in EXPERIMENT_REGISTRATION are chosen on measured
frequency x tactical depth, not on narrative appeal.

This is a PRE-registration input (a cheap re-read of stored raw observations, no game
regeneration, no model), legitimately run before AC-02. For each of the eight §11
candidate contexts it counts, over all three c006 splits:
  - total decisions
  - non-forced decisions
  - decisions with >=2 legal options (a raw fork)
  - decisions with >=2 MEANINGFUL choices (non-forced, >=2 options, and for the
    dedicated selection contexts >=2 distinct candidate cards/targets)

Outputs results/artifacts/context_frequency_census.json and a text log. The c006
frequencies are a proxy for the c007 dataset (same teacher/deck/opponents); the
census also reports the implied number of 600-game-scale examples per context.
"""

import argparse
import gzip
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import decision_taxonomy as dt  # noqa: E402

C006_SEQ = os.path.join(_REPO, "contracts", "c006_distilled_policy_baseline",
                        "results", "artifacts", "sequence_dataset")

# §11 candidate residual contexts -> classify() semantic_type
CANDIDATES = {
    "dragapult_damage_counter": "dragapult_damage_counter",
    "promotion_to_active": "promotion_to_active",
    "energy_attachment_target": "energy_attachment_target",
    "search_card_target": "search_card_target",
    "attack_choice_in_MAIN": "attack_choice_in_MAIN",   # attack vs continue setup
    "attack_target": "attack_target",
    "retreat_switch": "retreat_switch",
    "evolution_target": "evolution_target",
}


def _distinct_candidate_cards(opts):
    """Number of distinct referenced (cardId or attackId or option index) targets."""
    keys = set()
    for o in opts:
        k = (o.get("cardId"), o.get("attackId"), o.get("area"), o.get("index"),
             o.get("inPlayArea"), o.get("inPlayIndex"))
        keys.add(k)
    return len(keys)


def census():
    per = {c: {"total": 0, "non_forced": 0, "ge2_options": 0, "ge2_meaningful": 0,
               "by_importance": {}, "multiselect": 0} for c in CANDIDATES}
    totals = {"decisions": 0, "games": set()}
    semantic_counts = {}
    for sp in ("train", "validation", "test"):
        path = os.path.join(C006_SEQ, f"{sp}.jsonl.gz")
        with gzip.open(path, "rt") as fh:
            for line in fh:
                r = json.loads(line)
                totals["decisions"] += 1
                totals["games"].add(r["game_id"])
                info = dt.classify(r)
                sem = info["semantic_type"]
                semantic_counts[sem] = semantic_counts.get(sem, 0) + 1
                # find which candidate (if any) this decision maps to
                cand = None
                for c, target in CANDIDATES.items():
                    if sem == target:
                        cand = c
                        break
                if cand is None:
                    continue
                d = per[cand]
                d["total"] += 1
                opts = r["legal_options"]
                n = len(opts)
                if not info["forced"]:
                    d["non_forced"] += 1
                if n >= 2:
                    d["ge2_options"] += 1
                distinct = _distinct_candidate_cards(opts)
                if (not info["forced"]) and n >= 2 and distinct >= 2:
                    d["ge2_meaningful"] += 1
                if info["is_multiselect"]:
                    d["multiselect"] += 1
                ic = info["importance_class"]
                d["by_importance"][ic] = d["by_importance"].get(ic, 0) + 1

    n_games = len(totals["games"])
    scale = 600.0 / n_games  # proxy scale to a 600-game c007 dataset
    for c, d in per.items():
        d["projected_600_games_meaningful"] = round(d["ge2_meaningful"] * scale, 1)
        d["projected_600_games_total"] = round(d["total"] * scale, 1)

    return {
        "source": "c006 sequence_dataset (all splits)",
        "total_decisions": totals["decisions"],
        "total_games": n_games,
        "projection_scale_to_600_games": round(scale, 4),
        "admission_targets": {"min_examples": 300, "min_two_meaningful": 200},
        "candidates": per,
        "all_semantic_type_counts": dict(sorted(semantic_counts.items(),
                                                 key=lambda kv: -kv[1])),
    }


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", required=True)
    p.add_argument("--log", required=True)
    a = p.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    os.makedirs(os.path.dirname(a.log), exist_ok=True)
    out = census()
    json.dump(out, open(os.path.join(a.out_dir, "context_frequency_census.json"), "w"), indent=2)

    lines = []
    lines.append("c007 residual-context frequency census (proxy = c006 19,050 decisions)")
    lines.append("=" * 78)
    lines.append(f"total decisions {out['total_decisions']} over {out['total_games']} games; "
                 f"scale->600 games x{out['projection_scale_to_600_games']}")
    lines.append(f"admission needs: >=300 examples, >=200 with two meaningful choices\n")
    hdr = f"{'context':30s} {'total':>6s} {'nonforced':>9s} {'>=2opt':>7s} {'>=2mean':>8s} {'proj600m':>9s}"
    lines.append(hdr)
    lines.append("-" * len(hdr))
    ranked = sorted(out["candidates"].items(), key=lambda kv: -kv[1]["ge2_meaningful"])
    for c, d in ranked:
        lines.append(f"{c:30s} {d['total']:6d} {d['non_forced']:9d} {d['ge2_options']:7d} "
                     f"{d['ge2_meaningful']:8d} {d['projected_600_games_meaningful']:9.1f}")
    lines.append("")
    lines.append("Interpretation: contexts whose projected-600-game meaningful count clears 200")
    lines.append("with margin are viable AC-07 candidates; the top few by (frequency x depth)")
    lines.append("are registered as residual-context candidates.")
    txt = "\n".join(lines) + "\n"
    open(a.log, "w").write(txt)
    print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
