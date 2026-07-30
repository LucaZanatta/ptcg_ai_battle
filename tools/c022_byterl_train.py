"""c022 B3/B7 — asynchronous actors, a bounded blocking FIFO, and one learner.

`MANDATORY_IMPLEMENTATION B3` and `PROBE_MATRIX B08-B10` require an actual asynchronous
actor-learner system, not a synchronous gather. c021 collected whole iterations through per-chunk
worker processes and a drain; there was no queue to block on, no policy version on an unroll, and
no production/consumption ratio to control. That is why `CONTRACT.md §3.4` says c021 lacked "the
published b2 blocking FIFO actor-learner balance".

Stage semantics are `FIDELITY_RULES §4`, and adjacent stages differ ONLY by the published change:

    BR0    end-to-end baseline: gamma 0.99, one-sided V-trace, unbounded queue
    BR1    BR0 with gamma = 1.0                                    <- gamma only
    BR1_5  BR1 with published random initial construction choices  <- construction init only
    BR2    BR1_5 with a bounded blocking FIFO and balanced production/consumption  <- queue only
    BR3    BR2 with two-sided clipped V-trace and a PPO-style clipped objective <- objective only

`tests/test_c022_stage_ladder.py` asserts each adjacent pair differs in exactly the named fields,
so an extra change cannot ride along unnoticed.

**Why BR0/BR1/BR1_5 still use a queue.** The b2 delta is the queue being BOUNDED and BLOCKING,
not the queue existing. The lower rungs use the same machinery with an effectively unbounded
queue and no production throttle, so the rung difference is the control policy rather than the
architecture — otherwise "B2 improves things" would be confounded with "B2 has an actor-learner
split at all".
"""

from __future__ import annotations

import argparse
import collections
import io
import json
import math
import multiprocessing as mp
import os
import queue as pyqueue
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C22 = os.path.join(_REPO, "contracts",
                   "c022_mcgs_multideterminization_and_faithful_byterl_reproduction", "results")
BY = os.path.join(C22, "byterl")

# ---------------------------------------------------------------------------- stage ladder
STAGES: Dict[str, Dict[str, Any]] = {
    "BR0":   {"gamma": 0.99, "random_initial_construction": False,
              "bounded_blocking_fifo": False, "two_sided_and_ppo": False},
    "BR1":   {"gamma": 1.00, "random_initial_construction": False,
              "bounded_blocking_fifo": False, "two_sided_and_ppo": False},
    "BR1_5": {"gamma": 1.00, "random_initial_construction": True,
              "bounded_blocking_fifo": False, "two_sided_and_ppo": False},
    "BR2":   {"gamma": 1.00, "random_initial_construction": True,
              "bounded_blocking_fifo": True,  "two_sided_and_ppo": False},
    "BR3":   {"gamma": 1.00, "random_initial_construction": True,
              "bounded_blocking_fifo": True,  "two_sided_and_ppo": True},
}
STAGE_ORDER = ["BR0", "BR1", "BR1_5", "BR2", "BR3"]
STAGE_DELTA = {
    ("BR0", "BR1"): {"gamma"},
    ("BR1", "BR1_5"): {"random_initial_construction"},
    ("BR1_5", "BR2"): {"bounded_blocking_fifo"},
    ("BR2", "BR3"): {"two_sided_and_ppo"},
}

from cg.c022_byterl_actor import RANDOM_INITIAL_CONSTRUCTION_STEPS as ACT_RANDOM_STEPS

UNBOUNDED_QUEUE = 1 << 16          # "effectively unbounded" for the pre-b2 rungs
OPPONENTS = ["dragapult", "mega_lucario", "iono", "mega_abomasnow"]


