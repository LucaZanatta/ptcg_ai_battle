"""c022 — is the c021 overconfidence a world-count defect or a rollout defect?

This probe runs BEFORE the multi-determinization implementation, because the answer decides
whether varying K can move calibration at all.

The c021 reconciliation computed predicted win rate as `term_root_win / (term_root_win +
term_root_loss)` over EVERY rollout in a run — not over the selected action, and not per world.
That statistic can be ~0.96 for two very different reasons:

  A. **World-count defect.** Within one fixed hidden world many lines really are forced wins,
     and the searcher finds them; the MAXIMUM over root actions is near 1 while the MEAN over
     actions is moderate. Averaging over K independent worlds then shrinks the selection bias,
     and the K sweep is well posed.

  B. **Rollout defect.** The uniform-random rollout returns a root-player win ~96% of the time
     from essentially any state, in essentially every world. The MEAN over actions is already
     ~0.96 inside each world. Summing across K worlds cannot fix that: averaging removes
     variance and max-selection bias, not a bias every world shares. Calibration would stay
     pinned at ~0.96 for K = 1, 2, 4, 8, and reading that as "the ensemble didn't help" would
     be a misattribution.

The discriminating measurement, at frozen roots: sample K worlds, run a fixed number of rollouts
from each root ACTION in each world, and report per world both the mean over actions and the max
over actions. A third quantity settles it completely — the rollout return from the ROOT ITSELF,
before any action is taken, which no search decision can influence.

The probe also measures the same quantity for the OPPONENT's seat by symmetry: if the rollout
says both players win ~96% of the time, the rollout's terminal attribution is broken rather than
merely optimistic.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

OUT = os.path.join(_REPO, "contracts",
                   "c022_mcgs_multideterminization_and_faithful_byterl_reproduction",
                   "results", "mcgs", "calibration")


def capture_decisions(every: int, want: int, seed: int = 7, opponent: str = "dragapult",
                      max_games: int = 12):
    """Capture multi-option observations spread THROUGH games, not only their openings.

    The first version of the world probes took the first `n` multi-option observations, which are
    all setup decisions: zero prizes, empty opponent hand, both decks at 60. Those exercise a
    single regime, and the regime in which hidden information matters least. Sampling every
    `every`-th decision reaches mid-game states.

    Games are played until enough roots are captured. A single game is not enough: under random
    play a game can end in fewer than `every` agent decisions, and a run that captured nothing
    from one short game once reported "no mid-game decisions captured" and aborted. Capturing
    across several games is also better sampling — one game's mid-points are correlated.
    """
    import torch
    torch.set_num_threads(1)
    from kaggle_environments import make
    from cg import c019_core as K, c019_determinize as D19
    from cg import teachers as T, c009_eval as ce

    deck = D19.archetype_decks()["mega_lucario"]
    captured = []
    rng = np.random.default_rng(seed)

    for g in range(max_games):
        if len(captured) >= want:
            break
        seen = [0]

        class Probe:
            def __call__(self, obs):
                sel = obs.get("select")
                if sel is None:
                    return list(deck)
                opts = K.canonical_options(sel)
                seen[0] += 1
                if len(opts) > 1 and len(captured) < want and seen[0] % every == 0:
                    captured.append({"game": g, "decision_index": seen[0],
                                     "obs": dict(obs)})
                return K.to_select_payload([opts[int(rng.integers(len(opts)))]], sel)

        p = Probe()
        opp = T.make_fresh(opponent, ce.SOURCES)
        env = make("cabt")
        try:
            env.run([lambda o: p(o), lambda o: opp(o)])
        except Exception:  # noqa: BLE001
            continue
    # A decision index must be unique across games or two different roots would share a world
    # seed stream and the "independent worlds" claim would be false between them.
    for i, e in enumerate(captured):
        e["decision_index"] = e["game"] * 100000 + e["decision_index"]
        e["root_index"] = i
    return deck, captured


def measure_root(deck, entry, k, rollouts_per_action, seed):
    """Per-world mean-over-actions, max-over-actions, and root-only rollout return.

    The rollout is c021's own `MCGS.rollout` — the source-faithful uniform-random default policy
    with the source's retry, step cap and turn cap. Reimplementing it here would measure a
    different rollout and answer a different question.
    """
    from cg import api as A, c019_core as K
    from cg import c021_mcgs as S
    from cg import c021_mcgs_agent as AG
    from cg import c022_mcgs_worlds as W

    o = A.to_observation_class(entry["obs"])
    view = K.visible_view(o)
    sel = o.select
    opts = K.canonical_options(sel)
    worlds = W.sample_worlds(view, deck, seed, entry["decision_index"], k)

    cfg = dict(AG.REFERENCE_CFG)
    # No move clock inside a rollout: the source bounds a rollout by step/turn caps only, and
    # `MCGS.rollout` takes a deadline solely to abort a runaway decision.
    deadline = time.monotonic() + 3600.0
    per_world = []
    for w in worlds:
        stats = S.new_stats()
        rng = np.random.default_rng((seed ^ w.seed) & ((1 << 63) - 1))
        mcgs = S.MCGS(A, cfg, stats, rng, None, {})
        try:
            st = W.open_session(o, w, manual_coin=True)
            mcgs._track(st.searchId)
            root_player = S.MCGS._your_index(o, 0)
            root_node = mcgs._make_node(st, 0, None, root_player, 0)
            # (a) root-only: rollout straight from the root, before any action is chosen. No
            # search decision can influence this number.
            root_vals = [float(mcgs.rollout(root_node, deadline, root_player))
                         for _ in range(rollouts_per_action)]
            # (a2) THE SAME rollout scored for the OPPOSING seat. If both seats are told they
            # win ~2/3 of the time, the terminal attribution is broken rather than the rollout
            # merely optimistic -- and no amount of world averaging would fix that either.
            # c021 already found and fixed one attribution defect here ("on a rollout terminal
            # the owner is whoever happens to be to act"), so the check is not hypothetical.
            opp_vals = [float(mcgs.rollout(root_node, deadline, 1 - root_player))
                        for _ in range(rollouts_per_action)]
            # (b) per action.
            action_means = []
            for ai in range(len(opts)):
                vals = []
                for _ in range(rollouts_per_action):
                    try:
                        succ = A.search_step(
                            st.searchId, mcgs._payload(sel, opts[ai], opts))
                        child = mcgs._make_node(succ, 1, None, root_player, ai)
                        if child is None:
                            continue
                        vals.append(float(mcgs.rollout(child, deadline, root_player)))
                        try:
                            A.search_release(succ.searchId)
                        except Exception:  # noqa: BLE001
                            pass
                    except Exception:  # noqa: BLE001
                        pass
                if vals:
                    action_means.append(statistics.fmean(vals))
            # c021's headline statistic is `term_root_win / (term_root_win + term_root_loss)` --
            # DECIDED rollouts only. A mean rollout return scores a turn-capped rollout as 0.0,
            # i.e. as a loss. The two denominators differ, and quoting one against the other
            # would manufacture a discrepancy. Both are recorded.
            tw = int(stats.get("term_root_win", 0) or 0)
            tl = int(stats.get("term_root_loss", 0) or 0)
            tu = int(stats.get("term_undecided", 0) or 0)
            per_world.append({
                "world_id": w.world_id,
                "root_only_mean": round(statistics.fmean(root_vals), 4) if root_vals else None,
                "root_only_mean_opposing_seat": round(statistics.fmean(opp_vals), 4)
                if opp_vals else None,
                "term_root_win": tw, "term_root_loss": tl, "term_undecided": tu,
                "c021_style_predicted_over_decided": round(tw / (tw + tl), 4) if (tw + tl) else None,
                "predicted_over_all_rollouts": round(tw / (tw + tl + tu), 4)
                if (tw + tl + tu) else None,
                "turn_cap_fraction": round(tu / (tw + tl + tu), 4) if (tw + tl + tu) else None,
                "n_actions_measured": len(action_means),
                "mean_over_actions": round(statistics.fmean(action_means), 4)
                if action_means else None,
                "max_over_actions": round(max(action_means), 4) if action_means else None,
                "min_over_actions": round(min(action_means), 4) if action_means else None,
                "spread_over_actions": round(max(action_means) - min(action_means), 4)
                if action_means else None,
                "action_means": [round(x, 4) for x in action_means],
            })
        except Exception as e:  # noqa: BLE001
            per_world.append({"world_id": w.world_id,
                              "error": f"{type(e).__name__}: {e}"[:160]})
        finally:
            try:
                mcgs.release_all()
            except Exception:  # noqa: BLE001
                pass
            try:
                A.search_end()
            except Exception:  # noqa: BLE001
                pass

    good = [p for p in per_world if p.get("mean_over_actions") is not None]
    return {
        "decision_index": entry["decision_index"],
        "n_options": len(opts),
        "worlds": len(worlds),
        "per_world": per_world,
        "across_worlds": {
            "mean_of_mean_over_actions": round(
                statistics.fmean([p["mean_over_actions"] for p in good]), 4) if good else None,
            "mean_of_max_over_actions": round(
                statistics.fmean([p["max_over_actions"] for p in good]), 4) if good else None,
            "mean_of_root_only": round(
                statistics.fmean([p["root_only_mean"] for p in good
                                  if p.get("root_only_mean") is not None]), 4) if good else None,
            "mean_of_root_only_opposing_seat": round(
                statistics.fmean([p["root_only_mean_opposing_seat"] for p in good
                                  if p.get("root_only_mean_opposing_seat") is not None]), 4)
            if good else None,
            "between_world_sd_of_mean": round(
                statistics.pstdev([p["mean_over_actions"] for p in good]), 4)
            if len(good) > 1 else None,
            "mean_c021_style_predicted_over_decided": round(statistics.fmean(
                [p["c021_style_predicted_over_decided"] for p in good
                 if p.get("c021_style_predicted_over_decided") is not None]), 4)
            if any(p.get("c021_style_predicted_over_decided") is not None for p in good)
            else None,
            "mean_predicted_over_all_rollouts": round(statistics.fmean(
                [p["predicted_over_all_rollouts"] for p in good
                 if p.get("predicted_over_all_rollouts") is not None]), 4)
            if any(p.get("predicted_over_all_rollouts") is not None for p in good) else None,
            "mean_turn_cap_fraction": round(statistics.fmean(
                [p["turn_cap_fraction"] for p in good
                 if p.get("turn_cap_fraction") is not None]), 4)
            if any(p.get("turn_cap_fraction") is not None for p in good) else None,
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--rollouts", type=int, default=24)
    ap.add_argument("--roots", type=int, default=4)
    ap.add_argument("--every", type=int, default=12)
    ap.add_argument("--seed", type=int, default=606)
    ap.add_argument("--actual-field-score", type=float, default=0.1111,
                    help="the frozen C021_MCGS_K1_CONTROL field score; the reference point that "
                         "turns 'the search is confident' into 'the search is wrong by N pp'")
    ap.add_argument("--out", default=os.path.join(OUT, "rollout_bias_probe.json"))
    a = ap.parse_args(argv)

    import torch
    torch.set_num_threads(1)

    t0 = time.time()
    deck, captured = capture_decisions(a.every, a.roots, seed=a.seed)
    if not captured:
        raise SystemExit("no mid-game decisions captured")

    roots = [measure_root(deck, e, a.k, a.rollouts, a.seed) for e in captured]

    def avg(key):
        v = [r["across_worlds"][key] for r in roots if r["across_worlds"].get(key) is not None]
        return round(statistics.fmean(v), 4) if v else None

    m = avg("mean_of_mean_over_actions")
    mx = avg("mean_of_max_over_actions")
    ro = avg("mean_of_root_only")
    ro_opp = avg("mean_of_root_only_opposing_seat")
    sd = avg("between_world_sd_of_mean")

    # The reference point: what the agent ACTUALLY scores. Anything the search predicts above
    # this is error, whatever its source.
    ACTUAL = float(a.actual_field_score)

    attribution_ok = None
    if ro is not None and ro_opp is not None:
        # Draws exist, so the two seats need not sum to exactly 1; but if both seats are told
        # they win, attribution is broken.
        attribution_ok = bool((ro + ro_opp) <= 1.05 and not (ro > 0.55 and ro_opp > 0.55))

    decomposition = None
    if m is not None and mx is not None and ro is not None:
        decomposition = {
            "actual_field_score": ACTUAL,
            "total_overconfidence_pp": round(100 * (mx - ACTUAL), 1),
            "attributable_to_within_world_action_selection_pp": round(100 * (mx - m), 1),
            "attributable_to_rollout_optimism_pp": round(100 * (ro - ACTUAL), 1),
            "residual_action_conditioning_pp": round(100 * (m - ro), 1),
            "K_can_reduce": "the within-world action-selection term only",
            "K_cannot_reduce": "the rollout-optimism term, which every world shares",
        }

    if m is None:
        verdict = "UNDETERMINED — no root produced a measurable action mean"
    else:
        sel_gap = (mx - m) if mx is not None else 0.0
        roll_gap = (ro - ACTUAL) if ro is not None else 0.0
        if roll_gap > sel_gap * 1.5:
            head = "ROLLOUT_OPTIMISM_DOMINANT"
        elif sel_gap > roll_gap * 1.5:
            head = "WORLD_COUNT_DEFECT_DOMINANT"
        else:
            head = "BOTH_TERMS_MATERIAL"
        verdict = (
            f"{head} — the uniform-random rollout from the ROOT, before any action is chosen, "
            f"already says the root player wins {ro:.3f} of the time while the agent actually "
            f"scores {ACTUAL:.3f}. That {100*roll_gap:.0f} pp is shared by every world and NO "
            f"amount of cross-world averaging removes it. On top of it, choosing the best action "
            f"within a world adds {100*sel_gap:.0f} pp (mean over actions {m:.3f} -> max "
            f"{mx:.3f}); that term is exactly what independent worlds average away. "
            f"So the K sweep is well posed — it targets a real and measurable component — but "
            f"its calibration ceiling is bounded: even perfect world averaging leaves the "
            f"predicted rate near {ro:.3f}, not near {ACTUAL:.3f}. Any calibration target for "
            f"M08 must be stated against that ceiling, not against the true win rate.")

    out = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "question": "is c021's ~96% predicted win rate a property of the ROLLOUT or of the "
                       "single-world SELECTION?",
           "protocol": {"k_worlds": a.k, "rollouts_per_action": a.rollouts,
                        "roots": len(captured), "capture_every_nth_decision": a.every,
                        "seed": a.seed,
                        "rollout": "c021 MCGS.rollout — the source-faithful uniform-random "
                                   "default policy with the source's retry/step/turn caps",
                        "actual_field_score_reference": ACTUAL,
                        "actual_field_score_source":
                            "C021_MCGS_K1_CONTROL (t2_T0_control_summary.json)"},
           "headline": {"mean_over_actions": m, "max_over_actions": mx,
                        "root_only": ro, "root_only_opposing_seat": ro_opp,
                        "between_world_sd_of_mean": sd,
                        "selection_gap": round(mx - m, 4)
                        if (m is not None and mx is not None) else None,
                        "c021_style_predicted_over_decided":
                            avg("mean_c021_style_predicted_over_decided"),
                        "predicted_over_all_rollouts":
                            avg("mean_predicted_over_all_rollouts"),
                        "turn_cap_fraction": avg("mean_turn_cap_fraction")},
           "denominator_note":
               "c021's headline 0.79-0.99 is term_root_win/(win+loss) -- DECIDED rollouts only. "
               "A mean rollout return scores a turn-capped rollout as 0.0, i.e. as a loss. Both "
               "denominators are reported so the two campaigns' numbers are never compared "
               "across different definitions. A further difference remains by construction: "
               "c021's statistic is over rollouts launched from tree LEAVES that UCB selected "
               "into promising lines, while this probe launches from the root and its immediate "
               "children, which is what makes it attributable to world count rather than to "
               "search depth.",
           "terminal_attribution_consistent": attribution_ok,
           "terminal_attribution_check":
               "the SAME rollouts scored for both seats. If both seats are told they win, the "
               "terminal owner is being read off whoever happens to be to act -- the defect c021 "
               "found and fixed. Draws mean the two need not sum to exactly 1.",
           "decomposition": decomposition,
           "verdict": verdict,
           "roots": roots,
           "elapsed_s": round(time.time() - t0, 1)}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(out, fh, indent=2)
    print(json.dumps(out["headline"], indent=1))
    print(verdict)
    print(f"-> {a.out}  ({out['elapsed_s']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
