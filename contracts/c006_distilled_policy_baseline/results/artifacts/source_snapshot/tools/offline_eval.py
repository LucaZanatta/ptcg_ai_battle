"""c006 AC-07: frozen offline evaluation on the c005 TEST split (opened once here,
after checkpoint selection). Evaluates the selected S1 and S2 checkpoints and the
S2-vs-S1 memory ablation with per-game bootstrap intervals.
"""

import argparse
import collections
import csv
import json
import os
import sys
import time

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from cg import decoders as D
from cg.policy_data import featurize_records, group_by_game, load_split
from cg.policy_model import PolicyModel


def _softmax(x, mask):
    z = x.copy(); z[mask == 0] = -1e30
    z = z - z.max()
    e = np.exp(z)
    return e / e.sum()


def evaluate_model(model, decisions, game_index, recurrent):
    per_dec = []                       # (importance, semantic, context, form, exact, nll, conf, correct_top)
    lat = []
    top2 = [0, 0]; top3 = [0, 0]
    ms_exact = [0, 0]; ms_tp = 0; ms_fp = 0; ms_fn = 0
    fallback = 0; forced = 0
    calib = []                         # (confidence, correct) for single-choice
    for gid, idxs in game_index.items():
        hidden = None
        for i in idxs:
            d = decisions[i]
            feat = {"gdense": d["gdense"], "grows": d["grows"], "odense": d["odense"],
                    "orows": d["orows"], "n_options": d["n"], "prev": d["prev"]}
            t0 = time.perf_counter_ns()
            scores, hidden = model.np_scores(feat, hidden)
            n = d["n"]; lo = d["lo"]; hi = d["hi"]; form = d["form"]
            mask = np.ones(n) if n > 0 else np.zeros(0)
            if d.get("forced_flag"):
                forced += 1
            if form == D.ORDERED:
                pred = frozenset(D.safe_fallback(lo, hi, n)); fallback += 1
            elif n == 0:
                pred = frozenset()
            else:
                pred = frozenset(D.decode(scores, lo, hi, form))
            lat.append(time.perf_counter_ns() - t0)
            exact = int(pred == d["teacher_set"])
            # nll + calibration + topk for single-choice; bce for multi
            nll = 0.0; conf = None
            if form == D.SINGLE_CHOICE and n > 0:
                p = _softmax(scores, mask)
                tgt = d["target_idx"]
                nll = -np.log(p[tgt] + 1e-30)
                conf = float(p.max())
                calib.append((conf, int(np.argmax(p) == tgt)))
                order = np.argsort(-scores)
                top2[1] += 1; top3[1] += 1
                top2[0] += int(tgt in order[:2]); top3[0] += int(tgt in order[:3])
            elif n > 0:  # multiselect
                s = 1.0 / (1.0 + np.exp(-scores))
                t = d["multi_target"]
                nll = float(np.mean(np.log1p(np.exp(-np.abs(scores))) + np.maximum(scores, 0) - scores * t))
                ms_exact[1] += 1; ms_exact[0] += exact
                pset, tset = pred, d["teacher_set"]
                ms_tp += len(pset & tset); ms_fp += len(pset - tset); ms_fn += len(tset - pset)
            per_dec.append({"gid": gid, "importance": d["importance"], "semantic": d["semantic"],
                            "context": d["select_context"], "form": form, "exact": exact,
                            "nll": nll, "weight": d["weight"]})
    lat_ms = np.array(lat) / 1e6
    prec = ms_tp / (ms_tp + ms_fp) if (ms_tp + ms_fp) else 1.0
    rec = ms_tp / (ms_tp + ms_fn) if (ms_tp + ms_fn) else 1.0
    ece = _ece(calib)
    return {"per_dec": per_dec, "n": len(per_dec),
            "overall_exact_agreement": np.mean([p["exact"] for p in per_dec]) if per_dec else 0.0,
            "importance_weighted_agreement": _wmean([p["exact"] for p in per_dec], [p["weight"] for p in per_dec]),
            "nonforced_exact_agreement": np.mean([p["exact"] for p in per_dec if p["weight"] > 0]) if any(p["weight"] > 0 for p in per_dec) else 0.0,
            "top2_agreement_single": top2[0] / top2[1] if top2[1] else None,
            "top3_agreement_single": top3[0] / top3[1] if top3[1] else None,
            "multiselect_exact_set": ms_exact[0] / ms_exact[1] if ms_exact[1] else None,
            "multiselect_element_precision": prec, "multiselect_element_recall": rec,
            "multiselect_element_f1": 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0,
            "multiselect_n": ms_exact[1],
            "test_nll_mean": float(np.mean([p["nll"] for p in per_dec])) if per_dec else 0.0,
            "calibration_ece": ece, "mean_confidence": float(np.mean([c for c, _ in calib])) if calib else None,
            "single_choice_accuracy": float(np.mean([a for _, a in calib])) if calib else None,
            "fallback_decisions": fallback, "forced_bypass_decisions": forced,
            "fallback_rate": fallback / len(per_dec) if per_dec else 0.0,
            "latency_ms": {"p50": float(np.percentile(lat_ms, 50)), "p95": float(np.percentile(lat_ms, 95)),
                           "p99": float(np.percentile(lat_ms, 99)), "max": float(lat_ms.max())}}