# ============================================================================ actor process
def actor_loop(actor_id: int, cfg: Dict[str, Any], shared, q, metrics_q, stop):
    """One asynchronous actor: pull weights, play an episode, push its unrolls."""
    sys.path.insert(0, _REPO)
    import torch
    torch.set_num_threads(1)
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce
    from cg import c021_byterl_deck as DK
    from cg import c022_byterl_actor as ACT
    from cg import c022_byterl_encode as EN
    from cg import c022_byterl_model as M

    rng = np.random.default_rng(cfg["seed"] * 7919 + actor_id)
    pool = DK.CardPool.from_archetypes()
    dims = EN.dims()
    net = M.fresh(dims["global_dim"], dims["slot_dim"], dims["option_dim"], pool.size(),
                  n_cards=dims["n_cards"], seed=cfg["seed"])
    net.eval()
    weights = ACT.VersionedWeights(net)
    fixed = None if cfg["learn_construction"] else DK.greedy_reference_deck(pool)

    blocked_s = 0.0
    episodes = 0
    pushed = 0
    while not stop.is_set():
        weights.pull(shared)
        runner = ACT.EpisodeRunner(
            net, pool, rng, cfg["learn_construction"], fixed,
            unroll_length=cfg["unroll_length"], temperature=cfg["temperature"],
            random_initial_construction=cfg["random_initial_construction"])
        try:
            deck, deck_legal = runner.build_deck()
            if not deck_legal:
                # Never silently repaired: an illegal deck is a real signal and the episode is
                # dropped with the reason recorded (B18/B19 evidence).
                metrics_q.put({"actor": actor_id, "illegal_deck": 1})
                continue
            opp_name = OPPONENTS[int(rng.integers(len(OPPONENTS)))]
            opp = T.make_fresh(opp_name, ce.SOURCES)
            seat = int(rng.integers(2))

            def me(o):
                return runner.act(o)

            def them(o):
                return opp(o)

            agents = [me, them] if seat == 0 else [them, me]
            env = make("cabt")
            env.run(agents)
            last = env.steps[-1]
            score = 0.0
            completed = False
            if [s.status for s in last] == ["DONE", "DONE"]:
                rw = [s.reward for s in last]
                if rw[seat] is not None:
                    completed = True
                    score = (1.0 if rw[seat] > rw[1 - seat]
                             else (0.5 if rw[seat] == rw[1 - seat] else 0.0))
        except Exception as e:  # noqa: BLE001
            metrics_q.put({"actor": actor_id, "error": f"{type(e).__name__}: {e}"[:160]})
            continue

        episodes += 1
        unrolls = runner.finish(score, f"a{actor_id}:e{episodes}", weights.version)
        for u in unrolls:
            t0 = time.time()
            while not stop.is_set():
                try:
                    # BLOCKING put with a timeout, so a stop signal is still honoured. The
                    # timeout is not a fallback that drops the sample -- it retries -- so the
                    # producer really does block when the queue is full, which is the b2
                    # semantics. Time spent blocked is measured and reported (B09).
                    q.put(_pack(u), timeout=1.0)
                    pushed += 1
                    break
                except pyqueue.Full:
                    continue
            blocked_s += time.time() - t0
        metrics_q.put({"actor": actor_id, "episode": episodes, "completed": completed,
                       "score": score, "opponent": opp_name,
                       "n_construction": runner.n_construction, "n_battle": runner.n_battle,
                       "unrolls": len(unrolls), "policy_version": weights.version,
                       "blocked_s": round(blocked_s, 3), "pulls": weights.pulls,
                       "illegal_sequences": runner.illegal_sequences,
                       "option_truncations": runner.option_truncations,
                       "max_options_seen": runner.max_options_seen,
                       "random_initial_choices": runner.random_initial_choices,
                       "deck_legal": bool(deck_legal), "deck": list(deck)})


def _pack(u) -> Dict[str, Any]:
    """Serialize an unroll for the queue. Arrays stay as arrays; torch objects do not cross."""
    return {
        # `policy_logp` and `uniform_behaviour` (D19) must cross the queue. A pack that drops
        # them silently falls back to `behaviour_logp` in the B06 check, which is the pre-D19
        # comparison and fails on every B1.5 uniform step.
        "steps": [{"stage": s.stage, "enc": s.enc, "seq": s.seq,
                   "behaviour_logp": s.behaviour_logp, "value": s.value,
                   "reward": s.reward, "min_count": s.min_count, "max_count": s.max_count,
                   "policy_logp": (s.behaviour_logp if s.policy_logp is None
                                   else s.policy_logp),
                   "uniform_behaviour": bool(s.uniform_behaviour)}
                  for s in u.steps],
        "h0": u.h0, "c0": u.c0, "h_end": u.h_end, "c_end": u.c_end,
        "policy_version": u.policy_version,
        "episode_id": u.episode_id, "unroll_index": u.unroll_index,
        "bootstrap_value": u.bootstrap_value, "is_episode_end": u.is_episode_end,
        "created_at": u.created_at,
    }


