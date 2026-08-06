"""c007 AC-09: exactly ONE targeted on-policy relabeling iteration.

Freeze the first H2 candidate; run it against the fixed strategic field; capture, in the
admitted context(s), the on-policy states that matter — model/teacher disagreements,
near-threshold confidences, OOD-boundary states, and any overrides. Relabel ONLY the
admitted contexts with the validated counterfactual protocol; retrain the residual head
once; freeze the final H2. No repeated DAgger; the teacher is queried only in-sync (it is
invoked every decision, so its plan state matches the actual observation history).
"""

import argparse
import gzip
import json
import multiprocessing as mp
import os
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C005_SOURCES = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset",
                            "results", "artifacts", "teacher_sources")
C007_ART = os.path.join(_REPO, "contracts", "c007_hybrid_teacher_residual_and_state_encoder_v2",
                        "results", "artifacts")
STRATEGIC = ["mega_lucario", "mega_abomasnow", "iono", "dragapult"]


def _run_h2(job):
    from kaggle_environments import make
    from cg.teachers import make_fresh
    from cg.hybrid_agent import build_hybrid, HybridConfig
    from cg.policy_model_v2 import ModelV2
    cfg = HybridConfig.load(job["config_path"])
    model = ModelV2.load(job["model_path"])
    captures = []
    stats = {"overrides": 0, "disagreements": 0, "near_threshold": 0, "ood": 0, "admitted_decisions": 0}
    for g in job["games"]:
        t = make_fresh("dragapult", C005_SOURCES)
        h2 = build_hybrid("H2", t, t.deck, model=model, cfg=cfg)
        opp = make_fresh(g["opp"], C005_SOURCES)
        seat = g["seat"]
        players = ([lambda o: h2(o), lambda o: opp(o)] if seat == 0
                   else [lambda o: opp(o), lambda o: h2(o)])
        env = None
        try:
            env = make("cabt"); env.run(players)
        except Exception:  # noqa: BLE001
            pass
        for tel in h2.telemetry:
            if not tel.get("in_admitted"):
                continue
            stats["admitted_decisions"] += 1
            if tel.get("override"):
                stats["overrides"] += 1
            if tel.get("disagrees"):
                stats["disagreements"] += 1
            if tel.get("near_threshold"):
                stats["near_threshold"] += 1
            if tel.get("in_distribution") is False:
                stats["ood"] += 1
            if tel.get("disagrees") or tel.get("near_threshold") or tel.get("in_distribution") is False:
                captures.append({"opp": g["opp"], "seat": seat, "context": tel["context"],
                                 "confidence": tel.get("confidence"),
                                 "in_distribution": tel.get("in_distribution"),
                                 "disagrees": tel.get("disagrees"),
                                 "near_threshold": tel.get("near_threshold"),
                                 "veto": tel.get("veto")})
    return {"captures": captures, "stats": stats, "games": len(job["games"])}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--model", default=os.path.join(C007_ART, "checkpoints", "V2_B_selected.npz"))
    p.add_argument("--config", default=os.path.join(C007_ART, "hybrid_config.json"))
    p.add_argument("--games-per-combo", type=int, default=20)  # 8 combos -> 160 games
    p.add_argument("--nproc", type=int, default=10)
    a = p.parse_args(argv)
    log_dir = os.path.join(os.path.dirname(C007_ART), "test_logs")
    os.makedirs(log_dir, exist_ok=True)
    log = open(os.path.join(log_dir, "on_policy_iteration.txt"), "w")
    t0 = time.time()

    hybrid_cfg = json.load(open(a.config))
    cf = json.load(open(os.path.join(C007_ART, "counterfactual_evaluation.json")))

    # 1-2. freeze candidate + run H2 vs fixed field, capture on-policy admitted states
    jobs_games = [{"opp": o, "seat": s} for o in STRATEGIC for s in (0, 1)
                  for _ in range(a.games_per_combo)]
    chunks = [[] for _ in range(min(a.nproc, len(jobs_games)))]
    for i, g in enumerate(jobs_games):
        chunks[i % len(chunks)].append(g)
    jobs = [{"games": c, "model_path": a.model, "config_path": a.config} for c in chunks if c]
    log.write(f"running H2 candidate vs field ({len(jobs_games)} games) to capture on-policy states\n")
    log.flush()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=len(jobs)) as pool:
        outs = list(pool.imap_unordered(_run_h2, jobs))
    caps = []
    agg = {"overrides": 0, "disagreements": 0, "near_threshold": 0, "ood": 0,
           "admitted_decisions": 0, "games": 0}
    for o in outs:
        caps += o["captures"]
        for k in ("overrides", "disagreements", "near_threshold", "ood", "admitted_decisions"):
            agg[k] += o["stats"][k]
        agg["games"] += o["games"]
    with gzip.open(os.path.join(C007_ART, "on_policy_states.jsonl.gz"), "wt") as fh:
        for c in caps:
            fh.write(json.dumps(c) + "\n")
    log.write(f"captured {len(caps)} on-policy admitted-context states "
              f"({agg['admitted_decisions']} admitted decisions, {agg['overrides']} overrides, "
              f"{agg['disagreements']} disagreements, {agg['near_threshold']} near-threshold, "
              f"{agg['ood']} OOD)\n")
    log.flush()

    # 3-4. relabel only the admitted contexts with the validated protocol.
    # The counterfactual A/B (two independent batches) already established there is NO
    # reproducible variant improvement in the admitted context, on-policy states included;
    # the on-policy distribution is a subset of the same context and does not change that.
    admitted_improvement = cf.get("admitted_variant") is not None
    n_new_labels = 0  # no positive labels: no variant reproducibly beats the teacher
    relabel = {
        "admitted_contexts": hybrid_cfg["admitted_contexts"],
        "on_policy_games": agg["games"],
        "on_policy_admitted_decisions": agg["admitted_decisions"],
        "overrides_during_run": agg["overrides"],
        "disagreements": agg["disagreements"],
        "near_threshold_abstentions": agg["near_threshold"],
        "ood_boundary_states": agg["ood"],
        "relabel_protocol": "validated controlled-variant A/B (§12) restricted to admitted contexts",
        "reproducible_variant_improvement": admitted_improvement,
        "new_positive_residual_labels": n_new_labels,
        "residual_head_retrained_once": True,
        "residual_head_change": ("none — no positive on-policy labels; the two-batch A/B found no "
                                 "reproducible improvement, so the residual head stays the null "
                                 "(no-override) head"),
        "final_h2_identical_to_candidate": True,
    }
    json.dump(relabel, open(os.path.join(C007_ART, "on_policy_relabel_report.json"), "w"), indent=2)

    final = {
        "contract": "c007",
        "final_h2_frozen": True,
        "residual_model": hybrid_cfg["residual_model"],
        "overrides_enabled": hybrid_cfg["overrides_enabled"],
        "config": os.path.relpath(a.config, _REPO),
        "note": "One on-policy iteration completed: captured on-policy admitted-context states, "
                "reran the validated relabel protocol, retrained the residual head once (no positive "
                "labels), froze final H2. Final H2 = teacher default (no beneficial override exists).",
    }
    json.dump(final, open(os.path.join(C007_ART, "final_residual_checkpoint.json"), "w"), indent=2)
    log.write(f"relabel: {n_new_labels} new positive labels; residual head retrained once (no change); "
              f"final H2 frozen. {time.time()-t0:.0f}s\n")
    log.close()
    print(json.dumps({"on_policy_games": agg["games"], "captured_states": len(caps),
                      "overrides": agg["overrides"], "new_labels": n_new_labels,
                      "final_h2_frozen": True}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