def _wmean(vals, w):
    w = np.asarray(w, float); v = np.asarray(vals, float)
    return float((w * v).sum() / w.sum()) if w.sum() > 0 else 0.0


def _ece(calib, bins=10):
    if not calib:
        return None
    conf = np.array([c for c, _ in calib]); corr = np.array([a for _, a in calib])
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for b in range(bins):
        m = (conf >= edges[b]) & (conf < edges[b + 1] if b < bins - 1 else conf <= edges[b + 1])
        if m.sum() > 0:
            ece += m.mean() * abs(conf[m].mean() - corr[m].mean())
    return float(ece)


def by_group(per_dec, key):
    agg = collections.defaultdict(lambda: [0, 0])
    for p in per_dec:
        a = agg[p[key]]; a[1] += 1; a[0] += p["exact"]
    return {k: {"agreement": v[0] / v[1], "n": v[1]} for k, v in sorted(agg.items())}


def game_iw(per_dec):
    """game_id -> importance-weighted agreement (for bootstrap)."""
    g = collections.defaultdict(lambda: [0.0, 0.0])
    for p in per_dec:
        if p["weight"] > 0:
            g[p["gid"]][0] += p["weight"] * p["exact"]; g[p["gid"]][1] += p["weight"]
    return {k: (v[0] / v[1] if v[1] else 0.0) for k, v in g.items()}


