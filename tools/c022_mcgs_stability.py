"""c022 probes M09/M10 — action stability and world disagreement on a FROZEN decision set.

`TRAINING_AND_EVALUATION §5` requires "action disagreement and stability on at least 500 frozen
decisions". Game arms cannot supply that: every arm plays its own games, so two arms never face
the same decision twice and "stability" would be confounded with "different position".

This builds a frozen set once — real observations captured from real games, spread through them
rather than taken from their openings — and then replays THE SAME decisions under every K and
several independent world seeds. Everything except K and the world seed is held constant, so a
difference in the chosen action is attributable.

Two distinct quantities, often conflated:

* **Stability (M10)** — given the same decision and the same K, how often do independent world
  draws pick the same action? Low stability at K=1 and high stability at K=8 is the ensemble
  doing exactly what it is for: averaging away the accident of which world was sampled.
* **Disagreement (M09)** — within ONE decision, how much do the K worlds disagree with each
  other before aggregation? This is the raw material stability is made from. If the worlds never
  disagree, K cannot help and the whole correction is inert on this game.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import statistics
import sys
import time
from typing import Any, Dict, List

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C22 = os.path.join(_REPO, "contracts",
                   "c022_mcgs_multideterminization_and_faithful_byterl_reproduction", "results")
OUT = os.path.join(C22, "mcgs", "calibration")


def capture_frozen_set(n_decisions: int, every: int, seed: int, max_games: int):
    """Capture `n_decisions` multi-option observations spread through real games."""
    import torch
    torch.set_num_threads(1)
    from kaggle_environments import make
    from cg import c019_core as K, c019_determinize as D19
    from cg import teachers as T, c009_eval as ce

    deck = D19.archetype_decks()["mega_lucario"]
    opponents = ["dragapult", "mega_lucario", "iono", "mega_abomasnow"]
    captured: List[Dict[str, Any]] = []
    rng = np.random.default_rng(seed)

    for g in range(max_games):
        if len(captured) >= n_decisions:
            break
        seen = [0]
        opp_name = opponents[g % len(opponents)]

        class Probe:
            def __call__(self, obs):
                sel = obs.get("select")
                if sel is None:
                    return list(deck)
                opts = K.canonical_options(sel)
                seen[0] += 1
                if len(opts) > 1 and len(captured) < n_decisions and seen[0] % every == 0:
                    captured.append({"game": g, "opponent": opp_name,
                                     "decision_index": g * 100000 + seen[0],
                                     "n_options": len(opts), "obs": dict(obs)})
                return K.to_select_payload([opts[int(rng.integers(len(opts)))]], sel)

        p = Probe()
        opp = T.make_fresh(opp_name, ce.SOURCES)
        try:
            make("cabt").run([lambda o: p(o), lambda o: opp(o)])
        except Exception:  # noqa: BLE001
            continue
    return deck, captured


def evaluate(deck, frozen, ks, repeats, sims, protocol, base_seed, out_path):
    from cg import api as A
    from cg import c022_mcgs_agent as AG
    from cg import c022_mcgs_multidet as MD

    rows = []
    t0 = time.time()
    fh = open(out_path, "w")
    for di, entry in enumerate(frozen):
        o = A.to_observation_class(entry["obs"])
        rec: Dict[str, Any] = {"decision_index": entry["decision_index"],
                               "n_options": entry["n_options"],
                               "opponent": entry["opponent"], "k": {}}
        for k in ks:
            picks, probs, agreements, distinct = [], [], [], []
            for r in range(repeats):
                cfg = dict(AG.REFERENCE_CFG)
                cfg.update({"k_worlds": k, "budget_protocol": protocol,
                            "simulations_per_decision": sims, "graph_reuse": False,
                            "match_clock_seconds": 0.0, "decision_budget": 10 ** 9})
                rng = np.random.default_rng(base_seed + 7919 * r + k)
                try:
                    agg, trace = MD.multi_determinization_decision(
                        o, deck, cfg, rng,
                        # A DIFFERENT world seed per repeat is the whole point: stability is
                        # "does the choice survive a different draw of worlds?"
                        base_seed=base_seed + 104729 * r,
                        decision_index=entry["decision_index"], k=k,
                        total_simulations=sims, protocol=protocol,
                        deadline=time.monotonic() + 120.0)
                except Exception as e:  # noqa: BLE001
                    rec.setdefault("errors", []).append(f"{type(e).__name__}: {e}"[:120])
                    continue
                a = agg.select(MD.AGG_SOURCE_SUM)
                if a is None:
                    continue
                picks.append(int(a))
                p = agg.predicted_win_probability(a)
                if p is not None:
                    probs.append(float(p))
                d = trace["disagreement"]
                if d["modal_agreement"] is not None:
                    agreements.append(d["modal_agreement"])
                distinct.append(d["distinct_best_actions"])
            if not picks:
                continue
            modal = collections.Counter(picks).most_common(1)[0]
            rec["k"][str(k)] = {
                "repeats": len(picks),
                "picks": picks,
                "distinct_picks": len(set(picks)),
                "stability": round(modal[1] / len(picks), 4),
                "modal_action": modal[0],
                "mean_predicted": round(statistics.fmean(probs), 4) if probs else None,
                "predicted_sd": round(statistics.pstdev(probs), 4) if len(probs) > 1 else None,
                "mean_world_modal_agreement": round(statistics.fmean(agreements), 4)
                if agreements else None,
                "mean_distinct_best_actions_within_a_decision": round(
                    statistics.fmean(distinct), 4) if distinct else None,
            }
        rows.append(rec)
        fh.write(json.dumps(rec) + "\n")
        fh.flush()
        if (di + 1) % 25 == 0:
            print(f"  {di+1}/{len(frozen)} decisions, {time.time()-t0:.0f}s", flush=True)
    fh.close()
    return rows


def summarise(rows, ks) -> Dict[str, Any]:
    out = {"decisions": len(rows), "by_k": {}}
    for k in ks:
        s = [r["k"][str(k)] for r in rows if str(k) in r.get("k", {})]
        if not s:
            continue
        stab = [x["stability"] for x in s]
        sd = [x["predicted_sd"] for x in s if x["predicted_sd"] is not None]
        agree = [x["mean_world_modal_agreement"] for x in s
                 if x["mean_world_modal_agreement"] is not None]
        dis = [x["mean_distinct_best_actions_within_a_decision"] for x in s
               if x["mean_distinct_best_actions_within_a_decision"] is not None]
        out["by_k"][str(k)] = {
            "decisions": len(s),
            "mean_action_stability": round(statistics.fmean(stab), 4),
            "fraction_perfectly_stable": round(
                sum(1 for x in stab if x >= 0.999) / len(stab), 4),
            "mean_predicted_sd_across_repeats": round(statistics.fmean(sd), 4) if sd else None,
            "mean_within_decision_world_agreement": round(statistics.fmean(agree), 4)
            if agree else None,
            "mean_distinct_best_actions_within_a_decision": round(statistics.fmean(dis), 4)
            if dis else None,
        }
    base = out["by_k"].get("1")
    if base:
        for k, v in out["by_k"].items():
            if k == "1":
                continue
            v["stability_delta_vs_k1"] = round(
                v["mean_action_stability"] - base["mean_action_stability"], 4)
            if v["mean_predicted_sd_across_repeats"] is not None \
                    and base["mean_predicted_sd_across_repeats"] is not None:
                v["predicted_sd_delta_vs_k1"] = round(
                    v["mean_predicted_sd_across_repeats"]
                    - base["mean_predicted_sd_across_repeats"], 4)
    out["reading"] = (
        "Stability RISING with K is the ensemble working: the chosen action stops depending on "
        "which hidden world happened to be sampled. Predicted-probability SD FALLING with K is "
        "the same effect in the value estimate. If within-decision world agreement is already "
        "1.0 at K=8, the worlds never disagree on this decision set and K cannot help here -- "
        "that would be a real finding about the game, not a defect in the correction.")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--decisions", type=int, default=500)
    ap.add_argument("--every", type=int, default=7)
    ap.add_argument("--max-games", type=int, default=140)
    ap.add_argument("--ks", default="1,2,4,8")
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--sims", type=int, default=128)
    ap.add_argument("--protocol", default="fixed_total")
    ap.add_argument("--seed", type=int, default=515151)
    ap.add_argument("--out", default=os.path.join(OUT, "stability"))
    a = ap.parse_args(argv)

    import torch
    torch.set_num_threads(1)
    ks = [int(x) for x in a.ks.split(",")]
    os.makedirs(a.out, exist_ok=True)

    t0 = time.time()
    deck, frozen = capture_frozen_set(a.decisions, a.every, a.seed, a.max_games)
    print(f"captured {len(frozen)} frozen decisions in {time.time()-t0:.0f}s", flush=True)
    with open(os.path.join(a.out, "frozen_decision_set.json"), "w") as fh:
        json.dump({"n": len(frozen), "capture_every_nth": a.every, "seed": a.seed,
                   "decisions": [{k: v for k, v in e.items() if k != "obs"} for e in frozen]},
                  fh, indent=2)

    rows = evaluate(deck, frozen, ks, a.repeats, a.sims, a.protocol, a.seed,
                    os.path.join(a.out, "stability_rows.jsonl"))
    summary = summarise(rows, ks)
    summary.update({"protocol": a.protocol, "simulations_per_decision": a.sims,
                    "repeats_per_decision": a.repeats, "ks": ks, "seed": a.seed,
                    "frozen_decisions_requested": a.decisions,
                    "frozen_decisions_captured": len(frozen),
                    "meets_500_decision_minimum": len(frozen) >= 500,
                    "elapsed_s": round(time.time() - t0, 1)})
    with open(os.path.join(a.out, "stability_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    print(json.dumps({"decisions": summary["decisions"],
                      "meets_500_decision_minimum": summary["meets_500_decision_minimum"],
                      "by_k": summary["by_k"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
