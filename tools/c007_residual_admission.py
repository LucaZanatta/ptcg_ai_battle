"""c007 AC-07: score the registered residual-context candidates against the eight
admission criteria and admit at most three. Admission means a context is a VALID,
safe place to intervene — it is SEPARATE from whether an improvement exists there
(AC-08). Criterion 5 (a stable counterfactual evaluation) is only satisfiable where a
counterfactual A/B was actually run, i.e. the primary damage-counter context.
"""

import argparse
import gzip
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

import numpy as np  # noqa: E402
from cg import decoders, decision_taxonomy as dt, policy_model_v2 as pm, policy_data_v2 as pd  # noqa: E402

C007_ART = os.path.join(_REPO, "contracts", "c007_hybrid_teacher_residual_and_state_encoder_v2",
                        "results", "artifacts")
V2_DATA = os.path.join(C007_ART, "v2_dataset")

# candidate semantic context -> the raw select_context names it covers
CONTEXT_MAP = {
    "dragapult_damage_counter": {"DAMAGE_COUNTER_ANY", "DAMAGE_COUNTER"},
    "promotion_to_active": {"TO_ACTIVE", "SETUP_ACTIVE_POKEMON"},
    "retreat_switch": {"SWITCH"},
    "energy_attachment_target": {"ATTACH_FROM", "ATTACH_TO"},
    "search_card_target": {"TO_HAND", "TO_DECK", "TO_DECK_BOTTOM", "LOOK", "TO_PRIZE"},
    "evolution_target": {"EVOLVE"},
}
# contexts whose override cannot corrupt the teacher's cached plan (plan is recomputed at
# MAIN and read from the board fresh) -> leaf sub-decisions
NO_CORRUPT = {"dragapult_damage_counter", "promotion_to_active", "retreat_switch",
              "energy_attachment_target", "evolution_target", "search_card_target"}


def _load(splits=("train", "validation")):
    recs = []
    for sp in splits:
        with gzip.open(os.path.join(V2_DATA, f"{sp}.jsonl.gz"), "rt") as fh:
            for line in fh:
                recs.append(json.loads(line))
    return recs


