"""c020 B2 runtime evidence — how often do option-to-object references actually resolve?

The validator's original B2 check read the SOURCE for `opt_src`, `opt_tgt` and `OptionRef` and
passed while the resolver returned -1 for every option. This measures the RUNTIME effect on real
observations, which is the only thing that distinguishes an implemented mechanism from a working
one.

100% is the wrong target: end turn, pass, and deck/prize selections reference no board or hand
object, so a rate near 100% would itself indicate a bug.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C20 = os.path.join(_REPO, "contracts",
                   "c020_forced_method_correction_and_hybrid_integration_campaign", "results")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=8)
    a = ap.parse_args(argv)

    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce, api as A
    from cg import c020_baseline_memory as BM, c020_byterl_encode as E

    st = collections.Counter()
    by_ctx = collections.defaultdict(lambda: [0, 0])
    opps = ["dragapult", "mega_lucario", "iono", "mega_abomasnow"]

    for gi in range(a.games):
        state = {"mem": BM.initial_memory()}

        def make_me(s):
            def me(obs):
                act, _ = BM.recommend(obs, s["mem"])
                s["mem"] = BM.advance_after_executed(obs, act, s["mem"])
                if isinstance(obs, dict) and obs.get("select") is not None:
                    try:
                        o = A.to_observation_class(obs)
                        for r in E.option_refs(o):
                            st["options"] += 1
                            has = (r.source_index >= 0 or r.target_index >= 0
                                   or r.hand_index >= 0)
                            st["any"] += has
                            st["source"] += r.source_index >= 0
                            st["target"] += r.target_index >= 0
                            st["hand"] += r.hand_index >= 0
                            st["card"] += r.card_id >= 0
                            st["attack"] += r.attack_id >= 0
                            by_ctx[r.context][0] += 1
                            by_ctx[r.context][1] += int(has)
                    except Exception:  # noqa: BLE001
                        st["encode_errors"] += 1
                return list(act)
            return me

        def mo(o):
            def f(x):
                return o(x)
            return f

        opp = T.make_fresh(opps[gi % 4], ce.SOURCES)
        ags = ([make_me(state), mo(opp)] if gi % 2 == 0
               else [mo(opp), make_me(state)])
        try:
            env = make("cabt")
            env.run(ags)
        except Exception:  # noqa: BLE001
            st["game_errors"] += 1

    n = max(1, st["options"])
    out = {
        "games": a.games, "options": st["options"],
        "any_reference_pct": round(100 * st["any"] / n, 2),
        "source_pct": round(100 * st["source"] / n, 2),
        "target_pct": round(100 * st["target"] / n, 2),
        "hand_pct": round(100 * st["hand"] / n, 2),
        "card_id_pct": round(100 * st["card"] / n, 2),
        "attack_id_pct": round(100 * st["attack"] / n, 2),
        "encode_errors": st["encode_errors"],
        "by_select_context": {str(k): {"options": v[0],
                                       "with_reference_pct": round(100 * v[1] / max(1, v[0]), 1)}
                              for k, v in sorted(by_ctx.items(),
                                                 key=lambda kv: -kv[1][0])[:12]},
        "note": "100% is the wrong target -- end turn, pass and deck/prize selections reference "
                "no board or hand object. A rate of 0 means the resolver is inert, which is what "
                "it was until audited (failures/DEFECT_option_object_references_were_inert_"
                "during_training.md).",
    }
    d = os.path.join(C20, "byterl", "schema")
    os.makedirs(d, exist_ok=True)
    json.dump(out, open(os.path.join(d, "option_reference_resolution.json"), "w"), indent=2)
    print(json.dumps({k: v for k, v in out.items() if k != "by_select_context"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
