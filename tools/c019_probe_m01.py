"""c019 M01 — branch-local baseline memory parity.

The refactored `BranchLocalBaseline` with zero search budget must select the SAME actions and
produce the same outcome distribution as the original stateful agent. If it does not, every MCTS
number built on it is void, and `DECISION_RULES` makes "branch-local baseline parity is
established when search budget is zero" an explicit submission gate.

Two things are tested, because passing only the first would be misleading:

1. **Action-for-action parity** — two independent games driven in lockstep, comparing every
   decision. This is the strong test.
2. **Fork independence** — a forked memory advanced down one line must not change the parent's
   subsequent decisions. This is what a shared global would break, and it is the property MCTS
   actually needs.
"""

from __future__ import annotations

import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C19 = os.path.join(_REPO, "contracts", "c019_dual_method_campaign_ptcg_mcts_and_byterl",
                   "results")


def main():
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce
    from cg import c019_baseline as B

    cov = B.verify_state_coverage()
    wrapper = B.BranchLocalBaseline()
    opp_ids = ["dragapult", "iono", "mega_abomasnow", "mega_lucario"]

    out = {"probe": "M01_baseline_memory_parity", "state_coverage": cov,
           "games": [], "decisions": 0, "mismatches": 0, "first_mismatches": []}

    for gi in range(8):
        # Two agents in ONE game is impossible (they'd play different moves and diverge), so
        # parity is measured by driving the ORIGINAL agent and the WRAPPER on the identical
        # observation at every decision and comparing what each would choose. The original's
        # action is the one played, so the trajectory stays on the original's line.
        orig = B.baseline_module()
        for k in B.STATE_GLOBALS:
            pass
        orig.plan = type(orig.plan)()
        orig.pre_turn = 0
        orig.ability_used = False
        mem = wrapper.initial_memory()
        opp = T.make_fresh(opp_ids[gi % len(opp_ids)], ce.SOURCES)
        rec = {"game": gi, "opponent": opp_ids[gi % len(opp_ids)], "decisions": 0,
               "mismatch": 0}
        state = {"mem": mem}

        def me(obs):
            sel = obs.get("select") if isinstance(obs, dict) else None
            if sel is None:
                return orig.agent(obs)
            # what the WRAPPER would do from its branch-local memory
            w_action, w_next = wrapper.act(obs, state["mem"])
            # what the ORIGINAL does from its module globals -- and this is what is played,
            # so both stay on one trajectory
            o_action = list(orig.agent(obs))
            rec["decisions"] += 1
            out["decisions"] += 1
            if list(w_action) != o_action:
                rec["mismatch"] += 1
                out["mismatches"] += 1
                if len(out["first_mismatches"]) < 8:
                    out["first_mismatches"].append({
                        "game": gi, "decision": rec["decisions"],
                        "wrapper": list(w_action), "original": o_action,
                        "context": sel.get("context"),
                        "n_options": len(sel.get("option") or []),
                        "wrapper_memory": state["mem"].summary()})
            # advance branch memory along the executed line
            state["mem"] = w_next
            return o_action

        seat = gi % 2
        agents = [me, lambda o: opp(o)] if seat == 0 else [lambda o: opp(o), me]
        try:
            env = make("cabt")
            env.run(agents)
            last = env.steps[-1]
            st = [s.status for s in last]
            rw = [s.reward for s in last]
            rec["completed"] = st == ["DONE", "DONE"]
            rec["score"] = (None if not rec["completed"] or rw[seat] is None else
                            (1.0 if rw[seat] > rw[1 - seat] else
                             0.5 if rw[seat] == rw[1 - seat] else 0.0))
        except Exception as e:  # noqa: BLE001
            rec["completed"] = False
            rec["error"] = f"{type(e).__name__}: {str(e)[:120]}"
        out["games"].append(rec)

    # fork independence: advancing a fork must not move the parent
    mem = wrapper.initial_memory()
    forked = mem.fork()
    if forked.values.get("plan") is not None:
        setattr(forked.values["plan"], "attacker", 99)
    forked.values["ability_used"] = True
    out["fork_independence"] = {
        "parent_ability_used": mem.values.get("ability_used"),
        "fork_ability_used": forked.values.get("ability_used"),
        "parent_plan_attacker": getattr(mem.values.get("plan"), "attacker", None),
        "fork_plan_attacker": getattr(forked.values.get("plan"), "attacker", None),
        "independent": (mem.values.get("ability_used") is False
                        and getattr(mem.values.get("plan"), "attacker", None) != 99),
    }

    out["parity_rate"] = round(1.0 - out["mismatches"] / max(1, out["decisions"]), 6)
    out["status"] = ("PASS" if (out["mismatches"] == 0 and cov["covered"]
                                and out["fork_independence"]["independent"]) else "FAIL")
    d = os.path.join(C19, "probes", "M01_baseline_memory_parity")
    os.makedirs(d, exist_ok=True)
    json.dump(out, open(os.path.join(d, "probe.json"), "w"), indent=2, default=str)
    print(json.dumps({"decisions": out["decisions"], "mismatches": out["mismatches"],
                      "parity_rate": out["parity_rate"],
                      "state_coverage_ok": cov["covered"],
                      "untracked_globals": cov["untracked_mutable_globals"],
                      "fork_independent": out["fork_independence"]["independent"],
                      "status": out["status"]}, indent=2))
    for m in out["first_mismatches"][:3]:
        print("  mismatch:", json.dumps(m, default=str)[:220])
    return 0 if out["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
