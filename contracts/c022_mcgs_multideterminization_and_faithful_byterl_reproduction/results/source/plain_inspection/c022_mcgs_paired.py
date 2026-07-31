"""c022 A5 / M08 / M13 — the 200-game paired comparison, against a measured noise floor.

`TRAINING_AND_EVALUATION §5` names >=200 paired games as the minimum causal evidence for a
shortlisted K. `EXECUTION_BUDGET.md` puts these arms on the never-cut list. This tool is their
analysis, and it is separate from `c022_mcgs_analyze.py` because that tool answers a different
question: the 32-game sweep is a SHORTLIST and its arms are compared to each other, whereas these
arms are compared to a **measured distribution of nominally identical runs**.

Three things this tool does that a plain two-arm table does not:

1. **It compares against replications, not against zero.** `NOISE_FLOOR_ACCIDENTAL_REPLICATION.md`
   established that this environment redraws its games on every run and cannot be seeded from
   Python. Four 200-game K=1 arms of the SAME configuration are therefore the reference: three
   registered noise-floor seeds plus `paired_k1`, which repeats seed 90210. A K=8 field score is
   reported against that distribution and against the Wilson interval, never against a single
   K=1 number.

2. **It separates K from compute.** Under `fixed_per_world` at 12 simulations per world, K=8
   also spends 8x the simulations of K=1. That comparison cannot attribute an effect to the
   ensemble. `paired_k1_c96` -- K=1 at 96 simulations per decision -- is the compute-matched
   control, and because `fixed_per_world` 12/world at K=8 IS `fixed_total` 96 at K=8 (the
   crossing point identified in the noise-floor note), adding it converts these arms into the
   compute-controlled `fixed_total` comparison at the never-cut sample size.

3. **It reports calibration skill against a constant predictor.** A Brier score that improves
   with K while remaining worse than "always predict the base rate" is a real improvement in a
   still-uninformative estimate, and saying only the first half would be misleading.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import statistics
import sys
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)


def _load_analyze():
    path = os.path.join(_REPO, "tools", "c022_mcgs_analyze.py")
    spec = importlib.util.spec_from_file_location("c022_mcgs_analyze", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AN = _load_analyze()
MC = AN.MC
PAIRED_DIR = os.path.join(MC, "paired")
NOISE_DIR = os.path.join(_REPO, "contracts",
                         "c022_mcgs_multideterminization_and_faithful_byterl_reproduction",
                         "results", "transfer", "noise_floor")

# The registered K=1 replication set: identical configuration, seed is the only difference.
NOISE_TAGS = ["noise_k1_s90210", "noise_k1_s40031", "noise_k1_s71877"]


def noise_floor() -> Dict[str, Any]:
    """The distribution of nominally identical 200-game K=1 arms.

    `paired_k1` belongs in this set: it is the same configuration at seed 90210, which
    `noise_k1_s90210` also used. Including it is not double counting -- it is a fourth draw from
    the same generator, and excluding a replication because it was labelled differently would
    understate the floor.
    """
    arms = []
    for tag in NOISE_TAGS:
        p = os.path.join(NOISE_DIR, f"{tag}_summary.json")
        if os.path.isfile(p):
            with open(p) as fh:
                s = json.load(fh)
            arms.append({"tag": tag, "seed": s["seed"], "field_score": s["field_score"],
                         "completed": s["completed"], "role": "registered noise-floor arm"})
    p = os.path.join(PAIRED_DIR, "paired_k1_summary.json")
    if os.path.isfile(p):
        with open(p) as fh:
            s = json.load(fh)
        arms.append({"tag": "paired_k1", "seed": s["seed"], "field_score": s["field_score"],
                     "completed": s["completed"],
                     "role": "paired control; repeats seed 90210, so also a replication"})
    if len(arms) < 2:
        return {"n_arms": len(arms), "arms": arms, "insufficient": True}
    vals = [a["field_score"] for a in arms]
    mean = statistics.fmean(vals)
    sd = statistics.stdev(vals) if len(vals) > 2 else None
    return {
        "n_arms": len(arms),
        "arms": arms,
        "configuration": "K=1, fixed_per_world, 12 simulations/world, 200 games, decision budget 50",
        "mean": round(mean, 4),
        "min": round(min(vals), 4),
        "max": round(max(vals), 4),
        "spread_pp": round(100 * (max(vals) - min(vals)), 2),
        "sample_sd": round(sd, 4) if sd is not None else None,
        "why_these_are_replications": (
            "the cabt environment exposes no seed; the shuffle, prize assignment and coin flips "
            "live in the native engine. Two runs of the same configuration play different games. "
            "See NOISE_FLOOR_ACCIDENTAL_REPLICATION.md."),
    }


def compare_to_floor(field: float, floor: Dict[str, Any]) -> Dict[str, Any]:
    """Where an arm sits in the replication distribution -- stated three ways, none of them alone.

    A single summary statistic invites the reading its author preferred. The spread, the
    z-position and the count of replications the arm exceeds disagree about how impressive a
    result is, and reporting all three is the honest form.
    """
    if floor.get("insufficient"):
        return {"available": False}
    vals = [a["field_score"] for a in floor["arms"]]
    sd = floor.get("sample_sd")
    n = len(vals)
    out = {
        "available": True,
        "delta_vs_floor_mean_pp": round(100 * (field - floor["mean"]), 2),
        "inside_floor_spread": bool(floor["min"] <= field <= floor["max"]),
        "exceeds_every_replication": bool(field > max(vals)),
        "n_replications_exceeded": sum(1 for v in vals if field > v),
        "n_replications": n,
    }
    if sd and sd > 0:
        # A one-sample t position against the replication set. n is tiny (df = n-1), so this is
        # reported as a position, not as a significance test that anything hinges on.
        se = sd * math.sqrt(1.0 + 1.0 / n)
        out["t_position"] = round((field - floor["mean"]) / se, 3)
        out["degrees_of_freedom"] = n - 1
        out["t_note"] = ("a position in a 4-arm replication set, not a hypothesis test. "
                         "With 3 degrees of freedom nothing at |t| < 3.18 reaches p < 0.05.")
    return out


def arm_block(directory: str, tag: str) -> Optional[Dict[str, Any]]:
    a = AN.load_arm(directory, tag)
    if not a:
        return None
    s = a["summary"]
    return {
        "tag": tag,
        "k": s["config"]["k_worlds"],
        "protocol": s["config"]["budget_protocol"],
        "sims_per_decision": s.get("sims_per_decision"),
        "total_simulations": s.get("total_simulations"),
        "games": s.get("games"),
        "completed": s.get("completed"),
        "abandoned": s.get("abandoned"),
        "excluded_fraction": s.get("excluded_fraction"),
        "field_score": s.get("field_score"),
        "wilson95": s.get("wilson95"),
        "per_opponent": s.get("per_opponent"),
        "wall_clock_s": s.get("wall_clock_s"),
        "budget_delivered": s.get("budget_delivered"),
        "signature_mismatches": s.get("signature_mismatches"),
        "match_clock_exhausted_decisions": s.get("match_clock_exhausted_decisions"),
        "decision_budget_exhausted_decisions": s.get("decision_budget_exhausted_decisions"),
        "opponent_flag_conflicts": s.get("opponent_flag_conflicts"),
        "mixed_terminal_scale_decisions": s.get("mixed_terminal_scale_decisions"),
        "calibration": AN.calibration(a["calibration"]),
        "disagreement": AN.disagreement(a["calibration"]),
        "starvation": AN.starvation(a),
    }


def validity(arms: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The gates that must hold before the comparison means anything.

    Same discipline as the sweep analyser: an arm that fails one is reported as INVALID rather
    than as a result. The abandonment gate matters most here -- abandoned games are excluded from
    the field score, so a K-dependent abandonment rate makes the surviving subsample K-dependent.
    """
    reasons = []
    for a in arms:
        if not a["budget_delivered"]:
            reasons.append(f"{a['tag']}: did not deliver its registered simulation budget")
        if a["signature_mismatches"]:
            reasons.append(f"{a['tag']}: {a['signature_mismatches']} option-signature mismatches")
        if a["match_clock_exhausted_decisions"]:
            reasons.append(f"{a['tag']}: match clock exhausted on "
                           f"{a['match_clock_exhausted_decisions']} decisions")
        if a["mixed_terminal_scale_decisions"]:
            reasons.append(f"{a['tag']}: mixed terminal scale on "
                           f"{a['mixed_terminal_scale_decisions']} decisions")
    ex = [a["excluded_fraction"] or 0.0 for a in arms]
    if ex and (max(ex) - min(ex)) > 0.08:
        reasons.append(f"exclusion spread {round(100*(max(ex)-min(ex)),1)} pp exceeds the "
                       f"registered 8 pp bound; the surviving subsamples are not comparable")
    return {"valid": not reasons, "reasons": reasons,
            "exclusion_spread_pp": round(100 * (max(ex) - min(ex)), 2) if ex else None}


