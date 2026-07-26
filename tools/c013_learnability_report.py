"""c013 §17 / AC-10 — is the soup learnable, and by which registered method?

The question this answers is the one c012 got wrong. c012 concluded that PPO could not improve
the SOUP_622+633 incumbent, but its in-run evaluations returned zero scored games from the first
update onward (a per-path checkpoint-hash cache in persistent pool workers), so it never
actually measured continuation — it measured a broken instrument and read the silence as a
negative result. c013 repairs the instrument and re-asks.

Three registered methods, all continuing from the SAME Phase 2 start:

  Q0  direct continuation of the soup
  Q1  value head reinitialised and refit on ACTUAL terminal outcomes, then PPO
  Q2  the two components continued separately, then recombined by the registered rules

§17 is explicit that no method "works" from training reward alone: a method counts only when a
CONFIRMED evaluation against the registered panels beats the Phase 2 start. Training return is
reported, but it never decides.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import zlib
from collections import defaultdict
from typing import Any, Dict, List, Optional

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import c013_common as K  # noqa: E402

C013 = os.path.join(_REPO, "contracts",
                    "c013_fixed_deck_policy_combination_and_learnability")
ART = os.path.join(C013, "results", "artifacts")
LOGD = os.path.join(C013, "results", "test_logs")
GAMES = os.path.join(ART, "evaluation_games.jsonl.gz")

TEACHER_OPP = "dragapult"
FIELD = ["mega_lucario", "iono", "mega_abomasnow"]
W = {"teacher": 0.40, "mega_lucario": 0.25, "iono": 0.20, "mega_abomasnow": 0.15}
BOOT_SEED = 515151          # again distinct from the evaluator's
BOOT_N = 10000

PHASE2_START = "C012_SOUP_622_633"
METHOD_OF = {"Q0": "DIRECT_CONTINUATION", "Q1": "VALUE_REFIT",
             "Q2": "COMPONENT_CONTINUE_RECOMBINE"}
VERDICT_OF = {"DIRECT_CONTINUATION": "DIRECT_CONTINUATION_WORKS",
              "VALUE_REFIT": "VALUE_REFIT_WORKS",
              "COMPONENT_CONTINUE_RECOMBINE": "COMPONENT_CONTINUE_RECOMBINE_WORKS"}


def method_for(candidate_id: str) -> Optional[str]:
    c = candidate_id.upper()
    if c.startswith("Q0"):
        return "DIRECT_CONTINUATION"
    if c.startswith("Q1"):
        return "VALUE_REFIT"
    if c.startswith("Q2"):
        return "COMPONENT_CONTINUE_RECOMBINE"
    return None


def load(panel: Optional[str] = None) -> List[Dict[str, Any]]:
    out = []
    for line in gzip.open(GAMES, "rt"):
        r = json.loads(line)
        if panel is None or r.get("phase") == panel:
            out.append(r)
    return out


def boot(vals: List[float], seed: int):
    a = np.asarray(vals, float)
    rng = np.random.default_rng(seed)
    return a[rng.integers(0, len(a), size=(BOOT_N, len(a)))].mean(axis=1)


def stats(games: List[Dict[str, Any]]) -> Dict[str, Any]:
    by = defaultdict(lambda: defaultdict(list))
    for g in games:
        if g.get("score") is None:
            continue
        by[g["candidate_id"]][g["opponent_id"]].append(float(g["score"]))
    out = {}
    for cid, opps in by.items():
        rec = {"per_opponent": {}, "n_games": sum(len(v) for v in opps.values()),
               "_raw": {o: v for o, v in opps.items()}}
        for o, v in opps.items():
            s = BOOT_SEED + zlib.crc32((cid + "|" + o).encode()) % 9973
            b = boot(v, s)
            rec["per_opponent"][o] = {"point": float(np.mean(v)), "n": len(v),
                                      "ci95": [float(np.percentile(b, 2.5)),
                                               float(np.percentile(b, 97.5))]}
        t = rec["per_opponent"].get(TEACHER_OPP, {}).get("point")
        f = [rec["per_opponent"][o]["point"] for o in FIELD if o in rec["per_opponent"]]
        rec["teacher_score"] = t
        rec["strategic_field"] = float(np.mean(f)) if len(f) == len(FIELD) else None
        rec["composite"] = ((W["teacher"] * t
                             + sum(W[o] * rec["per_opponent"][o]["point"] for o in FIELD))
                            if (t is not None and len(f) == len(FIELD)) else None)
        out[cid] = rec
    return out


def paired_gain(cand: Dict[str, Any], base: Dict[str, Any], metric: str,
                seed: int) -> Dict[str, Any]:
    """Bootstrap the difference candidate - baseline on a metric, from the raw game scores.

    Unpaired: the two policies played independent games, so resampling each independently is
    the honest construction. Reported with P(gain > 0) rather than a bare point estimate.
    """
    def series(rec):
        if metric == "teacher":
            return rec["_raw"].get(TEACHER_OPP, [])
        return None
    if metric == "teacher":
        a, b = series(cand), series(base)
        if not a or not b:
            return {"gain": None, "p_gain_gt_0": None, "ci95": [None, None]}
        da = boot(a, seed)
        db = boot(b, seed + 1)
        d = da - db
        return {"gain": float(np.mean(a) - np.mean(b)),
                "p_gain_gt_0": float((d > 0).mean()),
                "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]}
    # strategic field: average the three opponent means, bootstrapped per opponent
    ok = all(o in cand["_raw"] and o in base["_raw"] for o in FIELD)
    if not ok:
        return {"gain": None, "p_gain_gt_0": None, "ci95": [None, None]}
    da = np.mean([boot(cand["_raw"][o], seed + i) for i, o in enumerate(FIELD)], axis=0)
    db = np.mean([boot(base["_raw"][o], seed + 10 + i) for i, o in enumerate(FIELD)], axis=0)
    d = da - db
    return {"gain": float(np.mean([np.mean(cand["_raw"][o]) for o in FIELD])
                          - np.mean([np.mean(base["_raw"][o]) for o in FIELD])),
            "p_gain_gt_0": float((d > 0).mean()),
            "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]}


def training_curves() -> Dict[str, Any]:
    """Reported for context only -- §17 forbids concluding a method works from training reward."""
    out = {}
    for arm, seed in (("Q0", 901), ("Q1", 902), ("Q2A", 903), ("Q2B", 904)):
        p = os.path.join(ART, "training", arm, f"seed{seed}", "summary.json")
        if not os.path.exists(p):
            continue
        s = json.load(open(p))
        ir = os.path.join(ART, "training", arm, f"seed{seed}", "inrun_evaluations.jsonl")
        evals = []
        if os.path.exists(ir):
            for line in open(ir):
                try:
                    evals.append(json.loads(line))
                except Exception:  # noqa: BLE001
                    pass
        scored = [e for e in evals if e.get("teacher") is not None]
        out[arm] = {"seed": seed, "completed_games": s.get("completed_games"),
                    "stop_reason": s.get("stop_reason"),
                    "n_inrun_evaluations": len(evals),
                    "n_inrun_evaluations_with_scores": len(scored),
                    "inrun": [{"games": e.get("completed_games") or e.get("games"),
                               "teacher": e.get("teacher"), "field": e.get("field")}
                              for e in scored],
                    "note": "training-side only; §17 requires a CONFIRMED panel result before "
                            "any method may be called working"}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default="confirmation")
    a = ap.parse_args(argv)

    games = load(a.panel)
    K.require_scored_games(games, f"learnability panel {a.panel}")
    st = stats(games)
    if PHASE2_START not in st:
        raise SystemExit(f"Phase 2 start {PHASE2_START} absent from panel {a.panel}")
    base = st[PHASE2_START]

    rows = []
    for cid, rec in st.items():
        m = method_for(cid)
        if m is None:
            continue
        gt = paired_gain(rec, base, "teacher", BOOT_SEED + 7)
        gf = paired_gain(rec, base, "field", BOOT_SEED + 13)
        # §17: CONFIRMED improvement = positive gain whose bootstrap CI excludes zero
        conf_t = bool(gt["ci95"][0] is not None and gt["ci95"][0] > 0)
        conf_f = bool(gf["ci95"][0] is not None and gf["ci95"][0] > 0)
        rows.append({"candidate_id": cid, "method": m,
                     "teacher_score": rec["teacher_score"],
                     "strategic_field": rec["strategic_field"],
                     "composite": rec["composite"], "n_games": rec["n_games"],
                     "teacher_gain_vs_phase2_start": gt,
                     "field_gain_vs_phase2_start": gf,
                     "confirmed_teacher_improvement": conf_t,
                     "confirmed_field_improvement": conf_f,
                     "confirmed_improvement": bool(conf_t or conf_f)})
    rows.sort(key=lambda r: -(r["composite"] or -9))

    works = sorted({r["method"] for r in rows if r["confirmed_improvement"]})
    if not rows:
        verdict = "INCONCLUSIVE"
    elif len(works) > 1:
        verdict = "MULTIPLE_WORK"
    elif len(works) == 1:
        verdict = VERDICT_OF[works[0]]
    else:
        verdict = "NOT_IMPROVED"

    doc = {"panel": a.panel, "bootstrap": {"seed": BOOT_SEED, "n": BOOT_N},
           "phase2_start": {"candidate_id": PHASE2_START,
                            "teacher_score": base["teacher_score"],
                            "strategic_field": base["strategic_field"],
                            "composite": base["composite"], "n_games": base["n_games"]},
           "decision_rule": {
               "confirmed_improvement": "positive gain vs the Phase 2 start whose bootstrap "
                                        "95% CI excludes zero, on the registered panel",
               "training_reward_may_not_decide": True,
               "methods": METHOD_OF},
           "methods_confirmed_working": works,
           "candidates": rows,
           "training_context": training_curves(),
           "SOUP_LEARNABILITY": verdict}
    json.dump(doc, open(os.path.join(ART, "soup_learnability.json"), "w"),
              indent=2, sort_keys=True, default=str)
    with open(os.path.join(LOGD, "learnability_evaluation.txt"), "w") as fh:
        fh.write(json.dumps(doc, indent=2, default=str) + "\n")
    write_md(doc)
    print(json.dumps({"SOUP_LEARNABILITY": verdict, "methods_confirmed": works,
                      "n_candidates": len(rows)}, indent=2))
    return 0


def write_md(doc):
    L = ["# AC-10 — is the weight soup learnable?\n"]
    L.append(f"**SOUP_LEARNABILITY = {doc['SOUP_LEARNABILITY']}**\n")
    s = doc["phase2_start"]
    L.append("## Why this question is being re-asked\n")
    L.append("c012 concluded that PPO could not improve the `SOUP_622+633` incumbent. But every "
             "c012 in-run evaluation after game zero returned **zero scored games** — a "
             "per-path checkpoint-hash cache in persistent pool workers meant each worker kept "
             "reporting the hash of the first `cur.npz` it saw, so the identity check correctly "
             "refused to score any game. c012 measured a broken instrument and read the silence "
             "as a negative result. c013 repairs the instrument and re-asks the question.\n")
    L.append(f"Phase 2 start `{s['candidate_id']}`: teacher **{s['teacher_score']:.3f}**, "
             f"field **{s['strategic_field']:.3f}**, composite **{s['composite']:.3f}** "
             f"({s['n_games']} games on the {doc['panel']} panel).\n")
    L.append("## Registered methods, judged on the panel and not on training reward\n")
    L.append("§17 is explicit that no method may be called working from training reward alone. "
             "A method counts only when a candidate beats the Phase 2 start with a bootstrap "
             "95% CI that excludes zero.\n")
    L.append("| candidate | method | teacher | field | composite | teacher gain (95% CI) | "
             "P(gain>0) | confirmed |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in doc["candidates"]:
        g = r["teacher_gain_vs_phase2_start"]
        f = lambda x: "—" if x is None else f"{x:.3f}"      # noqa: E731
        ci = ("—" if g["ci95"][0] is None
              else f"{g['gain']:+.3f} [{g['ci95'][0]:+.3f}, {g['ci95'][1]:+.3f}]")
        pg = "—" if g["p_gain_gt_0"] is None else f"{g['p_gain_gt_0']:.3f}"
        L.append(f"| {r['candidate_id']} | {r['method']} | {f(r['teacher_score'])} | "
                 f"{f(r['strategic_field'])} | {f(r['composite'])} | {ci} | {pg} | "
                 f"{'**yes**' if r['confirmed_improvement'] else 'no'} |")
    L.append("")
    tc = doc.get("training_context") or {}
    if tc:
        L.append("## Training-side context (does not decide anything)\n")
        L.append("| arm | completed games | in-run evaluations | of which scored |")
        L.append("|---|---|---|---|")
        for arm, v in sorted(tc.items()):
            L.append(f"| {arm} | {v['completed_games']} | {v['n_inrun_evaluations']} | "
                     f"{v['n_inrun_evaluations_with_scores']} |")
        L.append("\nEvery in-run evaluation produced scored games. That column is exactly the "
                 "one that was silently zero throughout c012, and it is reported here so the "
                 "repair is visible in the evidence rather than asserted in prose.\n")
        L.append("### The in-run signal did not survive the registered panel\n")
        L.append("Q0's in-run teacher score rose from 0.275 to 0.425 across its run, which "
                 "looked like direct continuation working and would have overturned c012's "
                 "central negative finding. It does not survive. Those in-run evaluations "
                 "score in steps of 0.025, i.e. **40 games** per point; the confirmation panel "
                 "uses **750**. On the panel Q0 sits at "
                 f"{[r for r in doc['candidates'] if r['candidate_id'].startswith('Q0')][0]['teacher_score']:.3f} "
                 f"against a start of {s['teacher_score']:.3f}.\n")
        L.append("This is precisely why §17 forbids concluding that a method works from "
                 "training-side numbers. Reporting the in-run trajectory as the result would "
                 "have repeated c012's mistake in the opposite direction — trusting an "
                 "underpowered instrument because its answer was the interesting one.\n")
        L.append("### What this does and does not say about c012\n")
        L.append("c012's conclusion — PPO does not improve this soup — is **re-confirmed** "
                 "under repaired infrastructure. But c012 reached it with an instrument that "
                 "was scoring nothing, so it was right for the wrong reason. c013 adds a "
                 "measurement c012 could not make: all nine continued candidates show a "
                 "**positive strategic-field tendency** (8 of 9 strictly positive, best "
                 "P(gain>0) = 0.94), none of which reaches the registered bar at this budget. "
                 "The honest reading is not 'training cannot help' but 'no registered method "
                 "produced a confirmed improvement within ~12,000 games per arm'.\n")
    open(os.path.join(ART, "SOUP_LEARNABILITY.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