# ============================================================================ learner
def replay_unroll(net, pack, cfg, check_recurrence: bool = False):
    """Recompute the unroll under the CURRENT policy, from the actor's stored `(h0, c0)`.

    Returns per-step target log-probabilities, entropies and values, plus the recurrence check
    `PROBE_MATRIX B06` requires. The check compares the learner's recomputed hidden state at the
    unroll start against the actor's stored one; they must agree, because the learner is handed
    the stored state and must not be silently zeroing it (`B4`: "zeroed recurrent starts" is a
    hard failure).
    """
    import torch
    from cg import c022_byterl_action as AC
    from cg import c022_byterl_encode as EN

    steps = pack["steps"]
    h0 = torch.from_numpy(np.ascontiguousarray(pack["h0"]))
    c0 = torch.from_numpy(np.ascontiguousarray(pack["c0"]))
    state = (h0, c0)
    battle = AC.BattleActionHead(net)
    construction = AC.ConstructionActionHead(net)

    tlogp, ents, vals = [], [], []
    recurrence_delta = None
    logp_delta = None
    for i, s in enumerate(steps):
        tt = EN.to_torch(s["enc"])
        h, state = net.step(EN.obs_parts(tt), state)
        if s["stage"] == EN.STAGE_CONSTRUCTION:
            lp, ent = construction.logp(h, tt["pool_mask"], s["seq"])
        else:
            n = int(s["enc"]["n_options"])
            legal = tt["opt_mask"].clone()
            legal[:, n:] = 0.0
            lp, ent = battle.logp(h, tt["opt"], tt["option_cards"], legal, s["seq"],
                                  int(s["min_count"]), int(s["max_count"]))
        tlogp.append(lp)
        ents.append(ent)
        vals.append(net.value(h, tt["stage"]).squeeze(0))

    if check_recurrence:
        # The learner's RECOMPUTED end-of-unroll state against the state the actor actually held
        # after the same decisions, and the recomputed joint log-probability against the stored
        # behaviour log-probability.
        #
        # WHAT THIS NUMBER MEANS DEPENDS ENTIRELY ON THE WEIGHTS. Recomputing with the learner's
        # CURRENT weights measures how far the learner has moved from the behaviour policy — a
        # staleness diagnostic, not a fidelity check. It is nonzero by design and would be
        # nonzero even in a perfect implementation. The exact-weights fidelity check is
        # `recurrence_fidelity_check` below, which reloads the behaviour version first; probe
        # B06 reads THAT one.
        he = torch.from_numpy(np.ascontiguousarray(pack["h_end"]))
        ce_ = torch.from_numpy(np.ascontiguousarray(pack["c_end"]))
        recurrence_delta = float(max(
            torch.abs(state[0] - he).max().item(),
            torch.abs(state[1] - ce_).max().item()))
        # AGAINST pi, NOT mu (defect D19). The question this check asks is whether the learner
        # rescores the action the way the actor's network did at identical weights. On a B1.5
        # uniform construction step mu is -log(n_legal) by design, so comparing against mu would
        # fail on a correct implementation -- and did, killing the ladder at the first check.
        # `policy_logp` falls back to `behaviour_logp` for packs written before D19, where the
        # two were the same thing.
        pol = torch.tensor([float(s.get("policy_logp", s["behaviour_logp"])) for s in steps],
                           dtype=torch.float32)
        logp_delta = float(torch.abs(torch.stack(tlogp).detach() - pol).max().item())
    return (torch.stack(tlogp), torch.stack(ents), torch.stack(vals),
            recurrence_delta, logp_delta)


