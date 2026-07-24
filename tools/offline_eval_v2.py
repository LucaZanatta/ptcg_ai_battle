"""c007 AC-06: offline evaluation + auxiliary-label ablation for the v2 advisory models.

Opens the c007 TEST split exactly once. Evaluates the selected V2-A and V2-B
checkpoints (and reports per-seed) on: teacher agreement (exact / importance-weighted
/ non-forced / by-importance / by-semantic-type), calibration (ECE), cross-option-set
sensitivity, c006-test back-evaluation (historical benchmark), single-process latency,
and parameter count. Ablation compares V2-A (action only) vs V2-B (+ privileged plan
auxiliary heads).
"""

import argparse
import json
import os
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

import numpy as np  # noqa: E402
from cg import policy_model_v2 as pm, policy_data_v2 as pd, decoders  # noqa: E402

C007_ART = os.path.join(_REPO, "contracts", "c007_hybrid_teacher_residual_and_state_encoder_v2",
                        "results", "artifacts")
V2_DATA = os.path.join(C007_ART, "v2_dataset")
C006_SEQ = os.path.join(_REPO, "contracts", "c006_distilled_policy_baseline",
                        "results", "artifacts", "sequence_dataset")


def _ece(model, decisions, n_bins=10, sample=4000):
    """Expected calibration error over single-choice decisions (softmax confidence)."""
    dec = [d for d in decisions if d["form"] == "SINGLE_CHOICE"][:sample]
    confs, corrects = [], []
    for s in range(0, len(dec), 256):
        sub = dec[s:s + 256]
        b = pd.collate(sub)
        scores = model.score_np(b)
        for i, d in enumerate(sub):
            if not d["action"]:
                continue  # declined single-choice (minCount 0) — not calibratable
            n = d["n"]
            z = scores[i, :n] - np.max(scores[i, :n])
            p = np.exp(z); p /= p.sum()
            a = int(np.argmax(p))
            confs.append(float(p[a]))
            corrects.append(int(a == d["action"][0]))
    confs = np.asarray(confs); corrects = np.asarray(corrects)
    if not len(confs):
        return {"ece": None, "n": 0}
    ece = 0.0
    for b in range(n_bins):
        lo, hi = b / n_bins, (b + 1) / n_bins
        m = (confs > lo) & (confs <= hi)
        if m.sum():
            ece += (m.sum() / len(confs)) * abs(corrects[m].mean() - confs[m].mean())
    return {"ece": float(ece), "n": int(len(confs)), "mean_conf": float(confs.mean()),
            "mean_acc": float(corrects.mean())}


def _option_set_sensitivity(model, decisions, sample=400):
    """Fraction of >=3-option decisions whose argmax changes when a NON-argmax legal option
    is removed. An independent scorer would score 0 (removing a non-top option cannot change
    the top); a positive rate proves the cross-option set encoder is used."""
    import copy
    cand = [d for d in decisions if d["n"] >= 3 and d["form"] == "SINGLE_CHOICE"][:sample]
    changed = tested = 0
    for d in cand:
        b = pd.collate([d])
        sc = model.score_np(b)[0, :d["n"]]
        top = int(np.argmax(sc))
        # remove one non-top option (the 2nd-highest, most likely to matter)
        order = np.argsort(-sc)
        drop = int(order[1])
        f = d["feat"]
        keep = [j for j in range(d["n"]) if j != drop]
        f2 = dict(f)
        f2["opt_dense"] = f["opt_dense"][keep]
        f2["opt_rows"] = f["opt_rows"][keep]
        f2["n_options"] = len(keep)
        d2 = dict(d); d2["feat"] = f2; d2["n"] = len(keep)
        b2 = pd.collate([d2])
        sc2 = model.score_np(b2)[0, :len(keep)]
        new_top_orig_idx = keep[int(np.argmax(sc2))]
        tested += 1
        if new_top_orig_idx != top:
            changed += 1
    return {"tested": tested, "argmax_changed_on_option_removal": changed,
            "change_rate": changed / tested if tested else 0.0}