def run(args):
    ds = os.path.join(args.in_dir, "sequence_dataset")
    ck = os.path.join(args.in_dir, "checkpoints")
    test = featurize_records(load_split(ds, "test"))
    # mark forced for reporting
    from cg.decision_taxonomy import classify
    for i, d in enumerate(test):
        d["forced_flag"] = (d["weight"] == 0)
    gi = group_by_game(test)

    out = {"contract": "c006_distilled_policy_baseline", "test_opened": True,
           "test_decisions": len(test), "test_games": len(gi), "models": {}}
    results = {}
    for arch, rec in (("S1_STATELESS", False), ("S2_RECURRENT", True)):
        path = os.path.join(ck, f"{arch}_selected.npz")
        model = PolicyModel.load(path)
        r = evaluate_model(model, test, gi, rec)
        r["param_count"] = model.param_count()
        r["model_size_bytes"] = os.path.getsize(path)
        results[arch] = r
        out["models"][arch] = {k: v for k, v in r.items() if k != "per_dec"}

    # memory ablation
    pd1, pd2 = results["S1_STATELESS"]["per_dec"], results["S2_RECURRENT"]["per_dec"]
    hi1 = np.mean([p["exact"] for p in pd1 if p["importance"] == "HIGH_IMPACT"])
    hi2 = np.mean([p["exact"] for p in pd2 if p["importance"] == "HIGH_IMPACT"])
    g1, g2 = game_iw(pd1), game_iw(pd2)
    games = sorted(set(g1) & set(g2))
    diffs = np.array([g2[g] - g1[g] for g in games])
    rng = np.random.default_rng(20260724)
    boot = []
    for _ in range(2000):
        samp = rng.integers(0, len(games), len(games))
        boot.append(diffs[samp].mean())
    lo95 = float(np.percentile(boot, 2.5)); hi95 = float(np.percentile(boot, 97.5))
    hi_gain_pp = float((hi2 - hi1) * 100)
    memory_matters = (hi_gain_pp >= 2.0) or (lo95 > 0.0)
    ablation = {
        "high_impact_test_agreement_S1": float(hi1), "high_impact_test_agreement_S2": float(hi2),
        "high_impact_gain_pp": hi_gain_pp,
        "game_level_iw_agreement_diff_mean": float(diffs.mean()),
        "game_level_iw_diff_ci95": [lo95, hi95],
        "s2_minus_s1_overall_exact": float(results["S2_RECURRENT"]["overall_exact_agreement"]
                                           - results["S1_STATELESS"]["overall_exact_agreement"]),
        "memory_decision_offline": "MEMORY_MATTERS" if memory_matters else "MEMORY_NOT_JUSTIFIED",
        "rule": "MEMORY_MATTERS if high-impact test gain >=2pp OR game-level iw-diff 95% CI lower bound >0 "
                "(gameplay may still promote to MEMORY_MATTERS on material game improvement)",
    }
    out["memory_ablation"] = ablation

    os.makedirs(args.in_dir, exist_ok=True)
    json.dump(out, open(os.path.join(args.in_dir, "offline_evaluation.json"), "w"), indent=2)
    json.dump(ablation, open(os.path.join(args.in_dir, "memory_ablation.json"), "w"), indent=2)

    # by-context / by-semantic CSVs
    for fname, key in (("offline_metrics_by_context.csv", "context"),
                       ("offline_metrics_by_semantic_type.csv", "semantic")):
        with open(os.path.join(args.in_dir, fname), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow([key, "S1_agreement", "S1_n", "S2_agreement", "S2_n"])
            g1 = by_group(pd1, key); g2 = by_group(pd2, key)
            for k in sorted(set(g1) | set(g2)):
                a = g1.get(k, {"agreement": None, "n": 0}); b = g2.get(k, {"agreement": None, "n": 0})
                w.writerow([k, a["agreement"], a["n"], b["agreement"], b["n"]])
    # by-taxonomy summary into the json
    out["agreement_by_taxonomy"] = {a: by_group(results[a]["per_dec"] if False else
                                    (pd1 if a == "S1_STATELESS" else pd2), "importance")
                                    for a in ("S1_STATELESS", "S2_RECURRENT")}
    json.dump(out, open(os.path.join(args.in_dir, "offline_evaluation.json"), "w"), indent=2)

    summary = {a: {"overall": round(out["models"][a]["overall_exact_agreement"], 4),
                   "iw": round(out["models"][a]["importance_weighted_agreement"], 4),
                   "nonforced": round(out["models"][a]["nonforced_exact_agreement"], 4),
                   "high_impact": round(by_group(pd1 if a == "S1_STATELESS" else pd2, "importance").get("HIGH_IMPACT", {}).get("agreement", 0), 4),
                   "p99_ms": round(out["models"][a]["latency_ms"]["p99"], 3),
                   "params": out["models"][a]["param_count"]}
               for a in out["models"]}
    print(json.dumps({"summary": summary, "memory": ablation["memory_decision_offline"],
                      "high_impact_gain_pp": round(hi_gain_pp, 3),
                      "game_iw_diff_ci95": [round(lo95, 4), round(hi95, 4)]}, indent=2))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--in-dir", required=True)
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
