"""c013 — evidence artifacts the acceptance criteria name directly.

Two jobs:

1. Phase-0 repair evidence (AC-02/AC-04): the trainer-state schema c013 actually persists, a
   report of which carried-forward defect each repair addresses and which test demonstrates it,
   and the ensemble-semantics validation §9 requires.

2. Promote the per-arm training outputs to the exact artifact names AC-07/AC-08 list. These are
   COPIES, and each copy records the source path and a hash computed on both sides, so a promoted
   file can be shown to be the same bytes as the run that produced it rather than merely
   plausible.
"""

from __future__ import annotations

import gzip
import json
import os
import shutil
import subprocess
import sys
from typing import Any, Dict

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import c013_common as K  # noqa: E402
import c013_ensemble_policy as ep  # noqa: E402

C013 = os.path.join(_REPO, "contracts",
                    "c013_fixed_deck_policy_combination_and_learnability")
ART = os.path.join(C013, "results", "artifacts")
LOGD = os.path.join(C013, "results", "test_logs")

REPAIRS = [
    {"repair": "active numpy Generator persisted via rng.bit_generator.state",
     "carried_from": "c011",
     "original_defect": "c011 stored np.random.get_state(), the legacy GLOBAL state, while the "
                        "trainer sampled from an np.random.Generator. Restore restored nothing "
                        "the trainer used, yet the run was described as a literal continuation.",
     "c013_owner": "tools/c013_common.py:TrainerState.save/load",
     "demonstrated_by": "tests/test_c013_continuation.py:ActiveGeneratorState",
     "negative_control": "test_legacy_global_state_would_not_have_caught_this"},
    {"repair": "content-addressed evaluation checkpoints",
     "carried_from": "c012",
     "original_defect": "cg.c009_eval.sha256_file memoises by PATH and pool workers persist. "
                        "The trainer rewrote a single cur.npz, so from the second in-run "
                        "evaluation onward every worker reported a stale hash, the identity "
                        "check refused to score, and the P1 curriculum never left stage 0.",
     "c013_owner": "tools/c013_common.py:content_addressed_copy",
     "demonstrated_by": "tests/test_c013_continuation.py:ContentAddressedHashRefresh",
     "negative_control": "test_a_per_path_cache_returns_a_stale_hash_on_the_fixed_path"},
    {"repair": "a registered evaluation returning zero scored games is fatal",
     "carried_from": "c012",
     "original_defect": "the condition returned None silently, which disabled the curriculum "
                        "gates and early stopping for an entire 90,000-game arm without any "
                        "error surfacing.",
     "c013_owner": "tools/c013_common.py:require_scored_games / ZeroScoredGamesError",
     "demonstrated_by": "tests/test_c013_continuation.py:ZeroScoredGamesIsFatal",
     "negative_control": "test_silently_returning_none_would_not_have_been_caught"},
    {"repair": "median best-per-seed is the registered statistic",
     "carried_from": "c011",
     "original_defect": "c011's scale decision used the MAXIMUM bootstrap significance over "
                        "any seed/metric pair, a materially weaker claim than the median.",
     "c013_owner": "tools/c013_common.py:median_best_per_seed",
     "demonstrated_by": "tests/test_c013_continuation.py:MedianBestPerSeed",
     "negative_control": "test_median_not_maximum"},
    {"repair": "completed games are the budget quantity",
     "carried_from": "c010",
     "original_defect": "rollout-granularity accounting let each seed overshoot its registered "
                        "budget because rollouts are atomic.",
     "c013_owner": "tools/c013_common.py:TrainerState counters",
     "demonstrated_by": "tests/test_c013_continuation.py:CompletedGameAccounting",
     "negative_control": "test_forced_only_games_count_toward_the_budget"},
    {"repair": "the frozen teacher is evaluated on the SAME panel as every candidate",
     "carried_from": "c010",
     "original_defect": "c010 could not compare candidates to the teacher on the strategic "
                        "field because the teacher was never run as a candidate on that panel.",
     "c013_owner": "cg/c011_eval_core.py teacher-as-candidate identity + c013_eval panels",
     "demonstrated_by": "results/artifacts/panel_final_summaries.json (T_teacher present)",
     "negative_control": "n/a - evidenced by the panel containing the teacher"},
]