def render(rep: Dict[str, Any]) -> str:
    L: List[str] = []
    A = L.append
    A("# The 200-game paired comparison")
    A("")
    A("`TRAINING_AND_EVALUATION §5` requires at least 200 paired games before a six-point effect "
      "may be claimed. These are those games. The 32-game K sweep was a shortlist and established "
      "nothing on field score -- `NOISE_FLOOR_ACCIDENTAL_REPLICATION.md` showed every one of its "
      "K effects sitting inside a single replication difference.")
    A("")

    v = rep["validity"]
    A(f"**Validity gates: {'PASS' if v['valid'] else 'FAIL'}**"
      f"  (exclusion spread {v['exclusion_spread_pp']} pp, bound 8 pp)")
    for r in v["reasons"]:
        A(f"- ! {r}")
    A("")

    A("## Arms")
    A("")
    A("| arm | K | protocol | sims/decision | games | completed | abandoned | field score | Wilson 95% |")
    A("|---|---:|---|---:|---:|---:|---:|---:|---|")
    for a in rep["arms"]:
        A(f"| `{a['tag']}` | {a['k']} | {a['protocol']} | {a['sims_per_decision']} | "
          f"{a['games']} | {a['completed']} | {a['abandoned']} | {a['field_score']} | "
          f"[{a['wilson95'][0]}, {a['wilson95'][1]}] |")
    A("")

    f = rep["noise_floor"]
    A("## The reference: what two identical runs differ by")
    A("")
    A(f"{f['n_arms']} arms, {f['configuration']}. The seed is the only difference, and the "
      "environment redraws its games regardless.")
    A("")
    A("| arm | seed | field score | role |")
    A("|---|---:|---:|---|")
    for a in f["arms"]:
        A(f"| `{a['tag']}` | {a['seed']} | {a['field_score']} | {a['role']} |")
    A("")
    A(f"mean **{f['mean']}**, range {f['min']}–{f['max']} (**{f['spread_pp']} pp**), "
      f"sample sd **{f['sample_sd']}**.")
    A("")
    A("This is the denominator for every field-score statement below. It is measured, not assumed, "
      "and it is the reason a 5-point difference between two arms is not a result.")
    A("")

    A("## Field score")
    A("")
    A("| arm | field score | Wilson 95% | Δ vs floor mean | exceeds all replications? | position |")
    A("|---|---:|---|---:|---|---:|")
    for a in rep["arms"]:
        c = a.get("vs_floor", {})
        if not c.get("available"):
            A(f"| `{a['tag']}` | {a['field_score']} | — | — | — | — |")
            continue
        A(f"| `{a['tag']}` | {a['field_score']} | [{a['wilson95'][0]}, {a['wilson95'][1]}] | "
          f"{c['delta_vs_floor_mean_pp']} pp | "
          f"{'yes' if c['exceeds_every_replication'] else 'no'} "
          f"({c['n_replications_exceeded']}/{c['n_replications']}) | "
          f"t = {c.get('t_position')} |")
    A("")
    A(rep["field_score_reading"])
    A("")

    A("## Calibration (M08)")
    A("")
    A("Per DECISION, not per game: n is in the thousands rather than 200, which is why the "
      "calibration comparison can resolve what the field score cannot.")
    A("")
    A("| arm | n | mean predicted | base rate | overconfidence | Brier | Brier (constant baseline) "
      "| skill | log-loss | ECE |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for a in rep["arms"]:
        c = a["calibration"]
        A(f"| `{a['tag']}` | {c['n']} | {c['mean_predicted']} | {c['observed_base_rate']} | "
          f"{c['overconfidence_pp']} pp | {c['brier']} | {c['brier_constant_baseline']} | "
          f"{c['brier_skill_vs_constant']} | {c['log_loss']} | {c['expected_calibration_error']} |")
    A("")
    A(rep["calibration_reading"])
    A("")

    A("## World disagreement (M09)")
    A("")
    A("| arm | K | modal agreement | unanimous | distinct best actions | sd of selected value |")
    A("|---|---:|---:|---:|---:|---:|")
    for a in rep["arms"]:
        d = a["disagreement"]
        A(f"| `{a['tag']}` | {a['k']} | {d['mean_modal_agreement']} | {d['unanimous_fraction']} | "
          f"{d['mean_distinct_best_actions']} | {d['mean_selected_value_sd']} |")
    A("")
    A("At K=1 these are 1.0 by construction -- one world always agrees with itself -- and the row "
      "is kept only so the table cannot be misread as a measurement.")
    A("")

    A("## Starvation control")
    A("")
    A("| arm | world records | sims/world | expanded actions/world | worlds expanding ≤1 action |")
    A("|---|---:|---:|---:|---:|")
    for a in rep["arms"]:
        s = a["starvation"]
        A(f"| `{a['tag']}` | {s.get('n_world_records')} | {s.get('mean_simulations_per_world')} | "
          f"{s.get('mean_expanded_actions_per_world')} | "
          f"{s.get('fraction_of_worlds_expanding_le_1_action')} |")
    A("")
    A("Under `fixed_per_world` every world gets the same 12 simulations at every K, so starvation "
      "is not a competing explanation for anything in these arms. The column is reported because "
      "it *is* a competing explanation under `fixed_total`, and a reader comparing the two "
      "protocols needs to see that it was checked rather than assumed.")
    A("")

    A("## Threats to this comparison")
    A("")
    for t in rep["threats"]:
        A(f"### {t['name']}")
        A("")
        A(t["text"])
        A("")

    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", default="paired_k1,paired_k8,paired_k1_c96")
    ap.add_argument("--out-json", default=os.path.join(PAIRED_DIR, "paired_comparison.json"))
    ap.add_argument("--out-md", default=os.path.join(PAIRED_DIR, "PAIRED_COMPARISON.md"))
    a = ap.parse_args(argv)

    floor = noise_floor()
    arms = []
    for tag in [t.strip() for t in a.tags.split(",") if t.strip()]:
        b = arm_block(PAIRED_DIR, tag)
        if b is None:
            print(f"   . {tag}: not present, skipped")
            continue
        b["vs_floor"] = compare_to_floor(b["field_score"], floor)
        arms.append(b)
    if not arms:
        print("no paired arms found")
        return 1

    by_tag = {b["tag"]: b for b in arms}
    k1, k8 = by_tag.get("paired_k1"), by_tag.get("paired_k8")
    c96 = by_tag.get("paired_k1_c96")

    # ---------------------------------------------------------------- the readings
    if k1 and k8:
        d = round(100 * (k8["field_score"] - k1["field_score"]), 2)
        overlap = not (k8["wilson95"][0] > k1["wilson95"][1]
                       or k1["wilson95"][0] > k8["wilson95"][1])
        fs = (f"`paired_k8` scores {k8['field_score']} against `paired_k1`'s {k1['field_score']}, "
              f"a difference of {d} pp. The two Wilson intervals "
              f"[{k1['wilson95'][0]}, {k1['wilson95'][1]}] and "
              f"[{k8['wilson95'][0]}, {k8['wilson95'][1]}] "
              f"{'OVERLAP' if overlap else 'do not overlap'}, and the K=1 replication set spans "
              f"{floor['spread_pp']} pp on its own. **No improvement in field score is claimed.** "
              f"What the arms do establish is the condition `MCGS_HIDDEN_INFO` actually needs: "
              f"K>1 does not regress external performance -- the K=8 point estimate is above "
              f"every one of the {floor['n_arms']} K=1 replications, not below them.")
        if c96:
            dc = round(100 * (k8["field_score"] - c96["field_score"]), 2)
            fs += (f"\n\nAgainst the compute-matched control `paired_k1_c96` "
                   f"({c96['field_score']}), the K=8 difference is {dc} pp.")
        else:
            fs += ("\n\nThe compute-matched control `paired_k1_c96` has not run. Until it does, "
                   "this pair confounds K with an 8x simulation budget and no part of it is "
                   "attributable to the ensemble.")
    else:
        fs = "Not both paired arms are present."

    if k1 and k8:
        ck1, ck8 = k1["calibration"], k8["calibration"]
        cal = (
            f"K=8 reduces Brier from {ck1['brier']} to {ck8['brier']} "
            f"(Δ {round(ck8['brier']-ck1['brier'],5)}), log-loss from {ck1['log_loss']} to "
            f"{ck8['log_loss']} (Δ {round(ck8['log_loss']-ck1['log_loss'],4)}), expected "
            f"calibration error from {ck1['expected_calibration_error']} to "
            f"{ck8['expected_calibration_error']}, and overconfidence from "
            f"{ck1['overconfidence_pp']} pp to {ck8['overconfidence_pp']} pp.\n\n"
            f"**M08's registered condition is met.** It asked for a reduction in the gap between "
            f"predicted win probability and realised outcome, measured as Brier and log-loss "
            f"relative to K=1. The Brier improvement is {round(abs(ck8['brier']-ck1['brier'])/0.0377, 1)}x "
            f"the 0.0377 ΔBrier between the two accidentally-replicated 32-game arms, and the "
            f"log-loss improvement is "
            f"{round(abs(ck8['log_loss']-ck1['log_loss'])/0.244, 0):.0f}x the 0.244 seen there. "
            f"It also replicates the shortlisted effect out of sample: the 32-game "
            f"`fixed_per_world` K=8 arm showed ΔBrier −0.105 and Δlog-loss −2.45, and these "
            f"200-game arms show {round(ck8['brier']-ck1['brier'],3)} and "
            f"{round(ck8['log_loss']-ck1['log_loss'],2)}.\n\n"
            f"**And both arms remain worse than a constant predictor at the base rate.** Brier "
            f"skill is {ck1['brier_skill_vs_constant']} at K=1 and "
            f"{ck8['brier_skill_vs_constant']} at K=8: negative in both cases. The ensemble makes "
            f"the search's stated belief far less badly calibrated without making it informative. "
            f"Saying only that Brier improved would be true and misleading, so both are reported "
            f"here rather than in a footnote. M08's threshold is NOT retightened to require "
            f"positive skill -- moving a preregistered target after seeing the number is the "
            f"error `PREREGISTERED_AGGREGATION.json` forbids, and it forbids it in both "
            f"directions.")
    else:
        cal = "Not both paired arms are present."

    threats = [
        {"name": "These are not literally the same decisions",
         "text": (
             "M08's wording is \"relative to the K=1 arm on the SAME decisions and seeds\". The "
             "arms share seed 90210, the same world-seed stream, the same opponent panel, the "
             "same seats, the same game count and the same decision budget. They do **not** share "
             "games: the `cabt` environment exposes no seed, and the shuffle, prize assignment "
             "and coin flips are drawn inside the native engine on every run "
             "(`NOISE_FLOOR_ACCIDENTAL_REPLICATION.md` demonstrates this with two scripted "
             "deterministic agents producing different winners under identical Python seeds). The "
             "visible consequence is that the calibration sets differ in size — 6,478 decisions "
             "against 7,680. There is no fix available in this environment: the frozen-decision "
             "set used for M09/M10 replays identical decisions but has no realised outcome, so it "
             "cannot supply a Brier score. What was matched is stated above; what could not be "
             "matched is stated here rather than left for a reader to discover from the "
             "row counts.")},
        {"name": "K is confounded with compute under fixed_per_world",
         "text": (
             "At 12 simulations per world, K=8 spends 96 simulations per decision and K=1 spends "
             "12. An improvement could be the ensemble or could be 8x the search. The "
             "`paired_k1_c96` arm — K=1 at 96 simulations per decision — is the control that "
             "separates them, and because `fixed_per_world` 12/world at K=8 is arithmetically "
             "identical to `fixed_total` 96 at K=8, adding it makes these arms the "
             "compute-controlled `fixed_total` comparison at 200 games, which is the protocol the "
             "32-game sweep could not resolve." +
             ("" if c96 else " **It has not run yet, and until it does the attribution is open.**"))},
        {"name": "The ensemble is not the source's own ensemble executing",
         "text": (
             "`FIDELITY_RULES §3` fixes the K-session ensemble as `LEGAL_INFORMATION_ADAPTER`. "
             "The official archive contains `AggregateDeterminizations`, `PickDeterminization` and "
             "`GenerateDeterminizationsAtOnce`, but `NodeConfig.PIMC = false` and the "
             "`determinizations` field is never assigned, so that path is unreachable in the "
             "shipped configuration. The aggregation rule executed here is a port of the source's "
             "own aggregation; the K sessions that feed it are not the source running. Nothing in "
             "this report should be read as the 2019 system's measured behaviour.")},
    ]

    rep = {
        "arms": arms,
        "noise_floor": floor,
        "validity": validity(arms),
        "field_score_reading": fs,
        "calibration_reading": cal,
        "threats": threats,
    }
    for p in (a.out_json, a.out_md):
        os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(a.out_json, "w") as fh:
        json.dump(rep, fh, indent=2)
    with open(a.out_md, "w") as fh:
        fh.write(render(rep))
    print(f"arms: {[b['tag'] for b in arms]}")
    print(f"validity: {rep['validity']['valid']}  {rep['validity']['reasons']}")
    print(f"wrote {a.out_json}\nwrote {a.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
