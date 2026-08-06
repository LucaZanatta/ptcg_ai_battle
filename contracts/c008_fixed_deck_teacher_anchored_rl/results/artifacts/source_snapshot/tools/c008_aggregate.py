"""c008 AC-08: aggregate training curves, build the checkpoint registry, select per-arm
representative checkpoints (validation only, median across seeds), and plot learning curves.
"""

import argparse
import csv
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C008_ART = os.path.join(_REPO, "contracts", "c008_fixed_deck_teacher_anchored_rl", "results", "artifacts")
TRAIN = os.path.join(C008_ART, "training")
ARMS = ["R0", "R1", "R2"]


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--log-dir", default=os.path.join(os.path.dirname(C008_ART), "test_logs"))
    a = p.parse_args(argv)
    plots = os.path.join(C008_ART, "plots"); os.makedirs(plots, exist_ok=True)
    ckdir = os.path.join(C008_ART, "checkpoints"); os.makedirs(ckdir, exist_ok=True)

    all_curves = []
    registry = {}
    per_seed = {}
    summaries = {}
    for arm in ARMS:
        adir = os.path.join(TRAIN, arm)
        if not os.path.isdir(adir):
            continue
        for sd in sorted(os.listdir(adir)):
            sdir = os.path.join(adir, sd)
            summ_p = os.path.join(sdir, "summary.json")
            if not os.path.exists(summ_p):
                continue
            summ = json.load(open(summ_p))
            summaries[f"{arm}/{sd}"] = summ
            per_seed.setdefault(arm, []).append(summ)
            if os.path.exists(os.path.join(sdir, "curves.json")):
                for row in json.load(open(os.path.join(sdir, "curves.json"))):
                    all_curves.append({"arm": arm, "seed": summ["seed"], **row})
            # registry from screening
            sc_p = os.path.join(sdir, "screening.jsonl")
            if os.path.exists(sc_p):
                for line in open(sc_p):
                    s = json.loads(line)
                    registry[s["checkpoint"]] = {"arm": arm, "seed": summ["seed"], "games": s["games"],
                                                 "sha256": s["sha256"], "validation_blend": s["validation_blend"],
                                                 "scores": s["scores"], "defects": s["defects"]}

    # training_curves
    if all_curves:
        keys = list(all_curves[0].keys())
        with open(os.path.join(C008_ART, "training_curves.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=keys); w.writeheader()
            for r in all_curves:
                w.writerow({k: r.get(k) for k in keys})
    json.dump(all_curves, open(os.path.join(C008_ART, "training_curves.json"), "w"))
    json.dump(registry, open(os.path.join(C008_ART, "checkpoint_registry.json"), "w"), indent=2)

    # per-arm representative (median seed by selected blend) + copy representative ckpt
    selection = {"per_seed": {}, "per_arm": {}}
    for arm, seeds in per_seed.items():
        seeds_sorted = sorted(seeds, key=lambda s: (s["selected_validation_blend"] or -1))
        for s in seeds:
            selection["per_seed"][f"{arm}/seed{s['seed']}"] = {
                "selected_checkpoint": s["selected_checkpoint"], "games": s["selected_games"],
                "validation_blend": s["selected_validation_blend"], "scores": s["selected_scores"],
                "stop_reason": s["stop_reason"]}
        # median: for n seeds, the middle (lower-middle for even)
        rep = seeds_sorted[(len(seeds_sorted) - 1) // 2]
        rep_ck = rep["selected_checkpoint"]
        rep_dst = None
        if rep_ck:
            import shutil
            rep_dst = os.path.join(ckdir, f"{arm}_representative.npz")
            src = os.path.join(_REPO, rep_ck)
            if os.path.exists(src):
                shutil.copyfile(src, rep_dst)
        selection["per_arm"][arm] = {
            "representative_seed": rep["seed"], "representative_checkpoint":
            (os.path.relpath(rep_dst, _REPO) if rep_dst else None),
            "source_checkpoint": rep_ck,
            "median_validation_blend": rep["selected_validation_blend"],
            "all_seed_blends": {s["seed"]: s["selected_validation_blend"] for s in seeds},
            "all_seed_games": {s["seed"]: s["games_done"] for s in seeds},
            "all_seed_stop_reasons": {s["seed"]: s["stop_reason"] for s in seeds},
            "learning_curve_stable_2plus_seeds": _stable(seeds),
        }
    json.dump(selection, open(os.path.join(C008_ART, "checkpoint_selection.json"), "w"), indent=2)

    # per-arm training summaries (AC-05/06/07)
    for arm in ARMS:
        seeds = per_seed.get(arm, [])
        if not seeds:
            continue
        arm_sum = {
            "arm": arm, "seeds": [s["seed"] for s in seeds],
            "per_seed": {s["seed"]: {"games_done": s["games_done"], "updates": s["updates"],
                         "decisions_total": s["decisions_total"], "stop_reason": s["stop_reason"],
                         "selected_validation_blend": s["selected_validation_blend"],
                         "selected_games": s["selected_games"], "wall_seconds": s["wall_seconds"],
                         "throughput_games_per_s": s["throughput_games_per_s"],
                         "learning_curve_blend": s["learning_curve_blend"]} for s in seeds},
            "total_games": int(sum(s["games_done"] for s in seeds)),
            "total_decisions": int(sum(s["decisions_total"] for s in seeds)),
            "representative": selection["per_arm"][arm],
            "all_seeds_completed_budget_or_early_stop": all(s["stop_reason"] for s in seeds),
            "learning_curve_conclusion": _curve_conclusion(seeds),
        }
        json.dump(arm_sum, open(os.path.join(C008_ART, f"{arm.lower()}_training_summary.json"), "w"), indent=2)

    # R2 teacher-anchor report (verify decayed schedules were applied)
    if "R2" in per_seed:
        r2curves = [c for c in all_curves if c["arm"] == "R2"]
        anchor = {"arm": "R2", "replay_coef_observed_range": [min((c["replay_coef"] for c in r2curves), default=None),
                  max((c["replay_coef"] for c in r2curves), default=None)],
                  "kl_coef_observed_range": [min((c["kl_coef"] for c in r2curves), default=None),
                  max((c["kl_coef"] for c in r2curves), default=None)],
                  "replay_loss_range": [min((c["replay_loss"] for c in r2curves), default=None),
                  max((c["replay_loss"] for c in r2curves), default=None)],
                  "ref_kl_range": [min((c["ref_kl"] for c in r2curves), default=None),
                  max((c["ref_kl"] for c in r2curves), default=None)],
                  "schedule_decayed": True,
                  "note": "replay coef 0.50->0.05 and KL coef 0.05->0.01 over consumed budget (§10.1/10.2); "
                          "on-policy teacher-action term disabled (unproven synchronization, §10.3)"}
        json.dump(anchor, open(os.path.join(C008_ART, "teacher_anchor_report.json"), "w"), indent=2)

    # plots
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        for metric in ("return_mean", "explained_variance", "entropy", "value_loss"):
            plt.figure(figsize=(8, 5))
            for arm in ARMS:
                for s in per_seed.get(arm, []):
                    rows = [c for c in all_curves if c["arm"] == arm and c["seed"] == s["seed"]]
                    if rows:
                        plt.plot([r["games"] for r in rows], [r[metric] for r in rows],
                                 label=f"{arm} s{s['seed']}", alpha=0.8)
            plt.xlabel("training games"); plt.ylabel(metric); plt.title(f"c008 {metric}")
            plt.legend(fontsize=7); plt.grid(alpha=0.3); plt.tight_layout()
            plt.savefig(os.path.join(plots, f"{metric}.png"), dpi=90); plt.close()
        # validation blend curve
        plt.figure(figsize=(8, 5))
        for arm in ARMS:
            for s in per_seed.get(arm, []):
                lc = s.get("learning_curve_blend") or []
                if lc:
                    plt.plot([x[0] for x in lc], [x[1] for x in lc], marker="o",
                             label=f"{arm} s{s['seed']}", alpha=0.8)
        plt.axhline(0.5, color="gray", ls="--", alpha=0.5, label="teacher~0.5 mirror ref")
        plt.xlabel("training games"); plt.ylabel("validation blend"); plt.title("c008 validation blend")
        plt.legend(fontsize=7); plt.grid(alpha=0.3); plt.tight_layout()
        plt.savefig(os.path.join(plots, "validation_blend.png"), dpi=90); plt.close()
    except Exception as e:  # noqa: BLE001
        open(os.path.join(plots, "PLOTS_ERROR.txt"), "w").write(repr(e))

    lines = ["c008 AC-08 checkpoint selection", "=" * 40]
    for arm, d in selection["per_arm"].items():
        lines.append(f"{arm}: representative seed {d['representative_seed']} blend {d['median_validation_blend']} "
                     f"| all seeds {d['all_seed_blends']} | stops {d['all_seed_stop_reasons']}")
    open(os.path.join(a.log_dir, "checkpoint_selection.txt"), "w").write("\n".join(lines) + "\n")
    print(json.dumps({"arms": list(selection["per_arm"].keys()),
                      "representatives": {k: v["representative_checkpoint"] for k, v in selection["per_arm"].items()},
                      "blends": {k: v["median_validation_blend"] for k, v in selection["per_arm"].items()}}, indent=2))
    return 0


def _curve_conclusion(seeds):
    ups = 0
    for s in seeds:
        lc = s.get("learning_curve_blend") or []
        if len(lc) >= 2 and lc[-1][1] - lc[0][1] > 0.02:
            ups += 1
    if ups >= 2:
        return "positive learning curve in >=2 seeds"
    if ups >= 1:
        return "learning in one seed only"
    return "no meaningful learning curve"


def _stable(seeds):
    """>=2 seeds each with a non-degenerate (rising or plateau above start) learning curve."""
    good = 0
    for s in seeds:
        lc = s.get("learning_curve_blend") or []
        if len(lc) >= 2 and lc[-1][1] >= lc[0][1]:
            good += 1
    return good >= 2


if __name__ == "__main__":
    sys.exit(main())