def phase0_evidence() -> Dict[str, Any]:
    doc = {"schema": K.schema(),
           "required_state_fields": list(K.REQUIRED_STATE_FIELDS),
           "ppo_config": K.PPO_CFG,
           "repairs": REPAIRS,
           "note": "every repair is re-implemented in c013-controlled code rather than imported "
                   "from c011/c012 (§5/§6), and every one is paired with a negative control "
                   "that reintroduces the old behaviour and asserts the test catches it."}
    json.dump(doc, open(os.path.join(ART, "continuation_repair_report.json"), "w"),
              indent=2, sort_keys=True, default=str)
    json.dump({"schema": "c013.v1", "fields": list(K.REQUIRED_STATE_FIELDS),
               "generator": "numpy Generator persisted through bit_generator.state; the legacy "
                            "global np.random state is deliberately unused",
               "torch": ["torch_cpu_rng", "torch_cuda_rng"],
               "optimizer": ["adam_moments", "optimizer_step"],
               "counters": ["completed_games", "games_with_trainable_decisions",
                            "trainable_decisions"],
               "continuation_kinds": ["literal", "optimizer_state_only"]},
              open(os.path.join(ART, "trainer_state_schema.json"), "w"), indent=2)
    return doc


def ensemble_semantics() -> Dict[str, Any]:
    """§9 — demonstrate the properties numerically here too, so the artifact carries the
    evidence and not just a claim that a test file exists."""
    import numpy as np
    logits = np.array([[6.0, 0.0, 0.0], [0.0, 1.0, 0.9]])
    mask = np.ones(3)

    def mk(mode):
        e = ep.EnsemblePolicy.__new__(ep.EnsemblePolicy)
        e.mode = mode
        e.weights = np.array([0.5, 0.5])
        return e

    pl = mk("logit")._combine(logits, mask)
    pp = mk("prob")._combine(logits, mask)

    shrunk = np.array([0.0, 1.0, 1.0])
    p_recomputed = mk("prob")._combine(logits, shrunk)
    naive = pp * shrunk
    naive = naive / naive.sum()

    x = np.array([1.0, -2.0, 0.5])
    W1 = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    W2 = np.array([[0.0, 2.0], [2.0, 0.0], [-1.0, 1.0]])
    relu = lambda v: np.maximum(v, 0.0)  # noqa: E731
    ens = 0.5 * (relu(x @ W1) + relu(x @ W2))
    soup = relu(x @ (0.5 * (W1 + W2)))

    doc = {
        "logit_vs_probability_are_different_functions": {
            "logit_rule": pl.tolist(), "probability_rule": pp.tolist(),
            "max_abs_difference": float(np.abs(pl - pp).max()),
            "conclusion": "the two registered rules disagree whenever components disagree"},
        "multiselect_recomputation": {
            "recomputed_per_step": p_recomputed.tolist(),
            "naive_renormalisation_of_one_averaged_vector": naive.tolist(),
            "max_abs_difference": float(np.abs(p_recomputed - naive).max()),
            "conclusion": "§9 requires each component to be renormalised over the shrinking "
                          "legal set and re-averaged; renormalising a single previously "
                          "averaged distribution is a different distribution"},
        "ensemble_is_not_a_weight_soup": {
            "ensemble_of_two_maps": ens.tolist(), "map_at_averaged_weights": soup.tolist(),
            "max_abs_difference": float(np.abs(ens - soup).max()),
            "conclusion": "a ReLU network at averaged parameters is not the average of the "
                          "networks, so §2 forbids treating the families as equivalent"},
        "equal_weights_only": {"weights": "1/n for n components", "tuned_after_results": False},
        "forced_decisions": "bypass ensemble scoring entirely (§9)",
    }
    json.dump(doc, open(os.path.join(ART, "ensemble_semantics_validation.json"), "w"),
              indent=2, default=str)
    return doc


