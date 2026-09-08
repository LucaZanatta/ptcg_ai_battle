"""c023 — loss mining: turn raw games into named, countable failure classes.

The optimization loop this contract prescribes needs losses assigned to concrete failure classes,
not adjectives. So this plays games with a candidate and records, per decision, only quantities
that map onto a decision a rule could make differently: whether an attack was available and
whether it was taken, when the first attack landed, how the prize race ran, whether the active
Pokémon was the energised one, whether a retreat was spent.

The aggregation then contrasts **won games against lost games** on those same features. A feature
that looks bad in absolute terms but identical in wins and losses is not a failure class — it is
how this deck plays. Only a feature that separates the two is a candidate for correction, and
even then the direction has to be argued, because losing games are longer and longer games
accumulate more of everything.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

OUT = os.path.join(_REPO, "results", "c023_autonomous_meta_first_competition_sprint")

IDENTITY_FIELDS = ("job_id", "candidate_id", "opponent_id", "seat", "replicate", "phase")


def _trace_play(job: Dict[str, Any]) -> Dict[str, Any]:
    sys.path.insert(0, _REPO)
    t0 = time.time()
    rec: Dict[str, Any] = {k: job[k] for k in IDENTITY_FIELDS}
    rec.update({"completed": False, "error": None, "score": None})
    cand = opp = None
    try:
        from kaggle_environments import make
        from cg import c023_players as P
        from cg.api import OptionType, SelectContext, to_observation_class

        cand = P.make_fresh(job["candidate_id"])
        opp = P.make_fresh(job["opponent_id"])

        feats = {
            "decisions": 0, "main_decisions": 0,
            "attack_available": 0, "attack_taken": 0,
            "retreat_available": 0, "retreat_taken": 0,
            "first_attack_turn": None, "last_turn": 0,
            "turns_seen": set(), "main_turns_with_attack": set(),
            "main_turns_attacked": set(),
            "active_zero_energy_main": 0,
            "bench_size_sum": 0, "bench_samples": 0,
            "hand_size_sum": 0,
            "my_prize_min": 6, "op_prize_min": 6,
        }

        def observe(o):
            a = cand(o)
            try:
                obs = to_observation_class(o)
                sel = obs.select
                if sel is None:
                    return a
                st = obs.current
                me = st.players[st.yourIndex]
                op = st.players[1 - st.yourIndex]
                feats["decisions"] += 1
                feats["last_turn"] = max(feats["last_turn"], int(st.turn))
                feats["turns_seen"].add(int(st.turn))
                feats["my_prize_min"] = min(feats["my_prize_min"], len(me.prize))
                feats["op_prize_min"] = min(feats["op_prize_min"], len(op.prize))
                feats["hand_size_sum"] += len(me.hand)
                feats["bench_size_sum"] += len(me.bench)
                feats["bench_samples"] += 1
                if sel.context == SelectContext.MAIN:
                    feats["main_decisions"] += 1
                    types = [o2.type for o2 in sel.option]
                    has_attack = OptionType.ATTACK in types
                    has_retreat = OptionType.RETREAT in types
                    if has_attack:
                        feats["attack_available"] += 1
                        feats["main_turns_with_attack"].add(int(st.turn))
                    if has_retreat:
                        feats["retreat_available"] += 1
                    chosen = [sel.option[i].type for i in a if 0 <= i < len(sel.option)]
                    if OptionType.ATTACK in chosen:
                        feats["attack_taken"] += 1
                        feats["main_turns_attacked"].add(int(st.turn))
                        if feats["first_attack_turn"] is None:
                            feats["first_attack_turn"] = int(st.turn)
                    if OptionType.RETREAT in chosen:
                        feats["retreat_taken"] += 1
                    act = me.active[0] if me.active else None
                    if act is not None and len(act.energies) == 0:
                        feats["active_zero_energy_main"] += 1
            except Exception:
                pass
            return a

        def plain(p):
            def f(x):
                return p(x)
            return f

        seat = int(job["seat"])
        agents = [observe, plain(opp)] if seat == 0 else [plain(opp), observe]
        env = make("cabt", configuration={})
        env.run(agents)
        last = env.steps[-1]
        st = [last[i]["status"] for i in (0, 1)]
        if st[0] == "DONE" and st[1] == "DONE":
            r = last[seat]["reward"]
            rec["completed"] = True
            rec["reward"] = r
            rec["score"] = 1.0 if r == 1 else (0.5 if r == 0 else 0.0)
        else:
            rec["error"] = f"status={st}"
        feats["turns"] = len(feats.pop("turns_seen"))
        feats["turns_attack_available"] = len(feats.pop("main_turns_with_attack"))
        feats["turns_attacked"] = len(feats.pop("main_turns_attacked"))
        feats["mean_bench"] = round(feats["bench_size_sum"] / max(1, feats["bench_samples"]), 3)
        feats["mean_hand"] = round(feats["hand_size_sum"] / max(1, feats["decisions"]), 3)
        feats["missed_attack_turns"] = feats["turns_attack_available"] - feats["turns_attacked"]
        rec["features"] = feats
        rec["steps"] = len(env.steps)
    except Exception as exc:  # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        for p in (cand, opp):
            if p is not None:
                try:
                    p.close()
                except Exception:
                    pass
    rec["seconds"] = round(time.time() - t0, 3)
    return rec


NUMERIC = ["turns", "decisions", "main_decisions", "attack_available", "attack_taken",
           "turns_attack_available", "turns_attacked", "missed_attack_turns",
           "retreat_available", "retreat_taken", "first_attack_turn",
           "active_zero_energy_main", "mean_bench", "mean_hand",
           "my_prize_min", "op_prize_min", "last_turn"]


def contrast(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    won = [r for r in results if r.get("completed") and r["score"] == 1.0]
    lost = [r for r in results if r.get("completed") and r["score"] == 0.0]
    out: Dict[str, Any] = {"won": len(won), "lost": len(lost), "features": {}}
    for k in NUMERIC:
        wv = [r["features"][k] for r in won if r["features"].get(k) is not None]
        lv = [r["features"][k] for r in lost if r["features"].get(k) is not None]
        if not wv or not lv:
            continue
        mw, ml = statistics.mean(wv), statistics.mean(lv)
        sd = statistics.pstdev(wv + lv) or 1e-9
        out["features"][k] = {
            "won_mean": round(mw, 3), "lost_mean": round(ml, 3),
            "delta_lost_minus_won": round(ml - mw, 3),
            "standardised": round((ml - mw) / sd, 3),
            "won_n": len(wv), "lost_n": len(lv),
        }
    out["ranked_by_separation"] = sorted(
        out["features"], key=lambda k: -abs(out["features"][k]["standardised"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--opponents", required=True)
    ap.add_argument("--games", type=int, default=60)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 4) - 4))
    a = ap.parse_args()

    sys.path.insert(0, os.path.join(_REPO, "tools"))
    import c023_eval as E

    opps = [x for x in a.opponents.split(",") if x]
    jobs = E.build_jobs([a.candidate], opps, a.games, "mine")
    print(f"[{a.tag}] mining {len(jobs)} games", flush=True)
    t0 = time.time()
    results = E.run_jobs(jobs, a.procs, progress_every=200, worker=_trace_play)
    el = time.time() - t0

    by_opp: Dict[str, Any] = {}
    for o in opps:
        sub = [r for r in results if r["opponent_id"] == o]
        by_opp[o] = contrast(sub)
    overall = contrast(results)

    d = os.path.join(OUT, "raw_evaluations", a.tag)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "traces.jsonl"), "w") as fh:
        for r in sorted(results, key=lambda x: x["job_id"]):
            fh.write(json.dumps(r) + "\n")
    payload = {"tag": a.tag, "candidate": a.candidate, "opponents": opps,
               "games": len(jobs), "elapsed_seconds": round(el, 1),
               "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "overall": overall, "per_opponent": by_opp}
    with open(os.path.join(d, "mining.json"), "w") as fh:
        json.dump(payload, fh, indent=2)

    print(f"\n{a.candidate}: {overall['won']} won / {overall['lost']} lost")
    print(f"{'feature':28s} {'won':>9s} {'lost':>9s} {'delta':>9s} {'std':>7s}")
    for k in overall["ranked_by_separation"]:
        v = overall["features"][k]
        print(f"{k:28s} {v['won_mean']:>9.3f} {v['lost_mean']:>9.3f} "
              f"{v['delta_lost_minus_won']:>9.3f} {v['standardised']:>7.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
