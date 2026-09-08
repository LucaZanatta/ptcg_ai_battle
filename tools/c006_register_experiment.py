"""c006 §6: freeze the experiment registration BEFORE training. Pins dataset,
teacher/deck, feature schema, vocabulary, taxonomy, architectures, param ceilings,
seeds, optimizer, early-stopping metric, offline metrics, gauntlet, non-inferiority
test, and the submission / RL-readiness gates. No unregistered architecture or
metric may become the final winner.
"""

import argparse
import hashlib
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from cg.card_vocab import build_vocab
from cg.policy_features import FEATURE_DIMS
from cg.policy_model import PolicyModel


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


REGISTRATION = {
    "contract": "c006_distilled_policy_baseline",
    "teacher_id": "dragapult",
    "frozen_deck_id": "sha256:8055443275c86105b38198992c9556a642b833a47430aa97fb1a84c9ee4fdbab",
    "architectures": {
        "S1_STATELESS": {"recurrent": False, "cfg": {"emb": 32, "h": 160, "h2": 128},
                         "param_target": [150000, 500000], "param_hard_max": 750000},
        "S2_RECURRENT": {"recurrent": True, "cfg": {"emb": 32, "h": 160, "h2": 128, "cc": 64, "hr": 128},
                         "param_target": [250000, 650000], "param_hard_max": 900000,
                         "recurrence": "single GRU over game decision sequence; reset at game start; "
                                       "prev context+action as explicit inputs; full BPTT (max game "
                                       "length 127 <= no truncation needed)"},
    },
    "seeds": {"S1_STATELESS": [101, 202, 303], "S2_RECURRENT": [111, 222, 333]},
    "optimizer": {"name": "adam", "lr": 1.5e-3, "betas": [0.9, 0.999], "eps": 1e-8,
                  "weight_decay": 0.0, "batch_decisions_s1": 256, "batch_s2": "per_game",
                  "max_epochs": {"S1_STATELESS": 40, "S2_RECURRENT": 30}, "patience": 6,
                  "blas_threads": "OMP_NUM_THREADS=1 for reproducibility"},
    "loss": {"single_choice": "masked softmax cross-entropy",
             "unordered_multiselect": "masked per-option BCE",
             "ordered": "none present -> safe fallback (not trained as BCE)",
             "importance_weighting": {"FORCED": 0.0, "ROUTINE": 1.0, "TACTICAL": 2.0, "HIGH_IMPACT": 4.0}},
    "early_stopping_metric": "importance_weighted_teacher_action_agreement (validation)",
    "checkpoint_selection": "best validation importance-weighted agreement per seed; "
                            "best seed per architecture; test opened once after freeze",
    "offline_metrics": ["overall_exact_agreement", "importance_weighted_agreement",
                        "agreement_by_taxonomy", "agreement_by_context", "agreement_by_semantic_type",
                        "top2_agreement", "top3_agreement", "multiselect_exact_set", "multiselect_element_f1",
                        "calibration", "fallback_rate", "test_nll", "param_count", "model_size_bytes",
                        "cpu_latency_p50_p95_p99_max"],
    "gameplay_gauntlet": {"opponents": ["mega_lucario", "mega_abomasnow", "iono", "teacher_mirror"],
                          "control": "det_starter (deterministic, reported separately)",
                          "both_seats": True, "protocol": "c004/c005 sequential balanced round-robin"},
    "noninferiority_test": {"metric": "student score vs teacher (win=1,draw=0.5,loss=0)",
                            "bound": "one-sided 95% lower bound (5th percentile, seat-balanced bootstrap)",
                            "margin": 0.05, "pass_threshold": ">= 0.45",
                            "games": "100 seat0 + 100 seat1, extend +50/orientation to 400 if ambiguous"},
    "memory_decision_rule": "MEMORY_MATTERS if S2 improves high-impact test agreement by >= 2pp, OR "
                            "game-level importance-weighted agreement 95% bootstrap interval > 0, OR "
                            "material gameplay improvement; else MEMORY_NOT_JUSTIFIED",
    "best_student_rule": "reliability-eligible; passes non-inferiority; highest gauntlet strength; "
                         "no major regression; higher high-impact test agreement; lower fallback; "
                         "lower P99; smaller model. NONE if neither passes non-inferiority.",
    "submission_gate": "SUBMIT iff best student exists AND non-inferiority passes AND no major regression "
                       "AND perfect official-eval reliability AND package validation passes AND P99+size pass",
    "rl_readiness_gate": "READY_FOR_RL iff best student exists AND submission gate passes (or misses only "
                         "for non-policy operational issue) AND not materially weaker than teacher AND "
                         "decoder covers >=99% of teacher decisions without strategic fallback AND memory "
                         "decision resolved AND frozen checkpoint+eval reproducible",
    "emergency_correction_policy": "a single documented code-defect correction that invalidates all runs "
                                   "may restart every affected model fairly; otherwise no changes after freeze",
}


