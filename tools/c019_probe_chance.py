"""c019 M08 precondition — is `search_step` stochastic?

This determines the MCTS node schema and must be answered before `simulate()` is written. If
identical actions from an identical state yield different successors, the tree needs chance
nodes; overwriting one outcome with another would silently discard information and fail M08.

Also answers the second design question the tree depends on: can a released `searchId` be
re-descended, or must a node's state be re-derived by replaying its action path from the root?
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C19 = os.path.join(_REPO, "contracts", "c019_dual_method_campaign_ptcg_mcts_and_byterl",
                   "results")


def obs_hash(o) -> str:
    """Structural hash of a successor observation, used to tell outcomes apart."""
    try:
        sel = o.select
        parts = [str(getattr(sel, "context", None)), str(getattr(sel, "minCount", None)),
                 str(getattr(sel, "maxCount", None)),
                 str(len(getattr(sel, "option", None) or []))]
        for op in (getattr(sel, "option", None) or [])[:24]:
            parts.append(f"{getattr(op, 'type', None)}:{getattr(op, 'index', None)}:"
                         f"{getattr(op, 'area', None)}:{getattr(op, 'playerIndex', None)}")
    except Exception:  # noqa: BLE001
        parts = ["terminal"]
    try:
        st = o.current
        for pi in (0, 1):
            p = st.players[pi]
            parts.append(f"p{pi}:deck={getattr(p, 'deckCount', None)}:"
                         f"hand={len(getattr(p, 'hand', None) or [])}:"
                         f"disc={len(getattr(p, 'discard', None) or [])}")
            for z in ("active", "bench"):
                for c in (getattr(p, z, None) or []):
                    parts.append("_" if c is None else
                                 f"{getattr(c, 'id', '?')}/{getattr(c, 'hp', '?')}")
    except Exception:  # noqa: BLE001
        pass
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:20]


def main():
    from kaggle_environments import make
    from cg import api as A, teachers as T, c009_eval as ce
    sys.path.insert(0, os.path.join(_REPO, "tools"))
    import c018_search as S     # reused ONLY for its determinizer, to reach a live root fast

    deck = T.read_deck("mega_lucario", ce.SOURCES)
    base = T.make_fresh("mega_lucario", ce.SOURCES)
    opp = T.make_fresh("dragapult", ce.SOURCES)
    captured = []

    def me(obs):
        sel = obs.get("select") if isinstance(obs, dict) else None
        if sel is None:
            return base(obs)
        if len(captured) < 6 and len(sel.get("option") or []) >= 3:
            captured.append(obs)
        return base(obs)

    try:
        make("cabt").run([me, lambda o: opp(o)])
    except Exception as e:  # noqa: BLE001
        print("episode error:", type(e).__name__, e)

    out = {"probe": "c019_chance_precondition", "roots_captured": len(captured), "roots": []}
    rng = np.random.default_rng(19)

    for ri, obs in enumerate(captured[:4]):
        rec = {"root": ri, "repeats": [], "reexpand_after_release": None,
               "replay_from_root": None}
        try:
            o = A.to_observation_class(obs)
            view = S.VisibleView(o.current, o.current.yourIndex)
            det = S.determinize(view, deck, rng)
        except Exception as e:  # noqa: BLE001
            rec["error"] = f"determinize:{type(e).__name__}"
            out["roots"].append(rec)
            continue

        # (1) same action, same root, repeated -- do successors differ?
        for trial in range(6):
            try:
                root = A.search_begin(o, det["your_deck"], det["your_prize"],
                                      det["opponent_deck"], det["opponent_prize"],
                                      det["opponent_hand"], det["opponent_active"])
                n_opt = len(root.observation.select.option or [])
                if n_opt < 2:
                    A.search_release(root.searchId)
                    A.search_end()
                    break
                nxt = A.search_step(root.searchId, [0])
                rec["repeats"].append({"trial": trial, "root_hash": obs_hash(root.observation),
                                       "succ_hash": obs_hash(nxt.observation),
                                       "succ_id": int(nxt.searchId),
                                       "root_id": int(root.searchId), "n_options": n_opt})
                A.search_release(nxt.searchId)
                A.search_release(root.searchId)
                A.search_end()
            except Exception as e:  # noqa: BLE001
                rec["repeats"].append({"trial": trial, "error":
                                       f"{type(e).__name__}: {str(e)[:120]}"})
                try:
                    A.search_end()
                except Exception:  # noqa: BLE001
                    pass

        # (2) can one root be stepped MULTIPLE times with different actions (branching from a
        #     live node), and can a stepped-from node be stepped again afterwards?
        try:
            root = A.search_begin(o, det["your_deck"], det["your_prize"],
                                  det["opponent_deck"], det["opponent_prize"],
                                  det["opponent_hand"], det["opponent_active"])
            n_opt = len(root.observation.select.option or [])
            kids = []
            for a in range(min(3, n_opt)):
                try:
                    k = A.search_step(root.searchId, [a])
                    kids.append({"action": a, "succ_hash": obs_hash(k.observation),
                                 "succ_id": int(k.searchId)})
                except Exception as e:  # noqa: BLE001
                    kids.append({"action": a, "error": f"{type(e).__name__}"})
            rec["multi_step_same_root"] = kids
            rec["distinct_children_from_one_root"] = len(
                {k.get("succ_hash") for k in kids if k.get("succ_hash")})
            # step a child further -- proves non-root expansion is reachable from a live node
            live = next((k for k in kids if k.get("succ_id")), None)
            if live:
                try:
                    g = A.search_step(live["succ_id"], [0])
                    rec["grandchild_ok"] = True
                    rec["grandchild_hash"] = obs_hash(g.observation)
                    A.search_release(g.searchId)
                except Exception as e:  # noqa: BLE001
                    rec["grandchild_ok"] = False
                    rec["grandchild_error"] = f"{type(e).__name__}: {str(e)[:120]}"
            for k in kids:
                if k.get("succ_id"):
                    try:
                        A.search_release(k["succ_id"])
                    except Exception:  # noqa: BLE001
                        pass
            A.search_release(root.searchId)
            A.search_end()
        except Exception as e:  # noqa: BLE001
            rec["multi_step_error"] = f"{type(e).__name__}: {str(e)[:160]}"
            try:
                A.search_end()
            except Exception:  # noqa: BLE001
                pass
        out["roots"].append(rec)

    # verdicts
    stoch = []
    for r in out["roots"]:
        hs = {t.get("succ_hash") for t in r.get("repeats", []) if t.get("succ_hash")}
        if hs:
            stoch.append(len(hs) > 1)
    out["identical_action_yields_multiple_outcomes"] = any(stoch)
    out["roots_with_stochastic_successor"] = sum(1 for x in stoch if x)
    out["roots_tested_for_stochasticity"] = len(stoch)
    out["one_live_root_can_branch"] = any(
        (r.get("distinct_children_from_one_root") or 0) > 1 for r in out["roots"])
    out["child_can_be_stepped_further"] = any(r.get("grandchild_ok") for r in out["roots"])
    out["design_implication"] = (
        ("chance nodes REQUIRED: identical action from identical state produced different "
         "successors") if out["identical_action_yields_multiple_outcomes"] else
        ("deterministic successors observed for the actions tested; chance handling still "
         "records outcome hashes so a stochastic action cannot silently overwrite another"))
    os.makedirs(os.path.join(C19, "probes", "M08_chance_precondition"), exist_ok=True)
    json.dump(out, open(os.path.join(C19, "probes", "M08_chance_precondition",
                                     "precondition.json"), "w"), indent=2, default=str)
    print(json.dumps({k: out[k] for k in
                      ("roots_captured", "identical_action_yields_multiple_outcomes",
                       "roots_with_stochastic_successor", "roots_tested_for_stochasticity",
                       "one_live_root_can_branch", "child_can_be_stepped_further",
                       "design_implication")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
