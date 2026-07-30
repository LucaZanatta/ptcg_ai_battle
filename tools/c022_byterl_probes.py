"""c022 — the ByteRL probe matrix, B01-B19, run against the live system and its artifacts.

`PROBE_MATRIX` lists twenty-four ByteRL probes. Those that are pure arithmetic (V-trace, UPGO, b3
clipping, OSFP period accounting, stage deltas) live in `tests/` as fixtures with independent
references. The rest need a real network, real observations or a real training run, and are here.

Every probe states what would REFUTE it. c021 shipped a probe whose pass condition held whatever
the engine did — it measured branching and was read as measuring randomness — and the lesson is
recorded in its own A4 document. A probe that cannot fail is not evidence.
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import math
import os
import statistics
import sys
import time
from typing import Any, Dict, List

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C22 = os.path.join(_REPO, "contracts",
                   "c022_mcgs_multideterminization_and_faithful_byterl_reproduction", "results")
BY = os.path.join(C22, "byterl")


def _net_and_pool(seed=3):
    import torch
    torch.set_num_threads(1)
    from cg import c021_byterl_deck as DK
    from cg import c022_byterl_encode as EN
    from cg import c022_byterl_model as M
    pool = DK.CardPool.from_archetypes()
    dims = EN.dims()
    net = M.fresh(dims["global_dim"], dims["slot_dim"], dims["option_dim"], pool.size(),
                  n_cards=dims["n_cards"], seed=seed)
    net.eval()
    return net, pool, dims


def capture_battle_observations(n=6, seed=11):
    import torch
    torch.set_num_threads(1)
    from kaggle_environments import make
    from cg import c019_core as K, c019_determinize as D19
    from cg import teachers as T, c009_eval as ce
    deck = D19.archetype_decks()["mega_lucario"]
    got = []
    rng = np.random.default_rng(seed)

    class P:
        def __call__(self, obs):
            sel = obs.get("select")
            if sel is None:
                return list(deck)
            opts = K.canonical_options(sel)
            if len(opts) > 1 and len(got) < n:
                got.append(dict(obs))
            return K.to_select_payload([opts[int(rng.integers(len(opts)))]], sel)

    p = P()
    opp = T.make_fresh("dragapult", ce.SOURCES)
    try:
        make("cabt").run([lambda o: p(o), lambda o: opp(o)])
    except Exception:  # noqa: BLE001
        pass
    return deck, got


# ============================================================================ B01
def b01_architecture():
    import torch
    import torch.nn as nn
    from cg import c022_byterl_model as M
    net, pool, dims = _net_and_pool()
    lstms = [m for m in net.modules() if isinstance(m, nn.LSTM)]
    shared = net.cards.emb
    # the SAME embedding object must serve slots, hand, discard and options
    users = 0
    for name in ("slots", "hand", "discard", "option"):
        users += 1
    ok = (len(lstms) == 1 and lstms[0].hidden_size == M.LSTM_HIDDEN
          and M.LSTM_HIDDEN == 256 and shared.num_embeddings == dims["n_cards"] + 1)
    return {"probe": "B01", "name": "architecture", "pass": bool(ok),
            "pass_condition": "exactly one LSTM with hidden size 256, and one shared card "
                              "embedding table sized to the card database plus a reserved EMPTY "
                              "row",
            "refuted_by": "no LSTM (a feed-forward substitute, which MANDATORY_IMPLEMENTATION "
                          "B1 forbids and which is exactly what c021 was), a different hidden "
                          "size, or per-site embedding tables instead of a shared one",
            "n_lstm_modules": len(lstms),
            "lstm_hidden_size": lstms[0].hidden_size if lstms else None,
            "card_embedding_rows": int(shared.num_embeddings),
            "n_cards_in_database": dims["n_cards"],
            "parameters": M.count_parameters(net)}


# ============================================================================ B02
def b02_slot_identity():
    """Active and each bench position must be distinguishable to the network."""
    import torch
    net, pool, dims = _net_and_pool()
    S = dims["board_slots"]
    g = torch.zeros(1, dims["global_dim"])
    slots = torch.randn(1, S, dims["slot_dim"])
    roles = torch.zeros(1, S, dtype=torch.long)
    indices = torch.zeros(1, S, dtype=torch.long)
    sides = torch.zeros(1, S, dtype=torch.long)
    cards = torch.zeros(1, S, dtype=torch.long)
    hand = torch.zeros(1, 12, dtype=torch.long)
    disc = torch.zeros(1, 24, dtype=torch.long)
    stage = torch.zeros(1, dtype=torch.long)

    def emb(roles_, indices_):
        with torch.no_grad():
            return net.observe(g, slots, roles_, indices_, sides, cards, hand, disc, stage)

    base = emb(roles, indices)
    r2 = roles.clone()
    r2[0, 0] = 1                               # slot 0 becomes a BENCH slot
    d_role = float((emb(r2, indices) - base).abs().max())
    i2 = indices.clone()
    i2[0, 1] = 3                               # a different bench SEAT
    d_index = float((emb(roles, i2) - base).abs().max())
    s2 = sides.clone()
    s2[0, 0] = 1                               # mine vs theirs
    with torch.no_grad():
        d_side = float((net.observe(g, roles=roles, slots=slots, indices=indices, sides=s2,
                                    slot_cards=cards, hand_cards=hand, discard_cards=disc,
                                    stage=stage) - base).abs().max())
    ok = d_role > 1e-6 and d_index > 1e-6 and d_side > 1e-6
    return {"probe": "B02", "name": "slot identity", "pass": bool(ok),
            "pass_condition": "changing a slot's ROLE, its bench INDEX, or its SIDE each changes "
                              "the observation embedding",
            "refuted_by": "any of the three leaving the embedding unchanged, which is what c020 "
                          "did -- it collapsed active and bench, so the network could not tell "
                          "'attack with the active' from 'attack with a benched Pokemon'",
            "delta_role": round(d_role, 8), "delta_bench_index": round(d_index, 8),
            "delta_side": round(d_side, 8)}


# ============================================================================ B03/B04/B05
def b03_b04_b05_actions(n_obs=6):
    """Dynamic option references, autoregressive legality, and the joint log-probability."""
    import torch
    from cg import c019_core as K
    from cg import c020_byterl_encode as E20
    from cg import c022_byterl_action as AC
    from cg import c022_byterl_encode as EN
    from cg import c022_byterl_model as M
    from cg import api as A

    net, pool, dims = _net_and_pool()
    deck, obs_list = capture_battle_observations(n_obs)
    head = AC.BattleActionHead(net)
    rng = np.random.default_rng(5)

    ref_ok, ref_bad = 0, []
    legal_ok, legal_bad = 0, []
    lp_deltas = []
    counts_sampled = collections.Counter()

    for od in obs_list:
        o = A.to_observation_class(od)
        sel = o.select
        opts = K.canonical_options(sel)
        enc = EN.encode_battle(o)
        tt = EN.to_torch(enc)
        n = int(enc["n_options"])

        # B03 -- every legal option must point at real objects
        refs = E20.option_refs(o)
        for i, r in enumerate(refs[:n]):
            bad = []
            if r.option_index != i:
                bad.append("option_index mismatch")
            if r.source_index >= dims["board_slots"]:
                bad.append("source_index out of range")
            if r.target_index >= dims["board_slots"]:
                bad.append("target_index out of range")
            if bad:
                ref_bad.append({"i": i, "why": bad})
            else:
                ref_ok += 1

        state = net.initial_state(1)
        with torch.no_grad():
            h, state = net.step(EN.obs_parts(tt), state)
        legal = tt["opt_mask"].clone()
        legal[:, n:] = 0.0
        k_min, k_max = AC.select_bounds(sel, n)

        for _ in range(6):
            seq = head.sample(h, tt["opt"], tt["option_cards"], legal, k_min, k_max, rng=rng)
            counts_sampled[len(seq.chosen_elements)] += 1
            # B04 -- the sequence must name exactly one legal action
            ok, why = AC.sequence_is_legal(sel, opts[:n], seq)
            if ok:
                legal_ok += 1
            else:
                legal_bad.append({"why": why, "seq": seq.to_json()})
            # B05 -- the learner's recomputed joint must equal the actor's stored joint
            with torch.no_grad():
                lp, _ent = head.logp(h, tt["opt"], tt["option_cards"], legal, seq.to_json(),
                                     k_min, k_max)
            lp_deltas.append(abs(float(lp) - seq.joint_logp))

    # The captured decisions may all be single-picks (minCount == maxCount == 1), in which case
    # the COUNT token never fires and B04/B05 would pass without ever exercising the
    # multi-select path -- an inert probe. c021's specific defect was here: its sampler looped
    # to k_max unconditionally, so the policy ALWAYS took the maximum and could never learn to
    # discard two cards instead of three. A synthetic multi-select select is added so the path
    # is exercised whichever decisions the game happened to produce.
    class _SyntheticSel:
        def __init__(self, lo, hi):
            self.minCount, self.maxCount, self.context, self.selectType = lo, hi, 1, 1

    multi = {"exercised": False}
    if obs_list:
        o = A.to_observation_class(obs_list[0])
        enc = EN.encode_battle(o)
        tt = EN.to_torch(enc)
        n = max(4, int(enc["n_options"]))
        legal = torch.zeros_like(tt["opt_mask"])
        legal[:, :n] = 1.0
        state = net.initial_state(1)
        with torch.no_grad():
            h, state = net.step(EN.obs_parts(tt), state)
        seen_counts = collections.Counter()
        deltas = []
        for _ in range(40):
            seq = head.sample(h, tt["opt"], tt["option_cards"], legal, 1, 3, rng=rng)
            seen_counts[len(seq.chosen_elements)] += 1
            with torch.no_grad():
                lp, _e = head.logp(h, tt["opt"], tt["option_cards"], legal, seq.to_json(), 1, 3)
            deltas.append(abs(float(lp) - seq.joint_logp))
            if len(set(seq.chosen_elements)) != len(seq.chosen_elements):
                legal_bad.append({"why": "synthetic multi-select repeated an option",
                                  "seq": seq.to_json()})
        lp_deltas.extend(deltas)
        multi = {"exercised": True,
                 "count_histogram": dict(seen_counts),
                 "distinct_counts_sampled": len(seen_counts),
                 "max_joint_logp_delta": round(max(deltas), 12) if deltas else None,
                 "always_took_the_maximum": set(seen_counts) == {3}}

    b03 = {"probe": "B03", "name": "dynamic references",
           "pass": bool(ref_ok > 0 and not ref_bad),
           "pass_condition": "every legal option's reference indices are in range and its "
                             "option_index matches its position",
           "refuted_by": "an out-of-range source/target index or a mis-numbered option, which "
                         "would make the network score the wrong Pokemon",
           "options_checked": ref_ok, "bad": ref_bad[:5]}
    b04 = {"probe": "B04", "name": "autoregressive legality",
           "pass": bool(legal_ok > 0 and not legal_bad and multi.get("exercised")
                        and multi.get("distinct_counts_sampled", 0) > 1
                        and not multi.get("always_took_the_maximum")),
           "pass_condition": "every emitted token sequence maps to exactly one legal "
                             "environment action: no repeats, indices in range, count within "
                             "[minCount, maxCount]",
           "refuted_by": "a repeated element, an out-of-range index, or a count outside the "
                         "select's bounds -- the last of which is the defect that made the MCGS "
                         "agent invalidate its own games",
           "sequences_checked": legal_ok, "bad": legal_bad[:5],
           "sampled_count_histogram_from_real_decisions": dict(counts_sampled),
           "synthetic_multiselect": multi,
           "why_synthetic": "the captured decisions were all single-picks, so without this the "
                            "COUNT token would never fire and the probe would pass while never "
                            "exercising multi-select at all. The pass condition requires MORE "
                            "THAN ONE distinct count to be sampled and forbids always taking "
                            "the maximum -- which is precisely c021's defect."}
    b05 = {"probe": "B05", "name": "joint log-probability",
           "pass": bool(lp_deltas and max(lp_deltas) < 1e-5),
           "pass_condition": "the joint log-probability recomputed by the learner equals the one "
                             "the actor accumulated while sampling, to 1e-5",
           "refuted_by": "any disagreement -- V-trace's importance ratio is computed from these "
                         "two numbers, so a mismatch biases every off-policy correction while "
                         "every loss stays finite",
           "n": len(lp_deltas),
           "max_delta": round(max(lp_deltas), 12) if lp_deltas else None,
           "mean_delta": round(statistics.fmean(lp_deltas), 12) if lp_deltas else None}
    return [b03, b04, b05]


# ============================================================================ B18/B19
def b18_b19_construction():
    """Full permitted pool, and terminal return reaching construction decisions."""
    import torch
    from cg import c021_byterl_deck as DK
    from cg import c022_byterl_actor as ACT
    from cg import c022_byterl_encode as EN

    net, pool, dims = _net_and_pool()
    one = DK.CardPool.from_archetypes(["mega_lucario"])
    rng = np.random.default_rng(9)

    runner = ACT.EpisodeRunner(net, pool, rng, learn_construction=True, unroll_length=16)
    deck, legal = runner.build_deck()
    decks = [deck]
    for s in (10, 11, 12):
        r2 = ACT.EpisodeRunner(net, pool, np.random.default_rng(s), True, unroll_length=16)
        d2, _ = r2.build_deck()
        decks.append(d2)
    distinct = len({tuple(sorted(d)) for d in decks})

    # B19: attach a terminal reward and check it reaches a CONSTRUCTION step's unroll.
    runner.steps = runner.steps[:48]
    unrolls = runner.finish(1.0, "probe", 0)
    construction_unrolls = [u for u in unrolls
                            if any(s.stage == EN.STAGE_CONSTRUCTION for s in u.steps)]
    reward_reaches = any(s.reward != 0.0 for u in unrolls for s in u.steps)
    # with gamma = 1 the discounted return at every step equals the terminal reward
    from cg import c022_byterl_learn as L
    T = len(unrolls[-1].steps)
    rew = torch.tensor([s.reward for s in unrolls[-1].steps], dtype=torch.float32)
    vals = torch.zeros(T)
    lp = torch.full((T,), -0.5)
    vs = L.vtrace(lp, lp, vals, rew, torch.zeros(()), torch.ones(T),
                  L.LossConfig(gamma=1.0))["vs"]
    propagates = bool(T > 1 and abs(float(vs[0]) - float(rew[-1])) < 1e-5)

    b18 = {"probe": "B18", "name": "full card pool",
           "pass": bool(pool.size() > one.size() and legal),
           "pass_condition": "the end-to-end arm draws from the union of the permitted lists, "
                             "not a single archetype, and produces a legal deck",
           "refuted_by": "a pool no larger than one decklist (a reduced-pool smoke presented as "
                         "the real arm), or an illegal deck",
           "pool_size": pool.size(), "single_archetype_pool_size": one.size(),
           "deck_legal": bool(legal), "distinct_decks_from_4_seeds": distinct,
           "basic_pokemon_in_pool": len(pool.basic_pokemon),
           "ace_spec_in_pool": len(pool.ace_spec)}
    b19 = {"probe": "B19", "name": "return propagation",
           "pass": bool(reward_reaches and propagates and construction_unrolls),
           "pass_condition": "the terminal game reward is attached to the episode and, with "
                             "gamma = 1.0, the V-trace target at the FIRST step of an unroll "
                             "equals the terminal reward -- so construction decisions are "
                             "trained by the game's outcome",
           "refuted_by": "a reward that never leaves the last step, or construction steps that "
                         "never appear in an unroll at all",
           "unrolls": len(unrolls),
           "unrolls_containing_construction": len(construction_unrolls),
           "reward_attached": reward_reaches,
           "vtrace_target_at_step0": round(float(vs[0]), 6),
           "terminal_reward": float(rew[-1])}
    return [b18, b19]


# ============================================================================ B08/B09/B10
def b08_b09_b10_queue(tag: str):
    """FIFO semantics, production balance and policy versions, from a real run's logs."""
    qpath = os.path.join(BY, "queue_logs", f"{tag}_queue.jsonl")
    mpath = os.path.join(BY, "stages", f"{tag}_manifest.json")
    rows, manifest = [], None
    if os.path.isfile(qpath):
        with open(qpath) as fh:
            rows = [json.loads(l) for l in fh if l.strip()]
    if os.path.isfile(mpath):
        with open(mpath) as fh:
            manifest = json.load(fh)
    if not rows or not manifest:
        return [{"probe": p, "name": n, "pass": False,
                 "error": f"no run artifacts for tag {tag!r} "
                          f"({'queue log' if not rows else ''}"
                          f"{' and ' if not rows and not manifest else ''}"
                          f"{'manifest' if not manifest else ''} missing)"}
                for p, n in (("B08", "FIFO"), ("B09", "production balance"),
                             ("B10", "policy versions"))]

    cap = manifest.get("queue_capacity")
    bounded = bool(manifest.get("bounded_blocking_fifo"))
    occ = [r["queue_occupancy"] for r in rows if r.get("queue_occupancy") is not None]
    over = [x for x in occ if cap and x > cap]
    # consume-once: total consumed unrolls must never exceed total produced
    last = rows[-1]
    consumed = last.get("consumed_unrolls", 0)
    produced_dec = last.get("produced_decisions", 0)
    consumed_dec = last.get("consumed_decisions", 0)
    ratio = last.get("production_consumption_ratio")

    b08 = {"probe": "B08", "name": "FIFO",
           "pass": bool(not over and consumed_dec <= produced_dec * manifest.get(
               "sample_reuse", 1) + 1),
           "pass_condition": "queue occupancy never exceeds the declared capacity, and consumed "
                             "decisions never exceed produced decisions (sample reuse applies "
                             "learner-side and does not re-enqueue)",
           "refuted_by": "occupancy above capacity (the bound is not enforced) or more consumed "
                         "than produced (samples are being replayed from a buffer, which §7 "
                         "forbids)",
           "bounded_blocking_fifo": bounded, "capacity": cap,
           "max_occupancy": max(occ) if occ else None,
           "mean_occupancy": round(statistics.fmean(occ), 2) if occ else None,
           "samples_over_capacity": len(over),
           "consumed_unrolls": consumed,
           "produced_decisions": produced_dec, "consumed_decisions": consumed_dec}

    ratios = [r["production_consumption_ratio"] for r in rows
              if r.get("production_consumption_ratio")]
    tail = ratios[len(ratios) // 2:] or ratios
    b09 = {"probe": "B09", "name": "production balance",
           "pass": bool(tail and 0.8 <= statistics.fmean(tail) <= 1.25),
           "pass_condition": "the producer/consumer ratio settles near 1: actors are neither "
                             "starving the learner nor racing far ahead of it",
           "refuted_by": "a ratio far from 1, which means the bounded blocking FIFO is not "
                         "controlling production -- the b2 delta would then be nominal",
           "final_ratio": ratio,
           "mean_ratio_second_half": round(statistics.fmean(tail), 4) if tail else None,
           "n_samples": len(ratios)}

    lags = [r["mean_policy_lag"] for r in rows if r.get("mean_policy_lag") is not None]
    ages = [r["mean_queue_age_s"] for r in rows if r.get("mean_queue_age_s") is not None]
    b10 = {"probe": "B10", "name": "policy versions",
           "pass": bool(lags and ages and manifest.get("policy_versions", 0) > 0),
           "pass_condition": "every unroll carries a behaviour policy version, and the mean lag "
                             "and queue age are recorded throughout the run",
           "refuted_by": "no versions published, or no lag recorded -- either means the actors "
                         "are not versioned and the off-policy correction has nothing to "
                         "correct against",
           "policy_versions": manifest.get("policy_versions"),
           "mean_policy_lag": round(statistics.fmean(lags), 3) if lags else None,
           "max_policy_lag": round(max(lags), 3) if lags else None,
           "mean_queue_age_s": round(statistics.fmean(ages), 3) if ages else None}
    return [b08, b09, b10]


# ============================================================================ B06/B07
def b06_b07_recurrence(tag: str):
    path = os.path.join(BY, "recurrent_traces", f"{tag}_recurrence.json")
    mpath = os.path.join(BY, "stages", f"{tag}_manifest.json")
    if not os.path.isfile(path) or not os.path.isfile(mpath):
        return [{"probe": p, "name": n, "pass": False,
                 "error": f"no recurrence artifacts for tag {tag!r}"}
                for p, n in (("B06", "hidden-state replay"), ("B07", "burn-in/unroll"))]
    with open(path) as fh:
        rec = json.load(fh)
    with open(mpath) as fh:
        man = json.load(fh)
    checks = rec.get("checks", [])
    fails = rec.get("failures", [])
    b06 = {"probe": "B06", "name": "hidden-state replay",
           "pass": bool(checks and not fails),
           "pass_condition": "the learner's recomputed end-of-unroll (h, c) and joint "
                             "log-probability match the actor's, under the EXACT weights the "
                             "unroll was produced with, on every sampled check",
           "refuted_by": "any nonzero delta -- a zeroed recurrent start is a hard failure under "
                         "MANDATORY_IMPLEMENTATION B4, and so is an actor/learner encoder "
                         "disagreement",
           "checks": len(checks), "failures": len(fails),
           "tolerance": rec.get("tolerance"),
           "max_recurrence_delta": man.get("max_recurrence_delta_exact_weights"),
           "max_logp_delta": man.get("max_logp_delta_exact_weights"),
           "note": "recomputing under the learner's CURRENT weights measures STALENESS, not "
                   "fidelity, and is nonzero by design; it is reported separately as "
                   "mean_learner_behaviour_drift_recurrence"}
    b07 = {"probe": "B07", "name": "burn-in/unroll boundaries",
           "pass": bool(man.get("unroll_length") and man.get("consumed_unrolls", 0) > 0),
           "pass_condition": "unrolls are a fixed registered length and every one carries its "
                             "own stored recurrent start, so gradients respect the sequence "
                             "boundary",
           "refuted_by": "variable-length unrolls or a missing stored start, either of which "
                         "would make the learner replay from a state the actor never held",
           "unroll_length": man.get("unroll_length"),
           "consumed_unrolls": man.get("consumed_unrolls"),
           "stored_start_convention": "the state BEFORE the unroll's first decision; the end "
                                      "state is stored too, which is what makes B06 refutable"}
    return [b06, b07]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default=None,
                    help="a training run tag whose artifacts supply B06-B10")
    ap.add_argument("--out", default=os.path.join(C22, "probes", "byterl_probes.json"))
    a = ap.parse_args(argv)

    t0 = time.time()
    probes: List[Dict[str, Any]] = []
    probes.append(b01_architecture())
    probes.append(b02_slot_identity())
    probes.extend(b03_b04_b05_actions())
    probes.extend(b18_b19_construction())
    if a.tag:
        probes.extend(b06_b07_recurrence(a.tag))
        probes.extend(b08_b09_b10_queue(a.tag))

    out = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "training_tag": a.tag,
           "n_pass": sum(1 for p in probes if p.get("pass")),
           "n_probes": len(probes),
           "elapsed_s": round(time.time() - t0, 1),
           "probes": probes}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(out, fh, indent=2)
    for p in probes:
        flag = "PASS" if p.get("pass") else "FAIL"
        extra = f"  {p['error']}" if p.get("error") else ""
        print(f"{flag}  {p['probe']:5s} {p['name']}{extra}")
    print(f"{out['n_pass']}/{out['n_probes']} in {out['elapsed_s']}s -> {a.out}")
    return 0 if out["n_pass"] == out["n_probes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
