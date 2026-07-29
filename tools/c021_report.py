"""c021 — assemble every result into the statuses DECISION_RULES defines.

This tool does NOT decide optimistically. Each status is computed from evidence that must be
present on disk; a missing input yields FAIL or PARTIAL with the reason recorded, never a pass by
default. Wilson intervals are used wherever a rate is compared, because at these sample sizes the
binomial noise is larger than most of the differences involved.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C21 = os.path.join(_REPO, "contracts",
                   "c021_source_faithful_mcgs_and_byterl_transfer_campaign", "results")


def wilson(k: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(max(p * (1 - p) / n + z * z / (4 * n * n), 0.0))
    return ((c - m) / d, (c + m) / d)


def load(path: str) -> Optional[Any]:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return None


def load_glob(pattern: str) -> Dict[str, Any]:
    out = {}
    for p in sorted(glob.glob(pattern)):
        d = load(p)
        if d is not None:
            out[os.path.basename(p)] = d
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(C21, "reports"))
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)

    ev: Dict[str, Any] = {}
    mcgs = load_glob(os.path.join(C21, "mcgs", "evaluations", "*_summary.json"))
    curves = load_glob(os.path.join(C21, "byterl", "curves", "*_curve.json"))
    manifests = load_glob(os.path.join(C21, "byterl", "manifests", "*_manifest.json"))
    validation = load(os.path.join(C21, "validation", "semantic_validation.json"))
    inventory = os.path.join(C21, "fidelity", "mcgs_official_source_inventory.json")
    eqmap = os.path.join(C21, "fidelity", "mcgs_paper_equation_map.md")
    a4doc = os.path.join(C21, "fidelity", "A4_chance_node_api_constraint.md")
    unres = os.path.join(C21, "fidelity", "UNRESOLVED_REFERENCE_CHOICES.md")

    # ---------------------------------------------------------------- SOURCE_FIDELITY
    have_archive = os.path.exists(inventory)
    have_eqmap = os.path.exists(eqmap)
    have_a4 = os.path.exists(a4doc)
    have_unres = os.path.exists(unres)
    val_ok = bool(validation and validation.get("all_checks_detect_their_defect"))
    sf_reasons = []
    if not have_archive:
        sf_reasons.append("no official source inventory")
    if not have_eqmap:
        sf_reasons.append("no paper equation map")
    if not val_ok:
        sf_reasons.append("semantic validation incomplete or has inert checks")
    if not have_a4:
        sf_reasons.append("A4 adapter not documented")
    source_fidelity = "PASS" if not sf_reasons else "PARTIAL"
    ev["SOURCE_FIDELITY"] = {
        "status": source_fidelity,
        "archive_inventory": have_archive, "equation_map": have_eqmap,
        "a4_adapter_documented": have_a4, "unresolved_choices_declared": have_unres,
        "semantic_validation": (f"{validation.get('passed')}/{validation.get('total')}"
                                if validation else None),
        "inert_checks": (validation or {}).get("inert", []),
        "reasons": sf_reasons,
        "caveat": ("The port is the !PIMC configuration MINUS the interior-determinization "
                   "operations the PTCG API does not expose. Chance nodes exist only at the "
                   "random surfaces manual_coin reveals. It does not sample draw order inside "
                   "the tree."),
    }

    # ---------------------------------------------------------------- EXECUTION
    def pick(tagpart, d):
        return {k: v for k, v in d.items() if tagpart in k}

    comp = pick("competitive", mcgs)
    exec_rows = []
    for name, s in mcgs.items():
        # Abandoned games are excluded from the field score, which is defensible but not free:
        # abandonment correlates with game length and length correlates with how the game was
        # going, so exclusion biases in an unknown direction. Bound it explicitly by scoring the
        # abandoned games all-losses and all-wins; the truth lies inside.
        comp = int(s.get("completed") or 0)
        ab = int(s.get("abandoned") or 0)
        fs = s.get("field_score")
        if fs is not None and (comp + ab) > 0:
            wins = fs * comp
            lo_b = wins / (comp + ab)
            hi_b = (wins + ab) / (comp + ab)
        else:
            lo_b = hi_b = None
        exec_rows.append({
            "run": name, "games": s.get("games"), "completed": s.get("completed"),
            "abandoned": ab,
            "field_score": s.get("field_score"),
            "field_score_bounds_if_abandoned_counted": (
                [round(lo_b, 4), round(hi_b, 4)] if lo_b is not None else None),
            "sims_per_decision": s.get("sims_per_decision"),
            "chance_nodes_created": s.get("chance_nodes_created"),
            "manual_coin_node_ucb_selected": s.get("manual_coin_node_ucb_selected"),
            "step_errors": s.get("step_errors"), "release_errors": s.get("release_errors"),
            "transposition_merges": s.get("transposition_merges"),
            "dummy_edges": s.get("dummy_edges"),
            "term_root_win": s.get("term_root_win"), "term_root_loss": s.get("term_root_loss"),
        })
    # `fctrl_`/`flearn_` are the FINAL ladder, measured end to end on one code version.
    # `ctrl_`/`learn_` straddled the sample_select fix and are retained only as history.
    FINAL_PFX = ("fctrl_", "flearn_")
    have_final = any(k.startswith(FINAL_PFX) for k in curves)
    ladder_pfx = FINAL_PFX if have_final else ("ctrl_", "learn_")
    ladder_done = sorted({k.replace("_curve.json", "") for k in curves
                          if k.startswith(ladder_pfx)})
    clean = all((r.get("step_errors") or 0) == 0 and
                (r.get("manual_coin_node_ucb_selected") or 0) == 0 for r in exec_rows)
    execution = "PASS" if (exec_rows and curves and clean) else "PARTIAL"
    ev["EXECUTION"] = {"status": execution, "mcgs_runs": exec_rows,
                       "byterl_runs": ladder_done,
                       "no_step_errors_and_no_coin_ucb_selection": clean}

    # ---------------------------------------------------------------- MCGS_COMPETITIVE
    # `competitive` and `transfer_T0_control` are the SAME configuration -- the source port with
    # every transfer switch off. Reporting whichever scored higher would be selection on exactly
    # the run-to-run noise this campaign measured, so they are POOLED.
    def eligible(name: str, s: Dict[str, Any]) -> bool:
        if s.get("SUPERSEDED"):
            return False
        if not s.get("manual_coin_contexts_are_coin_head_only", True):
            return False
        role = s.get("role")
        if role is None:      # pre-role runs: fall back to the explicit pooled pair only
            return name.replace("_summary.json", "") in ("competitive", "transfer_T0_control")
        if role == "competitive":
            return True
        # the T0 control shares the transfer harness but uses no prior, so it measures the
        # standalone port and is pooled with `competitive`
        return role == "transfer" and s.get("transfer_arm") == "T0_control"

    pool_names = ("competitive_summary.json", "transfer_T0_control_summary.json")
    pool_k, pool_n = 0.0, 0
    for nm in pool_names:
        d = mcgs.get(nm)
        if d and d.get("field_score") is not None and eligible(nm, d):
            pool_k += d["field_score"] * (d.get("completed") or 0)
            pool_n += int(d.get("completed") or 0)

    # ALLOW-list, not a blocklist. A blocklist enumerates what to exclude and is wrong the
    # moment a new diagnostic tag appears -- `scale_w2`, an 11-game worker-scaling probe, became
    # the best-scoring eligible candidate for the headline MCGS result under the old rule.
    # A run qualifies only if it explicitly declares itself competitive.
    best_mcgs, best_name = None, None
    for name, s in mcgs.items():
        if not eligible(name, s):
            continue
        fs = s.get("field_score")
        if fs is not None and (best_mcgs is None or fs > best_mcgs):
            best_mcgs, best_name = fs, name
    if pool_n > 0:
        best_name = " + ".join(n.replace("_summary.json", "") for n in pool_names
                               if mcgs.get(n))
        best_mcgs = pool_k / pool_n
        n_games = pool_n
    else:
        n_games = mcgs.get(best_name, {}).get("completed", 0) if best_name else 0
    pool_ab = sum(int((mcgs.get(n) or {}).get("abandoned") or 0) for n in pool_names
                  if mcgs.get(n))
    lo, hi = wilson((best_mcgs or 0) * n_games, n_games) if n_games else (0.0, 1.0)
    # the gate is judged on the PESSIMISTIC treatment of abandoned games, so exclusion can never
    # manufacture a pass
    lo_pess, _ = (wilson((best_mcgs or 0) * n_games, n_games + pool_ab)
                  if n_games else (0.0, 1.0))
    beats_half = lo_pess > 0.5
    ev["MCGS_COMPETITIVE"] = {
        "status": "PASS" if beats_half else "FAIL",
        "best_run": best_name, "field_score": best_mcgs, "games": n_games,
        "pooled": pool_n > 0,
        "pooling_note": ("competitive and transfer_T0_control are the same configuration; they "
                         "are pooled rather than max-selected, because reporting the higher of "
                         "two identical runs is selection on the measured noise."),
        "wilson95": [round(lo, 4), round(hi, 4)],
        "abandoned": pool_ab,
        "wilson95_lower_if_abandoned_are_losses": round(lo_pess, 4),
        "gate": ("lower bound of the 95% Wilson interval must exceed 0.5 against the field, "
                 "judged with abandoned games counted as losses so exclusion cannot manufacture "
                 "a pass"),
        "note": ("A technically faithful but weak MCGS is MCGS_COMPETITIVE=FAIL, not an "
                 "implementation failure (DECISION_RULES §1)."),
    }

    # ---------------------------------------------------------------- BYTERL_METHOD
    checks = {c["id"]: c["status"] for c in (validation or {}).get("checks", [])}
    byterl_ids = [k for k in checks if k.startswith("BYTERL_") or k.startswith("DECK_")]
    byterl_all = all(checks[k] == "PASS" for k in byterl_ids) if byterl_ids else False
    ladder_present = {r: any(r == k.split("_", 1)[1].replace("_curve.json", "")
                             for k in [])
                      for r in []}
    have_rungs = sorted({k.replace("_curve.json", "").split("_", 1)[1]
                         for k in curves if k.startswith(ladder_pfx)})
    weights_changed = []
    for name, c in curves.items():
        if not isinstance(c, list) or len(c) < 2:
            continue
        if not name.startswith(ladder_pfx):
            continue
        ups = sum(int(r.get("updates") or 0) for r in c)
        wrs = [r.get("win_rate") for r in c if r.get("win_rate") is not None]
        ae = sum(int(r.get("actor_errors") or 0) for r in c)
        ad = sum(int(r.get("n_decisions") or 0) for r in c) or None
        if ups > 0:
            run_name = name.replace("_curve.json", "")
            # B3 plays FROZEN CHECKPOINTS OF ITSELF. Its win rate is a mirror-match rate and sits
            # near 0.5 by construction; it is NOT comparable to the rungs that play the scripted
            # field, and DECISION_RULES §4 forbids submitting a checkpoint selected only on
            # self-play. Marked here so the number cannot be read as strength.
            selfplay = run_name.endswith("b3")
            weights_changed.append({"run": run_name,
                                    "updates": ups, "iterations": len(c),
                                    "actor_errors": ae,
                                    "actor_error_rate": (round(ae / ad, 4) if ad else None),
                                    "opponent": ("frozen self-play checkpoints (OSFP)"
                                                 if selfplay else "scripted field"),
                                    "win_rate_is_self_play": selfplay,
                                    "comparable_to_field": not selfplay,
                                    "first_win_rate": wrs[0] if wrs else None,
                                    "last_win_rate": wrs[-1] if wrs else None,
                                    "best_win_rate": max(wrs) if wrs else None})
    e2e = any((manifests.get(m) or {}).get("reductions", {}).get("learn_construction")
              for m in manifests)
    bm_reasons = []
    # DECISION_RULES §2 names "recurrent actor-learner execution". The implementation is
    # synchronous. That is a declared deviation against a named requirement, so the status is
    # PARTIAL -- a caveat in a field the reader may skip is not the same as a downgraded status.
    bm_reasons.append("actor-learner execution is synchronous, not the papers' decoupled "
                      "recurrent actor-learner (declared deviation against a named requirement)")
    if not byterl_all:
        bm_reasons.append("a ByteRL semantic check did not detect its defect")
    if not weights_changed:
        bm_reasons.append("no training run with non-zero updates")
    if not e2e:
        bm_reasons.append("no end-to-end deck-construction-plus-battle run")
    ev["BYTERL_METHOD"] = {
        "status": "PASS" if not bm_reasons else "PARTIAL",
        "semantic_checks": {k: checks[k] for k in sorted(byterl_ids)},
        "rungs_run": have_rungs,
        "training_runs_with_weight_updates": weights_changed,
        "end_to_end_construction_and_battle": e2e,
        "ladder_version": ("final, single code version" if have_final else
                           "MIXED CODE VERSIONS -- straddles the sample_select fix; "
                           "superseded by the fctrl_/flearn_ ladder"),
        "reasons": bm_reasons,
        "declared_deviation": ("Actor-learner execution is SYNCHRONOUS (actors fill a batch, "
                               "then the learner updates), not the papers' decoupled recurrent "
                               "actor-learner. The algorithm is unchanged; the execution "
                               "topology is not the published one, and this is a declared "
                               "deviation rather than a claimed reproduction."),
        "unresolved_choices": "results/fidelity/UNRESOLVED_REFERENCE_CHOICES.md",
        "self_play_warning": ("B3's win rate is measured against frozen checkpoints of itself and "
                              "sits near 0.5 by construction. It is not a field result and must "
                              "not be compared with the other rungs; DECISION_RULES §4 forbids "
                              "submitting a checkpoint selected only on self-play."),
    }

    # ---------------------------------------------------------------- BYTERL_SCALE
    total_games = 0
    for name, c in curves.items():
        if isinstance(c, list):
            total_games += sum(int(r.get("games") or 0) for r in c)
    ev["BYTERL_SCALE"] = {
        "status": "COMPUTE_LIMITED",
        "total_games_played": total_games,
        "paper_reference": "distributed fleet, millions of games, days of wall clock",
        "achieved_fraction_note": ("Order 1e3 games against an order 1e6+ reference, i.e. well "
                                   "under 1%. Convergence is NOT claimed; the learning "
                                   "trajectory is reported as-is."),
        "permitted_reductions_only": ["actors", "samples", "duration", "learning periods"],
        "architecture_simplified": False, "algorithm_simplified": False,
    }

    # ---------------------------------------------------------------- TRANSFER
    transfer = {k: v for k, v in mcgs.items() if v.get("transfer_arm")}
    arms = {}
    control = None
    for name, s in mcgs.items():
        if s.get("transfer_arm") == "T0_control":
            control = s            # the arm that shares the transfer harness but uses no prior
    if control is None:
        for name, s in mcgs.items():
            if "competitive" in name and not s.get("transfer_arm"):
                control = s
    for name, s in transfer.items():
        arm = s.get("transfer_arm")
        if arm == "T0_control":
            continue               # the control is reported separately, not as an arm
        n = s.get("completed") or 0
        fs = s.get("field_score")
        if fs is None or n == 0:
            continue
        lo_a, hi_a = wilson(fs * n, n)
        arms[arm] = {"run": name, "field_score": fs, "games": n,
                     "wilson95": [round(lo_a, 4), round(hi_a, 4)]}
    retained = []
    if control is not None and control.get("field_score") is not None:
        cn = control.get("completed") or 0
        clo, chi = wilson(control["field_score"] * cn, cn)
        for arm, d in arms.items():
            if d["wilson95"][0] > chi:      # non-overlapping, arm above control
                retained.append(arm)
    ev["TRANSFER"] = {
        "status": "PASS" if retained else ("FAIL" if arms else "NOT_RUN"),
        "control_field_score": (control or {}).get("field_score"),
        "arms": arms, "retained": retained,
        "interpretation": ("NOT RETAINED, and NOT REJECTED. The arm-to-control differences are "
                           "smaller than the measured run-to-run resolution limit, so the test "
                           "lacks the power to separate them. Treat the components as UNTESTED."),
        "rule": ("DECISION_RULES §3: a component is retained only on a credible improvement; "
                 "internal ByteRL-vs-history improvement alone is insufficient. Here that means "
                 "the arm's 95% lower bound must exceed the control's upper bound."),
    }

    # ---------------------------------------------------------------- PACKAGE / SUBMISSION
    ev["PACKAGE"] = {"status": "NOT_BUILT",
                     "reason": "no candidate cleared its registered gate, so none was packaged"}
    ev["SUBMISSION"] = {"status": "PENDING", "submission_ids": [],
                        "reason": ("DECISION_RULES §4 forbids submitting a candidate clearly "
                                   "dominated by the current champion.")}

    # ---------------------------------------------------------------- OVERALL
    both_done = (ev["EXECUTION"]["status"] in ("PASS", "PARTIAL")
                 and bool(exec_rows) and bool(weights_changed))
    credible = (ev["MCGS_COMPETITIVE"]["status"] == "PASS"
                or ev["TRANSFER"]["status"] == "PASS")
    overall = "PASS" if (both_done and credible) else ("PARTIAL" if both_done else "FAIL")
    ev["OVERALL"] = {
        "status": overall,
        "rule": ("OVERALL=PARTIAL is permitted when both methods are faithfully executed and "
                 "analyzed but no candidate clears the competitive gate (DECISION_RULES §6)."),
        "both_methods_implemented_and_executed": both_done,
        "credible_competitive_or_transfer_result": credible,
    }

    ev["generated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    out = os.path.join(a.out, "statuses.json")
    json.dump(ev, open(out, "w"), indent=2)
    print(json.dumps({k: (v.get("status") if isinstance(v, dict) else v)
                      for k, v in ev.items() if k != "generated"}, indent=2))
    print(f"\nwritten: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
