"""c024 — how big is the hand when an Alakazam agent attacks?

`EXCHANGE_RATE_CORRECTION.md` establishes that Powerful Hand does **20 damage per card in hand**,
so the entire policy question for this archetype reduces to one controllable quantity. Before
writing a line of policy, measure what the strong reference agents actually achieve on it.

The answer decides the scope of the build:

- if the reference agents attack at 10–12 cards (200–240 damage) the engine is *not* doing the
  work and the policy has to find the missing cards;
- if they are already at 15–17 (300–340, one-shotting a Mega) the deck's draw engine does it and
  our policy's job is mainly not to break it.

Nothing here plays a policy of ours. It observes an existing agent through a transparent wrapper
that records `len(hand)` at every MAIN decision, tags the ones where an ATTACK option is on the
table, and records which attack was actually chosen. One game per forked child, for the same
reason `c023_eval` forks: an engine abort must be a recorded outcome, not a hung pool.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import statistics
import sys
import time
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

OUT = os.path.join(_REPO, "results", "c024_final_sprint")


def _probe_game(job: Dict[str, Any]) -> Dict[str, Any]:
    sys.path.insert(0, _REPO)
    rec: Dict[str, Any] = {"job_id": job["job_id"],
                           "player": job["player"], "opponent": job["opponent"],
                           "seat": job["seat"], "replicate": job["replicate"],
                           "error": None, "score": None, "samples": [], "attacks": []}
    try:
        from kaggle_environments import make
        from cg import c023_players as P
        from cg.api import OptionType, SelectContext, to_observation_class

        me = P.make_fresh(job["player"])
        op = P.make_fresh(job["opponent"])

        def watched(player):
            def f(o):
                r = player(o)
                try:
                    obs = to_observation_class(o)
                    sel, st = obs.select, obs.current
                    if sel is not None and st is not None and sel.context == SelectContext.MAIN:
                        mp = st.players[st.yourIndex]
                        types = [x.type for x in sel.option]
                        can_attack = OptionType.ATTACK in types
                        rec["samples"].append({"turn": int(st.turn), "hand": len(mp.hand),
                                               "can_attack": bool(can_attack),
                                               "deck": int(mp.deckCount),
                                               "prize": len(mp.prize)})
                        chosen = [sel.option[i].type for i in (r or []) if 0 <= i < len(sel.option)]
                        if OptionType.ATTACK in chosen:
                            # The hand at the instant the attack is declared is the number
                            # Powerful Hand multiplies. Recorded separately from the general
                            # MAIN sample because that is the only one the damage depends on.
                            rec["attacks"].append({"turn": int(st.turn), "hand": len(mp.hand)})
                except Exception:  # noqa: BLE001
                    pass
                return r
            return f

        def plain(player):
            # The opponent must be wrapped in a plain closure too. Handing
            # `kaggle_environments` a LoadedPlayer instance directly ends the episode after the
            # deck handshake -- one call, a 0.5 reward, and zero recorded decisions, which reads
            # as "the agent never attacks" rather than as "the agent never played".
            def f(o):
                return player(o)
            return f

        agents = ([watched(me), plain(op)] if job["seat"] == 0 else [plain(op), watched(me)])
        env = make("cabt", configuration={})
        env.run(agents)
        last = env.steps[-1]
        rew = last[job["seat"]]["reward"]
        rec["score"] = 1.0 if rew == 1 else (0.5 if rew == 0 else 0.0)
    except Exception as exc:  # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--players", default="pub_romanrozen_v10_950,pub_jazivxt_rising_tide_v21")
    ap.add_argument("--opponents", default="official_dragapult,pub_tetsutani_grimmsnarl")
    ap.add_argument("--games", type=int, default=10)
    ap.add_argument("--procs", type=int, default=10)
    a = ap.parse_args()

    import c023_eval as E

    jobs = []
    for pl in a.players.split(","):
        for opp in a.opponents.split(","):
            for r in range(a.games):
                jobs.append({"job_id": f"{pl}|{opp}|{r}", "player": pl, "opponent": opp,
                             "seat": r % 2, "replicate": r})
    print(f"{len(jobs)} games, procs={a.procs}", flush=True)
    rows = E.run_jobs(jobs, a.procs, worker=_probe_game)

    report: Dict[str, Any] = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                              "games": len(rows), "players": {}}
    for pl in a.players.split(","):
        mine = [r for r in rows if r["player"] == pl and not r["error"]]
        atk = [s["hand"] for r in mine for s in r["attacks"]]
        avail = [s["hand"] for r in mine for s in r["samples"] if s["can_attack"]]
        allm = [s["hand"] for r in mine for s in r["samples"]]
        if not atk:
            report["players"][pl] = {"games": len(mine), "attacks": 0}
            continue
        q = lambda v, p: sorted(v)[min(len(v) - 1, int(p * len(v)))]  # noqa: E731
        report["players"][pl] = {
            "games": len(mine),
            "score": round(statistics.mean(r["score"] for r in mine), 4),
            "attacks": len(atk),
            "attacks_per_game": round(len(atk) / max(1, len(mine)), 2),
            "hand_at_attack": {"mean": round(statistics.mean(atk), 2),
                               "median": statistics.median(atk),
                               "p10": q(atk, 0.10), "p90": q(atk, 0.90),
                               "max": max(atk)},
            "damage_at_attack": {"mean": round(20 * statistics.mean(atk), 1),
                                 "median": 20 * statistics.median(atk),
                                 "p90": 20 * q(atk, 0.90)},
            "hand_when_attack_available": round(statistics.mean(avail), 2) if avail else None,
            "hand_all_main": round(statistics.mean(allm), 2) if allm else None,
            "attacks_at_16_plus": sum(1 for h in atk if h >= 16),
            "attacks_at_11_plus": sum(1 for h in atk if h >= 11),
            "histogram": dict(sorted(collections.Counter(atk).items())),
        }

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "HAND_SIZE.json"), "w") as fh:
        json.dump({"report": report, "rows": rows}, fh, indent=2)

    for pl, d in report["players"].items():
        if not d.get("attacks"):
            print(f"{pl}: no attacks recorded ({d['games']} games)")
            continue
        h = d["hand_at_attack"]
        print(f"\n{pl}  ({d['games']} games, score {d['score']}, "
              f"{d['attacks_per_game']} attacks/game)")
        print(f"  hand at attack     mean {h['mean']}  median {h['median']}  "
              f"p10 {h['p10']}  p90 {h['p90']}  max {h['max']}")
        print(f"  => damage          mean {d['damage_at_attack']['mean']}  "
              f"median {d['damage_at_attack']['median']}  p90 {d['damage_at_attack']['p90']}")
        print(f"  attacks >=11 cards (220+): {d['attacks_at_11_plus']}/{d['attacks']}   "
              f">=16 cards (320+): {d['attacks_at_16_plus']}/{d['attacks']}")
        print(f"  hand when an attack was available: {d['hand_when_attack_available']}   "
              f"all MAIN: {d['hand_all_main']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
