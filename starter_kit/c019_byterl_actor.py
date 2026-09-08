"""c019 Branch B — CPU actor producing recurrent unrolls with behavior policy metadata.

METHOD_FIDELITY B / probe B03: every step records behavior logits and the chosen probability,
the behavior policy VERSION, the LSTM state at unroll start, reward/discount/done, the value
prediction, the opponent checkpoint identity, and seat/game/trajectory IDs. Without the behavior
probability and version there is no importance ratio, and without an importance ratio V-trace is
just TD — which is precisely how "ordinary PPO renamed ByteRL" happens.

The simulator's sequential selection contexts ARE the autoregressive decomposition (§9.2), so one
atomic decision is one unroll step and the LSTM state carries across them, resetting only at the
game boundary.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

ACTOR_VERSION = "c019.actor.v1"


@dataclass
class Step:
    feats: Dict[str, np.ndarray]
    action_index: int
    behavior_logits: np.ndarray
    behavior_logp: float
    behavior_prob: float
    value: float
    n_options: int
    context: int
    n_picked: int = 1
    reward: float = 0.0
    discount: float = 1.0
    done: float = 0.0


@dataclass
class Trajectory:
    game_id: str
    seat: int
    opponent_kind: str
    opponent_id: Optional[str]
    behavior_version: int
    steps: List[Step] = field(default_factory=list)
    result_pm_one: float = 0.0
    completed: bool = False
    statuses: Optional[List[str]] = None
    error: Optional[str] = None
    lstm_h0: Optional[np.ndarray] = None
    lstm_c0: Optional[np.ndarray] = None
    seconds: float = 0.0

    def __len__(self):
        return len(self.steps)


def play_game(model, opponent_agent, deck, seat: int, game_id: str, behavior_version: int,
              opponent_kind: str, opponent_id: Optional[str], rng_seed: int,
              greedy: bool = False) -> Trajectory:
    """One real simulator game. Records everything the learner and B03 need."""
    from kaggle_environments import make
    from cg import api as A
    from cg import c019_core as K, c019_byterl_encode as E, c019_byterl_model as M

    gen = torch.Generator().manual_seed(int(rng_seed))
    traj = Trajectory(game_id=game_id, seat=seat, opponent_kind=opponent_kind,
                      opponent_id=opponent_id, behavior_version=behavior_version)
    h0, c0 = model.initial_state(1)
    traj.lstm_h0 = h0.detach().numpy().copy()
    traj.lstm_c0 = c0.detach().numpy().copy()
    state = [(h0, c0)]
    t0 = time.time()

    def me(obs):
        sel = obs.get("select") if isinstance(obs, dict) else None
        if sel is None:
            # The no-select observation is the DECK SUBMISSION step. §9.1 freezes deck
            # construction outside the model, so the frozen list is returned -- this is the
            # PTCG analogue of ByteRL's CB stage being disabled, not a policy decision.
            return list(deck)
        try:
            o = A.to_observation_class(obs)
            f = E.encode(o)
        except Exception:  # noqa: BLE001
            return []
        b = M.to_torch(f)
        with torch.no_grad():
            logits, value, nxt = model.forward(b, state[0])
            probs = M.masked_probs(logits, b["opt_mask"])[0]
        state[0] = (nxt[0].detach(), nxt[1].detach())
        k = min(int(f["n_options"]), E.N_OPT)
        if k <= 0:
            return []
        # Multi-select contexts require minCount..maxCount options, not one. Returning a
        # single index where the engine wants several is an INVALID action, and the seat dies
        # silently -- which looks exactly like a short game in the logs.
        lo = int(sel.get("minCount") or 0)
        hi = int(sel.get("maxCount") or 1)
        n_pick = max(1, min(lo if lo > 0 else 1, hi if hi > 0 else 1, k))
        p = probs[:k]
        s = p.sum()
        if not torch.isfinite(s) or float(s) <= 0:
            picks = list(range(n_pick))
            prob = 1.0 / max(1, k)
        else:
            p = p / s
            if greedy:
                picks = torch.topk(p, n_pick).indices.tolist()
            else:
                picks = torch.multinomial(p, n_pick, replacement=False,
                                          generator=gen).tolist()
            prob = float(p[picks[0]])
        idx = int(picks[0])
        traj.steps.append(Step(
            feats=f, action_index=idx,
            behavior_logits=logits[0].detach().numpy().astype(np.float32),
            behavior_logp=float(np.log(max(prob, 1e-12))), behavior_prob=prob,
            value=float(value[0]), n_options=k, context=int(f["global"][12:30].argmax()),
            n_picked=n_pick))
        opts = K.canonical_options(sel)
        try:
            chosen = [opts[i] for i in sorted(picks) if i < len(opts)]
            if chosen:
                return K.to_select_payload(chosen, sel)
        except Exception:  # noqa: BLE001
            pass
        return sorted(set(min(i, max(0, len(opts) - 1)) for i in picks))

    agents = [me, opponent_agent] if seat == 0 else [opponent_agent, me]
    try:
        env = make("cabt")
        env.run(agents)
        last = env.steps[-1]
        st = [s.status for s in last]
        rw = [s.reward for s in last]
        traj.statuses = list(st)
        traj.completed = st == ["DONE", "DONE"]
        if traj.completed and rw[seat] is not None and rw[1 - seat] is not None:
            traj.result_pm_one = (1.0 if rw[seat] > rw[1 - seat]
                                  else (-1.0 if rw[seat] < rw[1 - seat] else 0.0))
    except Exception as e:  # noqa: BLE001
        # record WHY a game aborted; a silently-failed game is indistinguishable from a
        # short one, and 12,000 of them looked like real training data
        traj.error = f"{type(e).__name__}: {str(e)[:200]}"
        traj.completed = False
    traj.seconds = time.time() - t0

    # terminal reward on the last step; gamma = 1.0 everywhere else (registered source value)
    if traj.steps:
        for s in traj.steps:
            s.reward = 0.0
            s.discount = 1.0
            s.done = 0.0
        traj.steps[-1].reward = traj.result_pm_one if traj.completed else 0.0
        traj.steps[-1].discount = 0.0
        traj.steps[-1].done = 1.0
    return traj


def unroll_batches(trajs: List[Trajectory], T: int) -> List[Dict[str, Any]]:
    """Slice trajectories into fixed-length unrolls, padding the tail with a mask.

    Padding is masked out of every loss rather than zero-filled, so a short game cannot
    contribute phantom transitions to the gradient.
    """
    from cg import c019_byterl_encode as E
    out = []
    for tr in trajs:
        n = len(tr.steps)
        if n == 0:
            continue
        for start in range(0, n, T):
            chunk = tr.steps[start:start + T]
            L = len(chunk)
            pad = T - L
            feats = {k: np.stack([s.feats[k] for s in chunk]) for k in E.TENSOR_KEYS}
            if pad:
                feats = {k: np.concatenate([v, np.repeat(v[-1:], pad, axis=0)])
                         for k, v in feats.items()}
            mx = max(s.behavior_logits.shape[0] for s in chunk)
            bl = np.zeros((T, mx), dtype=np.float32)
            for i, s in enumerate(chunk):
                bl[i, :s.behavior_logits.shape[0]] = s.behavior_logits
            def col(fn, dtype=np.float32):
                a = np.array([fn(s) for s in chunk], dtype=dtype)
                return np.concatenate([a, np.zeros(pad, dtype=dtype)]) if pad else a
            out.append({
                "feats": feats,
                "action_index": col(lambda s: s.action_index, np.int64),
                "behavior_logp": col(lambda s: s.behavior_logp),
                "behavior_prob": col(lambda s: s.behavior_prob),
                "behavior_logits": bl,
                "value": col(lambda s: s.value),
                "reward": col(lambda s: s.reward),
                "discount": col(lambda s: s.discount),
                "done": col(lambda s: s.done),
                "n_options": col(lambda s: s.n_options, np.int64),
                "mask": np.concatenate([np.ones(L, np.float32), np.zeros(pad, np.float32)]),
                "behavior_version": tr.behavior_version,
                "game_id": tr.game_id, "seat": tr.seat,
                "opponent_kind": tr.opponent_kind, "opponent_id": tr.opponent_id,
                "is_unroll_start": start == 0,
                "result_pm_one": tr.result_pm_one,
            })
    return out
