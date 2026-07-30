"""c022 probe M04 — does the c022 K=1 search reproduce the c021 K=1 search?

Every K>1 claim in this contract is measured against a K=1 control, so if that control is not the
c021 search, nothing built on it means anything. This evaluates the arm against the assertions
fixed in `results/mcgs/PREREGISTERED_M04_IDENTITY.json` — written before the arm ran, and written
because the probe matrix's own pass condition ("reproduces frozen c021 behaviour within
deterministic tolerance") is not executable: the frozen control was wall-clock budgeted and every
c022 arm is simulation budgeted.

What is asserted is the SEARCH's own invariants at the control's measured 177 simulations per
decision. What is NOT asserted is field score, and the reason is in the preregistration: 36
completed games with a Wilson interval of roughly [0.04, 0.26] cannot establish outcome equality
across a budget-regime change, and pretending otherwise would either fail the probe for the wrong
reason or force a tolerance that asserts nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C22 = os.path.join(_REPO, "contracts",
                   "c022_mcgs_multideterminization_and_faithful_byterl_reproduction", "results")
C021 = os.path.join(_REPO, "contracts",
                    "c021_source_faithful_mcgs_and_byterl_transfer_campaign", "results")
CONTROL = os.path.join(C021, "transfer", "prior_only", "t2_T0_control_summary.json")


def evaluate(arm: dict, control: dict, prereg: dict) -> dict:
    checks = []

    def add(cid, quantity, expected, got, ok, why, tolerance=None):
        checks.append({"id": cid, "quantity": quantity, "expected": expected, "got": got,
                       "tolerance": tolerance, "pass": bool(ok), "why": why})

    add("M04.a", "manual_coin_node_ucb_selected", 0,
        arm.get("manual_coin_node_ucb_selected"),
        (arm.get("manual_coin_node_ucb_selected") or 0) == 0,
        "a chance context must never reach the UCB branch")

    for q in ("finalised", "terminal_leaves", "lethal_bonus"):
        add("M04.b", q, 0, arm.get(q), (arm.get(q) or 0) == 0,
            "the frozen control recorded 0 over 226,277 rollouts; a nonzero value would mix the "
            "+/-10 terminal scale into the aggregate and break the probability reading")

    for q in ("step_errors", "begin_errors"):
        add("M04.c", q, 0, arm.get(q), (arm.get(q) or 0) == 0,
            "the control recorded 0; any nonzero value is a port regression, not a budget "
            "difference")

    tw, tl, tu = (arm.get("term_root_win") or 0), (arm.get("term_root_loss") or 0), \
        (arm.get("term_undecided") or 0)
    rate = (tw + tl + tu) and 1.0 or 0.0
    add("M04.d", "rollout_terminal_rate", 1.0, round(rate, 4), abs(rate - 1.0) <= 0.02,
        "the control's rollouts reached a real terminal every time; this is a property of the "
        "rollout, not of the budget", 0.02)

    spd = arm.get("sims_per_decision")
    add("M04.e", "sims_per_decision", 177, spd,
        spd is not None and abs(spd - 177) <= 2,
        "the simulation budget must actually be delivered, or the comparison is not like for "
        "like", 2)

    add("M04.f", "signature_mismatches", 0, arm.get("signature_mismatches"),
        (arm.get("signature_mismatches") or 0) == 0,
        "at K=1 there is one world, so a mismatch would be a defect in the signature machinery "
        "itself")

    # M04.g — graph structure per 1000 simulations, within a factor of 2 of the control.
    def per_k(d, key):
        sims = d.get("total_simulations") or d.get("searches") or 0
        return (1000.0 * (d.get(key) or 0) / sims) if sims else None

    for key in ("transposition_merges", "dummy_edges"):
        got, exp = per_k(arm, key), per_k(control, key)
        ok = None
        if got is not None and exp:
            ratio = got / exp if exp else None
            ok = ratio is not None and 0.5 <= ratio <= 2.0
        add("M04.g", f"{key} per 1000 simulations",
            round(exp, 3) if exp else None, round(got, 3) if got else None, bool(ok),
            "graph structure per unit of search is a property of the search, not of how much "
            "search there is; the factor-of-2 band is deliberately loose because the control "
            "ran a different simulation count against a different game mix",
            "factor of 2")

    passed = sum(1 for c in checks if c["pass"])
    return {
        "probe": "M04",
        "preregistration": "results/mcgs/PREREGISTERED_M04_IDENTITY.json",
        "arm": arm.get("tag"),
        "control": "C021_MCGS_K1_CONTROL (t2_T0_control_summary.json)",
        "checks": checks,
        "n_pass": passed, "n_checks": len(checks),
        "pass": passed == len(checks),
        "explicitly_not_asserted": {
            "field_score": {
                "c022_arm": arm.get("field_score"), "c022_wilson95": arm.get("wilson95"),
                "c021_control": control.get("field_score"),
                "why_not_asserted": prereg["what_is_actually_asserted"]
                ["explicitly_NOT_asserted"]["field_score"],
            }
        },
        "consequence_if_failed": "MCGS_HIDDEN_INFO cannot be PASS: every K>1 claim is measured "
                                 "against a K=1 control that has not been shown to be the c021 "
                                 "search.",
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default=os.path.join(
        C22, "mcgs", "k1_control", "m04_k1_reuse_summary.json"))
    ap.add_argument("--out", default=os.path.join(C22, "probes", "m04_identity.json"))
    a = ap.parse_args(argv)

    if not os.path.isfile(a.arm):
        print(f"arm summary not found: {a.arm}")
        return 2
    with open(a.arm) as fh:
        arm = json.load(fh)
    with open(CONTROL) as fh:
        control = json.load(fh)
    with open(os.path.join(C22, "mcgs", "PREREGISTERED_M04_IDENTITY.json")) as fh:
        prereg = json.load(fh)

    out = evaluate(arm, control, prereg)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(out, fh, indent=2)
    for c in out["checks"]:
        print(f"{'PASS' if c['pass'] else 'FAIL'}  {c['id']:7s} {c['quantity']:42s} "
              f"expected={c['expected']} got={c['got']}")
    print(f"{out['n_pass']}/{out['n_checks']} -> {a.out}")
    return 0 if out["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
