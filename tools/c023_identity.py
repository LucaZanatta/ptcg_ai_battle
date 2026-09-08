"""c023 — prove a candidate with no rules enabled is action-identical to its official base.

The wrapper architecture is only trustworthy if "no rules enabled" really means "the champion".
Asserting that in prose is what c016 called replacing a rich implementation with a smaller one
and calling it a reproduction. So this measures it.

Method (c007's parity design): play real games in which the acting policy is the *wrapper*, and
run a second, independent instance of the raw base agent alongside it on the identical
observation stream. Both are deterministic functions of the observations they have seen, and the
wrapper returns the base's action, so the two instances stay in the same state — any divergence
is a real behavioural difference, not drift.

A single mismatch fails the check and prints the decision.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

OUT = os.path.join(_REPO, "results", "c023_autonomous_meta_first_competition_sprint")


def _load(path: str, name: str):
    old = os.getcwd()
    d = os.path.dirname(path)
    os.chdir(d)
    if d not in sys.path:
        sys.path.insert(0, d)
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    finally:
        os.chdir(old)
    return mod


def _one_game(candidate_dir: str, base_dir: str, opponent_id: str, seat: int,
              counter: List[int], mismatches: List[Dict[str, Any]]) -> None:
    from kaggle_environments import make
    from cg import c023_players as P

    tag = f"{counter[0]}"
    wrapper = _load(os.path.join(candidate_dir, "main.py"), f"c023_wrap_{tag}")
    shadow = _load(os.path.join(base_dir, "main.py"), f"c023_shadow_{tag}")
    opp = P.make_fresh(opponent_id)

    def paired(o):
        a = wrapper.agent(o)
        b = shadow.agent(o)
        counter[1] += 1
        if list(a) != list(b):
            if len(mismatches) < 20:
                sel = o.get("select") or {}
                mismatches.append({"decision": counter[1], "wrapper": list(a), "base": list(b),
                                   "context": str(sel.get("context")),
                                   "n_options": len(sel.get("option") or [])})
        return a

    def plain(p):
        def f(x):
            return p(x)
        return f

    agents = [paired, plain(opp)] if seat == 0 else [plain(opp), paired]
    env = make("cabt", configuration={})
    env.run(agents)
    counter[0] += 1
    opp.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True, help="candidate id under results/.../agents")
    ap.add_argument("--base", required=True, help="official player id, e.g. official_dragapult")
    ap.add_argument("--games", type=int, default=12)
    ap.add_argument("--opponents", default="official_dragapult,official_mega_lucario,"
                                           "official_iono,official_mega_abomasnow")
    a = ap.parse_args()

    from cg import c023_players as P
    cdir = P.resolve(a.candidate)
    bdir = P.resolve(a.base)

    opps = [x for x in a.opponents.split(",") if x]
    counter = [0, 0]
    mismatches: List[Dict[str, Any]] = []
    t0 = time.time()
    for i in range(a.games):
        _one_game(cdir, bdir, opps[i % len(opps)], i % 2, counter, mismatches)

    ok = not mismatches
    rec = {"candidate": a.candidate, "base": a.base, "games": counter[0],
           "decisions_compared": counter[1], "mismatches": len(mismatches),
           "action_identical": ok, "examples": mismatches[:20],
           "seconds": round(time.time() - t0, 1),
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    d = os.path.join(OUT, "raw_evaluations", "identity")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{a.candidate}.json"), "w") as fh:
        json.dump(rec, fh, indent=2)
    print(json.dumps({k: rec[k] for k in ("candidate", "base", "games", "decisions_compared",
                                          "mismatches", "action_identical")}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
