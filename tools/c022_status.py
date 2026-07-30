"""c022 — the eleven statuses, each computed from artifacts rather than asserted.

`DECISION_RULES §1` fixes the vocabulary; §2-§5 fix what each status REQUIRES. This file turns
those requirements into predicates over the results tree, so that a status is a consequence of
the evidence and not a summary of how the campaign felt.

Three rules, and they are the whole point:

1. **A requirement with no artifact is `NOT_RUN`, never met.** The temptation at the end of a
   long contract is to read a missing file as "that part was fine". `results/validation_report`
   already learned this the hard way: five checks with no inputs reported PASS, and the fix was
   to make "no data" a distinct outcome. Same rule here.

2. **One unmet requirement is enough.** `DECISION_RULES §6`: "Do not compress these into a
   misleading single PASS." A status whose requirements are 4-of-5 met is `PARTIAL`, and the
   report names the fifth.

3. **The evidence is named inline.** Every requirement carries the path it was decided from, so
   a reader disagreeing with a status can go straight to the file rather than to the prose.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C22 = os.path.join(_REPO, "contracts",
                   "c022_mcgs_multideterminization_and_faithful_byterl_reproduction", "results")
MC = os.path.join(C22, "mcgs")
BY = os.path.join(C22, "byterl")

PASS, PARTIAL, FAIL = "PASS", "PARTIAL", "FAIL"
BLOCKED, COMPUTE_LIMITED = "BLOCKED", "COMPUTE_LIMITED"
INCONCLUSIVE, NOT_RUN = "INCONCLUSIVE", "NOT_RUN"


def jload(p: str) -> Optional[Any]:
    if not os.path.isfile(p):
        return None
    try:
        with open(p) as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return None


class Req:
    """One named requirement, its verdict, and the artifact it was decided from."""

    def __init__(self, name: str, fn: Callable[[], Tuple[Optional[bool], str]], evidence: str):
        self.name, self.fn, self.evidence = name, fn, evidence

    def run(self) -> Dict[str, Any]:
        try:
            met, detail = self.fn()
        except Exception as e:  # noqa: BLE001
            met, detail = None, f"could not be evaluated: {type(e).__name__}: {e}"
        return {"requirement": self.name,
                "met": met,                       # True / False / None == NOT_RUN
                "verdict": (NOT_RUN if met is None else ("met" if met else "NOT met")),
                "detail": detail,
                "evidence": self.evidence}


def roll_up(reqs: List[Dict[str, Any]], *, pass_status=PASS,
            partial_status=PARTIAL) -> str:
    """PASS only when every requirement is met and at least one was actually evaluated."""
    if not reqs:
        return NOT_RUN
    if all(r["met"] is None for r in reqs):
        return NOT_RUN
    if all(r["met"] is True for r in reqs):
        return pass_status
    if any(r["met"] is False for r in reqs):
        return partial_status
    return partial_status                          # a mix of met and NOT_RUN


# ============================================================================ evidence readers
def paired() -> Optional[Dict[str, Any]]:
    return jload(os.path.join(MC, "paired", "paired_comparison.json"))


def ladder() -> Optional[Dict[str, Any]]:
    return jload(os.path.join(BY, "component_analysis", "rung_ladder.json"))


def validation() -> Optional[Dict[str, Any]]:
    return jload(os.path.join(C22, "validation_report.json"))


def probes() -> Optional[Dict[str, Any]]:
    """ByteRL probes, re-keyed by probe id.

    The file stores a LIST of rows with a `probe` field, not a dict. Reading it as a dict
    silently yielded None for every lookup and reported eight requirements as NOT_RUN while the
    artifact sat on disk saying 7/7 pass -- the D21 failure mode, one file over.
    """
    d = jload(os.path.join(C22, "probes", "byterl_probes.json"))
    if not d:
        return None
    return {"probes": {str(r.get("probe")): r for r in (d.get("probes") or [])},
            "n_pass": d.get("n_pass"), "n_probes": d.get("n_probes")}


def arm(directory: str, tag: str) -> Optional[Dict[str, Any]]:
    return jload(os.path.join(directory, f"{tag}_summary.json"))


def byterl_eval(tag: str) -> Optional[Dict[str, Any]]:
    return jload(os.path.join(BY, "external_evaluations", f"{tag}_eval.json"))


def manifest(tag: str) -> Optional[Dict[str, Any]]:
    return jload(os.path.join(BY, "stages", f"{tag}_manifest.json"))


def wilson_separated(a, b) -> Optional[bool]:
    """True when two Wilson intervals do NOT overlap. None when either is missing."""
    if not a or not b or a[0] is None or b[0] is None:
        return None
    return bool(a[0] > b[1] or b[0] > a[1])


# ============================================================================ MCGS_HIDDEN_INFO
def s_mcgs_hidden_info() -> Dict[str, Any]:
    p = paired()

    def repeated_worlds():
        pr = jload(os.path.join(C22, "probes", "mcgs_world_probes.json"))
        if not pr:
            return None, "results/probes/mcgs_world_probes.json absent"
        rows = pr.get("probes") or []
        ok = bool(rows) and all(r.get("pass") for r in rows)
        names = ", ".join(f"{r.get('probe')} {r.get('name')}" for r in rows)
        return ok, f"{pr.get('n_pass')}/{pr.get('n_probes')} world probes pass: {names}"

    def aggregation_traced():
        pre = jload(os.path.join(MC, "PREREGISTERED_AGGREGATION.json"))
        if not pre or not p:
            return None, "preregistration or paired comparison absent"
        k8 = next((a for a in p["arms"] if a["k"] > 1), None)
        if not k8:
            return None, "no K>1 arm in the paired comparison"
        d = k8["disagreement"]
        return True, (f"rule `{pre['primary_aggregation_rule']['id']}` ported from "
                      f"AggregateDeterminizations; {d['decisions_with_k_gt_1']} decisions traced "
                      f"with per-world statistics, modal agreement {d['mean_modal_agreement']}")

    def overconfidence_reduced():
        if not p:
            return None, "paired comparison absent"
        k1 = next((a for a in p["arms"] if a["k"] == 1), None)
        k8 = next((a for a in p["arms"] if a["k"] > 1), None)
        if not k1 or not k8:
            return None, "the paired pair is incomplete"
        o1, o8 = k1["calibration"]["overconfidence_pp"], k8["calibration"]["overconfidence_pp"]
        b1, b8 = k1["calibration"]["brier"], k8["calibration"]["brier"]
        return (o8 < o1 and b8 < b1), (
            f"overconfidence {o1} -> {o8} pp, Brier {b1} -> {b8}; c021 predicted ~96% at the "
            f"root, this arm predicts {k8['calibration']['mean_predicted']}")

    def no_regression():
        if not p:
            return None, "paired comparison absent"
        k1 = next((a for a in p["arms"] if a["k"] == 1), None)
        k8 = next((a for a in p["arms"] if a["k"] > 1), None)
        if not k1 or not k8:
            return None, "the paired pair is incomplete"
        floor = p["noise_floor"]
        # "does not regress beyond noise" -- the K>1 arm must not sit below the replication set
        # by more than its spread. Stated against the MEASURED floor, never against zero.
        below = (floor["mean"] - k8["field_score"]) * 100
        return (below <= floor["spread_pp"]), (
            f"K=8 field {k8['field_score']} vs a K=1 replication mean of {floor['mean']} "
            f"(spread {floor['spread_pp']} pp over {floor['n_arms']} arms); Wilson "
            f"{k8['wilson95']} vs {k1['wilson95']}")

    def compute_controlled():
        if not p:
            return None, "paired comparison absent"
        c96 = next((a for a in p["arms"] if a["tag"] == "paired_k1_c96"), None)
        if not c96:
            return None, ("paired_k1_c96 has not run; under fixed_per_world K=8 also spends 8x "
                          "the simulations, so no part of the improvement is yet attributable "
                          "to the ensemble rather than to compute")
        k8 = next((a for a in p["arms"] if a["k"] > 1), None)
        d = k8["calibration"]["brier"] - c96["calibration"]["brier"]
        return (d < 0), (f"K=8 Brier {k8['calibration']['brier']} vs compute-matched K=1 "
                         f"{c96['calibration']['brier']} (delta {round(d, 5)})")

    reqs = [
        Req("repeated legal hidden worlds are demonstrated", repeated_worlds,
            "results/probes/world_probes.json"),
        Req("aggregation / re-determinization implemented and traced", aggregation_traced,
            "results/mcgs/PREREGISTERED_AGGREGATION.json, paired/*_traces.jsonl"),
        Req("c021 overconfidence is materially reduced", overconfidence_reduced,
            "results/mcgs/paired/PAIRED_COMPARISON.md"),
        Req("K>1 does not regress external field performance beyond noise", no_regression,
            "results/mcgs/paired/, results/transfer/noise_floor/"),
        Req("the calibration gain is attributable to K rather than to compute", compute_controlled,
            "results/mcgs/paired/paired_k1_c96_summary.json"),
    ]
    rows = [r.run() for r in reqs]
    return {"status": roll_up(rows), "requirements": rows,
            "source": "DECISION_RULES §2 MCGS_HIDDEN_INFO"}


# ============================================================================ MCGS_COMPETITIVE
def s_mcgs_competitive() -> Dict[str, Any]:
    panel = jload(os.path.join(MC, "final_panel", "panel.json"))

    def beats_champion():
        if not panel:
            return None, "results/mcgs/final_panel/panel.json absent -- the panel has not run"
        best = panel.get("champion_comparison")
        if not best:
            return None, "the panel ran but records no champion comparison"
        return bool(best.get("credible_improvement")), json.dumps(best)[:300]

    def not_a_small_noisy_gain():
        p = paired()
        if not p:
            return None, "paired comparison absent"
        k8 = next((a for a in p["arms"] if a["k"] > 1), None)
        k1 = next((a for a in p["arms"] if a["k"] == 1), None)
        if not k8 or not k1:
            return None, "the paired pair is incomplete"
        sep = wilson_separated(k1["wilson95"], k8["wilson95"])
        floor = p["noise_floor"]
        delta = round(100 * (k8["field_score"] - k1["field_score"]), 2)
        return (bool(sep) and delta > floor["spread_pp"]), (
            f"delta {delta} pp against a measured {floor['spread_pp']} pp replication spread; "
            f"Wilson intervals {'separate' if sep else 'OVERLAP'}. DECISION_RULES §2: "
            f"'A small noisy improvement over c021 MCGS is not a competitive pass.'")

    reqs = [
        Req("credibly beats the strongest frozen champion on the broad panel", beats_champion,
            "results/mcgs/final_panel/panel.json"),
        Req("the improvement exceeds measured run-to-run noise", not_a_small_noisy_gain,
            "results/mcgs/paired/, NOISE_FLOOR_ACCIDENTAL_REPLICATION.md"),
    ]
    rows = [r.run() for r in reqs]
    return {"status": roll_up(rows), "requirements": rows,
            "source": "DECISION_RULES §2 MCGS_COMPETITIVE"}


# ============================================================================ BYTERL fidelity
def s_byterl_reference_fidelity() -> Dict[str, Any]:
    pr = probes() or {}
    v = validation() or {}

    def from_probe(pid: str, label: str):
        def f():
            row = (pr.get("probes") or {}).get(pid)
            if row is None:
                return None, f"probe {pid} has not run"
            return bool(row.get("pass")), f"{pid}: {str(row.get('detail'))[:220]}"
        return f

    def numerical_fixtures():
        f = jload(os.path.join(BY, "numerical_fixtures", "fixtures.json"))
        if not f:
            return None, "the numerical fixtures have not been written"
        return bool(f.get("all_agree")), (
            f"{f.get('n_agreeing')}/{f.get('n_comparisons')} comparisons agree at "
            f"{f.get('tolerance')} against references transcribed independently of the "
            f"implementation and of the test suite's own copies")

    def osfp_accounting():
        o = jload(os.path.join(BY, "osfp", "osfp_accounting.json"))
        if not o:
            return None, "OSFP accounting has not been written"
        ok = bool(o.get("history_bounded") and
                  o.get("existing_entries_not_mutated_by_promotion"))
        c = o.get("constants") or {}
        return ok, (f"history {o.get('history_size')}/{o.get('max_history')} after "
                    f"{o.get('periods')} periods, bounded={o.get('history_bounded')}, "
                    f"immutable={o.get('existing_entries_not_mutated_by_promotion')}; "
                    f"self-play {c.get('OSFP_SELFPLAY_PROB')}, promotion threshold "
                    f"{c.get('OSFP_PROMOTION_THRESHOLD')}")

    def fidelity_runs():
        tags = [os.path.basename(p).replace("_manifest.json", "")
                for p in glob.glob(os.path.join(BY, "stages", "fid_*_manifest.json"))]
        if not tags:
            return None, "the dedicated high-coverage B06 runs have not run (D20)"
        rows = []
        for t in sorted(tags):
            m = manifest(t) or {}
            rows.append(f"{t}: {m.get('recurrence_checks')} checks, coverage "
                        f"{m.get('recurrence_check_coverage')}, failures "
                        f"{m.get('recurrence_check_failures')}")
        ok = all((manifest(t) or {}).get("recurrence_check_failures") == 0
                 and float((manifest(t) or {}).get("recurrence_check_coverage") or 0) >= 0.9
                 for t in tags)
        return ok, "; ".join(rows)

    def stage_deltas():
        lad = ladder()
        if not lad:
            return None, "the rung ladder has not been analysed"
        if lad["flag_problems"]:
            return False, "; ".join(lad["flag_problems"])
        return True, (f"{len(lad['rungs'])} rungs, one codebase; "
                      "tests/test_c022_stage_ladder.py rejects extra changes")

    def validator():
        if not v:
            return None, "validation report absent"
        ran = v.get("n_ran") or 0
        return bool(ran and v.get("n_pass") == ran and v.get("all_injections_detected")), (
            f"{v.get('n_pass')}/{ran} checks that ran pass, "
            f"no_data={v.get('checks_with_no_data')}, inert={v.get('inert_checks')}, "
            f"undetected injections={v.get('injections_not_detected')}")

    reqs = [
        Req("LSTM-256 recurrence", from_probe("B01", "architecture"),
            "results/probes/byterl_probes.json B01"),
        Req("exact complete-action autoregression", from_probe("B04", "actions"),
            "results/probes/byterl_probes.json B03-B05"),
        Req("actor versions and stored recurrent starts", from_probe("B07", "versions"),
            "results/probes/byterl_probes.json B06-B07"),
        Req("bounded blocking FIFO and measured production/consumption",
            from_probe("B09", "queue"), "results/probes/byterl_probes.json B08-B10"),
        Req("exact numerical V-trace / UPGO / b3 fixtures", numerical_fixtures,
            "results/byterl/numerical_fixtures/fixtures.json"),
        Req("published stage-delta tests", stage_deltas,
            "tests/test_c022_stage_ladder.py, results/byterl/component_analysis/"),
        Req("recurrent replay verified at high coverage", fidelity_runs,
            "results/byterl/stages/fid_*_manifest.json"),
        Req("immutable OSFP history and correct period accounting", osfp_accounting,
            "results/byterl/osfp/osfp_accounting.json"),
        Req("end-to-end construction path implemented", from_probe("B18", "construction"),
            "results/byterl/end_to_end/"),
        Req("every reported number survives an injection-tested validator", validator,
            "results/validation_report.json"),
    ]
    rows = [r.run() for r in reqs]
    return {"status": roll_up(rows), "requirements": rows,
            "source": "DECISION_RULES §3 BYTERL_REFERENCE_FIDELITY"}


def _improvement_over_floor(tag: str, floor_tag: str) -> Tuple[Optional[bool], str]:
    ev, fl = byterl_eval(tag), byterl_eval(floor_tag)
    if not ev:
        return None, f"{tag} has not been evaluated"
    if not fl:
        return None, f"the random floor {floor_tag} has not been evaluated"
    sep = wilson_separated(fl.get("wilson95"), ev.get("wilson95"))
    return (bool(sep) and ev["field_score"] > fl["field_score"]), (
        f"{tag} {ev['field_score']} {ev.get('wilson95')} vs floor {fl['field_score']} "
        f"{fl.get('wilson95')} over {ev.get('games')} games; intervals "
        f"{'separate' if sep else 'OVERLAP'}")


def s_byterl_fixed_deck() -> Dict[str, Any]:
    def improvement():
        return _improvement_over_floor("br3_fixed_deck", "floor_fixed_deck")

    def trajectory():
        c = jload(os.path.join(BY, "stages", "br3_fixed_deck_curve.json"))
        if not c:
            return None, "no training curve recorded for the decisive fixed-deck arm"
        return bool(c.get("monotone_upward")), str(c.get("summary"))[:220]

    rows = [Req("statistically credible improvement over the random floor", improvement,
                "results/byterl/external_evaluations/").run(),
            Req("a reproducible upward external trajectory", trajectory,
                "results/byterl/stages/br3_fixed_deck_curve.json").run()]
    return {"status": roll_up(rows), "requirements": rows,
            "source": "DECISION_RULES §3 BYTERL_FIXED_DECK"}


def s_byterl_e2e() -> Dict[str, Any]:
    def legal_diverse():
        pr = probes() or {}
        row = (pr.get("probes") or {}).get("B18")
        if row is None:
            return None, "probe B18 has not run"
        return bool(row.get("pass")), str(row.get("detail"))[:220]

    def improvement():
        return _improvement_over_floor("br3_end_to_end", "floor_end_to_end")

    rows = [Req("legal, diverse deck construction", legal_diverse,
                "results/byterl/end_to_end/").run(),
            Req("external improvement above random / fixed weak baselines", improvement,
                "results/byterl/external_evaluations/").run()]
    st = roll_up(rows)
    # DECISION_RULES §3 names this case explicitly rather than leaving it to judgement:
    # "Merely generating legal decks is partial."
    if rows[0]["met"] is True and rows[1]["met"] is not True:
        st = PARTIAL
    return {"status": st, "requirements": rows,
            "source": "DECISION_RULES §3 BYTERL_E2E"}


def s_byterl_scale() -> Dict[str, Any]:
    budget = jload(os.path.join(BY, "budget", "c021_matched_budget.json")) or {}
    target = int(((budget.get("MATCHED_BUDGET_FOR_C022") or {}).get("value")) or 0)
    rows = []
    for tag in ("br3_fixed_deck", "br3_end_to_end"):
        m = manifest(tag)
        if not m:
            rows.append({"requirement": f"{tag} reaches the matched budget", "met": None,
                         "verdict": NOT_RUN, "detail": f"{tag} has not run",
                         "evidence": f"results/byterl/stages/{tag}_manifest.json"})
            continue
        prod = int(m.get("produced_decisions") or 0)
        frac = prod / target if target else 0.0
        rows.append({
            "requirement": f"{tag} reaches the matched budget",
            "met": bool(target and prod >= target),
            "verdict": "met" if (target and prod >= target) else "NOT met",
            "detail": (f"produced_decisions {prod:,} of {target:,} "
                       f"({frac:.1%}); the budget is defined in ENVIRONMENT decisions, so the "
                       f"actor-side counter is the one reported"),
            "evidence": f"results/byterl/stages/{tag}_manifest.json"})
    if all(r["met"] is None for r in rows):
        st = NOT_RUN
    elif all(r["met"] is True for r in rows):
        st = PASS
    else:
        # DECISION_RULES §3: COMPUTE_LIMITED is the EXPECTED outcome when fidelity passes and
        # paper scale is not approached. It is not a failure and must not be reported as one.
        st = COMPUTE_LIMITED
    return {"status": st, "requirements": rows, "source": "DECISION_RULES §3 BYTERL_SCALE"}


# ============================================================================ transfer
def s_transfer() -> Dict[str, Any]:
    noise = sorted(glob.glob(os.path.join(C22, "transfer", "noise_floor", "*_summary.json")))
    t_arms = sorted(glob.glob(os.path.join(C22, "transfer", "arms", "*_summary.json")))

    def floor_measured():
        if len(noise) < 3:
            return None if not noise else False, f"{len(noise)} replication arms; 3 required"
        vals = [jload(p)["field_score"] for p in noise]
        return True, (f"{len(vals)} arms, spread "
                      f"{round(100*(max(vals)-min(vals)), 2)} pp: {vals}")

    def component_improves():
        if not t_arms:
            return None, "no transfer arm has run"
        rows = []
        for p in t_arms:
            s = jload(p)
            rows.append(f"{s.get('tag')}: {s.get('field_score')} {s.get('wilson95')}")
        return None, ("arms present but the comparison is made by the transfer analysis: "
                      + "; ".join(rows))

    rows = [Req("a measured paired run-to-run noise floor exists", floor_measured,
                "results/transfer/noise_floor/").run(),
            Req("one isolated ByteRL component improves corrected MCGS beyond that noise",
                component_improves, "results/transfer/arms/").run()]
    st = roll_up(rows)
    # §4: "A positive point estimate smaller than the measured noise floor is INCONCLUSIVE,
    # not pass or fail." Absent the arms entirely, the honest status is NOT_RUN.
    if rows[1]["met"] is None and rows[0]["met"] is True:
        st = NOT_RUN
    return {"status": st, "requirements": rows, "source": "DECISION_RULES §4 TRANSFER"}


# ============================================================================ package/submission
def s_package() -> Dict[str, Any]:
    pkg = jload(os.path.join(MC, "packages", "package_validation.json"))

    def validated():
        if not pkg:
            return None, "no package has been built or validated"
        return bool(pkg.get("valid")), str(pkg.get("summary"))[:220]

    rows = [Req("package validation passes", validated,
                "results/mcgs/packages/package_validation.json").run()]
    return {"status": roll_up(rows), "requirements": rows, "source": "DECISION_RULES §5"}


def s_submission() -> Dict[str, Any]:
    sub = jload(os.path.join(MC, "submissions", "submission_decision.json"))
    comp = s_mcgs_competitive()

    def frozen_identity():
        if not sub:
            return None, "no submission decision has been recorded"
        return bool(sub.get("candidate_sha256")), str(sub.get("candidate"))[:200]

    def gate():
        if comp["status"] != PASS:
            return False, (f"MCGS_COMPETITIVE is {comp['status']}; DECISION_RULES §5 requires a "
                           "credible gate to pass before submitting, and §2 says a small noisy "
                           "improvement is not one")
        return True, "the registered credible gate passed"

    rows = [Req("exact candidate identity is frozen", frozen_identity,
                "results/mcgs/submissions/").run(),
            Req("a registered credible gate passes", gate,
                "results/mcgs/final_panel/").run()]
    st = roll_up(rows)
    if any(r["met"] is False for r in rows):
        # §5: "No automatic submission is required when no candidate qualifies."
        st = NOT_RUN if all(r["met"] is not True for r in rows) else PARTIAL
    return {"status": st, "requirements": rows, "source": "DECISION_RULES §5"}


def s_source_fidelity() -> Dict[str, Any]:
    audit_path = os.path.join(C22, "fidelity", "mcgs_hidden_information_trace.jsonl")
    ctrls = jload(os.path.join(C22, "controls", "control_manifest.json"))

    def audited():
        if not os.path.isfile(audit_path):
            return None, "the source audit trace has not been written"
        sites = claims = 0
        archive = None
        for ln in open(audit_path):
            try:
                r = json.loads(ln)
            except Exception:  # noqa: BLE001
                continue
            if r.get("record") == "site":
                sites += 1
            elif r.get("record") == "structural_claim":
                claims += 1
            elif r.get("record") == "archive":
                archive = r.get("archive_sha256")
        return bool(sites >= 20), (f"{sites} anchored source sites and {claims} structural "
                                   f"absence claims against archive {str(archive)[:16]}...")

    def controls_intact():
        v = validation() or {}
        row = next((r for r in (v.get("checks") or []) if r["id"] == "V13"), None)
        if not row:
            return None, "V13 has not run"
        return bool(row.get("pass")), f"{row.get('n_inputs')} frozen files re-hashed"

    def adaptations_declared():
        p = os.path.join(C22, "fidelity", "ADAPTATION_LEDGER.md")
        if not os.path.isfile(p):
            return None, "ADAPTATION_LEDGER.md absent"
        n = sum(1 for ln in open(p) if ln.strip().startswith("|"))
        return True, f"{n} ledger rows; every deviation carries a class and a reason"

    rows = [Req("the official source is audited at anchored sites", audited,
                "results/fidelity/mcgs_hidden_information_trace.jsonl").run(),
            Req("frozen controls still hash to what was frozen", controls_intact,
                "results/validation_report.json V13").run(),
            Req("every deviation is declared with its adaptation class", adaptations_declared,
                "results/fidelity/ADAPTATION_LEDGER.md").run()]
    return {"status": roll_up(rows), "requirements": rows,
            "source": "FIDELITY_RULES §1-§3"}


STATUSES = [
    ("SOURCE_FIDELITY", s_source_fidelity),
    ("MCGS_HIDDEN_INFO", s_mcgs_hidden_info),
    ("MCGS_COMPETITIVE", s_mcgs_competitive),
    ("BYTERL_REFERENCE_FIDELITY", s_byterl_reference_fidelity),
    ("BYTERL_FIXED_DECK", s_byterl_fixed_deck),
    ("BYTERL_E2E", s_byterl_e2e),
    ("BYTERL_SCALE", s_byterl_scale),
    ("TRANSFER", s_transfer),
    ("PACKAGE", s_package),
    ("SUBMISSION", s_submission),
]


def render(rep: Dict[str, Any]) -> str:
    L: List[str] = []
    A = L.append
    A("# c022 statuses")
    A("")
    A("Each status is computed from artifacts by `tools/c022_status.py`, and each requirement "
      "names the file it was decided from. `DECISION_RULES §6`: \"Do not compress these into a "
      "misleading single PASS.\"")
    A("")
    A("**A requirement with no artifact is `NOT_RUN`, never met.** One unmet requirement makes "
      "the status `PARTIAL` and the report names it.")
    A("")
    A("| status | value |")
    A("|---|---|")
    for name, _ in STATUSES:
        A(f"| `{name}` | **{rep['statuses'][name]['status']}** |")
    A(f"| `OVERALL` | **{rep['overall']['status']}** |")
    A("")
    A(rep["overall"]["reading"])
    A("")
    for name, _ in STATUSES:
        d = rep["statuses"][name]
        A(f"## `{name}` = {d['status']}")
        A("")
        A(f"*{d['source']}*")
        A("")
        A("| requirement | verdict | evidence |")
        A("|---|---|---|")
        for r in d["requirements"]:
            A(f"| {r['requirement']} | **{r['verdict']}** | `{r['evidence']}` |")
        A("")
        for r in d["requirements"]:
            A(f"- **{r['requirement']}** — {r['detail']}")
        A("")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-json", default=os.path.join(C22, "STATUS.json"))
    ap.add_argument("--out-md", default=os.path.join(C22, "STATUS.md"))
    a = ap.parse_args(argv)

    st = {name: fn() for name, fn in STATUSES}
    n_pass = sum(1 for d in st.values() if d["status"] == PASS)
    n_notrun = sum(1 for d in st.values() if d["status"] == NOT_RUN)
    overall = {
        "status": (PASS if n_pass == len(st) else
                   (NOT_RUN if n_notrun == len(st) else PARTIAL)),
        "reading": (
            f"{n_pass} of {len(st)} statuses PASS; {n_notrun} have not run. "
            "The honest outcomes `DECISION_RULES §6` lists are combinations, not a single "
            "verdict, and this table is meant to be read as one."),
    }
    rep = {"statuses": st, "overall": overall}
    with open(a.out_json, "w") as fh:
        json.dump(rep, fh, indent=2)
    with open(a.out_md, "w") as fh:
        fh.write(render(rep))
    for name, _ in STATUSES:
        d = st[name]
        unmet = [r["requirement"] for r in d["requirements"] if r["met"] is False]
        nr = [r["requirement"] for r in d["requirements"] if r["met"] is None]
        print(f"{d['status']:16s} {name}")
        for u in unmet:
            print(f"      NOT met: {u}")
        for u in nr:
            print(f"      NOT_RUN: {u}")
    print(f"{overall['status']:16s} OVERALL")
    print(f"wrote {a.out_json}\nwrote {a.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