def _latency(model, decisions, sample=1500):
    import time as _t
    dec = decisions[:sample]
    ts = []
    for d in dec:
        b = pd.collate([d])
        t0 = _t.perf_counter_ns()
        model.score_np(b)
        ts.append((_t.perf_counter_ns() - t0) / 1e6)
    a = np.asarray(ts)
    return {"n": len(a), "p50_ms": float(np.percentile(a, 50)),
            "p95_ms": float(np.percentile(a, 95)), "p99_ms": float(np.percentile(a, 99)),
            "mean_ms": float(a.mean())}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--ckpt-dir", default=os.path.join(C007_ART, "checkpoints"))
    p.add_argument("--log-dir", default=os.path.join(os.path.dirname(C007_ART), "test_logs"))
    a = p.parse_args(argv)
    os.makedirs(a.log_dir, exist_ok=True)
    log = open(os.path.join(a.log_dir, "v2_offline_evaluation.txt"), "w")
    t0 = time.time()

    log.write("featurizing c007 test (opened once) + c006 test...\n"); log.flush()
    test = pd.featurize_split(pd.load_split(os.path.join(V2_DATA, "test.jsonl.gz")))
    c006_test = pd.featurize_split(pd.load_split(os.path.join(C006_SEQ, "test.jsonl.gz")))
    log.write(f"c007 test {len(test)} decisions; c006 test {len(c006_test)} decisions\n"); log.flush()

    results = {}
    for arch in ("V2_A", "V2_B"):
        sel = os.path.join(a.ckpt_dir, f"{arch}_selected.npz")
        if not os.path.exists(sel):
            log.write(f"MISSING {sel}\n"); continue
        model = pm.ModelV2.load(sel)
        agr = pd.evaluate_agreement(model, test)
        back = pd.evaluate_agreement(model, c006_test)
        results[arch] = {
            "checkpoint": sel, "param_count": model.param_count(),
            "c007_test": {k: agr[k] for k in ("n", "exact_agreement",
                          "importance_weighted_agreement", "nonforced_agreement")},
            "c007_test_by_importance": agr["by_importance"],
            "c007_test_by_semantic_type": agr["by_semantic_type"],
            "c006_test_backeval": {k: back[k] for k in ("n", "exact_agreement",
                                   "importance_weighted_agreement")},
            "calibration": _ece(model, test),
            "option_set_sensitivity": _option_set_sensitivity(model, test),
            "latency_single_process": _latency(model, test),
        }
        log.write(f"[{arch}] test exact {agr['exact_agreement']:.4f} iw {agr['importance_weighted_agreement']:.4f} "
                  f"| c006 back exact {back['exact_agreement']:.4f} | ECE {results[arch]['calibration']['ece']} "
                  f"| optset change_rate {results[arch]['option_set_sensitivity']['change_rate']:.3f} "
                  f"| P99 {results[arch]['latency_single_process']['p99_ms']:.3f}ms\n")
        log.flush()

    # ablation V2-A vs V2-B
    ablation = None
    if "V2_A" in results and "V2_B" in results:
        a_iw = results["V2_A"]["c007_test"]["importance_weighted_agreement"]
        b_iw = results["V2_B"]["c007_test"]["importance_weighted_agreement"]
        a_hi = results["V2_A"]["c007_test_by_importance"].get("HIGH_IMPACT", {}).get("acc", 0.0)
        b_hi = results["V2_B"]["c007_test_by_importance"].get("HIGH_IMPACT", {}).get("acc", 0.0)
        ablation = {
            "V2A_test_iw": a_iw, "V2B_test_iw": b_iw, "iw_diff_B_minus_A": b_iw - a_iw,
            "V2A_high_impact_acc": a_hi, "V2B_high_impact_acc": b_hi,
            "high_impact_diff_B_minus_A": b_hi - a_hi,
            "privileged_aux_helps": (b_iw - a_iw) > 0.005 or (b_hi - a_hi) > 0.01,
            "interpretation": "does adding privileged planning auxiliary heads improve teacher "
                              "agreement / high-impact agreement?",
        }
        log.write(f"ablation: V2B-V2A iw {b_iw-a_iw:+.4f}, high-impact {b_hi-a_hi:+.4f}, "
                  f"aux_helps={ablation['privileged_aux_helps']}\n")

    out = {"contract": "c007", "results": results, "wall_seconds": round(time.time() - t0, 1)}
    json.dump(out, open(os.path.join(C007_ART, "v2_offline_evaluation.json"), "w"), indent=2)
    json.dump(ablation or {}, open(os.path.join(C007_ART, "v2_ablation.json"), "w"), indent=2)

    # per-context / per-semantic csvs for the selected best (higher test iw)
    best = max(results, key=lambda k: results[k]["c007_test"]["importance_weighted_agreement"]) if results else None
    if best:
        import csv
        with open(os.path.join(C007_ART, "v2_offline_metrics_by_semantic_type.csv"), "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(["semantic_type", "n", "acc"])
            for k, v in results[best]["c007_test_by_semantic_type"].items():
                w.writerow([k, v["n"], round(v["acc"], 4)])
        out["selected_best_by_test_iw"] = best
        json.dump(out, open(os.path.join(C007_ART, "v2_offline_evaluation.json"), "w"), indent=2)
    log.write(f"DONE {out['wall_seconds']}s; best={best}\n"); log.close()
    print(json.dumps({"best": best, "V2_A" if "V2_A" in results else "": results.get("V2_A", {}).get("c007_test"),
                      "V2_B" if "V2_B" in results else "": results.get("V2_B", {}).get("c007_test"),
                      "ablation": ablation}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
