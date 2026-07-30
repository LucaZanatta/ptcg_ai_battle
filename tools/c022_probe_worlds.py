"""c022 probes M01-M03 — the hidden-world guarantees, measured against the live engine.

`MANDATORY_IMPLEMENTATION A2` lists six properties every generated world must have. c021 already
established the API constraint that forces the K-session design, but `CONTRACT.md §3` says its
findings are "starting facts to verify from raw artifacts, not optional narrative", and this one
is load-bearing for the entire MCGS branch. So it is re-measured here against the engine as
shipped today rather than cited.

Each probe is written so that it can FAIL. A probe whose pass condition holds no matter what the
engine does is inert — c021 shipped one of those (a "direct check" that measured branching and
was read as measuring randomness), and the lesson is recorded in its A4 document. Where a probe
could be inert, this file states what result would have refuted it.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

OUT = os.path.join(_REPO, "contracts",
                   "c022_mcgs_multideterminization_and_faithful_byterl_reproduction",
                   "results", "probes")


def capture_decisions(n: int, seed: int = 7, opponent: str = "dragapult"):
    """Play one real game and capture the first `n` multi-option agent observations."""
    import torch
    torch.set_num_threads(1)
    from kaggle_environments import make
    from cg import c019_core as K, c019_determinize as D19
    from cg import teachers as T, c009_eval as ce

    deck = D19.archetype_decks()["mega_lucario"]
    captured = []

    class Probe:
        def __call__(self, obs):
            sel = obs.get("select")
            if sel is None:
                return list(deck)
            opts = K.canonical_options(sel)
            if len(captured) < n and len(opts) > 1:
                captured.append(dict(obs))
            return K.to_select_payload([opts[0]], sel)

    p = Probe()
    opp = T.make_fresh(opponent, ce.SOURCES)
    env = make("cabt")
    env.run([lambda o: p(o), lambda o: opp(o)])
    return deck, captured


# ============================================================================ M02
def probe_m02_repeated_worlds(deck, captured, k=8):
    """M02 — same public root, legal DISTINCT hidden worlds.

    Refutable: if `sample_worlds` returned k copies of one world, or produced illegal
    multiplicities, `distinct_world_ids` would be 1 or `all_legal` would be False.
    """
    from cg import api as A, c019_core as K, c022_mcgs_worlds as W

    rows = []
    for di, obs_d in enumerate(captured):
        o = A.to_observation_class(obs_d)
        view = K.visible_view(o)
        worlds = W.sample_worlds(view, deck, base_seed=911, decision_index=di, k=k)
        ids = [w.world_id for w in worlds]
        rows.append({
            "decision": di,
            "requested_k": k,
            "returned": len(worlds),
            "distinct_world_ids": len(set(ids)),
            "all_legal": all(w.legal for w in worlds),
            "all_multiplicity_ok": all(w.multiplicity_ok for w in worlds),
            "archetypes": dict(collections.Counter(w.archetype for w in worlds)),
            "world_summaries": [w.summary() for w in worlds],
        })
    ok = all(r["returned"] == k and r["distinct_world_ids"] == k
             and r["all_legal"] and r["all_multiplicity_ok"] for r in rows)
    return {"probe": "M02", "name": "repeated world generation", "pass": ok,
            "pass_condition": "for every captured root, K requested worlds are returned, all K "
                              "world ids are distinct, and every world is legal with legal "
                              "multiplicities",
            "refuted_by": "returning fewer than K, duplicate world ids, or an illegal world",
            "rows": rows}


# ============================================================================ M02b
def probe_m02b_determinism(deck, captured, k=4):
    """The world stream must be deterministic in (base_seed, decision_index).

    Without this, no arm can be replayed and the paired-seed protocol in
    `TRAINING_AND_EVALUATION §5` is meaningless.
    """
    from cg import api as A, c019_core as K, c022_mcgs_worlds as W

    rows = []
    for di, obs_d in enumerate(captured[:3]):
        o = A.to_observation_class(obs_d)
        view = K.visible_view(o)
        a = [w.world_id for w in W.sample_worlds(view, deck, 911, di, k)]
        b = [w.world_id for w in W.sample_worlds(view, deck, 911, di, k)]
        c = [w.world_id for w in W.sample_worlds(view, deck, 912, di, k)]
        rows.append({"decision": di, "same_seed_identical": a == b,
                     "different_seed_differs": a != c,
                     "ids_seed911": a, "ids_seed912": c})
    ok = all(r["same_seed_identical"] and r["different_seed_differs"] for r in rows)
    return {"probe": "M02b", "name": "world stream determinism", "pass": ok,
            "pass_condition": "identical (base_seed, decision) reproduces identical world ids; a "
                              "different base_seed produces different ones",
            "refuted_by": "non-reproducible ids, or a base_seed that changes nothing",
            "rows": rows}


# ============================================================================ M02c
def probe_m02c_seed_stream_independence(deck, captured, k=4):
    """World seeds must not be drawn from the agent's own generator (advisor item 6).

    Refutable: if `world_seeds` consumed a shared generator, drawing K=8 first and K=1 second
    would give a different first world than drawing K=1 alone.
    """
    from cg import c022_mcgs_worlds as W

    s1 = W.world_seeds(4242, 17, 1)
    s8 = W.world_seeds(4242, 17, 8)
    prefix_stable = s8[:1] == s1
    # And an agent generator used in between must not shift the stream.
    rng = np.random.default_rng(4242)
    _ = rng.integers(0, 1 << 40, size=1000)
    s1_after = W.world_seeds(4242, 17, 1)
    unaffected = s1_after == s1
    distinct = len(set(s8)) == 8
    return {"probe": "M02c", "name": "world seed stream independence", "pass":
            bool(prefix_stable and unaffected and distinct),
            "pass_condition": "world seeds depend only on (base_seed, decision_index, i): the "
                              "K=8 stream starts with the K=1 seed, is unaffected by consuming "
                              "an unrelated generator, and yields 8 distinct seeds",
            "refuted_by": "a K-dependent or draw-order-dependent first seed, which would make "
                          "the K=1 arm stop reproducing the c021 control for reasons unrelated "
                          "to the algorithm (probe M04)",
            "k1_seed": s1, "k8_prefix": s8[:1], "k8_distinct": distinct,
            "unaffected_by_foreign_rng": unaffected}


# ============================================================================ M03
def probe_m03_no_leakage(deck, captured, k=4):
    """M03 — no root-player-inaccessible information reaches the agent.

    Three separate checks, because "no leakage" has three failure modes here:
      a. the determinizer reads hidden state from the environment rather than sampling it;
      b. a hidden zone is written into a trace record;
      c. a hidden zone is handed to policy code.
    """
    from cg import api as A, c019_core as K, c022_mcgs_worlds as W

    o = A.to_observation_class(captured[0])
    view = K.visible_view(o)

    # (a) the determinizer sees only the VisibleObservation. If it were reading the true opponent
    # hand, every world would reproduce it and world ids would collapse to one.
    worlds = W.sample_worlds(view, deck, 555, 0, k)
    distinct = len({w.world_id for w in worlds})

    # (b) a world summary must be publishable.
    summary_clean, summary_err = True, None
    try:
        for w in worlds:
            W.assert_no_leakage(w.summary(), "world.summary")
    except W.LeakageError as e:
        summary_clean, summary_err = False, str(e)

    # (c) the leakage guard must actually fire on a real hidden payload. A guard that never
    # fires is inert -- this is the c021 lesson applied to c022's own check.
    guard_fires, guard_err = False, None
    try:
        W.assert_no_leakage({"opponent_hand": worlds[0].zones["opponent_hand"]}, "injected")
    except W.LeakageError as e:
        guard_fires, guard_err = True, str(e)
    guard_fires_unnamed = False
    try:
        W.assert_no_leakage({"harmless_key": worlds[0].zones["opponent_deck"]}, "injected2")
    except W.LeakageError:
        guard_fires_unnamed = True

    # The runtime guard's KNOWN LIMIT, measured rather than assumed: a SHORT hidden list under a
    # key with no revealing substring (e.g. the 1-2 card opponent_active) is below the 20-int
    # length heuristic and passes. Recording the limit here is the point -- the real guarantee
    # is the static one below, not the heuristic.
    short_leak_caught = False
    try:
        W.assert_no_leakage({"xz": list(worlds[0].zones["opponent_active"])}, "injected3")
    except W.LeakageError:
        short_leak_caught = True

    # STATIC guarantee: WorldHandle.zones may be read only inside c022_mcgs_worlds.py itself.
    # Every other c022 module must go through begin_args(), which hands the lists to
    # api.search_begin and to nothing else. This is a stronger property than any runtime
    # heuristic, because it does not depend on a payload happening to be inspected.
    import glob
    import re as _re
    zone_readers = []
    for p in sorted(glob.glob(os.path.join(_REPO, "starter_kit", "c022_*.py"))
                    + glob.glob(os.path.join(_REPO, "tools", "c022_*.py"))):
        base = os.path.basename(p)
        if base == "c022_mcgs_worlds.py":
            continue
        for i, ln in enumerate(open(p).read().splitlines(), 1):
            if _re.search(r"\.zones\b", ln) and not ln.strip().startswith("#"):
                zone_readers.append({"file": base, "line": i, "text": ln.strip()[:120]})
    # tools/c022_probe_worlds.py is this file: it reads .zones on purpose, to build the
    # injected payloads above. It is the one permitted exception and is named explicitly.
    zone_readers = [z for z in zone_readers if z["file"] != "c022_probe_worlds.py"]

    # WorldHandle must not print its contents either.
    repr_clean = "opponent_hand" not in repr(worlds[0]) and \
                 str(worlds[0].zones.get("opponent_deck", [])[:1]) not in repr(worlds[0])

    ok = bool(distinct == k and summary_clean and guard_fires and guard_fires_unnamed
              and repr_clean and not zone_readers)
    return {"probe": "M03", "name": "no leakage", "pass": ok,
            "pass_condition": "worlds differ (so hidden state was sampled, not read); world "
                              "summaries pass the leakage guard; the guard fires on a hidden "
                              "zone both under its own name and under an innocent key; a "
                              "WorldHandle repr does not print its zones; and NO c022 module "
                              "outside c022_mcgs_worlds.py reads WorldHandle.zones",
            "refuted_by": "identical worlds (the determinizer read the truth), a summary "
                          "containing a hidden zone, a guard that never fires, or any module "
                          "reaching into .zones instead of going through begin_args()",
            "distinct_worlds": distinct, "requested": k,
            "summary_clean": summary_clean, "summary_error": summary_err,
            "guard_fires_on_named_field": guard_fires, "guard_message": guard_err,
            "guard_fires_on_disguised_field": guard_fires_unnamed,
            "short_hidden_list_under_opaque_key_caught": short_leak_caught,
            "runtime_guard_known_limit":
                "a hidden list shorter than 20 entries, under a key containing none of "
                "hand/deck/prize/zone, is not caught by the runtime heuristic. The static check "
                "below is what actually holds the guarantee.",
            "modules_reading_WorldHandle_zones": zone_readers,
            "repr_clean": repr_clean}


# ============================================================================ M03b
def probe_m03b_public_identity(deck, captured, k=6):
    """The public observation must be IDENTICAL across worlds, and the root option set with it.

    This is the precondition for aggregating by action index. It is checked at the root of a real
    `search_begin` for each world, not merely on the pre-session observation.
    """
    from cg import api as A, c019_core as K, c022_mcgs_worlds as W

    rows = []
    for di, obs_d in enumerate(captured[:3]):
        o = A.to_observation_class(obs_d)
        view = K.visible_view(o)
        worlds = W.sample_worlds(view, deck, 777, di, k)
        sigs, nopts, errs = [], [], []
        for w in worlds:
            try:
                st = W.open_session(o, w, manual_coin=True)
                sel = getattr(st.observation, "select", None)
                if sel is None:
                    errs.append("no select at root")
                    continue
                sigs.append(W.option_signature(sel))
                nopts.append(len(K.canonical_options(sel)))
            except Exception as e:  # noqa: BLE001
                errs.append(f"{type(e).__name__}: {e}"[:160])
            finally:
                try:
                    A.search_end()
                except Exception:  # noqa: BLE001
                    pass
        rows.append({"decision": di, "worlds": len(worlds),
                     "distinct_option_signatures": len(set(sigs)),
                     "option_counts": sorted(set(nopts)),
                     "errors": errs,
                     "agent_side_signature": W.option_signature(o.select)})
    ok = all(r["distinct_option_signatures"] == 1 and not r["errors"] for r in rows)
    return {"probe": "M03b", "name": "public root identity across worlds", "pass": ok,
            "pass_condition": "every world's search_begin root presents exactly one distinct "
                              "option signature, so action indices are comparable across worlds",
            "refuted_by": "more than one signature, which would mean cross-world aggregation by "
                          "ActionIndex is summing statistics for different actions",
            "rows": rows}


# ============================================================================ M01b
def probe_m01b_api_constraint(deck, captured):
    """Re-verify the constraint that forces the K-session design (source map, gap analysis).

    Three sub-probes:
      1. `search_step` is deterministic within a session — the same action from the same state
         yields one successor, so there is no interior randomness to sample over.
      2. Re-calling `search_begin` with a different world yields different successors — so the
         randomness lives at session start.
      3. An interior observation carries no `search_begin_input`, so no interior node can open a
         session.
    """
    from cg import api as A, c019_core as K, c022_mcgs_worlds as W
    from cg import c021_mcgs_abstraction as AB

    o = A.to_observation_class(captured[0])
    view = K.visible_view(o)
    sel = o.select
    opts = K.canonical_options(sel)
    w0 = W.sample_worlds(view, deck, 31337, 0, 1)[0]

    # 1. determinism within a session
    det_rows = []
    for oi in range(min(3, len(opts))):
        seen = collections.Counter()
        for _ in range(12):
            st = W.open_session(o, w0)
            try:
                succ = A.search_step(st.searchId, K.to_select_payload([opts[oi]], sel))
                seen[hash(AB.StateAbstraction(succ.observation, None, None, True))] += 1
            except Exception as e:  # noqa: BLE001
                seen[f"ERR:{type(e).__name__}"] += 1
            finally:
                A.search_end()
        det_rows.append({"option": oi, "distinct_successors": len(seen), "trials": 12})

    # 2. randomness at search_begin
    worlds = W.sample_worlds(view, deck, 24680, 0, 8)
    hs = collections.Counter()
    for w in worlds:
        st = W.open_session(o, w)
        try:
            succ = A.search_step(st.searchId, K.to_select_payload([opts[0]], sel))
            hs[hash(AB.StateAbstraction(succ.observation, None, None, True))] += 1
        except Exception:  # noqa: BLE001
            hs["ERR"] += 1
        finally:
            A.search_end()

    # 3. no interior search_begin_input
    st = W.open_session(o, w0)
    root_has = getattr(o, "search_begin_input", None) is not None
    succ = A.search_step(st.searchId, K.to_select_payload([opts[0]], sel))
    interior_has = getattr(succ.observation, "search_begin_input", None) is not None
    interior_begin_error = None
    try:
        W.open_session(succ.observation, w0)
        interior_begin_error = "NO ERROR -- interior search_begin SUCCEEDED"
    except Exception as e:  # noqa: BLE001
        interior_begin_error = f"{type(e).__name__}: {e}"[:160]
    A.search_end()

    deterministic = all(r["distinct_successors"] == 1 for r in det_rows)
    varies = len(hs) > 1
    ok = bool(deterministic and varies and root_has and not interior_has)
    return {"probe": "M01b", "name": "API hidden-information constraint", "pass": ok,
            "pass_condition": "search_step is deterministic within a session; different worlds "
                              "give different successors; only the agent-facing root observation "
                              "carries search_begin_input",
            "refuted_by": "a nondeterministic search_step (priority 1 would then be available "
                          "and the whole K-session design would be the wrong branch), or an "
                          "interior observation that can open a session",
            "within_session_determinism": det_rows,
            "across_world_successors": {"distinct": len(hs), "of": len(worlds)},
            "root_has_search_begin_input": root_has,
            "interior_has_search_begin_input": interior_has,
            "interior_search_begin_result": interior_begin_error}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--captures", type=int, default=4)
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--out", default=os.path.join(OUT, "mcgs_world_probes.json"))
    a = ap.parse_args(argv)

    t0 = time.time()
    deck, captured = capture_decisions(a.captures)
    if not captured:
        raise SystemExit("captured no multi-option decisions")

    probes = [
        probe_m01b_api_constraint(deck, captured),
        probe_m02_repeated_worlds(deck, captured, a.k),
        probe_m02b_determinism(deck, captured),
        probe_m02c_seed_stream_independence(deck, captured),
        probe_m03_no_leakage(deck, captured),
        probe_m03b_public_identity(deck, captured),
    ]
    out = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "captured_decisions": len(captured),
           "elapsed_s": round(time.time() - t0, 1),
           "n_pass": sum(1 for p in probes if p["pass"]),
           "n_probes": len(probes),
           "probes": probes}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(out, fh, indent=2)
    for p in probes:
        print(f"{'PASS' if p['pass'] else 'FAIL'}  {p['probe']:6s} {p['name']}")
    print(f"{out['n_pass']}/{out['n_probes']} in {out['elapsed_s']}s -> {a.out}")
    return 0 if out["n_pass"] == out["n_probes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