def recurrence_fidelity_check(scratch_net, blob: bytes, pack, cfg) -> Dict[str, float]:
    """B06 proper — replay an unroll under the EXACT weights that produced it.

    `MANDATORY_IMPLEMENTATION B3`: "Recompute recurrent outputs independently during learner
    replay and assert agreement before optimization." Agreement is only defined at identical
    weights, so this reloads the behaviour policy version into a scratch network first.

    Two deltas must both be ~0:

      * `recurrence_delta` — the recomputed end-of-unroll `(h, c)` against the actor's observed
        end state. Catches a zeroed start, a shifted unroll boundary, and any actor/learner
        disagreement in the encoder.
      * `logp_delta` — the recomputed joint log-probability against the stored value of **pi**,
        the acting network's own score for the same action. Catches an autoregressive
        factorization that differs between sampling and scoring, which would silently bias every
        importance ratio downstream.
      * `behaviour_delta` — the check that D19 must not be allowed to weaken. Comparing replay
        against pi removes the old implicit guarantee that `behaviour_logp` was the network's
        value, so `mu` is now verified directly and from stored data alone: on a uniform B1.5
        step it must equal `-log(n_legal)` exactly, and on every other step it must equal `pi`.
        The result is a STRICTLY STRONGER assertion than before, because it now holds separately
        for the two kinds of step instead of collapsing them.

    Neither is checkable from the running metrics, because between two publications the learner's
    weights move while the version number does not — so "zero policy lag" does not mean "identical
    weights". Measuring it that way reported a 0.0997 log-probability delta that was pure weight
    drift and would have been read as a defect.
    """
    import torch
    scratch_net.load_state_dict(
        torch.load(io.BytesIO(blob), map_location="cpu", weights_only=False))
    scratch_net.eval()
    with torch.no_grad():
        _tl, _e, _v, rdelta, ldelta = replay_unroll(scratch_net, pack, cfg,
                                                    check_recurrence=True)
    bdelta, n_uniform = behaviour_consistency(pack)
    return {"recurrence_delta": rdelta, "logp_delta": ldelta,
            "behaviour_delta": bdelta, "uniform_steps": n_uniform,
            "policy_version": int(pack["policy_version"]),
            "steps": len(pack["steps"])}


def behaviour_consistency(pack) -> Tuple[float, int]:
    """Is `behaviour_logp` the distribution that actually chose the action? (D19)

    Checkable from stored data alone, with no network involved:

      * a uniform B1.5 step must carry `-log(n_legal)`, from the mask the actor drew against;
      * any other step must carry exactly the network's `pi`.

    A step claiming to be uniform while recording the policy's log-probability is the precise
    corruption D17 was written to prevent and D19's separation of mu from pi could silently
    reintroduce, so it is asserted every time the fidelity check runs rather than in a unit test
    alone.
    """
    worst, n_uniform = 0.0, 0
    for s in pack["steps"]:
        mu = float(s["behaviour_logp"])
        if s.get("uniform_behaviour"):
            n_uniform += 1
            toks = s["seq"].get("tokens") or []
            if not toks:
                continue
            n_legal = int(toks[0].get("n_legal") or 0)
            if n_legal <= 0:
                continue
            worst = max(worst, abs(mu - (-math.log(n_legal))))
        else:
            worst = max(worst, abs(mu - float(s.get("policy_logp", mu))))
    return worst, n_uniform