def run(args):
    art = args.art_dir
    ds_dir = os.path.join(art, "sequence_dataset")
    reg = dict(REGISTRATION)
    reg["dataset"] = {
        "source_manifest": "sequence_dataset_manifest.json",
        "split_file_sha256": {sp: _sha(os.path.join(ds_dir, f"{sp}.jsonl.gz"))
                              for sp in ("train", "validation", "test")},
        "sequence_index_sha256": _sha(os.path.join(ds_dir, "sequence_index.json")),
    }
    reg["feature_schema"] = dict(FEATURE_DIMS)
    reg["card_vocabulary"] = {"source_hash": build_vocab()["source_hash"],
                              "vocab_size": build_vocab()["vocab_size"]}
    reg["taxonomy_sha256"] = _sha(os.path.join(art, "decision_taxonomy.json"))
    reg["decoder_coverage_sha256"] = _sha(os.path.join(art, "decoder_coverage_report.json"))
    reg["actual_param_counts"] = {
        "S1_STATELESS": PolicyModel({"recurrent": False}).param_count(),
        "S2_RECURRENT": PolicyModel({"recurrent": True}).param_count(),
    }
    # verify counts within registered bounds
    for k in ("S1_STATELESS", "S2_RECURRENT"):
        lo, hi = reg["architectures"][k]["param_target"]
        pc = reg["actual_param_counts"][k]
        reg["architectures"][k]["param_count_in_target"] = bool(lo <= pc <= hi)

    json.dump(reg, open(os.path.join(art, "experiment_registration.json"), "w"), indent=2)

    md = ["# c006 Experiment Registration (frozen before training)", "",
          f"Teacher: `{reg['teacher_id']}`  |  Deck: `{reg['frozen_deck_id']}`", "",
          "## Architectures & parameter ceilings"]
    for k, a in reg["architectures"].items():
        pc = reg["actual_param_counts"][k]
        md.append(f"- **{k}**: {pc:,} params (target {a['param_target']}, hard max {a['param_hard_max']}) "
                  f"— in target: {a['param_count_in_target']}")
    md += ["", "## Seeds", f"- S1: {reg['seeds']['S1_STATELESS']}  |  S2: {reg['seeds']['S2_RECURRENT']}",
           "", "## Optimizer", f"- Adam lr={reg['optimizer']['lr']}, betas={reg['optimizer']['betas']}, "
           f"max_epochs={reg['optimizer']['max_epochs']}, patience={reg['optimizer']['patience']}, "
           f"{reg['optimizer']['blas_threads']}",
           "", "## Early-stopping metric", f"- {reg['early_stopping_metric']}",
           "", "## Loss", f"- single: {reg['loss']['single_choice']}; multi: {reg['loss']['unordered_multiselect']}; "
           f"ordered: {reg['loss']['ordered']}",
           f"- importance weights: {reg['loss']['importance_weighting']}",
           "", "## Non-inferiority", f"- {reg['noninferiority_test']['bound']}; pass {reg['noninferiority_test']['pass_threshold']}; "
           f"margin {reg['noninferiority_test']['margin']}",
           "", "## Gates",
           f"- Memory: {reg['memory_decision_rule']}",
           f"- Best student: {reg['best_student_rule']}",
           f"- Submission: {reg['submission_gate']}",
           f"- RL readiness: {reg['rl_readiness_gate']}",
           "", "## Dataset freeze",
           f"- train/val/test sha256: {json.dumps(reg['dataset']['split_file_sha256'], indent=2)}",
           f"- card vocab source hash: `{reg['card_vocabulary']['source_hash']}`",
           "", f"Emergency correction policy: {reg['emergency_correction_policy']}"]
    open(os.path.join(art, "EXPERIMENT_REGISTRATION.md"), "w").write("\n".join(md))
    print(json.dumps({"param_counts": reg["actual_param_counts"],
                      "in_target": {k: reg["architectures"][k]["param_count_in_target"]
                                    for k in reg["architectures"]}}, indent=2))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--art-dir", required=True)
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
