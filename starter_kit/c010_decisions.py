"""c010 decision rules as pure, testable functions (§17–§25).

Every rule is implemented exactly as registered and takes bootstrap distributions as input so
it can be unit-tested with synthetic evidence. Nothing here reads the contract's example
values as outcomes; the incumbent is protected by construction — a candidate replaces I0 only
by satisfying every promotion condition.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

TEACHER = "dragapult"
FIELD = ["mega_lucario", "iono", "mega_abomasnow"]
HELD_OUT = "mega_abomasnow"
COMPOSITE_W = {TEACHER: 0.55, "mega_lucario": 0.15, "iono": 0.15, "mega_abomasnow": 0.15}
MAJOR_REGRESSION_DELTA = 0.07
MAJOR_REGRESSION_PROB = 0.90
SIG_PROB = 0.90

# Threshold comparisons are made on differences of means, so a gain that is mathematically
# EQUAL to its threshold can land a few ulps below it in binary floating point. Observed in
# this run: Arm C's median field gain is exactly 47/150 - 17/60 = 9/300 = 3/100, yet the
# float difference evaluated to 0.029999999999999916 and failed a bare `>= 0.03`.
# The metrics are seat-balanced means over 100-200 game panels, so their true resolution is
# 1/600 ~= 0.0017; a tolerance of 1e-9 cannot admit a value that is genuinely below the
# threshold, it only prevents an exact tie from being read as a miss. "At least N percentage
# points" is inclusive, so an exact tie must count as met.
GAIN_EPS = 1e-9


def _ge(value, threshold, eps: float = GAIN_EPS) -> bool:
    """`value >= threshold`, tolerant of representation error at an exact tie."""
    return value is not None and value >= threshold - eps


# -------------------- metric helpers --------------------

def composite(per_opponent_points: Dict[str, float]) -> Optional[float]:
    if not all(o in per_opponent_points for o in COMPOSITE_W):
        return None
    return float(sum(COMPOSITE_W[o] * per_opponent_points[o] for o in COMPOSITE_W))


def field_score(per_opponent_points: Dict[str, float]) -> Optional[float]:
    pts = [per_opponent_points[o] for o in FIELD if o in per_opponent_points]
    return float(np.mean(pts)) if len(pts) == len(FIELD) else None


def prob_above_zero(diff_boot: Sequence[float]) -> float:
    return float((np.asarray(diff_boot) > 0).mean())


def major_regression(cand_point: float, base_point: float, diff_boot: Sequence[float],
                     delta: float = MAJOR_REGRESSION_DELTA,
                     prob: float = MAJOR_REGRESSION_PROB) -> bool:
    """candidate <= baseline - delta AND bootstrap P(regression) >= prob (§17)."""
    if cand_point is None or base_point is None:
        return False
    return bool(cand_point <= base_point - delta
                and float((np.asarray(diff_boot) < -delta).mean()) >= prob)


TEACHER_NON_INFERIORITY_LB = 0.47


def plausibly_teacher_non_inferior(teacher_ci95: Optional[Sequence[float]],
                                   threshold: float = TEACHER_NON_INFERIORITY_LB) -> bool:
    """§16: extend teacher head-to-head to 800 games while non-inferiority is still live.

    A finalist is *plausibly* non-inferior when the current sample cannot yet rule the claim
    out -- i.e. the upper end of the two-sided 95% interval still reaches the threshold. If
    the whole interval lies below it, more teacher games cannot change the verdict and the
    extension would be wasted. Note this is deliberately weaker than the promotion gate,
    which requires the one-sided 95% LOWER bound to reach the same threshold.
    """
    if not teacher_ci95 or teacher_ci95[1] is None:
        return False
    return bool(teacher_ci95[1] >= threshold)


# -------------------- nomination (§17) --------------------

def nominate(screen: Dict[str, Any], branch_best: Optional[Dict[str, Any]],
             is_final_checkpoint: bool) -> Dict[str, Any]:
    """Nomination is NOT promotion; it only buys a confirmation panel."""
    reasons = []
    if branch_best is None:
        reasons.append("first screened checkpoint in branch")
    else:
        if (screen.get("promotion_composite") is not None
                and branch_best.get("promotion_composite") is not None
                and screen["promotion_composite"] > branch_best["promotion_composite"]):
            reasons.append("promotion composite exceeds branch best")
        if (screen.get("teacher_score") is not None
                and branch_best.get("teacher_score") is not None
                and _ge(screen["teacher_score"] - branch_best["teacher_score"], 0.03)):
            reasons.append("teacher score improves by >= 3pp")
        if (screen.get("strategic_field_score") is not None
                and branch_best.get("strategic_field_score") is not None
                and _ge(screen["strategic_field_score"] - branch_best["strategic_field_score"], 0.04)):
            reasons.append("strategic-field score improves by >= 4pp")
    if is_final_checkpoint:
        reasons.append("branch's final registered checkpoint")
    return {"nominated": bool(reasons), "reasons": reasons}


# -------------------- promotion (§21) --------------------

def promotion_qualifies(cand: Dict[str, Any], incumbent: Dict[str, Any],
                        diff_boots: Dict[str, Sequence[float]]) -> Dict[str, Any]:
    """A candidate may replace I0 only when every condition holds (§21)."""
    c_comp, i_comp = cand.get("promotion_composite"), incumbent.get("promotion_composite")
    c_t, i_t = cand.get("teacher_score"), incumbent.get("teacher_score")
    c_f, i_f = cand.get("strategic_field_score"), incumbent.get("strategic_field_score")
    rel = cand.get("reliability", {})
    reliability_ok = (rel.get("defects", 1) == 0 and rel.get("invalid", 1) == 0
                      and rel.get("exceptions", 1) == 0 and rel.get("timeouts", 1) == 0)
    sig = max([prob_above_zero(diff_boots.get("teacher", [0])),
               prob_above_zero(diff_boots.get("field", [0]))])
    regressions = [o for o in [TEACHER] + FIELD
                   if major_regression(cand.get("per_opponent", {}).get(o, {}).get("point"),
                                       incumbent.get("per_opponent", {}).get(o, {}).get("point"),
                                       diff_boots.get(f"opp::{o}", [0]))]
    crit = {
        "reliability_passes": bool(reliability_ok),
        "composite_higher": bool(c_comp is not None and i_comp is not None and c_comp > i_comp),
        "teacher_not_lower": bool(c_t is not None and i_t is not None and c_t >= i_t),
        "field_not_lower": bool(c_f is not None and i_f is not None and c_f >= i_f),
        "one_primary_improvement_90pct": bool(sig >= SIG_PROB),
        "no_major_regression": not regressions,
        "hashes_validate": bool(cand.get("hashes_validate", True)),
    }
    return {"qualifies": all(crit.values()), "criteria": crit,
            "major_regressions": regressions, "significance": sig}


def promotion_tiebreak_key(cand: Dict[str, Any]):
    """§21 tie-breakers, highest-first (training games ascending last)."""
    po = cand.get("per_opponent", {})
    worst = min((po[o]["point"] for o in [TEACHER] + FIELD if o in po), default=0.0)
    return (cand.get("teacher_score") or 0, cand.get("strategic_field_score") or 0,
            po.get(HELD_OUT, {}).get("point") or 0, worst,
            -(cand.get("latency_p99_max_ms") or 0), -(cand.get("training_games") or 0))


# -------------------- arm-level rules (§18–§20) --------------------

def _median(xs):
    return float(np.median(xs)) if len(xs) else None


def exact_reproducibility(seed_bests: List[Dict[str, Any]], b0: Dict[str, Any],
                          diff_boots_by_seed: Dict[str, Dict[str, Sequence[float]]],
                          reliability_ok: bool) -> Dict[str, Any]:
    """§18 — six conditions, all required for PROVEN."""
    t_above = [s for s in seed_bests
               if s.get("teacher_score") is not None and s["teacher_score"] > b0["teacher_score"]]
    f_above = [s for s in seed_bests
               if s.get("strategic_field_score") is not None
               and s["strategic_field_score"] > b0["strategic_field_score"]]
    med_t = _median([s["teacher_score"] for s in seed_bests if s.get("teacher_score") is not None])
    med_f = _median([s["strategic_field_score"] for s in seed_bests
                     if s.get("strategic_field_score") is not None])
    dt = (med_t - b0["teacher_score"]) if med_t is not None else None
    df = (med_f - b0["strategic_field_score"]) if med_f is not None else None
    sig = max([max(prob_above_zero(d.get("teacher", [0])), prob_above_zero(d.get("field", [0])))
               for d in diff_boots_by_seed.values()], default=0.0)
    abom_reg = [s["candidate_id"] for s in seed_bests
                if major_regression(s.get("per_opponent", {}).get(HELD_OUT, {}).get("point"),
                                    b0.get("per_opponent", {}).get(HELD_OUT, {}).get("point"),
                                    diff_boots_by_seed.get(s["candidate_id"], {})
                                    .get(f"opp::{HELD_OUT}", [0]))]
    cond = {
        "c1_two_seeds_above_b0_teacher": len(t_above) >= 2,
        "c2_two_seeds_above_b0_field": len(f_above) >= 2,
        "c3_median_gain_teacher_3pp_and_field_5pp": bool(_ge(dt, 0.03) and _ge(df, 0.05)),
        "c4_one_median_difference_90pct": bool(sig >= SIG_PROB),
        "c5_majority_no_abomasnow_regression": len(abom_reg) <= len(seed_bests) // 2,
        "c6_reliability_passes": bool(reliability_ok),
    }
    if all(cond.values()):
        decision = "PROVEN"
    else:
        both = [s for s in seed_bests if s in t_above and s in f_above]
        # FAILED only when fewer than two seeds improve on BOTH primary dimensions and the
        # reason is not uncertainty (i.e. there is a clear, statistically supported shortfall).
        decision = "FAILED" if (len(both) < 2 and sig < 0.5) else "INCONCLUSIVE"
    return {"decision": decision, "conditions": cond,
            "seeds_above_b0_teacher": [s["candidate_id"] for s in t_above],
            "seeds_above_b0_field": [s["candidate_id"] for s in f_above],
            "median_teacher": med_t, "median_field": med_f,
            "median_teacher_gain": dt, "median_field_gain": df,
            "max_significance": sig, "abomasnow_regressions": abom_reg}


def continuation(seed_bests: List[Dict[str, Any]], i0: Dict[str, Any],
                 diff_boots_by_seed: Dict[str, Dict[str, Sequence[float]]],
                 reliability_ok: bool, label: str = "continuation") -> Dict[str, Any]:
    """§19 / §20 — EXTENDED requires >=2 seeds confirmed above I0 plus the median gains."""
    above = [s for s in seed_bests
             if s.get("teacher_score") is not None and s.get("strategic_field_score") is not None
             and (s["teacher_score"] > i0["teacher_score"]
                  or s["strategic_field_score"] > i0["strategic_field_score"])]
    med_t = _median([s["teacher_score"] for s in seed_bests if s.get("teacher_score") is not None])
    med_f = _median([s["strategic_field_score"] for s in seed_bests
                     if s.get("strategic_field_score") is not None])
    dt = (med_t - i0["teacher_score"]) if med_t is not None else None
    df = (med_f - i0["strategic_field_score"]) if med_f is not None else None
    sig = max([max(prob_above_zero(d.get("teacher", [0])), prob_above_zero(d.get("field", [0])))
               for d in diff_boots_by_seed.values()], default=0.0)
    regs = {s["candidate_id"]: [o for o in [TEACHER] + FIELD
                                if major_regression(s.get("per_opponent", {}).get(o, {}).get("point"),
                                                    i0.get("per_opponent", {}).get(o, {}).get("point"),
                                                    diff_boots_by_seed.get(s["candidate_id"], {})
                                                    .get(f"opp::{o}", [0]))]
            for s in seed_bests}
    any_reg = any(v for v in regs.values())
    cond = {"two_seeds_confirmed_above_i0": len(above) >= 2,
            "median_teacher_gain_3pp": bool(_ge(dt, 0.03)),
            "median_field_gain_3pp": bool(_ge(df, 0.03)),
            "one_gain_90pct": bool(sig >= SIG_PROB),
            "no_major_regression": not any_reg,
            "reliability_passes": bool(reliability_ok)}
    if all(cond.values()):
        decision = "EXTENDED"
    else:
        confirmed_improvement = [s for s in seed_bests
                                 if (s.get("teacher_score", 0) > i0["teacher_score"]
                                     and s.get("strategic_field_score", 0) > i0["strategic_field_score"])]
        decision = "NOT_EXTENDED" if (not confirmed_improvement and sig < 0.5) else "INCONCLUSIVE"
    strong = bool(med_t is not None and med_f is not None and med_t >= 0.30 and med_f >= 0.30) or \
        (sum(1 for s in seed_bests if (s.get("teacher_score") or 0) >= 0.30
             and (s.get("strategic_field_score") or 0) >= 0.30) >= 2)
    return {"decision": decision, "label": label, "conditions": cond,
            "seeds_above_i0": [s["candidate_id"] for s in above],
            "median_teacher": med_t, "median_field": med_f,
            "median_teacher_gain": dt, "median_field_gain": df,
            "max_significance": sig, "major_regressions": regs,
            "strong_continuation_flag": strong}


# -------------------- status / submission / next step (§22–§25) --------------------

def training_loop_status(repro: str, exact_cont: str, stab_cont: str, promoted: bool,
                         survives_final_panel: bool, any_major_regression: bool,
                         real_gain_exists: bool) -> str:
    if (repro == "PROVEN" and (exact_cont == "EXTENDED" or stab_cont == "EXTENDED")
            and promoted and survives_final_panel and not any_major_regression):
        return "VALIDATED"
    if repro == "FAILED" and exact_cont != "EXTENDED" and stab_cont != "EXTENDED":
        return "REJECTED"
    return "PROMISING" if real_gain_exists else "REJECTED"


def submission_gate(best_agent_id: str, best: Dict[str, Any], teacher_lb95: Optional[float],
                    reproducible_strategic_improvement: bool, any_major_regression: bool,
                    reliability_ok: bool, package_ok: bool) -> Dict[str, Any]:
    crit = {"best_agent_is_new": best_agent_id not in ("B0_v2a", "I0_incumbent", "NONE", None),
            "reliability_passes": bool(reliability_ok),
            "teacher_non_inferiority_lb95_ge_0.47": bool(teacher_lb95 is not None
                                                         and teacher_lb95 >= 0.47),
            "reproducible_strategic_improvement_over_teacher": bool(reproducible_strategic_improvement),
            "no_major_regression": not any_major_regression,
            "package_validation": bool(package_ok)}
    return {"decision": "SUBMIT" if all(crit.values()) else "DO_NOT_SUBMIT", "criteria": crit}


def next_step(loop_status: str, best_below_teacher: bool, credible_headroom: bool,
              deck_gate_met: bool, ppo_cannot_reliably_extend: Optional[bool] = None) -> str:
    """§25, encoded by its stated conditions rather than as a fall-through.

    §25 attaches REDESIGN to "the loop is rejected or PPO cannot reliably extend I0". A blanket
    default to REDESIGN for every non-VALIDATED status would assert that second clause even
    when the evidence contradicts it -- e.g. a PROMISING loop that did promote a new agent
    which beat I0 on the final panel. `ppo_cannot_reliably_extend` is therefore supplied by
    the caller from the continuation decisions, so the evidence decides which clause fires.

    Note none of §25's three options is written for a PROMISING loop that *did* extend I0;
    that gap is resolved here in favour of the option whose stated condition is not
    contradicted by the measurements, and is called out explicitly in the summary.
    """
    if ppo_cannot_reliably_extend is None:
        # §22 makes an extended continuation a necessary condition of VALIDATED, so a
        # validated loop cannot simultaneously have failed to extend I0.
        ppo_cannot_reliably_extend = loop_status != "VALIDATED"
    if deck_gate_met and loop_status == "VALIDATED":
        return "BEGIN_DECK_PIPELINE"
    if loop_status == "REJECTED" or ppo_cannot_reliably_extend:
        return "REDESIGN_FIXED_DECK_AGENT"
    if best_below_teacher and credible_headroom:
        return "SCALE_FIXED_DECK_RL"
    return "REDESIGN_FIXED_DECK_AGENT"