def learner_update(net, opt, batch, cfg, stats):
    """One optimizer step over a batch of unrolls, with published sample reuse.

    `FIDELITY_RULES §4` gives `sample reuse = 2`. `MANDATORY_IMPLEMENTATION B3` says FIFO samples
    are consumed once "unless published sample reuse explicitly applies learner-side" — it does,
    so each batch is used for exactly `sample_reuse` optimizer passes and then dropped. It is
    never returned to the queue, which would be a replay buffer and is a hard failure (`§7`).
    """
    import torch
    from cg import c022_byterl_learn as L

    feats = STAGES[cfg["stage"]]
    lc = L.LossConfig(
        gamma=feats["gamma"],
        two_sided=feats["two_sided_and_ppo"],
        ppo_clip=feats["two_sided_and_ppo"],
        value_coef=L.VALUE_COEF, ppo_coef=L.PPO_COEF, upgo_coef=L.UPGO_COEF,
        entropy_coef=L.ENTROPY_COEF, max_grad_norm=cfg["max_grad_norm"])

    n_updates = 0
    for reuse_pass in range(int(cfg["sample_reuse"])):
        for pack in batch:
            if not pack["steps"]:
                continue
            tl, ents, vals, rdelta, ldelta = replay_unroll(
                net, pack, cfg, check_recurrence=(reuse_pass == 0))
            # DIAGNOSTICS, not fidelity checks: recomputed under the learner's CURRENT weights,
            # so both are nonzero by design and measure how far the learner has drifted from the
            # behaviour policy. The fidelity check is `recurrence_fidelity_check`, which reloads
            # the behaviour version first and is asserted below.
            if rdelta is not None:
                stats["drift_recurrence"].append(rdelta)
            if ldelta is not None:
                stats["drift_logp"].append(ldelta)
            Tn = len(pack["steps"])
            beh = torch.tensor([s["behaviour_logp"] for s in pack["steps"]],
                               dtype=torch.float32)
            rew = torch.tensor([s["reward"] for s in pack["steps"]], dtype=torch.float32)
            disc = torch.full((Tn,), float(feats["gamma"]), dtype=torch.float32)
            boot = torch.tensor(float(pack["bootstrap_value"]))
            total, st = L.byterl_losses(tl, beh, ents, vals, rew, boot, disc, lc)
            opt.zero_grad(set_to_none=True)
            total.backward()
            gn = L.clip_grads(net, cfg["max_grad_norm"])
            opt.step()
            n_updates += 1
            for k, v in st.items():
                stats[k].append(v)
            stats["grad_norm"].append(gn)
            stats["policy_lag"].append(int(cfg["_version"]) - int(pack["policy_version"]))
            stats["queue_age_s"].append(time.time() - float(pack["created_at"]))
    return n_updates


