"""c013 AC-05/AC-06 — combination panels, recomputed from raw games.

Every number in the reports this writes is recomputed **from the per-game records**, with a
bootstrap seed deliberately different from the one `c013_eval.py` used. Aggregates that only
ever get copied out of the file that produced them cannot detect a bug in the aggregation, and
c010/c012 both shipped conclusions that a genuine recount would have caught. So the panel
summary files are treated as claims to be checked, not as sources.

§2 forbids treating an online ensemble as equivalent to a weight soup, and forbids tuning
combination weights after seeing results. Both families are reported separately and every
combination carries `weights: equal`; nothing here selects or reweights anything.

Panel roles are kept strictly apart:
  selection     - may choose finalists
  confirmation  - the registered gate panel (Q3 reads this one)
  final         - untouched; it reports, it never selects
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import sys
import zlib
from collections import defaultdict
from typing import Any, Dict, List

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

TEACHER_OPP = "dragapult"      # the opponent id the evaluator records for the frozen teacher
FIELD = ["mega_lucario", "iono", "mega_abomasnow"]
# §30 promotion composite
W = {"teacher": 0.40, "mega_lucario": 0.25, "iono": 0.20, "mega_abomasnow": 0.15}
RECOUNT_BOOT_SEED = 90210          # deliberately NOT c013_eval.py's seed
BOOT_N = 10000


def load(panel: str = None) -> List[Dict[str, Any]]:
    out = []
    for line in gzip.open(GAMES, "rt"):
        r = json.loads(line)
        if panel is None or r.get("phase") == panel:
            out.append(r)
    return out


def boot_ci(vals: List[float], seed: int, n: int = BOOT_N):
    if not vals:
        return None, None, None
    a = np.asarray(vals, float)
    rng = np.random.default_rng(seed)
    m = a[rng.integers(0, len(a), size=(n, len(a)))].mean(axis=1)
    return float(a.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def recompute(games: List[Dict[str, Any]], seed: int = RECOUNT_BOOT_SEED) -> Dict[str, Any]:
    """Independent recount: candidate -> opponent -> statistics, straight from the games."""
    by = defaultdict(lambda: defaultdict(list))
    identity_defects = defaultdict(int)
    for g in games:
        if g.get("score") is None:
            identity_defects[str(g.get("defect"))] += 1
            continue
        by[g["candidate_id"]][g["opponent_id"]].append(float(g["score"]))
    out = {}
    for cid, opps in by.items():
        rec = {"per_opponent": {}, "n_games": sum(len(v) for v in opps.values())}
        for opp, vals in opps.items():
            # zlib.crc32, not hash(): Python randomises str hashing per process, which would
            # make these bootstrap seeds -- and therefore the published CIs -- unreproducible.
            pt, lo, hi = boot_ci(vals, seed + zlib.crc32((cid + "|" + opp).encode()) % 9973)
            rec["per_opponent"][opp] = {"point": pt, "ci95": [lo, hi], "n": len(vals)}
        t = rec["per_opponent"].get(TEACHER_OPP, {}).get("point")
        fvals = [rec["per_opponent"][o]["point"] for o in FIELD
                 if o in rec["per_opponent"] and rec["per_opponent"][o]["point"] is not None]
        rec["teacher_score"] = t
        rec["strategic_field"] = float(np.mean(fvals)) if fvals else None
        if t is not None and len(fvals) == len(FIELD):
            rec["composite"] = (W["teacher"] * t
                                + sum(W[o] * rec["per_opponent"][o]["point"] for o in FIELD))
        else:
            rec["composite"] = None
        rec["candidate_type"] = None
        out[cid] = rec
    return {"candidates": out, "unscored_by_defect": dict(identity_defects)}


def families(reg_path: str) -> Dict[str, str]:
    if not os.path.exists(reg_path):
        return {}
    reg = json.load(open(reg_path))
    fam = {}
    for cid, c in (reg.get("combinations") or {}).items():
        fam[cid] = c.get("candidate_type")
    for cid, c in (reg.get("candidates") or {}).items():
        # honour the type the registry declares. The c012 incumbent is itself a weight soup,
        # and defaulting registered candidates to "single_policy" would have reported it as one.
        fam.setdefault(cid, c.get("candidate_type") or "single_policy")
    return fam


def split_panels() -> Dict[str, str]:
    """AC-05/AC-06 want the raw games for each panel as their own artifact."""
    paths = {}
    for panel, name in (("selection", "combination_selection_games.jsonl.gz"),
                        ("confirmation", "combination_confirmation_games.jsonl.gz"),
                        ("final", "combination_final_games.jsonl.gz")):
        rows = load(panel)
        p = os.path.join(ART, name)
        with gzip.open(p, "wt") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        paths[panel] = p
    return paths


def q3_gate(conf: Dict[str, Any], fam: Dict[str, str]) -> Dict[str, Any]:
    """§16 — an ONLINE ENSEMBLE must beat every TRAINABLE single/soup candidate on the
    CONFIRMATION panel by >=3pp teacher gain or >=3pp strategic-field gain."""
    cands = conf["candidates"]
    ens = {c: v for c, v in cands.items() if fam.get(c) == "online_ensemble"}
    # "every trainable single/soup candidate" = everything that is NOT an online ensemble,
    # minus the frozen teacher. Defined by exclusion on purpose: an allow-list of type names
    # silently shrinks the comparison set whenever a registry spells a type differently
    # ("single" vs "single_policy"), and a smaller comparison set makes the gate EASIER to pass.
    trainable = {c: v for c, v in cands.items()
                 if fam.get(c) != "online_ensemble" and c != "T_teacher"}
    best_tr_t = max((v["teacher_score"] for v in trainable.values()
                     if v["teacher_score"] is not None), default=None)
    best_tr_f = max((v["strategic_field"] for v in trainable.values()
                     if v["strategic_field"] is not None), default=None)
    rows = []
    passed = False
    for c, v in ens.items():
        dt = (v["teacher_score"] - best_tr_t) if (v["teacher_score"] is not None
                                                  and best_tr_t is not None) else None
        df = (v["strategic_field"] - best_tr_f) if (v["strategic_field"] is not None
                                                    and best_tr_f is not None) else None
        ok = bool((dt is not None and dt >= 0.03) or (df is not None and df >= 0.03))
        passed = passed or ok
        rows.append({"ensemble": c, "teacher": v["teacher_score"],
                     "field": v["strategic_field"], "teacher_gain_vs_best_trainable": dt,
                     "field_gain_vs_best_trainable": df, "passes": ok})
    return {"panel": "confirmation",
            "rule": "online ensemble must beat EVERY trainable single/soup candidate by "
                    ">=0.03 teacher gain or >=0.03 strategic-field gain (§16)",
            "best_trainable_teacher": best_tr_t, "best_trainable_field": best_tr_f,
            "n_ensembles_evaluated": len(ens), "n_trainable_compared": len(trainable),
            "per_ensemble": sorted(rows, key=lambda r: -(r["teacher_gain_vs_best_trainable"]
                                                         or -9)),
            "GATE": "PASS" if passed else "FAIL",
            "Q3": "RUN" if passed else "SKIPPED_BY_GATE"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="report", choices=["report"])
    ap.parse_args(argv)
    os.makedirs(ART, exist_ok=True)
    os.makedirs(LOGD, exist_ok=True)
    fam = families(os.path.join(ART, "combination_registry.json"))
    fam.update(families(os.path.join(ART, "candidate_registry.json")))

    paths = split_panels()
    per_panel = {}
    for panel in ("selection", "confirmation", "final"):
        games = load(panel)
        rc = recompute(games)
        K.require_scored_games(games, f"combination panel {panel}")
        per_panel[panel] = rc

    # cross-check the recount against the summaries c013_eval.py wrote
    disagreements = []
    for panel in per_panel:
        sp = os.path.join(ART, f"panel_{panel}_summaries.json")
        if not os.path.exists(sp):
            continue
        claimed = json.load(open(sp))
        for cid, c in claimed.items():
            mine = per_panel[panel]["candidates"].get(cid)
            if not mine:
                continue
            for opp, o in (c.get("per_opponent") or {}).items():
                m = mine["per_opponent"].get(opp)
                if m and o.get("point") is not None and m["point"] is not None:
                    if abs(o["point"] - m["point"]) > 1e-9:
                        disagreements.append({"panel": panel, "candidate": cid,
                                              "opponent": opp, "claimed": o["point"],
                                              "recomputed": m["point"]})

    gate = q3_gate(per_panel["confirmation"], fam)

    fin = per_panel["final"]["candidates"]
    ranked = sorted([c for c in fin if fin[c]["composite"] is not None],
                    key=lambda c: -fin[c]["composite"])
    winner_family = None
    non_teacher = [c for c in ranked if c != "T_teacher"]
    if non_teacher:
        winner_family = fam.get(non_teacher[0], "single_policy")
    result = ("ONLINE_ENSEMBLE_WINS" if winner_family == "online_ensemble"
              else "WEIGHT_SOUP_WINS" if winner_family == "weight_soup"
              else "SINGLE_POLICY_WINS" if winner_family else "INCONCLUSIVE")

    doc = {"recount": {"bootstrap_seed": RECOUNT_BOOT_SEED,
                       "note": "aggregates recomputed from raw per-game records with a seed "
                               "different from the evaluator's; summaries are checked, not "
                               "trusted"},
           "panel_games": {k: os.path.relpath(v, _REPO) for k, v in paths.items()},
           "panels": per_panel,
           "families": fam,
           "summary_recount_disagreements": disagreements,
           "q3_gate": gate,
           "COMBINATION_RESULT": result,
           "winner": non_teacher[0] if non_teacher else None,
           "winner_family": winner_family,
           "ranking_final_panel": [{"candidate_id": c, "family": fam.get(c, "single_policy"),
                                    "composite": fin[c]["composite"],
                                    "teacher": fin[c]["teacher_score"],
                                    "field": fin[c]["strategic_field"]} for c in ranked]}
    json.dump(doc, open(os.path.join(ART, "combination_results.json"), "w"),
              indent=2, sort_keys=True, default=str)

    # AC-06 final panel artifacts
    with open(os.path.join(ART, "combination_final_matrix.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        opps = [TEACHER_OPP] + FIELD
        w.writerow(["candidate_id", "family"] + opps + ["teacher", "strategic_field",
                                                        "composite", "n_games"])
        for c in ranked:
            v = fin[c]
            w.writerow([c, fam.get(c, "single_policy")]
                       + [(v["per_opponent"].get(o) or {}).get("point") for o in opps]
                       + [v["teacher_score"], v["strategic_field"], v["composite"],
                          v["n_games"]])
    json.dump({c: {"family": fam.get(c, "single_policy"),
                   "per_opponent": fin[c]["per_opponent"],
                   "composite": fin[c]["composite"]} for c in ranked},
              open(os.path.join(ART, "combination_final_intervals.json"), "w"),
              indent=2, default=str)

    write_md(doc, fin, fam, ranked)
    for name, panels in (("combination_evaluation.txt", ("selection", "confirmation")),
                         ("combination_final_panel.txt", ("final",))):
        with open(os.path.join(LOGD, name), "w") as fh:
            for p in panels:
                fh.write(f"=== panel {p} ===\n")
                fh.write(json.dumps(per_panel[p], indent=2, default=str) + "\n")
            if "confirmation" in panels:
                fh.write("=== Q3 gate ===\n" + json.dumps(gate, indent=2, default=str) + "\n")
            fh.write(f"summary/recount disagreements: {len(disagreements)}\n")
    print(json.dumps({"COMBINATION_RESULT": result, "winner": doc["winner"],
                      "winner_family": winner_family, "Q3": gate["Q3"],
                      "recount_disagreements": len(disagreements)}, indent=2))
    return 0


def write_md(doc, fin, fam, ranked):
    L = ["# AC-05 / AC-06 — combination families on the registered panels\n"]
    L.append(f"**COMBINATION_RESULT = {doc['COMBINATION_RESULT']}** "
             f"(winner `{doc['winner']}`, family `{doc['winner_family']}`)\n")
    L.append("Every number below is recomputed from the raw per-game records with bootstrap "
             f"seed {RECOUNT_BOOT_SEED}, which is not the seed the evaluator used. The panel "
             "summary files are cross-checked against this recount rather than quoted: "
             f"**{len(doc['summary_recount_disagreements'])}** disagreements found.\n")
    L.append("## Why the two families are reported separately\n")
    L.append("A weight soup evaluates ONE network at averaged parameters; an online ensemble "
             "evaluates every component and combines their outputs. For a non-linear network "
             "these are different functions — `tests/test_c013_ensemble_math.py` demonstrates "
             "it numerically — so §2 forbids treating them as interchangeable. All weights are "
             "equal and were never tuned after results.\n")
    L.append("## Final panel — untouched, reports but never selects\n")
    L.append("| rank | candidate | family | teacher | field | composite |")
    L.append("|---|---|---|---|---|---|")
    for i, c in enumerate(ranked, 1):
        v = fin[c]
        f = lambda x: "—" if x is None else f"{x:.3f}"  # noqa: E731
        L.append(f"| {i} | {c} | {fam.get(c, 'single_policy')} | {f(v['teacher_score'])} | "
                 f"{f(v['strategic_field'])} | {f(v['composite'])} |")
    g = doc["q3_gate"]
    L.append(f"\n## Q3 gate (§16), read from the **confirmation** panel\n")
    L.append(f"`{g['rule']}`\n")
    L.append(f"Best trainable single/soup on confirmation: teacher {g['best_trainable_teacher']}, "
             f"field {g['best_trainable_field']}. Ensembles evaluated: "
             f"{g['n_ensembles_evaluated']}.\n")
    L.append("| ensemble | teacher | field | teacher gain | field gain | passes |")
    L.append("|---|---|---|---|---|---|")
    for r in g["per_ensemble"]:
        f = lambda x: "—" if x is None else f"{x:+.3f}"  # noqa: E731
        p = lambda x: "—" if x is None else f"{x:.3f}"   # noqa: E731
        L.append(f"| {r['ensemble']} | {p(r['teacher'])} | {p(r['field'])} | "
                 f"{f(r['teacher_gain_vs_best_trainable'])} | "
                 f"{f(r['field_gain_vs_best_trainable'])} | {r['passes']} |")
    L.append(f"\n**GATE = {g['GATE']} → Q3 = {g['Q3']}**\n")
    open(os.path.join(ART, "COMBINATION_RESULT.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
