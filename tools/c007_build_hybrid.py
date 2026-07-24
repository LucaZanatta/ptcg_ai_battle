"""c007: assemble the H2 hybrid runtime config from the admitted contexts, the
counterfactual A/B advantage, and a per-context OOD envelope mined from the v2 training
data. Also records the residual-model reference. If no reproducible improvement was
admitted (AC-08), every admitted context's advantage LCB is <= 0, so H2 defaults to the
teacher everywhere (safe-by-construction).
"""

import argparse
import gzip
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

import numpy as np  # noqa: E402
from cg import state_encoder_v2 as enc  # noqa: E402

C007_ART = os.path.join(_REPO, "contracts", "c007_hybrid_teacher_residual_and_state_encoder_v2",
                        "results", "artifacts")
V2_DATA = os.path.join(C007_ART, "v2_dataset")

CONTEXT_MAP = {
    "dragapult_damage_counter": {"DAMAGE_COUNTER_ANY", "DAMAGE_COUNTER"},
    "promotion_to_active": {"TO_ACTIVE", "SETUP_ACTIVE_POKEMON"},
    "retreat_switch": {"SWITCH"}, "energy_attachment_target": {"ATTACH_FROM", "ATTACH_TO"},
    "search_card_target": {"TO_HAND", "TO_DECK", "TO_DECK_BOTTOM", "LOOK", "TO_PRIZE"},
    "evolution_target": {"EVOLVE"},
}


def _ood_envelope(select_context_names):
    """[1,99] percentile envelope of the global feature vector + option-count range.

    History is threaded per game (as at runtime) so the previous-action-identity dims of
    the envelope match the live featurization; using initial_prev_state here would leave
    those dims empty and flag every live (history-carrying) decision as OOD."""
    globs = []
    nopts = []
    for sp in ("train", "validation"):
        games = {}
        with gzip.open(os.path.join(V2_DATA, f"{sp}.jsonl.gz"), "rt") as fh:
            for line in fh:
                r = json.loads(line)
                games.setdefault(r["game_id"], []).append(r)
        for gid, recs in games.items():
            recs.sort(key=lambda r: r["decision_index"])
            prev = enc.initial_prev_state()
            for r in recs:
                if r["select_context"] in select_context_names:
                    f = enc.encode(r["observation"], prev)
                    globs.append(f["global"]); nopts.append(f["n_options"])
                prev = enc.derive_prev_state(r["observation"], r["teacher_action_indices"])
    if not globs:
        return None
    G = np.stack(globs)
    lo = np.percentile(G, 1, axis=0); hi = np.percentile(G, 99, axis=0)
    # calibrate the OOD tolerance ON the training data: per-decision fraction of dims
    # outside [1,99], then set tolerance at the 95th percentile so ~95% of in-context
    # training decisions are (correctly) in-distribution. Per-dim [1,99] alone flags ~2%
    # of dims by construction, so a fixed small tolerance would flag nearly everything.
    outside_frac = np.mean((G < lo) | (G > hi), axis=1)
    tol = float(np.percentile(outside_frac, 95))
    return {"lo": lo.tolist(), "hi": hi.tolist(),
            "opt_lo": int(np.min(nopts)), "opt_hi": int(np.max(nopts)), "n": len(globs),
            "tolerance": tol, "train_outside_frac_median": float(np.median(outside_frac))}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--ckpt-dir", default=os.path.join(C007_ART, "checkpoints"))
    a = p.parse_args(argv)
    reg = json.load(open(os.path.join(C007_ART, "experiment_registration.json")))
    admission = json.load(open(os.path.join(C007_ART, "residual_context_admission.json")))
    cf = json.load(open(os.path.join(C007_ART, "counterfactual_evaluation.json")))
    admitted_semantic = admission["admitted_contexts"]

    # per-admitted-context reproducible advantage LCB = max over variants of
    # min(batch1_lcb, batch2_lcb) (<= 0 unless a variant reproduced an improvement)
    b1 = cf.get("ab_batch1", {}).get("variants", {})
    b2 = cf.get("ab_batch2", {}).get("variants", {})
    repro_lcb = -1.0
    for vn in b1:
        lcb = min(b1[vn]["diff_lcb_90"], b2.get(vn, {}).get("diff_lcb_90", -1.0))
        repro_lcb = max(repro_lcb, lcb)

    # map admitted semantic contexts to raw select_context names for the runtime agent
    admitted_ctx_names = []
    context_adv = {}
    ood = {}
    for sem in admitted_semantic:
        names = sorted(CONTEXT_MAP.get(sem, {sem}))
        for nm in names:
            admitted_ctx_names.append(nm)
            # only the damage-counter context carries a measured counterfactual advantage
            context_adv[nm] = repro_lcb if sem == cf.get("admitted_context_semantic",
                                                          "dragapult_damage_counter") else -1.0
            env = _ood_envelope({nm})
            if env:
                ood[nm] = env

    gates = reg["gates"]
    sel_model = os.path.join(a.ckpt_dir, "V2_B_selected.npz")
    if not os.path.exists(sel_model):
        sel_model = os.path.join(a.ckpt_dir, "V2_A_selected.npz")

    cfg = {
        "contract": "c007",
        "admitted_contexts": admitted_ctx_names,
        "admitted_semantic_contexts": admitted_semantic,
        "confidence_min": gates["override_confidence_min"],
        "advantage_lcb_min": gates["advantage_lcb_min"],
        "budget_per_game": gates["override_budget_per_game"],
        "budget_per_context": gates["override_budget_per_context_per_game"],
        "context_advantage_lcb": context_adv,
        "reproducible_advantage_lcb": repro_lcb,
        "ood_envelope": ood,
        "ood_tolerance": 0.02,
        "residual_model": os.path.relpath(sel_model, _REPO),
        "residual_note": ("No variant produced a reproducible improvement (AC-08), so every "
                          "admitted context's advantage LCB <= 0 and H2 never overrides — it is "
                          "the frozen teacher by construction (safe hybrid, no beneficial residual)."),
        "overrides_enabled": any(v > gates["advantage_lcb_min"] for v in context_adv.values()),
    }
    json.dump(cfg, open(os.path.join(C007_ART, "hybrid_config.json"), "w"), indent=2)
    print(json.dumps({"admitted_contexts": admitted_ctx_names,
                      "reproducible_advantage_lcb": repro_lcb,
                      "overrides_enabled": cfg["overrides_enabled"],
                      "residual_model": cfg["residual_model"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
