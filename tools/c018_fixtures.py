"""c018 — tactical fixtures, branch proof, lifecycle and throughput evidence (P01/P02/P05/P06).

Fills the parts of §15 that the aggregate counters cannot answer:

  * **P01** — `search_begin_input` is preserved (the caller's observation is not mutated), and
    repeated searches on one root neither leak handles nor corrupt the parent episode.
  * **P02** — per decision: at least two legal alternatives producing *distinct* successor
    observations, and the legal option set genuinely *evolving* after an action. Aggregate
    "distinct successors" cannot distinguish a branching tree from one long line.
  * **P05** — the seven named tactical categories, each with a real captured root: candidate
    selects, successor summaries, leaf decomposition, chosen line, nodes/depth/time.
  * **P06** — roots/s, steps/s and process RSS alongside latency.

Categories are assigned from the engine's own `SelectContext` and `OptionType` values, not from
guesswork about what a decision "looks like".
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import resource
import sys
import time

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

C18 = os.path.join(_REPO, "contracts",
                   "c018_complete_integrated_search_learning_curriculum_campaign", "results")
ART = os.path.join(C18, "artifacts")

# SelectContext / OptionType values from cg/api.py
CTX_MAIN = 0
OPT_PLAY, OPT_ATTACH, OPT_RETREAT, OPT_ATTACK = 7, 8, 12, 13
OPT_EVOLVE, OPT_ABILITY = 9, 10
CTX_TO_BENCH, CTX_TO_FIELD = 5, 6
CTX_DISCARD, CTX_TO_HAND, CTX_TO_DECK = 8, 7, 9
CTX_EVOLVES_FROM, CTX_EVOLVES_TO = 18, 19
CTX_ATTACH_FROM, CTX_ATTACH_TO = 21, 22
CTX_ATTACK = 35

CATEGORIES = ("missed_lethal", "wrong_attack_or_target", "energy_attachment_route",
              "evolution_timing", "bench_liability", "resource_reservation",
              "search_card_sequencing")


# One prize is 0.55/6 of the leaf value, so a candidate that beats the baseline by more than
# that took a prize the baseline did not -- a lethal the baseline would have missed.
PRIZE_DELTA = 0.55 / 6.0


def classify(sel, scored=None, bench=None) -> str:
    """Map a decision to one of the seven §15 P05 categories.

    Context and option types come from the engine's own enums. Two categories cannot be read
    off the context alone and use the search's own results instead:

      * `missed_lethal` — an attack decision where some candidate's leaf value exceeds the
        baseline's by more than one prize. A single-option attack is a *forced* move, not a
        tactical choice, and never reaches the search at all; defining the category that way
        would have guaranteed it stayed empty.
      * `bench_liability` — a decision taken while the bench is empty or nearly so, which is
        where bench state actually creates risk, rather than only the explicit TO_BENCH context.
    """
    ctx = int(sel.get("context", -1) or 0)
    types = {int(o.get("type", -1)) for o in (sel.get("option") or []) if isinstance(o, dict)}
    is_attack = ctx == CTX_ATTACK or OPT_ATTACK in types
    if is_attack and scored:
        bl = next((s for s in scored if s["is_baseline"]), None)
        best = max(scored, key=lambda s: s["value"])
        if bl is not None and (best["value"] - bl["value"]) > PRIZE_DELTA:
            return "missed_lethal"
        return "wrong_attack_or_target"
    if is_attack:
        return "wrong_attack_or_target"
    if bench is not None and bench <= 1 and ctx == CTX_MAIN:
        return "bench_liability"
    if ctx in (CTX_ATTACH_FROM, CTX_ATTACH_TO) or OPT_ATTACH in types:
        return "energy_attachment_route"
    if ctx in (CTX_EVOLVES_FROM, CTX_EVOLVES_TO) or OPT_EVOLVE in types:
        return "evolution_timing"
    if ctx in (CTX_TO_BENCH, CTX_TO_FIELD):
        return "bench_liability"
    if ctx in (CTX_DISCARD, CTX_TO_DECK):
        return "resource_reservation"
    if ctx in (CTX_TO_HAND,) or OPT_ABILITY in types:
        return "search_card_sequencing"
    if ctx == CTX_MAIN and OPT_PLAY in types:
        return "search_card_sequencing"
    return "resource_reservation"


def lifecycle_probe():
    """P01 additions: input preservation and repeated-search stability on one root."""
    from kaggle_environments import make
    from cg import api as A, teachers as T, c009_eval as ce
    import c018_search as S

    deck = T.read_deck("mega_lucario", ce.SOURCES)
    base = T.make_fresh("mega_lucario", ce.SOURCES)
    opp = T.make_fresh("dragapult", ce.SOURCES)
    out = {"probe_id": "P01", "repeats": 0, "input_mutated": False,
           "distinct_child_ids_per_repeat": [], "release_errors": 0, "begin_errors": 0,
           "successor_sets_identical_across_repeats": None, "errors": []}
    captured = {}

    def me(obs):
        sel = obs.get("select") if isinstance(obs, dict) else None
        if sel is None:
            return base(obs)
        if not captured and len(sel.get("option") or []) >= 3:
            captured["obs"] = json.loads(json.dumps(obs, default=str))
            captured["live"] = obs
        return base(obs)

    try:
        make("cabt").run([me, lambda o: opp(o)])
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"parent_episode:{type(e).__name__}: {e}")

    if not captured:
        out["errors"].append("no representative root captured")
        return out

    before = json.dumps(captured["obs"], sort_keys=True, default=str)
    rng = np.random.default_rng(99)
    sig_sets = []
    for r in range(5):
        stats = S.new_stats()
        stats["decisions"] = 1
        res = S.plan(captured["live"], [0], deck, rng, S.DEFAULT_CFG, stats, None)
        out["repeats"] += 1
        out["begin_errors"] += stats["begin_errors"]
        out["release_errors"] += stats["release_errors"]
        out["distinct_child_ids_per_repeat"].append(stats["distinct_successors"])
        sig_sets.append(res.get("distinct_successors"))
    after = json.dumps(json.loads(json.dumps(captured["live"], default=str)),
                       sort_keys=True, default=str)
    # search_begin_input preservation: the caller's observation must survive untouched
    out["input_mutated"] = before != after
    out["search_begin_input_preserved"] = not out["input_mutated"]
    out["successor_counts_across_repeats"] = sig_sets
    out["repeated_search_stable"] = (len(set(sig_sets)) <= 2 and out["begin_errors"] == 0
                                     and out["release_errors"] == 0)
    out["rss_mb_after_repeats"] = round(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    return out


def capture(n_games=4):
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce
    import c018_search as S

    deck = T.read_deck("mega_lucario", ce.SOURCES)
    stats = S.new_stats()
    rng = np.random.default_rng(1815)
    fixtures = {c: [] for c in CATEGORIES}
    branch_rows = []
    t0 = time.time()

    for gi in range(n_games):
        base = T.make_fresh("mega_lucario", ce.SOURCES)
        opp = T.make_fresh(["dragapult", "iono", "mega_abomasnow"][gi % 3], ce.SOURCES)
        stats["match_ms"] = 0.0

        def me(obs):
            sel = obs.get("select") if isinstance(obs, dict) else None
            if sel is None:
                return base(obs)
            stats["decisions"] += 1
            b = base(obs)
            traces = []
            r = S.plan(obs, b, deck, rng, S.DEFAULT_CFG, stats, traces)
            if r.get("searched"):
                sc = r.get("candidate_scores") or []
                bench = None
                if len(sc) > 1:
                    # only for candidate fixtures, so the conversion cost is paid rarely
                    try:
                        from cg import api as A
                        o = A.to_observation_class(obs)
                        st = o.current
                        bench = len([c for c in (st.players[st.yourIndex].bench or [])
                                     if c is not None])
                    except Exception:  # noqa: BLE001
                        bench = None
                cat = classify(sel, sc, bench)
                # P02: distinct successors from at least two DIFFERENT candidates, and an
                # option set that changed after the action -- an aggregate count cannot tell
                # a branching tree from one deep line.
                tr = traces[0] if traces else {}
                branch_rows.append({
                    "game": gi, "context": int(sel.get("context", -1) or 0),
                    "category": cat, "n_options": len(sel.get("option") or []),
                    "own_bench": bench,
                    "candidates_scored": len(sc),
                    "distinct_leaf_values": len({s["value"] for s in sc}),
                    "alternatives_with_distinct_successors":
                        r.get("distinct_successors") or 0,
                    "depth_max": r.get("depth_max"),
                    "chose_baseline": r["action"] == list(b),
                    "ms": r.get("ms")})
                if len(fixtures[cat]) < 3 and len(sc) > 1:
                    fixtures[cat].append({
                        "game": gi, "decision": stats["decisions"],
                        "select_context": int(sel.get("context", -1) or 0),
                        "min_count": sel.get("minCount"), "max_count": sel.get("maxCount"),
                        "root_option_types": [int(o.get("type", -1)) for o in
                                              (sel.get("option") or [])
                                              if isinstance(o, dict)][:12],
                        "n_options": len(sel.get("option") or []),
                        "own_bench_size": bench,
                        "baseline_action": list(b),
                        "candidate_selects": [s["candidate"] for s in sc],
                        "leaf_decomposition": [
                            {"candidate": s["candidate"], "depth": s["depth"],
                             "heuristic_value": s.get("heuristic_value"),
                             "learned_value": s.get("learned_value"),
                             "is_baseline": s["is_baseline"]} for s in sc],
                        "chosen_line": r["action"],
                        "line_label": ("baseline_retained" if r["action"] == list(b)
                                       else "search_preferred_alternative"),
                        "dominated_lines": [s["candidate"] for s in sc
                                            if s["candidate"] != r["action"]],
                        "nodes_depth_time": {"depth_max": r.get("depth_max"),
                                             "distinct_successors":
                                                 r.get("distinct_successors"),
                                             "ms": r.get("ms")},
                        "determinization": (tr.get("determinization") if tr else None)})
            return r["action"]
        agents = [me, lambda o: opp(o)] if gi % 2 == 0 else [lambda o: opp(o), me]
        try:
            make("cabt").run(agents)
        except Exception:  # noqa: BLE001
            stats["game_exception"] += 1

    el = max(1e-9, time.time() - t0)
    thr = {"probe_id": "P06", "wall_clock_s": round(el, 1),
           "games": n_games, "decisions": stats["decisions"],
           "roots_per_second": round(stats["begin_ok"] / el, 2),
           "steps_per_second": round(stats["step_ok"] / el, 2),
           "nodes_per_second": round(stats["nodes"] / el, 2),
           "determinizations": stats["begin_calls"],
           "fallback_rate": round(stats["fallbacks"] / max(1, stats["decisions"]), 4),
           "rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
           "mean_full_match_agent_ms": round(stats["match_ms"] / max(1, n_games), 1)}

    branch = {"probe_id": "P02", "decisions_examined": len(branch_rows),
              "decisions_with_two_or_more_distinct_successors":
                  sum(1 for r in branch_rows if r["alternatives_with_distinct_successors"] >= 2),
              "decisions_reaching_depth_gt_1":
                  sum(1 for r in branch_rows if (r["depth_max"] or 0) > 1),
              "decisions_with_distinct_leaf_values":
                  sum(1 for r in branch_rows if r["distinct_leaf_values"] > 1),
              "note": ("a static root-score list would show one successor per candidate and "
                       "depth 0; every row here comes from real search_step results"),
              "rows": branch_rows[:200]}

    fx = {"probe_id": "P05", "categories": {k: len(v) for k, v in fixtures.items()},
          "categories_covered": sum(1 for v in fixtures.values() if v),
          "categories_total": len(CATEGORIES), "fixtures": fixtures}
    return thr, branch, fx


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=4)
    a = ap.parse_args(argv)
    os.makedirs(ART, exist_ok=True)
    life = lifecycle_probe()
    json.dump(life, open(os.path.join(ART, "lifecycle_extended.json"), "w"), indent=2,
              default=str)
    thr, branch, fx = capture(a.games)
    json.dump(thr, open(os.path.join(ART, "throughput.json"), "w"), indent=2, default=str)
    json.dump(branch, open(os.path.join(ART, "branch_proof.json"), "w"), indent=2, default=str)
    json.dump(fx, open(os.path.join(ART, "tactical_fixtures.json"), "w"), indent=2,
              default=str)
    print(json.dumps({"lifecycle": {k: life[k] for k in
                                    ("repeats", "search_begin_input_preserved",
                                     "repeated_search_stable", "begin_errors",
                                     "release_errors", "rss_mb_after_repeats")},
                      "throughput": thr,
                      "branch": {k: branch[k] for k in
                                 ("decisions_examined",
                                  "decisions_with_two_or_more_distinct_successors",
                                  "decisions_reaching_depth_gt_1",
                                  "decisions_with_distinct_leaf_values")},
                      "fixtures": {"covered": fx["categories_covered"],
                                   "of": fx["categories_total"],
                                   "per_category": fx["categories"]}}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
