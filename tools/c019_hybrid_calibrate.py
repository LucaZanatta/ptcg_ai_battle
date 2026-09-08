"""c019 H02 — run the leaf-value calibration gate on held-out leaves.

`DECISION_RULES.md` allows the ByteRL value head to serve as an MCTS leaf evaluator ONLY if it
beats BOTH a constant baseline and the hand-written heuristic on held-out leaves. Until this
tool runs, `ByteRLLeafValue` refuses to return anything and H02 is honest-but-unexercised.

The gate is worth running even though the pure MCTS branch failed its own gate: it answers a
question the campaign otherwise leaves open — does a from-scratch ByteRL value head carry any
usable ordering signal about PTCG positions, or does it not? Refusal backed by measurement is
different evidence from refusal backed by "we did not look".

Leaves are collected by playing real games with the frozen baseline and snapshotting the
observation at randomly chosen decisions; the label is the eventual game result from the
snapshotted seat, so no leaf is scored against an outcome it could see. `§10` caps hybrid work
at 15% of the campaign and forbids it delaying pure submissions, so this stays deliberately
small and runs alongside ByteRL training rather than in place of it.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C19 = os.path.join(_REPO, "contracts", "c019_dual_method_campaign_ptcg_mcts_and_byterl",
                   "results")


def collect(n_games: int, per_game: int, seed: int):
    """Play real games and snapshot observations with their eventual outcome label."""
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce
    from cg import c019_baseline as B

    rng = random.Random(seed)
    wrapper = B.BranchLocalBaseline()
    opp_ids = ["dragapult", "iono", "mega_abomasnow", "mega_lucario"]
    leaves, games = [], []

    for gi in range(n_games):
        opp = T.make_fresh(opp_ids[gi % len(opp_ids)], ce.SOURCES)
        seat = gi % 2
        state = {"mem": wrapper.initial_memory(), "snaps": [], "decisions": 0}

        # FACTORY, not default-arg capture: `kaggle_environments` inspects the signature and
        # passes (observation, configuration) to anything that accepts two parameters, so
        # `def me(obs, _st=state)` silently receives the config as `_st`. See
        # failures/DEFECT_agent_signature_capture_killed_every_self_play_game.md.
        def make_me(st, w, r):
            def me(obs):
                sel = obs.get("select") if isinstance(obs, dict) else None
                action, nxt = w.act(obs, st["mem"])
                st["mem"] = nxt
                if sel is not None:
                    st["decisions"] += 1
                    # small fixed keep-probability so snapshots spread over the whole game
                    # rather than clustering at the opening
                    if r.random() < 0.12 and len(st["snaps"]) < per_game:
                        st["snaps"].append({"decision": st["decisions"], "obs": obs})
                return list(action)
            return me

        def make_other(o):
            def other(obs):
                return o(obs)
            return other

        me, other = make_me(state, wrapper, rng), make_other(opp)

        agents = [me, other] if seat == 0 else [other, me]
        rec = {"game": gi, "opponent": opp_ids[gi % len(opp_ids)], "seat": seat}
        try:
            env = make("cabt")
            env.run(agents)
            last = env.steps[-1]
            done = [s.status for s in last] == ["DONE", "DONE"]
            rw = [s.reward for s in last]
            if done and rw[seat] is not None:
                out = 1.0 if rw[seat] > rw[1 - seat] else (0.0 if rw[seat] == rw[1 - seat]
                                                           else -1.0)
                rec.update({"completed": True, "outcome_pm_one": out,
                            "snapshots": len(state["snaps"]),
                            "decisions": state["decisions"]})
                for s in state["snaps"]:
                    leaves.append({"obs": s["obs"], "outcome": out, "game": gi,
                                   "decision": s["decision"], "seat": seat})
            else:
                rec.update({"completed": False, "snapshots": 0})
        except Exception as e:  # noqa: BLE001
            rec.update({"completed": False, "error": f"{type(e).__name__}: {str(e)[:120]}"})
        games.append(rec)
    return leaves, games


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=80)
    ap.add_argument("--per-game", type=int, default=4)
    ap.add_argument("--seed", type=int, default=19)
    ap.add_argument("--checkpoint", default=None)
    a = ap.parse_args(argv)

    from cg import c019_hybrid as H, c019_leaf as L

    ck = a.checkpoint
    if ck is None:
        d = os.path.join(C19, "byterl", "checkpoints", "scaled")
        cands = [f for f in os.listdir(d) if f.endswith(".pt")]
        # highest learner VERSION, not newest mtime -- a resumed run can rewrite older files
        cands.sort(key=lambda f: int("".join(c for c in f if c.isdigit()) or 0))
        ck = os.path.join(d, cands[-1])

    t0 = time.time()
    leaves, games = collect(a.games, a.per_game, a.seed)
    obs = [x["obs"] for x in leaves]
    outcomes = [x["outcome"] for x in leaves]

    # the heuristic sees the leaf from the same current-player perspective the value head does
    res = H.calibrate_leaf_value(ck, obs, outcomes, L.make_leaf_fn(None))
    res.update({
        "checkpoint": os.path.basename(ck),
        "games_played": len(games),
        "games_completed": sum(1 for g in games if g.get("completed")),
        "leaves_collected": len(leaves),
        "held_out": "leaves come from baseline games the checkpoint never trained on; the label "
                    "is the eventual result from the snapshotted seat",
        "seconds": round(time.time() - t0, 1),
    })
    res["status"] = ("PASS" if res["may_enable_leaf_value_adapter"] else "REFUSED")

    d = os.path.join(C19, "hybrid", "comparisons")
    os.makedirs(d, exist_ok=True)
    json.dump(res, open(os.path.join(d, "leaf_value_calibration.json"), "w"), indent=2)
    raw = os.path.join(C19, "hybrid", "smoke_traces")
    os.makedirs(raw, exist_ok=True)
    with open(os.path.join(raw, "calibration_games.jsonl"), "w") as f:
        for g in games:
            f.write(json.dumps(g) + "\n")
    print(json.dumps({k: v for k, v in res.items() if k != "rule"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
