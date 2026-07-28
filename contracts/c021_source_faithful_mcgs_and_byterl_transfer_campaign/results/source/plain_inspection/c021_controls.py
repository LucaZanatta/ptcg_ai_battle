"""c021 §2 — freeze the five required controls before any c021 code runs.

`CONTRACT §2` names five and forbids silently regenerating any of them from different code. Four
already exist as measured artifacts in c005/c020; this records their identities, hashes and PRIOR
evaluation numbers so a c021 re-measurement can be compared against what was actually claimed
before, rather than quietly replacing it.
"""
from __future__ import annotations
import glob, hashlib, json, os, subprocess, sys
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
C20 = os.path.join(_REPO, "contracts",
                   "c020_forced_method_correction_and_hybrid_integration_campaign", "results")
C21 = os.path.join(_REPO, "contracts",
                   "c021_source_faithful_mcgs_and_byterl_transfer_campaign", "results")

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()

def jload(p, d=None):
    try:
        return json.load(open(p))
    except (OSError, ValueError):
        return d

def main():
    panel = jload(os.path.join(C20, "final_panel", "final_aggregates.json"), {}) or {}
    rows = {r["candidate_id"]: r for r in panel.get("results", [])}
    out = {"frozen_at_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                                              capture_output=True, text=True).stdout.strip(),
           "c020_final_panel_games": panel.get("scored_games"),
           "controls": {}}

    base_dir = os.path.join(C20, "controls", "baseline_package")
    files = {}
    if os.path.isdir(base_dir):
        for root, _d, fs in os.walk(base_dir):
            for f in sorted(fs):
                p = os.path.join(root, f)
                files[os.path.relpath(p, base_dir)] = sha(p)
    out["controls"]["BASELINE_OFFICIAL_MEGA_LUCARIO"] = {
        "role": "frozen official baseline; the competitive bar",
        "files_sha256": files,
        "c020_panel_field": (rows.get("BASELINE_OFFICIAL_MEGA_LUCARIO") or {}).get("field_score"),
        "c020_panel_ci": (rows.get("BASELINE_OFFICIAL_MEGA_LUCARIO") or {}).get("field_ci"),
        "live_ladder_score_observed": 632.3, "kaggle_submission_ref": 55011215}

    d5 = os.path.join(_REPO, "contracts",
                      "c016_public_agent_reproduction_gauntlet_and_champion_submission",
                      "results", "artifacts", "candidates", "official_dragapult")
    dfiles = {}
    if os.path.isdir(d5):
        for root, _d, fs in os.walk(d5):
            for f in sorted(fs):
                p = os.path.join(root, f)
                dfiles[os.path.relpath(p, d5)] = sha(p)
    out["controls"]["CHAMPION_C005_DRAGAPULT"] = {
        "role": "externally confirmed champion; the role-board reference",
        "dir": os.path.relpath(d5, _REPO) if os.path.isdir(d5) else None,
        "files_sha256": dfiles,
        "live_ladder_score_observed": 719.7,
        "note": "used as a panel OPPONENT throughout c019/c020; no c020 candidate beat it"}

    mrun = None
    for f in glob.glob(os.path.join(C20, "mcts", "evaluations", "*_summary.json")):
        d = jload(f)
        if isinstance(d, dict) and not d.get("superseded_by") and \
                d.get("tag") == "postrepair_scaled":
            mrun = d
    src = {}
    for rel in ("starter_kit/c020_ismcts.py", "starter_kit/c020_infoset.py",
                "starter_kit/c020_agent.py", "starter_kit/c020_tactical_leaf.py",
                "starter_kit/c020_override.py", "starter_kit/c020_determinize.py"):
        p = os.path.join(_REPO, rel)
        if os.path.exists(p):
            src[rel] = sha(p)
    out["controls"]["C020_CORRECTED_MCTS_CONTROL"] = {
        "role": "c020 PUCT/override search; NEGATIVE evidence and comparison, not an authority",
        "honest_label": "PUCT with a handcrafted tactical leaf evaluator and a conservative "
                        "baseline-override gate. NOT MCGS: no graph/DAG, no transposition table, "
                        "no chance nodes, no UCD, no source rollout.",
        "source_sha256": src,
        "c020_panel_field": (rows.get("C020_CORRECTED_MCTS") or {}).get("field_score"),
        "c020_panel_ci": (rows.get("C020_CORRECTED_MCTS") or {}).get("field_ci")}

    bsum = jload(os.path.join(C20, "byterl", "learner_logs", "c020b_training_summary.json"), {})
    ck = os.path.join(C20, "byterl", "checkpoints", "c020b", "c020b_final_v097649.pt")
    out["controls"]["C020_CORRECTED_BYTERL_CONTROL"] = {
        "role": "c020 ByteRL final checkpoint; the improvement bar for c021 ByteRL",
        "checkpoint": os.path.relpath(ck, _REPO) if os.path.exists(ck) else None,
        "checkpoint_sha256": sha(ck) if os.path.exists(ck) else None,
        "training": {k: (bsum or {}).get(k) for k in
                     ("actual_games", "optimizer_steps", "learning_periods", "historical_pool")},
        "c020_panel_field": (rows.get("C020_CORRECTED_BYTERL") or {}).get("field_score"),
        "c020_panel_ci": (rows.get("C020_CORRECTED_BYTERL") or {}).get("field_ci"),
        "must_not_initialize_c021": True,
        "note": "FIDELITY_RULES §4 forbids c019/c020 weights as initialization"}

    out["controls"]["C020_H1_PRIOR_HYBRID_CONTROL"] = {
        "role": "c020's best candidate: corrected ByteRL priors + tactical heuristic",
        "c020_panel_field": (rows.get("C020_H1") or {}).get("field_score"),
        "c020_panel_ci": (rows.get("C020_H1") or {}).get("field_ci"),
        "promotable_in_c020": False,
        "why_not": "prior admission failed on 130 catastrophic baseline suppressions; value "
                   "admission failed against the constant predictor",
        "note": "the one c020 signal suggesting ByteRL priors can help a search; c021 transfer "
                "tests must verify runtime call counts rather than trusting the label"}

    os.makedirs(os.path.join(C21, "controls"), exist_ok=True)
    json.dump(out, open(os.path.join(C21, "controls", "control_manifest.json"), "w"), indent=2)
    print(json.dumps({"frozen_at": out["frozen_at_commit"][:12],
                      "controls": {k: v.get("c020_panel_field") for k, v in
                                   out["controls"].items()}}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