def publish(net, shared, version: int, history: Optional[Dict[int, bytes]] = None,
            keep: int = 8):
    """Publish immutable versioned weights. Bytes, not tensors: actors cannot alias the learner.

    `history` keeps the last `keep` published blobs so `recurrence_fidelity_check` can reload the
    exact weights an unroll was produced under. Without it there is no way to assert agreement,
    because the learner's live weights have already moved.
    """
    import torch
    buf = io.BytesIO()
    torch.save({k: v.detach().cpu() for k, v in net.state_dict().items()}, buf)
    blob = buf.getvalue()
    # ONE key, written atomically. Writing `blob` and `version` as two keys lets an actor read
    # version N and then fetch version N+1's blob, labelling every unroll it produces with a
    # policy version that did not produce it. See VersionedWeights.pull.
    shared["published"] = (int(version), blob)
    if history is not None:
        history[int(version)] = blob
        for v in sorted(history)[:-keep]:
            history.pop(v, None)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="BR3", choices=STAGE_ORDER)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--learn-construction", type=int, default=0,
                    help="0 = FIXED_DECK_BATTLE_CONTROL, 1 = END_TO_END")
    ap.add_argument("--actors", type=int, default=8)
    ap.add_argument("--queue-size", type=int, default=64)
    ap.add_argument("--batch-unrolls", type=int, default=8)
    ap.add_argument("--unroll-length", type=int, default=32)
    ap.add_argument("--sample-reuse", type=int, default=2)
    ap.add_argument("--lr", type=float, default=7e-5)
    ap.add_argument("--entropy-coef", type=float, default=0.01)
    ap.add_argument("--max-grad-norm", type=float, default=40.0)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--target-decisions", type=int, default=0,
                    help="stop when this many environment decisions have been consumed")
    ap.add_argument("--deadline-seconds", type=float, default=0.0)
    ap.add_argument("--publish-every", type=int, default=4, help="updates between publications")
    ap.add_argument("--log-every", type=int, default=25)
    ap.add_argument("--checkpoint-every", type=int, default=200)
    ap.add_argument("--recurrence-check-every", type=int, default=20,
                    help="batches between exact-weights B06 recurrence assertions; 0 disables")
    ap.add_argument("--recurrence-tolerance", type=float, default=1e-4)
    ap.add_argument("--recurrence-strict", type=int, default=1,
                    help="1 = a replay mismatch aborts the run, as TRAINING_AND_EVALUATION §4 "
                         "requires ('stop immediately for ... recurrent replay mismatch')")
    ap.add_argument("--seed", type=int, default=4242)
    ap.add_argument("--out", default=BY)
    a = ap.parse_args(argv)

    import torch
    torch.set_num_threads(max(1, (os.cpu_count() or 8) // 4))
    from cg import c021_byterl_deck as DK
    from cg import c022_byterl_encode as EN
    from cg import c022_byterl_model as M

    feats = STAGES[a.stage]
    cfg = {
        "stage": a.stage, "seed": a.seed,
        "learn_construction": bool(a.learn_construction),
        "unroll_length": a.unroll_length, "temperature": a.temperature,
        "sample_reuse": a.sample_reuse, "max_grad_norm": a.max_grad_norm,
        "_version": 0,
        # THE B1.5 DELTA. Until this line existed the flag was declared in STAGES, asserted by
        # the stage-delta test, and read by nothing -- so BR1 and BR1_5 were the same system and
        # the rung was a no-op. The stage table said they differed; the code did not.
        "random_initial_construction": bool(feats["random_initial_construction"]),
    }
    qsize = a.queue_size if feats["bounded_blocking_fifo"] else UNBOUNDED_QUEUE

    ctx = mp.get_context("spawn")
    manager = ctx.Manager()
    shared = manager.dict()
    q = ctx.Queue(maxsize=qsize)
    metrics_q = ctx.Queue()
    stop = ctx.Event()

    pool = DK.CardPool.from_archetypes()
    dims = EN.dims()
    net = M.fresh(dims["global_dim"], dims["slot_dim"], dims["option_dim"], pool.size(),
                  n_cards=dims["n_cards"], seed=a.seed)
    opt = torch.optim.Adam(net.parameters(), lr=a.lr)
    # A scratch network for the exact-weights recurrence check. Separate object, so loading a
    # historical version into it cannot disturb the live learner.
    scratch = M.fresh(dims["global_dim"], dims["slot_dim"], dims["option_dim"], pool.size(),
                      n_cards=dims["n_cards"], seed=a.seed)
    published_blobs: Dict[int, bytes] = {}
    publish(net, shared, 0, published_blobs)

    procs = [ctx.Process(target=actor_loop, args=(i, cfg, shared, q, metrics_q, stop))
             for i in range(a.actors)]
    for p in procs:
        p.start()

    os.makedirs(a.out, exist_ok=True)
    for sub in ("queue_logs", "checkpoints", "stages", "action_traces", "recurrent_traces"):
        os.makedirs(os.path.join(a.out, sub), exist_ok=True)
    qlog = open(os.path.join(a.out, "queue_logs", f"{a.tag}_queue.jsonl"), "w")
    ep_log = open(os.path.join(a.out, f"{a.tag}_episodes.jsonl"), "w")

    stats = collections.defaultdict(list)
    curve: List[Dict[str, Any]] = []
    consumed_unrolls = 0
    consumed_decisions = 0
    produced_episodes = 0
    produced_decisions = 0
    updates = 0
    version = 0
    batches = 0
    recurrence_checks: List[Dict[str, float]] = []
    recurrence_failures: List[Dict[str, float]] = []
    illegal_decks = 0
    actor_errors = 0
    random_initial_choices = 0
    wins, scored = 0.0, 0
    t0 = time.time()
    deadline = t0 + a.deadline_seconds if a.deadline_seconds > 0 else None

    try:
        while True:
            if deadline and time.time() > deadline:
                break
            if a.target_decisions and consumed_decisions >= a.target_decisions:
                break

            # ---- drain actor metrics (never blocks the learner)
            while True:
                try:
                    m = metrics_q.get_nowait()
                except Exception:  # noqa: BLE001
                    break
                if m.get("illegal_deck"):
                    illegal_decks += 1
                    continue
                if m.get("error"):
                    actor_errors += 1
                    continue
                random_initial_choices += int(m.get("random_initial_choices", 0) or 0)
                produced_episodes += 1
                produced_decisions += int(m.get("n_construction", 0)) + int(
                    m.get("n_battle", 0))
                if m.get("completed"):
                    wins += float(m.get("score") or 0.0)
                    scored += 1
                ep_log.write(json.dumps({k: m[k] for k in m if k != "deck"}) + "\n")

            # ---- take a batch off the FIFO
            batch = []
            while len(batch) < a.batch_unrolls:
                try:
                    batch.append(q.get(timeout=5.0))
                except Exception:  # noqa: BLE001
                    break
            if not batch:
                if all(not p.is_alive() for p in procs):
                    break
                continue

            occupancy = q.qsize() if hasattr(q, "qsize") else -1
            cfg["_version"] = version

            # B06: assert recurrent agreement BEFORE optimizing on this batch. Checked on a
            # sampled unroll whose behaviour version is still in the published history, under
            # those exact weights.
            if a.recurrence_check_every and (batches % a.recurrence_check_every == 0):
                cand = next((b for b in batch if int(b["policy_version"]) in published_blobs),
                            None)
                if cand is not None:
                    chk = recurrence_fidelity_check(
                        scratch, published_blobs[int(cand["policy_version"])], cand, cfg)
                    recurrence_checks.append(chk)
                    if (chk["recurrence_delta"] > a.recurrence_tolerance
                            or chk["logp_delta"] > a.recurrence_tolerance
                            or chk["behaviour_delta"] > a.recurrence_tolerance):
                        recurrence_failures.append(chk)
                        if a.recurrence_strict:
                            raise RuntimeError(
                                f"B06 recurrent replay mismatch: {chk} "
                                f"(tolerance {a.recurrence_tolerance})")
            batches += 1
            n = learner_update(net, opt, batch, cfg, stats)
            updates += n
            consumed_unrolls += len(batch)
            consumed_decisions += sum(len(b["steps"]) for b in batch)

            if updates // max(1, a.publish_every) > version:
                version += 1
                publish(net, shared, version, published_blobs)

            qlog.write(json.dumps({
                "t": round(time.time() - t0, 2),
                "queue_occupancy": occupancy, "queue_capacity": qsize,
                "batch_unrolls": len(batch),
                "consumed_unrolls": consumed_unrolls,
                "consumed_decisions": consumed_decisions,
                "produced_episodes": produced_episodes,
                "produced_decisions": produced_decisions,
                "production_consumption_ratio": round(
                    produced_decisions / max(1, consumed_decisions), 4),
                "policy_version": version, "updates": updates,
                "mean_policy_lag": round(float(np.mean(stats["policy_lag"][-256:])), 3)
                if stats["policy_lag"] else None,
                "mean_queue_age_s": round(float(np.mean(stats["queue_age_s"][-256:])), 3)
                if stats["queue_age_s"] else None,
            }) + "\n")

            if updates and updates % a.log_every < n:
                row = {"updates": updates, "version": version,
                       "consumed_decisions": consumed_decisions,
                       "produced_decisions": produced_decisions,
                       "episodes": produced_episodes,
                       "win_rate": round(wins / scored, 4) if scored else None,
                       "queue_occupancy": occupancy,
                       "illegal_decks": illegal_decks, "actor_errors": actor_errors,
        "random_initial_construction": bool(feats["random_initial_construction"]),
        "random_initial_choices": random_initial_choices,
        "random_initial_construction_steps": (
            ACT_RANDOM_STEPS if feats["random_initial_construction"] else 0),
                       "elapsed_s": round(time.time() - t0, 1)}
                for k in ("pg_loss", "upgo_loss", "value_loss", "entropy", "total",
                          "rho_mean", "rho_clipped_upper_frac", "rho_clipped_lower_frac",
                          "ppo_clip_frac", "vs_mean", "grad_norm", "policy_lag",
                          "queue_age_s", "drift_recurrence", "drift_logp"):
                    if stats[k]:
                        row[k] = round(float(np.mean(stats[k][-512:])), 6)
                curve.append(row)
                print(json.dumps(row), flush=True)

            if a.checkpoint_every and updates % a.checkpoint_every < n:
                torch.save(net.state_dict(),
                           os.path.join(a.out, "checkpoints",
                                        f"{a.tag}_u{updates:06d}.pt"))
    finally:
        stop.set()
        for p in procs:
            p.join(timeout=10)
            if p.is_alive():
                p.terminate()
        qlog.close()
        ep_log.close()

    torch.save(net.state_dict(), os.path.join(a.out, "checkpoints", f"{a.tag}_final.pt"))
    manifest = {
        "tag": a.tag, "stage": a.stage, "stage_features": feats,
        "arm": "END_TO_END_DECK_CONSTRUCTION_AND_BATTLE" if a.learn_construction
               else "FIXED_DECK_BATTLE_CONTROL",
        "fresh_random_weights": True,
        "params": M.count_parameters(net),
        "lstm_hidden": net.lstm_hidden,
        "actors": a.actors, "queue_capacity": qsize,
        "bounded_blocking_fifo": feats["bounded_blocking_fifo"],
        "unroll_length": a.unroll_length, "batch_unrolls": a.batch_unrolls,
        "sample_reuse": a.sample_reuse, "lr": a.lr,
        "entropy_coef": a.entropy_coef, "gamma": feats["gamma"],
        "two_sided_and_ppo": feats["two_sided_and_ppo"],
        "updates": updates, "policy_versions": version,
        "consumed_unrolls": consumed_unrolls,
        "consumed_decisions": consumed_decisions,
        "produced_decisions": produced_decisions,
        "produced_episodes": produced_episodes,
        "production_consumption_ratio": round(
            produced_decisions / max(1, consumed_decisions), 4),
        "illegal_decks": illegal_decks, "actor_errors": actor_errors,
        "random_initial_construction": bool(feats["random_initial_construction"]),
        "random_initial_choices": random_initial_choices,
        "random_initial_construction_steps": (
            ACT_RANDOM_STEPS if feats["random_initial_construction"] else 0),
        "final_win_rate": round(wins / scored, 4) if scored else None,
        "recurrence_checks": len(recurrence_checks),
        "recurrence_check_failures": len(recurrence_failures),
        "recurrence_tolerance": a.recurrence_tolerance,
        "max_recurrence_delta_exact_weights": round(
            max((c["recurrence_delta"] for c in recurrence_checks), default=0.0), 9)
        if recurrence_checks else None,
        "max_logp_delta_exact_weights": round(
            max((c["logp_delta"] for c in recurrence_checks), default=0.0), 9)
        if recurrence_checks else None,
        # D19: mu verified against what it claims to be, separately from pi.
        "max_behaviour_delta": round(
            max((c["behaviour_delta"] for c in recurrence_checks), default=0.0), 9)
        if recurrence_checks else None,
        "uniform_behaviour_steps_seen_in_checks": sum(
            c.get("uniform_steps", 0) for c in recurrence_checks),
        "mean_learner_behaviour_drift_recurrence": round(
            float(np.mean(stats["drift_recurrence"])), 6) if stats["drift_recurrence"] else None,
        "mean_learner_behaviour_drift_logp": round(
            float(np.mean(stats["drift_logp"])), 6) if stats["drift_logp"] else None,
        "wall_clock_s": round(time.time() - t0, 1),
        "seed": a.seed,
    }
    with open(os.path.join(a.out, "stages", f"{a.tag}_manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    with open(os.path.join(a.out, "stages", f"{a.tag}_curve.json"), "w") as fh:
        json.dump(curve, fh, indent=2)
    with open(os.path.join(a.out, "recurrent_traces", f"{a.tag}_recurrence.json"), "w") as fh:
        json.dump({"tolerance": a.recurrence_tolerance,
                   "checks": recurrence_checks, "failures": recurrence_failures}, fh, indent=2)
    print(json.dumps({k: manifest[k] for k in
                      ("tag", "stage", "arm", "updates", "consumed_decisions",
                       "produced_decisions", "production_consumption_ratio",
                       "final_win_rate", "recurrence_checks", "recurrence_check_failures",
                       "max_recurrence_delta_exact_weights", "max_logp_delta_exact_weights",
                       "mean_learner_behaviour_drift_recurrence",
                       "wall_clock_s")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
