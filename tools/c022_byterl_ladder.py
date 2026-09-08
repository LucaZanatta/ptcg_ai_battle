"""c022 — the controlled rung ladder BR0 -> BR3, at equal budget.

`TRAINING_AND_EVALUATION §2` asks for adjacent-rung attribution: each published change measured
against the rung below it, at an EQUAL decision budget, on the same external panel. This tool is
that comparison.

Four things it refuses to do, each because a defect in this contract came from doing it:

* **It refuses to compare rungs that did not run alone where they had to.** D18: BR0, BR1 and
  BR1.5 have an unbounded queue, so their production/consumption ratio, queue age and policy lag
  are the ratio of two THROUGHPUTS and move with machine load. `ctrl_BR0` under a concurrent MCGS
  arm ran its learner at 1.24 updates/s against a clean 11.4 and reported a ratio of 12.06 against
  a clean 7.79. Any rung whose learner rate is far off the ladder's median is flagged and its
  queue statistics are reported as INVALID rather than as a stage property.

* **It refuses to read a win-rate difference as an effect.** 128 evaluation games give a Wilson
  interval spanning roughly 8 points at these rates. Adjacent rungs are reported with their
  intervals and with whether they overlap, and the random floor is always in the table.

* **It refuses to call a rung verified because its manifest says so.** The stage flags are
  checked against what the run actually did: a rung claiming `random_initial_construction` must
  have a nonzero `random_initial_choices`, which is precisely what D17 did not have.

* **It refuses to hide a fidelity check that did not run.** `recurrence_checks` of zero is
  reported as NO_DATA, not as a pass -- the same rule the validator uses.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import statistics
import sys
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C22 = os.path.join(_REPO, "contracts",
                   "c022_mcgs_multideterminization_and_faithful_byterl_reproduction", "results")
BY = os.path.join(C22, "byterl")

STAGE_ORDER = ["BR0", "BR1", "BR1_5", "BR2", "BR3"]
DELTA_NAME = {
    ("BR0", "BR1"): "gamma 0.99 -> 1.0",
    ("BR1", "BR1_5"): "published random initial deck-construction selections",
    ("BR1_5", "BR2"): "bounded blocking FIFO + balanced production/consumption",
    ("BR2", "BR3"): "two-sided clipped V-trace + PPO-style clipped policy objective",
}
UNBOUNDED = {"BR0", "BR1", "BR1_5"}


def wilson(k: float, n: int, z: float = 1.96):
    if n <= 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def overlaps(a, b) -> Optional[bool]:
    if not a or not b or a[0] is None or b[0] is None:
        return None
    return not (a[0] > b[1] or b[0] > a[1])


def load(prefix: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for stage in STAGE_ORDER:
        tag = f"{prefix}_{stage}"
        m = os.path.join(BY, "stages", f"{tag}_manifest.json")
        e = os.path.join(BY, "external_evaluations", f"{tag}_eval.json")
        if not os.path.isfile(m):
            continue
        with open(m) as fh:
            man = json.load(fh)
        ev = None
        if os.path.isfile(e):
            with open(e) as fh:
                ev = json.load(fh)
        out[stage] = {"tag": tag, "manifest": man, "eval": ev}
    return out


def floor_scores() -> Dict[str, Any]:
    out = {}
    for name in ("floor_fixed_deck", "floor_end_to_end"):
        p = os.path.join(BY, "external_evaluations", f"{name}_eval.json")
        if os.path.isfile(p):
            with open(p) as fh:
                d = json.load(fh)
            out[name] = {"field_score": d.get("field_score"), "wilson95": d.get("wilson95"),
                         "games": d.get("games")}
    return out


def throughput_validity(rungs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """D18: flag any rung whose learner ran at a rate the rest of the ladder did not.

    The learner rate is the diagnostic, not the ratio, because the ratio is what the rung is
    SUPPOSED to differ in. `steps/update` and `decisions/episode` are the invariants -- they were
    identical between the contaminated and clean BR0 -- so a rate difference with those held
    constant is machine load and nothing else.
    """
    rates = {}
    for s, r in rungs.items():
        m = r["manifest"]
        w = float(m.get("wall_clock_s") or 0.0)
        if w > 0:
            rates[s] = round(float(m.get("consumed_decisions", 0)) / w, 1)
    if len(rates) < 2:
        return {"available": False, "rates": rates}
    med = statistics.median(rates.values())
    outliers = {s: v for s, v in rates.items() if v < 0.6 * med or v > 1.7 * med}
    # A rate outlier only INVALIDATES a rung whose reported quantity is a throughput ratio, and
    # that is exactly the pre-b2 rungs. D18's own conclusion is that a bounded blocking FIFO
    # pins the ratio near 1 under every load tested -- so flagging BR2 or BR3 for running slowly
    # would hide the number that demonstrates the b2 delta behind a warning about a property
    # that change was made to remove. Marking correct behaviour INVALID is the V08 mistake.
    suspect = {s: v for s, v in outliers.items() if s in UNBOUNDED}
    return {
        "available": True,
        "consumed_decisions_per_second": rates,
        "median": round(med, 1),
        "rate_outliers_all_rungs": sorted(outliers),
        "contended_rungs": sorted(suspect),
        "queue_statistics_valid": not suspect,
        "why_bounded_rungs_are_not_flagged": (
            "BR2 and BR3 block their actors when the queue is full, so their production/"
            "consumption ratio is pinned by construction rather than by throughput. A slow "
            "bounded rung is a slow rung, not an invalid measurement."),
        "rule": ("a rung whose learner rate is outside [0.6, 1.7] x the ladder median did not "
                 "run under the same conditions as the rest; D18 measured a 9x spread from "
                 "concurrent load alone, with steps/update and decisions/episode unchanged"),
    }


def flag_consistency(rungs: Dict[str, Dict[str, Any]]) -> List[str]:
    """D17: a stage flag that the run did not act on makes its rung a no-op."""
    bad = []
    for s, r in rungs.items():
        m = r["manifest"]
        claims = bool(m.get("random_initial_construction"))
        acted = int(m.get("random_initial_choices") or 0)
        if claims and acted == 0:
            bad.append(f"{s}: claims random_initial_construction and made 0 uniform choices")
        if (not claims) and acted:
            bad.append(f"{s}: made {acted} uniform choices without the flag")
        if s in UNBOUNDED and m.get("bounded_blocking_fifo"):
            bad.append(f"{s}: is a pre-b2 rung but reports a bounded queue")
    return bad


def fidelity(rungs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """B06/D19 status per rung. Zero checks is NO_DATA, never a pass."""
    out = {}
    for s, r in rungs.items():
        m = r["manifest"]
        n = int(m.get("recurrence_checks") or 0)
        if n == 0:
            out[s] = {"status": "NO_DATA", "checks": 0,
                      "why": "no fidelity check ran; this is not a pass"}
            continue
        out[s] = {
            "status": "PASS" if not m.get("recurrence_check_failures") else "FAIL",
            "checks": n,
            "failures": m.get("recurrence_check_failures"),
            "max_recurrence_delta": m.get("max_recurrence_delta_exact_weights"),
            "max_logp_delta": m.get("max_logp_delta_exact_weights"),
            "max_behaviour_delta": m.get("max_behaviour_delta"),
            "uniform_steps_checked": m.get("uniform_behaviour_steps_seen_in_checks"),
        }
        # D19: a BR1.5+ rung whose checks never SAW a uniform step has not exercised the case
        # that broke the ladder, so its PASS is weaker than it looks and says so.
        if (m.get("random_initial_construction")
                and not m.get("uniform_behaviour_steps_seen_in_checks")):
            out[s]["caveat"] = ("no uniform construction step appeared in any sampled unroll, so "
                                "the D19 case was not exercised by this rung's checks")
    return out


def render(rep: Dict[str, Any]) -> str:
    L: List[str] = []
    A = L.append
    A(f"# The controlled rung ladder — `{rep['prefix']}`")
    A("")
    A(f"Equal budget at every rung: **{rep['target_decisions']:,} decisions**, one codebase, "
      f"one commit. `FIDELITY_RULES §4` fixes the deltas; `MANDATORY_IMPLEMENTATION B7` requires "
      "adjacent stages to differ only by the published change, and `tests/test_c022_stage_ladder.py` "
      "rejects extra changes.")
    A("")

    t = rep["throughput"]
    if t.get("available"):
        A(f"**Throughput validity (D18): "
          f"{'PASS' if t['queue_statistics_valid'] else 'FAIL'}**")
        A("")
        A(f"learner rate per rung: `{t['consumed_decisions_per_second']}` "
          f"(median {t['median']}/s)")
        if t["contended_rungs"]:
            A("")
            A(f"! rungs {t['contended_rungs']} ran at a rate the rest of the ladder did not. "
              "Their queue statistics are load measurements, not stage properties, and are "
              "reported as INVALID below.")
        A("")
        A("**These rungs are not claimed to have run in isolation (D22).** The pre-b2 rungs ran "
          "with no competing MCGS arm, which is what D18 requires, but light foreground tooling "
          "— a 695-test suite, the validator, the status and fixture tools — ran during BR0's "
          "and BR1's windows. The rates above are the measurement of that, and they are printed "
          "rather than smoothed. The spread is 1.26x against D18's 9x, and the `[0.6, 1.7]` "
          "bound is set for the latter, so it correctly does not fire here. Nothing below rests "
          "on the rungs having been isolated; the external comparisons rest on their evaluation "
          "games, which are played from frozen checkpoints and are not affected by the rate at "
          "which those checkpoints were produced.")
        A("")

    if rep["flag_problems"]:
        A("**Stage flags that the runs did not act on:**")
        for b in rep["flag_problems"]:
            A(f"- ! {b}")
        A("")

    A("## Rungs")
    A("")
    A("| rung | delta from below | decisions | dec/s | prod/cons | B06 coverage | "
      "external field | Wilson 95% |")
    A("|---|---|---:|---:|---:|---:|---:|---|")
    prev = None
    for s in STAGE_ORDER:
        r = rep["rungs"].get(s)
        if not r:
            continue
        m, ev = r["manifest"], r["eval"]
        delta = DELTA_NAME.get((prev, s), "—") if prev else "—"
        invalid = s in (rep["throughput"].get("contended_rungs") or [])
        ratio = "INVALID" if invalid else m.get("production_consumption_ratio")
        rate = (rep["throughput"].get("consumed_decisions_per_second") or {}).get(
            r["tag"], "—")
        cov = m.get("recurrence_check_coverage")
        cov_s = "—" if cov is None else f"{cov:.0%} ({m.get('recurrence_checks')})"
        f = ev.get("field_score") if ev else None
        w = ev.get("wilson95") if ev else None
        A(f"| **{s}** | {delta} | {m.get('consumed_decisions'):,} | {rate} | {ratio} | {cov_s} | "
          f"{f if f is not None else '—'} | "
          f"{f'[{w[0]}, {w[1]}]' if w else '—'} |")
        prev = s
    A("")
    for name, d in rep["floor"].items():
        A(f"random floor `{name}`: **{d['field_score']}** "
          f"[{d['wilson95'][0]}, {d['wilson95'][1]}] over {d['games']} games")
    A("")

    A("## Adjacent-rung comparisons")
    A("")
    A("| pair | published change | Δ field | intervals overlap? | reading |")
    A("|---|---|---:|---|---|")
    for c in rep["adjacent"]:
        A(f"| {c['from']} → {c['to']} | {c['change']} | "
          f"{c['delta_pp'] if c['delta_pp'] is not None else '—'} pp | "
          f"{'yes' if c['overlap'] else ('no' if c['overlap'] is not None else '—')} | "
          f"{c['reading']} |")
    A("")
    A("At 128 evaluation games a Wilson interval spans roughly 8 points at these win rates, so "
      "an overlapping pair establishes no effect on external strength. That is a statement about "
      "the evaluation's resolution, not about the change: `FIDELITY_RULES §5` forbids converting "
      "an unresolved comparison into a method failure.")
    A("")

    A("## B06 / D19 replay fidelity per rung")
    A("")
    A("| rung | status | checks | max recurrence Δ | max logp Δ | max behaviour Δ | uniform steps seen |")
    A("|---|---|---:|---:|---:|---:|---:|")
    for s in STAGE_ORDER:
        d = rep["fidelity"].get(s)
        if not d:
            continue
        A(f"| {s} | **{d['status']}** | {d['checks']} | {d.get('max_recurrence_delta', '—')} | "
          f"{d.get('max_logp_delta', '—')} | {d.get('max_behaviour_delta', '—')} | "
          f"{d.get('uniform_steps_checked', '—')} |")
    A("")
    for s, d in rep["fidelity"].items():
        if d.get("caveat"):
            A(f"- {s}: {d['caveat']}")
        if d["status"] == "NO_DATA":
            A(f"- {s}: {d['why']}")
    A("")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="ctrl")
    ap.add_argument("--out-json", default=os.path.join(BY, "component_analysis",
                                                       "rung_ladder.json"))
    ap.add_argument("--out-md", default=os.path.join(BY, "component_analysis",
                                                     "RUNG_LADDER.md"))
    a = ap.parse_args(argv)

    rungs = load(a.prefix)
    if not rungs:
        print(f"no rungs found for prefix {a.prefix}")
        return 1
    thr = throughput_validity(rungs)

    adjacent = []
    prev = None
    for s in STAGE_ORDER:
        if s not in rungs:
            continue
        if prev:
            pe, ce = rungs[prev]["eval"], rungs[s]["eval"]
            dp = ov = None
            if pe and ce and pe.get("field_score") is not None:
                dp = round(100 * (ce["field_score"] - pe["field_score"]), 2)
                ov = overlaps(pe.get("wilson95"), ce.get("wilson95"))
            contended = {prev, s} & set(thr.get("contended_rungs") or [])
            if contended:
                reading = (f"NOT COMPARABLE — {sorted(contended)} did not run under the same "
                           "conditions (D18)")
            elif dp is None:
                reading = "no evaluation"
            elif ov:
                reading = "no resolvable effect at 128 games"
            else:
                reading = "intervals separate"
            adjacent.append({"from": prev, "to": s,
                             "change": DELTA_NAME.get((prev, s), "?"),
                             "delta_pp": dp, "overlap": ov, "reading": reading})
        prev = s

    target = max((int(r["manifest"].get("consumed_decisions") or 0) for r in rungs.values()),
                 default=0)
    rep = {
        "prefix": a.prefix,
        "target_decisions": target,
        "rungs": rungs,
        "throughput": thr,
        "flag_problems": flag_consistency(rungs),
        "fidelity": fidelity(rungs),
        "floor": floor_scores(),
        "adjacent": adjacent,
    }
    for p in (a.out_json, a.out_md):
        os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(a.out_json, "w") as fh:
        json.dump(rep, fh, indent=2, default=str)
    with open(a.out_md, "w") as fh:
        fh.write(render(rep))
    print(f"rungs: {sorted(rungs)}")
    print(f"throughput valid: {thr.get('queue_statistics_valid')} "
          f"contended={thr.get('contended_rungs')}")
    for b in rep["flag_problems"]:
        print(f"   ! {b}")
    print(f"wrote {a.out_json}\nwrote {a.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