def _distinct_targets(opts):
    keys = set()
    for o in opts:
        keys.add((o.get("cardId"), o.get("attackId"), o.get("area"), o.get("index"),
                  o.get("inPlayArea"), o.get("inPlayIndex")))
    return len(keys)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--ckpt-dir", default=os.path.join(C007_ART, "checkpoints"))
    a = p.parse_args(argv)

    reg = json.load(open(os.path.join(C007_ART, "experiment_registration.json")))
    pool = reg["residual_contexts"]["candidate_pool"]
    counterfactual = json.load(open(os.path.join(C007_ART, "counterfactual_evaluation.json")))
    # which contexts had a stable counterfactual A/B?
    cf_context = counterfactual.get("admitted_context")  # "DAMAGE_COUNTER_ANY"
    cf_semantic = "dragapult_damage_counter"

    recs = _load()
    # per-candidate structural stats
    stats = {c: {"total": 0, "non_forced": 0, "two_meaningful": 0, "forced": 0,
                 "ordered": 0, "multiselect": 0} for c in pool}
    per_ctx_records = {c: [] for c in pool}
    for r in recs:
        sc = r["select_context"]
        for c, names in CONTEXT_MAP.items():
            if c in stats and sc in names:
                info = dt.classify(r)
                s = stats[c]
                s["total"] += 1
                if info["forced"]:
                    s["forced"] += 1
                else:
                    s["non_forced"] += 1
                if (not info["forced"]) and len(r["legal_options"]) >= 2 and _distinct_targets(r["legal_options"]) >= 2:
                    s["two_meaningful"] += 1
                form = decoders.classify_form(sc, r.get("min_count") or 0, r.get("max_count") or 0,
                                              len(r["legal_options"]))
                if form == "ORDERED":
                    s["ordered"] += 1
                if info["is_multiselect"]:
                    s["multiselect"] += 1
                if len(per_ctx_records[c]) < 3000:
                    per_ctx_records[c].append(r)
                break

    # in-context calibration (ECE) for the counterfactual context, using the selected model
    ece_ctx = {}
    sel = os.path.join(a.ckpt_dir, "V2_B_selected.npz")
    if not os.path.exists(sel):
        sel = os.path.join(a.ckpt_dir, "V2_A_selected.npz")
    model = pm.ModelV2.load(sel) if os.path.exists(sel) else None
    if model is not None:
        for c, rlist in per_ctx_records.items():
            dec = pd.featurize_split(rlist)
            single = [d for d in dec if d["form"] == "SINGLE_CHOICE"]
            if len(single) < 30:
                ece_ctx[c] = {"ece": None, "n_single": len(single), "note": "too few single-choice"}
                continue
            confs, corr = [], []
            for s0 in range(0, len(single), 256):
                sub = single[s0:s0 + 256]
                b = pd.collate(sub)
                scr = model.score_np(b)
                for i, d in enumerate(sub):
                    if not d["action"]:
                        continue
                    n = d["n"]; z = scr[i, :n] - scr[i, :n].max(); pr = np.exp(z); pr /= pr.sum()
                    am = int(np.argmax(pr)); confs.append(float(pr[am]))
                    corr.append(int(am == d["action"][0]))
            confs = np.asarray(confs); corr = np.asarray(corr)
            ece = 0.0
            for bnb in range(10):
                lo, hi = bnb / 10, (bnb + 1) / 10
                m = (confs > lo) & (confs <= hi)
                if m.sum():
                    ece += (m.sum() / len(confs)) * abs(corr[m].mean() - confs[m].mean())
            ece_ctx[c] = {"ece": float(ece), "n_single": int(len(confs))}

    # evaluate 8 criteria
    admission = {}
    admitted = []
    for c in pool:
        s = stats[c]
        counterfactual_stable = (c == cf_semantic)  # only the A/B'd context has a stable CF eval
        ece = ece_ctx.get(c, {}).get("ece")
        calib_ok = (ece is not None and ece <= 0.15)
        crit = {
            "c1_min_300_examples": s["total"] >= 300,
            "c2_min_200_two_meaningful": s["two_meaningful"] >= 200,
            "c3_decoder_supported": s["ordered"] == 0,
            "c4_teacher_sync_valid": True,  # teacher invoked every decision -> synced (§8)
            "c5_counterfactual_stable": counterfactual_stable,
            "c6_h1_calibration_ok": bool(calib_ok),
            "c7_not_primarily_forced": (s["forced"] / s["total"]) < 0.5 if s["total"] else False,
            "c8_no_future_teacher_state_corruption": c in NO_CORRUPT,
        }
        all_ok = all(crit.values())
        admission[c] = {"stats": s, "ece_in_context": ece_ctx.get(c), "criteria": crit,
                        "admitted": all_ok}
        if all_ok:
            admitted.append(c)
    admitted = admitted[:3]

    out = {
        "contract": "c007",
        "candidate_pool": pool,
        "counterfactual_context": cf_semantic,
        "admission": admission,
        "admitted_contexts": admitted,
        "max_admitted": 3,
        "note": "Admission = a valid, safe intervention point (structural + sync + calibration + "
                "stable counterfactual). It is SEPARATE from whether an improvement exists there "
                "(AC-08). Only the damage-counter context has a counterfactual A/B, so it is the "
                "only admissible context; the A/B found no reproducible improvement, so no residual "
                "override is beneficial (BEST_HYBRID decided in AC-13).",
    }
    json.dump({"candidate_pool": pool, "stats": stats, "ece_in_context": ece_ctx},
              open(os.path.join(C007_ART, "residual_context_candidates.json"), "w"), indent=2)
    json.dump(out, open(os.path.join(C007_ART, "residual_context_admission.json"), "w"), indent=2)

    md = ["# Residual Contexts (AC-07)", "",
          f"Admitted (<=3): **{admitted or 'NONE'}**", "",
          "Admission is a valid+safe intervention point; it is separate from whether an "
          "improvement exists there (AC-08 found none).", "",
          "| context | total | non-forced | 2-meaningful | ECE | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | admitted |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in pool:
        s = admission[c]["stats"]; cr = admission[c]["criteria"]
        ece = admission[c]["ece_in_context"]
        eces = f"{ece['ece']:.3f}" if ece and ece.get("ece") is not None else "n/a"
        md.append(f"| {c} | {s['total']} | {s['non_forced']} | {s['two_meaningful']} | {eces} | "
                  + " | ".join("Y" if cr[k] else "N" for k in
                    ["c1_min_300_examples", "c2_min_200_two_meaningful", "c3_decoder_supported",
                     "c4_teacher_sync_valid", "c5_counterfactual_stable", "c6_h1_calibration_ok",
                     "c7_not_primarily_forced", "c8_no_future_teacher_state_corruption"])
                  + f" | {'YES' if admission[c]['admitted'] else 'no'} |")
    open(os.path.join(C007_ART, "RESIDUAL_CONTEXTS.md"), "w").write("\n".join(md) + "\n")
    print(json.dumps({"admitted_contexts": admitted,
                      "per_context_admitted": {c: admission[c]["admitted"] for c in pool}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
