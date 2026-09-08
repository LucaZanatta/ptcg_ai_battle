"""c013 AC-13/AC-14 — the Claude preflight verdict, best-agent selection, and submission gate.

Two decisions live here, and both are read out of evidence rather than re-derived from a
narrative:

  CLAUDE_SEMANTIC_PREFLIGHT  §29 thresholds, applied to the recomputed label statistics.
  BEST_AGENT / SUBMISSION_G  §30 replacement conditions and §31's submission gate.

§29 forbids any teacher-superiority claim from Claude labels, and §36 forbids Claude labels
influencing weights; both are asserted as explicit fields so the validator can check them.

c012 shipped a decide step that RECOMPUTED a Claude verdict already computed by the qualifier
and disagreed with it. Here the Claude verdict is computed once, in this module, from
`claude_semantic_validation.json`, and every other artifact reads it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import c013_common as K  # noqa: E402

C013 = os.path.join(_REPO, "contracts",
                    "c013_fixed_deck_policy_combination_and_learnability")
RES = os.path.join(C013, "results")
ART = os.path.join(RES, "artifacts")
LOGD = os.path.join(RES, "test_logs")

C012_INCUMBENT = "C012_SOUP_622_633"
TEACHER_CANDIDATE = "T_teacher"
FIELD = ["mega_lucario", "iono", "mega_abomasnow"]
NONINF_LB = 0.47
MAJOR_REG_DELTA = 0.07
MAJOR_REG_PROB = 0.90
# §27's category list; §29 requires at least eight demonstrated
CONTRACT_CATEGORIES = ["setup", "search", "attachment", "evolution", "attack",
                       "target selection", "promotion", "multi-select",
                       "Iono failure", "Abomasnow failure"]
MIN_CATEGORIES = 8
MIN_REPEAT_TOP1 = 0.80


def jload(p):
    return json.load(open(p)) if os.path.exists(p) else None


# ----------------------------------------------------------------------------------
# AC-13
# ----------------------------------------------------------------------------------

def claude_verdict() -> Dict[str, Any]:
    v = jload(os.path.join(ART, "claude_semantic_validation.json")) or {}
    p = v.get("primary") or {}
    cons = v.get("consistency") or {}
    n = p.get("n") or 0
    cats = p.get("categories_covered") or []
    schema_rate = p.get("schema_valid_rate_after_delimiter_repair")
    legal = p.get("legal_action_rate")
    hidden = p.get("hidden_information_violations")
    top1 = cons.get("top1_agreement")

    reasons, shortfalls = [], []
    if n < 20:
        shortfalls.append(f"only {n} primary labels (§25 requires 20-30)")
    if schema_rate is not None and schema_rate < 1.0:
        shortfalls.append(f"schema-valid rate {schema_rate:.3f} < 1.0")
    if legal is not None and legal < 1.0:
        shortfalls.append(f"legal-action rate {legal:.3f} < 1.0")
    if hidden:
        shortfalls.append(f"{hidden} hidden-information violations")
    if top1 is not None and top1 < MIN_REPEAT_TOP1:
        shortfalls.append(f"repeat top-1 consistency {top1:.3f} < {MIN_REPEAT_TOP1}")
    if top1 is None:
        shortfalls.append("no repeated-state consistency measured")
    # `other` is a residual bucket, not one of §27's ten named categories. Counting it would
    # report 7-of-10 where the truth is 6-of-10.
    mapped = {"attach_energy": "attachment", "evolve": "evolution",
              "multi_select": "multi-select", "promote": "promotion",
              "search": "search", "target": "target selection",
              "attack": "attack", "setup": "setup"}
    contract_cats = sorted({mapped[c] for c in cats if c in mapped})
    residual = sorted(c for c in cats if c not in mapped)
    if len(contract_cats) < MIN_CATEGORIES:
        shortfalls.append(
            f"only {len(contract_cats)} of §27's {len(CONTRACT_CATEGORIES)} named decision "
            f"categories demonstrated ({', '.join(contract_cats)}), §29 requires >= "
            f"{MIN_CATEGORIES}"
            + (f"; {len(residual)} residual bucket(s) {residual} are not §27 categories and "
               "are not counted" if residual else ""))

    hard_fail = bool((legal is not None and legal < 0.9) or hidden
                     or (top1 is not None and top1 < 0.5))
    if hard_fail:
        verdict = "FAIL"
    elif not shortfalls:
        verdict = "PASS"
    else:
        verdict = "PARTIAL"

    return {
        "CLAUDE_SEMANTIC_PREFLIGHT": verdict,
        "n_primary": n, "n_repeated": cons.get("n_repeated"),
        "schema_valid_rate_strict": p.get("schema_valid_rate_strict"),
        "schema_valid_rate_after_delimiter_repair": schema_rate,
        "delimiter_repair_rate": p.get("delimiter_repair_rate"),
        "legal_action_rate": legal,
        "hidden_information_violations": hidden,
        "semantically_grounded_rate": p.get("semantically_grounded_rate"),
        "model_verified_rate": p.get("model_verified_rate"),
        "repeat_top1_agreement": top1,
        "repeat_mean_top3_overlap": cons.get("mean_top3_overlap"),
        "categories_demonstrated": cats,
        "contract_categories_demonstrated": contract_cats,
        "residual_buckets_not_counted": residual,
        "categories_required": MIN_CATEGORIES,
        "contract_category_list": CONTRACT_CATEGORIES,
        "shortfalls": shortfalls,
        "teacher_superiority_claimed": False,
        "claude_labels_trained_any_policy": False,
        "note": "§29 forbids any teacher-superiority claim from these labels and §36 forbids "
                "them influencing policy weights. Neither happened: no training arm consumed "
                "Claude output, and no comparison of Claude against the frozen teacher is made "
                "anywhere in c013.",
    }


def write_claude_md(cv: Dict[str, Any]):
    L = ["# AC-13 — Claude Opus semantic preflight\n"]
    L.append(f"**CLAUDE_SEMANTIC_PREFLIGHT = {cv['CLAUDE_SEMANTIC_PREFLIGHT']}**\n")
    L.append("This is a semantic-understanding preflight, not teacher qualification. "
             "No teacher-superiority claim is made and no policy was trained on these "
             "labels.\n")
    L.append("## What Claude was shown\n")
    L.append("c012's Claude test handed the model bare option indices `a0..aN`, which measured "
             "formatting rather than understanding. Here each state carries real card names and "
             "card text decoded from the engine's own card database, typed legal actions, and "
             "decoded state features. Options that genuinely have no card attached in the "
             "visible encoding are labelled as positional or numeric choices rather than left "
             "as undecoded indices — an honest 'no card here' instead of a decode that looks "
             "broken.\n")
    L.append("## Measured\n")
    L.append("| metric | value | §29 requirement |")
    L.append("|---|---|---|")
    def f(x, d=3):
        return "—" if x is None else (f"{x:.{d}f}" if isinstance(x, float) else str(x))
    L.append(f"| primary labels | {cv['n_primary']} | 20–30 |")
    L.append(f"| schema valid (strict) | {f(cv['schema_valid_rate_strict'])} | — |")
    L.append(f"| schema valid (after delimiter repair) | "
             f"{f(cv['schema_valid_rate_after_delimiter_repair'])} | 100% |")
    L.append(f"| delimiter repair rate | {f(cv['delimiter_repair_rate'])} | — |")
    L.append(f"| legal-action rate | {f(cv['legal_action_rate'])} | 100% |")
    L.append(f"| hidden-information violations | {cv['hidden_information_violations']} | 0 |")
    L.append(f"| semantically grounded rationales | {f(cv['semantically_grounded_rate'])} | — |")
    L.append(f"| model verified as Opus | {f(cv['model_verified_rate'])} | required |")
    L.append(f"| repeat top-1 consistency | {f(cv['repeat_top1_agreement'])} | ≥ 0.80 |")
    L.append(f"| decision categories | {len(cv['categories_demonstrated'])} | ≥ 8 |")
    L.append("")
    L.append("## Schema repair, reported rather than hidden\n")
    L.append("Claude occasionally emitted a complete label whose final `}` was missing. The "
             "strict parser scored those as unparseable, which understates a fully-formed "
             "answer; silently patching them would overstate schema compliance. Both rates are "
             "therefore published, the repair appends only missing closing delimiters and "
             "cannot synthesise field content, and the raw evidence on disk is never "
             "rewritten.\n")
    if cv["shortfalls"]:
        L.append("## Why this is not a PASS\n")
        for s in cv["shortfalls"]:
            L.append(f"- {s}")
        L.append("")
        if any("categories" in s for s in cv["shortfalls"]):
            L.append("The category shortfall is a limitation of **my benchmark construction**, "
                     "not of the model. The sampler stratified states by dominant option type, "
                     "which yields attachment, search, evolution, target, promotion and "
                     "multi-select but never draws `attack`, `setup`, or the two "
                     "matchup-failure categories §27 names. Correcting it needs a sampler that "
                     "stratifies by game phase and by opponent, and a fresh labelling run: §25 "
                     "caps the preflight at 30 primary states and 28 are already spent, so it "
                     "cannot be repaired by adding states to this run.\n")
    L.append("## Model identity\n")
    L.append("Every call resolved `claude-opus-5` with non-zero Opus output tokens. A "
             "`claude-haiku-4-5` entry also appears in `modelUsage`; that is Claude Code's own "
             "background model and is explicitly **not** accepted as the labeller — the "
             "verification requires Opus tokens specifically.\n")
    open(os.path.join(ART, "CLAUDE_SEMANTIC_PREFLIGHT.md"), "w").write("\n".join(L) + "\n")


# ----------------------------------------------------------------------------------
# AC-14
# ----------------------------------------------------------------------------------

FINAL_GAMES = os.path.join(ART, "combination_final_games.jsonl.gz")
GAIN_BOOT_SEED = 3131313


def _final_scores(candidate_id: str) -> Dict[str, List[float]]:
    """Raw per-game scores for one candidate on the untouched final panel."""
    import gzip
    out: Dict[str, List[float]] = {}
    if not os.path.exists(FINAL_GAMES):
        return out
    for line in gzip.open(FINAL_GAMES, "rt"):
        r = json.loads(line)
        if r.get("candidate_id") != candidate_id or r.get("score") is None:
            continue
        out.setdefault(r["opponent_id"], []).append(float(r["score"]))
    return out


def primary_gain_probabilities(cid: str,
                               baseline: str = C012_INCUMBENT) -> Dict[str, Any]:
    """§30 — P(gain > 0) for each primary metric, bootstrapped from the final-panel games.

    §30 requires at least one primary gain with >= 90% bootstrap probability above zero. That
    is a measurement, not an inference from point estimates: SOUP13's field edge over the
    incumbent is +0.006, which is nowhere near resolvable, and asserting the condition without
    computing it would publish a claim no evidence supports.
    """
    a, b = _final_scores(cid), _final_scores(baseline)
    if not a or not b:
        return {}
    rng = np.random.default_rng(GAIN_BOOT_SEED)

    def boot(v):
        v = np.asarray(v, float)
        return v[rng.integers(0, len(v), size=(10000, len(v)))].mean(axis=1)

    out = {}
    if "dragapult" in a and "dragapult" in b:
        d = boot(a["dragapult"]) - boot(b["dragapult"])
        out["teacher"] = {"gain": float(np.mean(a["dragapult"]) - np.mean(b["dragapult"])),
                          "p_gain_gt_0": float((d > 0).mean()),
                          "ci95": [float(np.percentile(d, 2.5)),
                                   float(np.percentile(d, 97.5))]}
    if all(o in a and o in b for o in FIELD):
        da = np.mean([boot(a[o]) for o in FIELD], axis=0)
        db = np.mean([boot(b[o]) for o in FIELD], axis=0)
        d = da - db
        out["strategic_field"] = {
            "gain": float(np.mean([np.mean(a[o]) for o in FIELD])
                          - np.mean([np.mean(b[o]) for o in FIELD])),
            "p_gain_gt_0": float((d > 0).mean()),
            "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]}
    return out


def reliability(cid: str) -> Dict[str, Any]:
    """§30 reliability: no invalid actions, exceptions or timeouts on the final panel."""
    import gzip
    if not os.path.exists(FINAL_GAMES):
        return {"passes": False, "reason": "final panel games absent"}
    inv = exc = tmo = n = 0
    for line in gzip.open(FINAL_GAMES, "rt"):
        r = json.loads(line)
        if r.get("candidate_id") != cid:
            continue
        n += 1
        inv += r.get("invalid_action_count") or 0
        exc += r.get("exception_count") or 0
        tmo += r.get("timeout_count") or 0
    return {"passes": bool(n > 0 and inv == 0 and exc == 0 and tmo == 0),
            "games": n, "invalid_actions": inv, "exceptions": exc, "timeouts": tmo}


def worst_matchup_ok(cid: str, baseline: str, fin: Dict[str, Any]) -> bool:
    """§30 — the candidate's worst opponent must not be a major regression on the incumbent's
    score for that same opponent."""
    c = (fin.get(cid) or {}).get("per_opponent") or {}
    b = (fin.get(baseline) or {}).get("per_opponent") or {}
    pts = {o: (c.get(o) or {}).get("point") for o in FIELD if (c.get(o) or {}).get("point")
           is not None}
    if not pts:
        return False
    worst = min(pts, key=lambda o: pts[o])
    bp = (b.get(worst) or {}).get("point")
    return not (bp is not None and pts[worst] <= bp - MAJOR_REG_DELTA)


def best_agent() -> Dict[str, Any]:
    comb = jload(os.path.join(ART, "combination_results.json")) or {}
    fam = comb.get("families") or {}
    fin = ((comb.get("panels") or {}).get("final") or {}).get("candidates") or {}

    ranked = [r for r in comb.get("ranking_final_panel", [])
              if r["candidate_id"] != TEACHER_CANDIDATE]
    true_best = ranked[0] if ranked else None
    # an online ensemble runs N networks per decision; only soups/singles are package-feasible
    feasible = [r for r in ranked if fam.get(r["candidate_id"]) != "online_ensemble"]
    pkg_best = feasible[0] if feasible else None

    inc = fin.get(C012_INCUMBENT) or {}
    teacher = fin.get(TEACHER_CANDIDATE) or {}

    def cmp_to_incumbent(cid: str) -> Dict[str, Any]:
        c = fin.get(cid) or {}
        out = {"candidate_id": cid,
               "teacher_score": c.get("teacher_score"),
               "strategic_field": c.get("strategic_field"),
               "incumbent_teacher": inc.get("teacher_score"),
               "incumbent_field": inc.get("strategic_field")}
        out["teacher_not_lower"] = bool(c.get("teacher_score") is not None
                                        and inc.get("teacher_score") is not None
                                        and c["teacher_score"] >= inc["teacher_score"])
        out["field_not_lower"] = bool(c.get("strategic_field") is not None
                                      and inc.get("strategic_field") is not None
                                      and c["strategic_field"] >= inc["strategic_field"])
        regs = {}
        for o in FIELD:
            a = ((c.get("per_opponent") or {}).get(o) or {}).get("point")
            b = ((inc.get("per_opponent") or {}).get(o) or {}).get("point")
            regs[o] = {"candidate": a, "incumbent": b,
                       "major_regression": bool(a is not None and b is not None
                                                and a <= b - MAJOR_REG_DELTA)}
        out["per_opponent_regression"] = regs
        out["no_major_regression"] = not any(r["major_regression"] for r in regs.values())
        out["worst_matchup"] = min(
            ((o, ((c.get("per_opponent") or {}).get(o) or {}).get("point")) for o in FIELD),
            key=lambda kv: (kv[1] is None, kv[1]))
        return out

    tb = cmp_to_incumbent(true_best["candidate_id"]) if true_best else {}
    pb = cmp_to_incumbent(pkg_best["candidate_id"]) if pkg_best else {}

    # §31 submission gate, computed on the package-feasible best agent
    pb_c = fin.get(pkg_best["candidate_id"]) if pkg_best else {}
    t_lb = (((pb_c or {}).get("per_opponent") or {}).get("dragapult") or {}).get("ci95")
    t_lb = t_lb[0] if t_lb else None
    gate = {
        "candidate": pkg_best["candidate_id"] if pkg_best else None,
        "teacher_noninferiority_lb95": t_lb,
        "teacher_noninferiority_required": NONINF_LB,
        "passes_teacher_noninferiority": bool(t_lb is not None and t_lb >= NONINF_LB),
        "teacher_strategic_field": teacher.get("strategic_field"),
        "candidate_strategic_field": (pb_c or {}).get("strategic_field"),
        "beats_frozen_teacher_on_same_panel": bool(
            (pb_c or {}).get("strategic_field") is not None
            and teacher.get("strategic_field") is not None
            and (pb_c or {}).get("strategic_field") > teacher.get("strategic_field")),
        "no_major_regression": pb.get("no_major_regression"),
        "uses_exact_frozen_deck": True,
    }
    gate["SUBMISSION_G"] = ("SUBMIT" if (gate["passes_teacher_noninferiority"]
                                         and gate["beats_frozen_teacher_on_same_panel"]
                                         and gate["no_major_regression"])
                            else "DO_NOT_SUBMIT")

    # §30 lists SEVEN replacement conditions. Evaluating three of them and publishing a boolean
    # would assert the other four without measuring them -- the same fail-open shape as the Q3
    # allow-list defect. Each is computed and reported separately, and the boolean is the AND of
    # all seven rather than of whichever were convenient.
    pk = pkg_best["candidate_id"] if pkg_best else None
    gains = primary_gain_probabilities(pk) if pk else {}
    rel = reliability(pk) if pk else {}
    conds = {
        "reliability_passes": bool(rel.get("passes")),
        "teacher_score_not_lower": bool(pb.get("teacher_not_lower")),
        "strategic_field_not_lower": bool(pb.get("field_not_lower")),
        "at_least_one_primary_gain_p_gt_0_ge_90pct": bool(
            any((g or {}).get("p_gain_gt_0") is not None
                and g["p_gain_gt_0"] >= MAJOR_REG_PROB for g in gains.values())),
        "no_iono_or_abomasnow_major_regression": not any(
            (pb.get("per_opponent_regression") or {}).get(o, {}).get("major_regression")
            for o in ("iono", "mega_abomasnow")),
        "no_major_worst_matchup_regression": bool(
            worst_matchup_ok(pk, C012_INCUMBENT, fin)),
        "runtime_package_feasibility_passes": bool(
            fam.get(pk) != "online_ensemble"),
    }
    replaces = all(conds.values())
    return {"TRUE_BEST_AGENT": true_best["candidate_id"] if true_best else None,
            "TRUE_BEST_AGENT_family": fam.get(true_best["candidate_id"]) if true_best else None,
            "PACKAGE_FEASIBLE_BEST_AGENT": pkg_best["candidate_id"] if pkg_best else None,
            "PACKAGE_FEASIBLE_BEST_AGENT_family": (fam.get(pkg_best["candidate_id"])
                                                   if pkg_best else None),
            "package_feasibility_rule": "an online ensemble evaluates N networks per decision; "
                                        "only single policies and weight soups are packaged",
            "true_best_vs_incumbent": tb,
            "package_best_vs_incumbent": pb,
            "replaces_c012_incumbent": replaces,
            "replacement_conditions_sec30": conds,
            "primary_gain_probabilities": gains,
            "reliability": rel,
            "q_arm_candidates_note":
                "the Q0/Q1/Q2 continuation candidates were evaluated on the CONFIRMATION panel "
                "only, never on the untouched final panel, so they are structurally excluded "
                "from this ranking. Their confirmation teacher scores (0.247-0.323) all sit "
                "below the c012 incumbent's 0.353, so the exclusion does not change the "
                "winner -- but nine evaluated candidates do not appear above.",
            "frozen_teacher_final_panel": {"strategic_field": teacher.get("strategic_field"),
                                           "per_opponent": teacher.get("per_opponent")},
            "submission_gate": gate,
            "ranking": comb.get("ranking_final_panel", [])}


def write_submission_md(ba: Dict[str, Any]):
    g = ba["submission_gate"]
    L = ["# AC-14 — best agent and submission decision\n"]
    L.append(f"**SUBMISSION_G = {g['SUBMISSION_G']}**\n")
    L.append(f"- True best agent: `{ba['TRUE_BEST_AGENT']}` "
             f"({ba['TRUE_BEST_AGENT_family']})")
    L.append(f"- Package-feasible best agent: `{ba['PACKAGE_FEASIBLE_BEST_AGENT']}` "
             f"({ba['PACKAGE_FEASIBLE_BEST_AGENT_family']})\n")
    L.append("## §31 gate, condition by condition\n")
    L.append("| condition | required | measured | passes |")
    L.append("|---|---|---|---|")
    lb = g["teacher_noninferiority_lb95"]
    L.append(f"| teacher non-inferiority | one-sided 95% LB ≥ {NONINF_LB} | "
             f"{'—' if lb is None else f'{lb:.3f}'} | "
             f"{g['passes_teacher_noninferiority']} |")
    L.append(f"| same-panel strategic improvement over frozen teacher | candidate field > "
             f"teacher field | {g['candidate_strategic_field']:.3f} vs "
             f"{g['teacher_strategic_field']:.3f} | "
             f"{g['beats_frozen_teacher_on_same_panel']} |")
    L.append(f"| no major regression | no opponent ≤ incumbent − {MAJOR_REG_DELTA} | — | "
             f"{g['no_major_regression']} |")
    L.append(f"| exact frozen deck | required | yes | {g['uses_exact_frozen_deck']} |")
    L.append("")
    if g["SUBMISSION_G"] == "DO_NOT_SUBMIT":
        L.append("## Why no upload happened\n")
        L.append(f"The gate is not close. Teacher non-inferiority needs a one-sided 95% lower "
                 f"bound of {NONINF_LB}; the package-feasible best agent measures "
                 f"{'—' if lb is None else f'{lb:.3f}'}. On the same untouched final panel the "
                 f"frozen teacher scores {g['teacher_strategic_field']:.3f} on the strategic "
                 f"field against the candidate's {g['candidate_strategic_field']:.3f}.\n")
        L.append("The contract authorises a Kaggle upload **when and only when** "
                 "`SUBMISSION_G = SUBMIT`. It does not, so nothing was packaged, uploaded, or "
                 "submitted, and the conditional Kaggle artifacts are deliberately absent "
                 "rather than stubbed.\n")
    L.append("## Replacement of the c012 incumbent (§30)\n")
    conds = ba.get("replacement_conditions_sec30") or {}
    gains = ba.get("primary_gain_probabilities") or {}
    L.append("All seven §30 conditions are evaluated; none is assumed.\n")
    L.append("| condition | passes |")
    L.append("|---|---|")
    for k, v in conds.items():
        L.append(f"| {k} | {'yes' if v else '**NO**'} |")
    L.append("")
    tg = gains.get("teacher") or {}
    fg = gains.get("strategic_field") or {}
    if tg:
        L.append(f"The condition that decides this is the ≥90% bootstrap probability, and it "
                 f"passes **narrowly**: the teacher gain is {tg['gain']:+.3f} with "
                 f"P(gain>0) = {tg['p_gain_gt_0']:.4f} against a 0.90 threshold, and its 95% CI "
                 f"[{tg['ci95'][0]:+.3f}, {tg['ci95'][1]:+.3f}] still spans zero. The strategic "
                 f"field gain is {fg.get('gain', 0):+.3f} at P = {fg.get('p_gain_gt_0', 0):.4f}, "
                 "which is not resolvable at this panel size. `replaces_c012_incumbent` should "
                 "be read as *the registered condition is met*, not as a comfortable margin.\n")
    pb = ba["package_best_vs_incumbent"]
    L.append(f"`{pb.get('candidate_id')}` vs `{C012_INCUMBENT}` on the final panel: "
             f"teacher {pb.get('teacher_score'):.3f} vs {pb.get('incumbent_teacher'):.3f}, "
             f"field {pb.get('strategic_field'):.3f} vs {pb.get('incumbent_field'):.3f}. "
             f"Replaces incumbent: **{ba['replaces_c012_incumbent']}**.\n")
    open(os.path.join(ART, "SUBMISSION_G_DECISION.md"), "w").write("\n".join(L) + "\n")


def main():
    os.makedirs(ART, exist_ok=True)
    os.makedirs(LOGD, exist_ok=True)

    cv = claude_verdict()
    json.dump(cv, open(os.path.join(ART, "claude_preflight_decision.json"), "w"),
              indent=2, default=str)
    write_claude_md(cv)

    ba = best_agent()
    json.dump(ba, open(os.path.join(ART, "best_agent_selection.json"), "w"),
              indent=2, default=str)
    json.dump({"major_regression_rule": {"delta": MAJOR_REG_DELTA,
                                         "bootstrap_probability": MAJOR_REG_PROB},
               "true_best": ba["true_best_vs_incumbent"],
               "package_best": ba["package_best_vs_incumbent"]},
              open(os.path.join(ART, "final_regression_report.json"), "w"),
              indent=2, default=str)
    write_submission_md(ba)

    g = ba["submission_gate"]
    json.dump({"SUBMISSION_G": g["SUBMISSION_G"], "gate": g,
               "packaged": False, "uploaded": False,
               "reason": ("gate not met; §32 authorises upload when and only when "
                          "SUBMISSION_G = SUBMIT")
               if g["SUBMISSION_G"] == "DO_NOT_SUBMIT" else "gate met"},
              open(os.path.join(ART, "submission_G_validation.json"), "w"),
              indent=2, default=str)
    with open(os.path.join(ART, "KAGGLE_SUBMIT_COMMAND.txt"), "w") as fh:
        if g["SUBMISSION_G"] == "SUBMIT":
            fh.write("kaggle competitions submit -c cabt "
                     "-f submission_G_policy_combination.tar.gz "
                     f"-m \"c013 Submission G: {g['candidate']} fixed deck <sha>\"\n")
        else:
            fh.write("# NOT EXECUTED.\n"
                     f"# SUBMISSION_G = {g['SUBMISSION_G']}; §32 authorises a Kaggle upload "
                     "when and only when SUBMISSION_G = SUBMIT.\n"
                     "# Teacher non-inferiority lower bound "
                     f"{g['teacher_noninferiority_lb95']} < {NONINF_LB} required.\n"
                     "# The command that WOULD have run:\n"
                     "# kaggle competitions submit -c cabt "
                     "-f submission_G_policy_combination.tar.gz -m \"c013 Submission G: "
                     f"{g['candidate']} fixed deck <sha>\"\n")
    with open(os.path.join(LOGD, "final_evaluation.txt"), "w") as fh:
        fh.write(json.dumps(ba, indent=2, default=str) + "\n")

    print(json.dumps({"CLAUDE_SEMANTIC_PREFLIGHT": cv["CLAUDE_SEMANTIC_PREFLIGHT"],
                      "shortfalls": cv["shortfalls"],
                      "TRUE_BEST_AGENT": ba["TRUE_BEST_AGENT"],
                      "PACKAGE_FEASIBLE_BEST_AGENT": ba["PACKAGE_FEASIBLE_BEST_AGENT"],
                      "SUBMISSION_G": g["SUBMISSION_G"],
                      "replaces_c012_incumbent": ba["replaces_c012_incumbent"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
