"""c020 — freeze the c019 controls before any c020 code runs.

`CONTRACT.md §2` requires exact source hashes, model hashes, configs, package manifests and c019
gameplay summaries for four frozen controls. Freezing them FIRST matters: c020 exists to be
compared against c019, and a control recorded after the fact can silently drift toward whatever
makes c020 look better.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C19 = os.path.join(_REPO, "contracts", "c019_dual_method_campaign_ptcg_mcts_and_byterl",
                   "results")
C20 = os.path.join(_REPO, "contracts",
                   "c020_forced_method_correction_and_hybrid_integration_campaign", "results")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def jload(p, d=None):
    return json.load(open(p)) if os.path.exists(p) else d


def main():
    from cg import c009_eval as ce

    out = {"frozen_at_commit": subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=_REPO, capture_output=True, text=True).stdout.strip(),
        "controls": {}}

    # ---------------------------------------------------------------- baseline
    bdir = os.path.join(_REPO, "cg", "teachers", "official_mega_lucario")
    if not os.path.isdir(bdir):
        cand = glob.glob(os.path.join(_REPO, "**", "official_mega_lucario"), recursive=True)
        bdir = cand[0] if cand else None
    files = {}
    if bdir:
        for root, _d, fs in os.walk(bdir):
            for fn in sorted(fs):
                p = os.path.join(root, fn)
                files[os.path.relpath(p, bdir)] = {"sha256": sha(p),
                                                  "bytes": os.path.getsize(p)}
    out["controls"]["BASELINE_OFFICIAL_MEGA_LUCARIO"] = {
        "role": "frozen baseline, rollout source and prior source",
        "dir": os.path.relpath(bdir, _REPO) if bdir else None,
        "files": files,
        "deck_locked": True,
        "note": "CONTRACT §2 forbids deck edits, alternative official-agent submission, "
                "public-agent replacement and any anti-meta branch.",
    }

    # ---------------------------------------------------------------- c019 MCTS
    src = {}
    for rel in ("starter_kit/c019_mcts.py", "starter_kit/c019_ismcts.py",
                "starter_kit/c019_determinize.py", "starter_kit/c019_leaf.py",
                "starter_kit/c019_baseline.py", "starter_kit/c019_core.py"):
        p = os.path.join(_REPO, rel)
        if os.path.exists(p):
            src[rel] = sha(p)
    mgate = jload(os.path.join(C19, "mcts", "evaluations", "mcts_gate_decision.json"), {})
    out["controls"]["C019_PIMC_PUCT_CONTROL"] = {
        "role": "c019 separate-tree PIMC/PUCT search, retained as a named control",
        "honest_label": "PIMC-like: one independent tree per determinization, aggregated at the "
                        "root only. NOT shared-statistics ISMCTS (C019_AUDIT_FINDINGS #1).",
        "source_sha256": src,
        "c019_gate": {"field": mgate.get("candidate_field"),
                      "baseline_field": mgate.get("baseline_field"),
                      "delta_field_points": mgate.get("delta_field_points"),
                      "eligible": mgate.get("eligible_for_submission")},
    }

    # ---------------------------------------------------------------- c019 ByteRL
    bsrc = {}
    for rel in ("starter_kit/c019_byterl_encode.py", "starter_kit/c019_byterl_model.py",
                "starter_kit/c019_byterl_actor.py", "starter_kit/c019_vtrace.py",
                "starter_kit/c019_osfp.py"):
        p = os.path.join(_REPO, rel)
        if os.path.exists(p):
            bsrc[rel] = sha(p)
    ck_dir = os.path.join(C19, "byterl", "checkpoints", "scaled2")
    cks = sorted(glob.glob(os.path.join(ck_dir, "*.pt")),
                 key=lambda f: int("".join(c for c in os.path.basename(f) if c.isdigit()) or 0))
    final_ck = cks[-1] if cks else None
    bsum = jload(os.path.join(C19, "byterl", "learner_logs",
                              "scaled2_training_summary.json"), {})
    bgate = jload(os.path.join(C19, "byterl", "evaluations", "byterl_gate_decision.json"), {})
    hist = {}
    hd = os.path.join(C19, "byterl", "osfp", "historical_checkpoints", "scaled2")
    if os.path.isdir(hd):
        for fn in sorted(os.listdir(hd)):
            hist[fn] = sha(os.path.join(hd, fn))
    out["controls"]["C019_BYTERL_CONTROL"] = {
        "role": "c019 ByteRL final checkpoint, retained as a control and as the ByteRL "
                "improvement bar in the c020 gate",
        "source_sha256": bsrc,
        "final_checkpoint": os.path.relpath(final_ck, _REPO) if final_ck else None,
        "final_checkpoint_sha256": sha(final_ck) if final_ck else None,
        "historical_checkpoints_sha256": hist,
        "training": {"games": bsum.get("actual_games"),
                     "optimizer_steps": bsum.get("optimizer_steps"),
                     "learning_periods": bsum.get("learning_periods"),
                     "historical_pool": bsum.get("historical_pool")},
        "c019_gate": {"field": bgate.get("candidate_field"),
                      "baseline_field": bgate.get("baseline_field"),
                      "delta_field_points": bgate.get("delta_field_points"),
                      "eligible": bgate.get("eligible_for_submission")},
        "must_not_initialize_c020": True,
        "note": "CONTRACT §2 and §6: corrected ByteRL starts from fresh random weights because "
                "observation/action/recurrent semantics change. These weights are a control only.",
    }

    # ---------------------------------------------------------------- c019 hybrid
    hsrc = {}
    p = os.path.join(_REPO, "starter_kit", "c019_hybrid.py")
    if os.path.exists(p):
        hsrc["starter_kit/c019_hybrid.py"] = sha(p)
    abl = jload(os.path.join(C19, "hybrid", "comparisons", "adapter_ablation.json"), {})
    hgate = jload(os.path.join(C19, "hybrid", "comparisons", "hybrid_gate_decision.json"), {})
    out["controls"]["C019_HYBRID_CONTROL"] = {
        "role": "c019 hybrid adapters, retained as a control",
        "honest_label": "called recurrent ByteRL with state=None at search nodes "
                        "(C019_AUDIT_FINDINGS #14)",
        "source_sha256": hsrc,
        "c019_gate": {"field": hgate.get("candidate_field"),
                      "delta_field_points": hgate.get("delta_field_points"),
                      "eligible": hgate.get("eligible_for_submission")},
        "c019_adapter_ablation": abl,
    }

    out["c019_panels"] = {}
    for p in sorted(glob.glob(os.path.join(C19, "final_panel", "*_aggregates.json"))):
        d = json.load(open(p))
        out["c019_panels"][d.get("tag")] = {
            "games": d.get("scored_games"), "incomplete": d.get("incomplete_games"),
            "results": [{"candidate": r["candidate_id"], "field": r["field_score"],
                         "ci": r.get("field_ci")} for r in d.get("results", [])]}

    os.makedirs(os.path.join(C20, "controls"), exist_ok=True)
    json.dump(out, open(os.path.join(C20, "controls", "control_manifest.json"), "w"), indent=2)
    json.dump(out["c019_panels"],
              open(os.path.join(C20, "controls", "c019_control_results.json"), "w"), indent=2)
    print(json.dumps({"frozen_at_commit": out["frozen_at_commit"],
                      "controls": list(out["controls"]),
                      "baseline_files": len(files),
                      "c019_byterl_final_ck": os.path.basename(final_ck) if final_ck else None,
                      "c019_historical": len(hist),
                      "c019_panels": list(out["c019_panels"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
