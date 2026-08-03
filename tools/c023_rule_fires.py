"""c023 — how often does each enabled rule actually fire?

A rule that never fires is not a null result, it is an inert check, and reporting "no
difference from the control" for it would be a false negative dressed as a measurement. c022 shipped
a validator check that could not fail and only found out because it injected a defect and the check
stayed silent; the same trap is available to an override rule whose precondition is never met.

So this plays real games with a candidate, counts how many decisions each enabled rule was
consulted on and how many it actually changed, and reports both. A rule with zero fires is
reported as `INERT`.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from typing import Any, Dict

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

OUT = os.path.join(_REPO, "results", "c023_autonomous_meta_first_competition_sprint")


def _play(job: Dict[str, Any]) -> Dict[str, Any]:
    sys.path.insert(0, _REPO)
    rec = {k: job[k] for k in ("job_id", "candidate_id", "opponent_id", "seat", "replicate",
                               "phase")}
    rec.update({"completed": False, "error": None, "score": None, "fires": {}, "consulted": 0})
    try:
        from kaggle_environments import make
        from cg import c023_players as P

        cand = P.make_fresh(job["candidate_id"])
        opp = P.make_fresh(job["opponent_id"])
        mod = cand._mod

        fires: Dict[str, int] = {}
        consulted = [0]
        # Wrap each enabled rule so a firing is counted without changing what it returns.
        for name in list(getattr(mod, "RULES_ON", [])):
            fn = mod.RULES.get(name)
            if fn is None:
                continue
            fires[name] = 0

            def wrap(n, f):
                def g(v, base_action):
                    r = f(v, base_action)
                    if r is not None and list(r) != list(base_action or []):
                        fires[n] += 1
                    return r
                return g
            mod.RULES[name] = wrap(name, fn)

        orig_agent = mod.agent

        def counting(o):
            sel = o.get("select") if isinstance(o, dict) else None
            if sel:
                consulted[0] += 1
            return orig_agent(o)

        def plain(p):
            def f(x):
                return p(x)
            return f

        seat = int(job["seat"])
        agents = [counting, plain(opp)] if seat == 0 else [plain(opp), counting]
        env = make("cabt", configuration={})
        env.run(agents)
        last = env.steps[-1]
        if last[0]["status"] == "DONE" and last[1]["status"] == "DONE":
            r = last[seat]["reward"]
            rec["completed"] = True
            rec["score"] = 1.0 if r == 1 else (0.5 if r == 0 else 0.0)
        rec["fires"] = dict(fires)
        rec["consulted"] = consulted[0]
        cand.close(); opp.close()
    except Exception as exc:  # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--opponents", required=True)
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--procs", type=int, default=8)
    ap.add_argument("--tag", default="rule_fires")
    a = ap.parse_args()

    sys.path.insert(0, os.path.join(_REPO, "tools"))
    import c023_eval as E

    cands = [x for x in a.candidates.split(",") if x]
    opps = [x for x in a.opponents.split(",") if x]
    jobs = E.build_jobs(cands, opps, a.games, "fires")
    results = E.run_jobs(jobs, a.procs, worker=_play)

    out: Dict[str, Any] = {}
    for c in cands:
        rs = [r for r in results if r["candidate_id"] == c]
        tot = sum(r["consulted"] for r in rs)
        names = sorted({n for r in rs for n in r["fires"]})
        out[c] = {
            "games": len(rs),
            "decisions": tot,
            "rules": {n: {"fires": sum(r["fires"].get(n, 0) for r in rs),
                          "fire_rate": round(sum(r["fires"].get(n, 0) for r in rs) / max(1, tot), 5),
                          "status": ("INERT" if sum(r["fires"].get(n, 0) for r in rs) == 0
                                     else "ACTIVE")}
                      for n in names},
        }
    d = os.path.join(OUT, "raw_evaluations", a.tag)
    os.makedirs(d, exist_ok=True)
    payload = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "opponents": opps, "games_per_pair": a.games, "candidates": out}
    with open(os.path.join(d, "rule_fires.json"), "w") as fh:
        json.dump(payload, fh, indent=2)
    for c, v in out.items():
        rules = "  ".join(f"{n}={r['fires']}({r['fire_rate']:.3%},{r['status']})"
                          for n, r in v["rules"].items()) or "(no rules enabled)"
        print(f"{c:24s} {v['games']:4d} games {v['decisions']:6d} decisions   {rules}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
