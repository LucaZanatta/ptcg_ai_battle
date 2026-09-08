"""c023 — a (1+λ) search over the sample agent's own score constants.

The official agents decide by adding hand-chosen round numbers. `tools/c023_paramize.py` turns
110 of those constants into parameters whose defaults reproduce the sample exactly (verified:
0 mismatches over 1,263 decisions). This searches them.

It is not a blind sweep. Every parameter has a name, a function and a line in the original source
(`_slots.json`), so a change can always be read back as "the weight this agent puts on playing a
Rare Candy" rather than as parameter #47.

**The honesty problem, and what is done about it.** This panel's run-to-run noise floor is ~1 point
at 1,200 games and ~3 at 400. A hill climb that accepts the best of λ mutants each round will drift
upward on noise alone. Three defences, all registered before the search runs:

1. **The incumbent is re-measured every round, in the same run as its challengers.** A round's
   comparison is therefore between numbers produced under identical conditions.
2. **Acceptance needs a margin**, not just a lead — `--accept` points, defaulting to twice the
   standard error of the difference at the round's game count.
3. **The search result is a hypothesis, not a candidate.** Whatever it produces goes through the
   registered confirm (≥1,000 games, fresh run) and validate (disjoint opponent panel) stages in
   `PANEL_SPLIT.json`, and is expected to lose most of its apparent gain there. The size of that
   loss is itself a reportable measurement.

Perturbations are multiplicative and sign-preserving: a `-1` that means "never do this" stays
negative, and a `50000` that means "this wins the game" stays enormous.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

OUT = os.path.join(_REPO, "results", "c023_autonomous_meta_first_competition_sprint")
TUNE = os.path.join(OUT, "tuning")


def mutate(weights: Dict[int, int], slots: List[Dict[str, Any]], rng: random.Random,
           k_max: int, sigma: float) -> Dict[int, int]:
    w = dict(weights)
    k = rng.randint(1, k_max)
    for idx in rng.sample(range(len(slots)), k):
        cur = w.get(idx, slots[idx]["default"])
        if cur == 0:
            new = rng.choice([-1, 1])
        else:
            f = math.exp(rng.gauss(0.0, sigma))
            new = int(round(cur * f))
            if new == cur:
                new = cur + (1 if rng.random() < 0.5 else -1)
            if (new > 0) != (cur > 0):          # never flip the sign of a sentinel
                new = cur
        w[idx] = new
    return w


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="official_dragapult")
    ap.add_argument("--param-source", required=True)
    ap.add_argument("--slots", required=True)
    ap.add_argument("--opponents", required=True)
    ap.add_argument("--games", type=int, default=200, help="games per opponent per arm")
    ap.add_argument("--children", type=int, default=5)
    ap.add_argument("--rounds", type=int, default=60)
    ap.add_argument("--k-max", type=int, default=5)
    ap.add_argument("--sigma", type=float, default=0.35)
    ap.add_argument("--accept", type=float, default=None,
                    help="required margin in points; default = 2 x SE of the difference")
    ap.add_argument("--procs", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20260803)
    ap.add_argument("--deadline-utc", help="stop starting rounds after this ISO time")
    ap.add_argument("--tag", default="tune")
    a = ap.parse_args()

    sys.path.insert(0, os.path.join(_REPO, "tools"))
    import c023_eval as E
    import c023_build_candidate as B

    slots = json.load(open(a.slots))["slots"]
    opps = [x for x in a.opponents.split(",") if x]
    rng = random.Random(a.seed)
    os.makedirs(TUNE, exist_ok=True)

    n_arm = a.games * len(opps)
    se_diff = math.sqrt(2 * 0.25 / n_arm) * 100.0        # points, per-arm pooled approximation
    accept = a.accept if a.accept is not None else round(2 * se_diff, 2)

    incumbent: Dict[int, int] = {}
    best_score: Optional[float] = None
    history: List[Dict[str, Any]] = []
    deadline = a.deadline_utc

    print(f"[{a.tag}] {len(slots)} parameters, {len(opps)} opponents, {n_arm} games/arm, "
          f"accept margin {accept} pts (2 x SE_diff = {2*se_diff:.2f})", flush=True)

    for rnd in range(a.rounds):
        if deadline and time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) > deadline:
            print(f"[{a.tag}] deadline reached; stopping before round {rnd}", flush=True)
            break
        arms = {f"{a.tag}_r{rnd}_inc": dict(incumbent)}
        for c in range(a.children):
            arms[f"{a.tag}_r{rnd}_c{c}"] = mutate(incumbent, slots, rng, a.k_max, a.sigma)
        for cid, w in arms.items():
            B.build(cid, a.base, None,
                    {"rules": {}, "weights": {str(k): v for k, v in w.items()}},
                    parent=f"{a.tag}_r{rnd-1}_inc" if rnd else a.base,
                    rationale=f"{a.tag} round {rnd}",
                    param_source=os.path.join(_REPO, a.param_source))

        jobs = E.build_jobs(list(arms), opps, a.games, f"{a.tag}_r{rnd}")
        t0 = time.time()
        results = E.run_jobs(jobs, a.procs)
        summary = E.summarize(results, a.games)
        E.write_out(f"{a.tag}_r{rnd}", jobs, results, summary,
                    {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                     "round": rnd, "accept_margin": accept, "opponents": opps,
                     "games_per_pair": a.games,
                     "elapsed_seconds": round(time.time() - t0, 1)})

        scored = {cid: summary[cid]["field_score_off_mirror"] for cid in arms
                  if cid in summary}
        inc_id = f"{a.tag}_r{rnd}_inc"
        inc = scored.get(inc_id)
        challengers = {c: s for c, s in scored.items() if c != inc_id}
        top = max(challengers, key=lambda c: challengers[c]) if challengers else None
        gain = (challengers[top] - inc) * 100.0 if (top and inc is not None) else 0.0
        accepted = bool(top and gain >= accept)
        if accepted:
            incumbent = arms[top]
            best_score = challengers[top]
        elif inc is not None:
            best_score = inc

        rec = {"round": rnd, "incumbent_score": inc, "best_child": top,
               "best_child_score": challengers.get(top) if top else None,
               "gain_points": round(gain, 3), "accepted": accepted,
               "n_changed_params": len(incumbent),
               "elapsed_seconds": round(time.time() - t0, 1),
               "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        history.append(rec)
        print(f"  r{rnd:<3d} inc={inc}  best={challengers.get(top)}  "
              f"gain={gain:+.2f}pt  {'ACCEPT' if accepted else 'reject'}  "
              f"params_changed={len(incumbent)}  {rec['elapsed_seconds']:.0f}s", flush=True)

        # Keep the manifests (they carry the weights, so every arm is reconstructible) and drop
        # the candidate directories, which are 100 KB of copied base agent each.
        import shutil as _sh
        for cid in arms:
            _d = os.path.join(OUT, "agents", cid)
            if os.path.isdir(_d):
                _sh.rmtree(_d, ignore_errors=True)

        with open(os.path.join(TUNE, f"{a.tag}_history.json"), "w") as fh:
            json.dump({"config": vars(a), "accept_margin": accept,
                       "se_diff_points": round(se_diff, 3),
                       "history": history,
                       "incumbent_weights": {str(k): v for k, v in incumbent.items()},
                       "incumbent_slots": [
                           {**slots[k], "tuned_to": v} for k, v in sorted(incumbent.items())],
                       "best_score": best_score}, fh, indent=2)

    # the search's output is a hypothesis; build it under a stable name for the confirm stage
    if incumbent:
        B.build(f"{a.tag}_best", a.base, None,
                {"rules": {}, "weights": {str(k): v for k, v in incumbent.items()}},
                parent=a.base,
                rationale=f"{a.tag}: winner of a (1+{a.children}) search over {len(slots)} score "
                          f"constants; {len(incumbent)} changed. A HYPOTHESIS, not a candidate -- "
                          f"it must clear the registered confirm and validate stages.",
                param_source=os.path.join(_REPO, a.param_source))
        print(f"[{a.tag}] built {a.tag}_best with {len(incumbent)} changed parameters", flush=True)
    else:
        print(f"[{a.tag}] no round accepted; the defaults were never beaten by {accept} points",
              flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