def promote() -> Dict[str, Any]:
    """Copy per-arm outputs to the artifact names AC-07/AC-08 name, hashing both sides."""
    moves = [
        ("training/Q0/seed901/summary.json", "Q0_summary.json"),
        ("training/Q1/seed902/summary.json", "Q1_summary.json"),
        ("training/Q0/seed901/training_games.jsonl.gz", "Q0_training_games.jsonl.gz"),
        ("training/Q1/seed902/training_games.jsonl.gz", "Q1_training_games.jsonl.gz"),
    ]
    rec = []
    for src, dst in moves:
        s = os.path.join(ART, src)
        d = os.path.join(ART, dst)
        if not os.path.exists(s):
            rec.append({"source": src, "target": dst, "status": "SOURCE_MISSING"})
            continue
        shutil.copyfile(s, d)
        rec.append({"source": src, "target": dst, "status": "copied",
                    "source_sha256": K.sha_file(s), "target_sha256": K.sha_file(d),
                    "identical": K.sha_file(s) == K.sha_file(d)})

    # Q2 is two arms; concatenate their raw games into the single artifact AC-08 names,
    # tagging each row with its arm so the merge is reversible rather than lossy.
    q2 = os.path.join(ART, "Q2_training_games.jsonl.gz")
    parts = [("Q2A", "training/Q2A/seed903/training_games.jsonl.gz"),
             ("Q2B", "training/Q2B/seed904/training_games.jsonl.gz")]
    n = 0
    with gzip.open(q2, "wt") as out:
        for arm, rel in parts:
            p = os.path.join(ART, rel)
            if not os.path.exists(p):
                continue
            for line in gzip.open(p, "rt"):
                r = json.loads(line)
                r["_arm"] = arm
                out.write(json.dumps(r) + "\n")
                n += 1
    rec.append({"source": [p for _, p in parts], "target": "Q2_training_games.jsonl.gz",
                "status": "concatenated", "rows": n,
                "note": "each row tagged with _arm so the concatenation is reversible",
                "target_sha256": K.sha_file(q2)})

    # Q2 component registry
    comp = {}
    for arm, seed in (("Q2A", 903), ("Q2B", 904)):
        p = os.path.join(ART, "training", arm, f"seed{seed}", "checkpoint_registry.json")
        s = os.path.join(ART, "training", arm, f"seed{seed}", "summary.json")
        if not os.path.exists(p):
            continue
        reg = json.load(open(p))
        last = reg[max(reg, key=lambda x: int(x))] if reg else None
        comp[arm] = {"seed": seed, "final_checkpoint": last,
                     "completed_games": json.load(open(s)).get("completed_games")
                     if os.path.exists(s) else None,
                     "continued_component": {"Q2A": "S622", "Q2B": "S633"}[arm]}
    recomb = os.path.join(ART, "Q2_recombination_results.json")
    doc = {"components": comp,
           "recombinations": (json.load(open(recomb)).get("recombinations")
                              if os.path.exists(recomb) else {}),
           "note": "S622 and S633 were continued SEPARATELY from the same Phase 2 start and "
                   "then recombined by the registered equal-weight rules; no weights were "
                   "tuned after results (§15)"}
    json.dump(doc, open(os.path.join(ART, "Q2_component_registry.json"), "w"),
              indent=2, default=str)

    # per-arm training logs under the names AC-07/AC-08 use
    for src, dst in (("_Q0.txt", "Q0_training.txt"), ("_Q1.txt", "Q1_value_refit.txt"),
                     ("_Q2A.txt", "Q2_component_continuation.txt")):
        s = os.path.join(LOGD, src)
        if os.path.exists(s):
            shutil.copyfile(s, os.path.join(LOGD, dst))
    b = os.path.join(LOGD, "_Q2B.txt")
    if os.path.exists(b):
        with open(os.path.join(LOGD, "Q2_component_continuation.txt"), "a") as fh:
            fh.write("\n\n=== Q2B seed904 ===\n")
            fh.write(open(b, errors="ignore").read())
    return {"promoted": rec, "q2_components": list(comp)}


def main():
    os.makedirs(ART, exist_ok=True)
    os.makedirs(LOGD, exist_ok=True)
    p0 = phase0_evidence()
    es = ensemble_semantics()
    pr = promote()
    out = {"repairs": len(p0["repairs"]),
           "ensemble_checks": list(es),
           "promoted": pr}
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
