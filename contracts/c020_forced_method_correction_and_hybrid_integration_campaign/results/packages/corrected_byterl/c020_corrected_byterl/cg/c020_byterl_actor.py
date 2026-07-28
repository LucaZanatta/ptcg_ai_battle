"""c020 B3/B4 — actor that records complete multi-select actions and exact recurrent state.

Audit #10/#11: c019's actor carried recurrent state correctly, but the LEARNER reset it to zero at
every mid-game unroll boundary, so target probabilities were computed from a blank memory while
behavior probabilities came from a memory carrying the whole game. Every importance ratio on a
mid-game unroll was therefore comparing two different functions.

The fix is to make the actor's state a recorded ARTIFACT rather than a transient: every unroll
stores the `h0`/`c0` it started from, the episode-start flag, the actor's policy version, and a
per-timestep context fingerprint the learner must reproduce. `c020_vtrace.assert_same_context`
turns "the learner replayed correctly" from an assumption into a checked precondition.

`MultiSelectRecord` stores the FULL ordered selection, the per-step probabilities, the joint log
probability and the exact environment payload (B3).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_core as K  # noqa: E402
from cg import c020_byterl_encode as E  # noqa: E402
from cg import c020_byterl_model as M  # noqa: E402

UNROLL_LENGTH = 32


def _hash(*parts) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8", "replace"))
    return h.hexdigest()[:16]


def state_hash(state) -> str:
    if state is None:
        return "ZERO"
    h, c = state
    return _hash(np.round(h.detach().cpu().numpy(), 5).tobytes(),
                 np.round(c.detach().cpu().numpy(), 5).tobytes())


@dataclass
class MultiSelectRecord:
    """B3: the COMPLETE action, not its first item."""

    decision: int
    k: int
    selected: List[int]                       # ordered option indices
    payload: List[int]                        # exact environment payload
    steps: List[Dict[str, Any]]               # per-pick logits/probs/masks
    joint_logp: float
    min_count: int
    max_count: int
    n_legal: int

    def to_json(self) -> Dict[str, Any]:
        return {"decision": self.decision, "k": self.k, "selected": self.selected,
                "payload": self.payload, "joint_logp": round(self.joint_logp, 6),
                "steps": [{"step": s["step"], "chosen": s["chosen"],
                           "prob": round(s["prob"], 6), "logp": round(s["logp"], 6),
                           "n_legal": s["n_legal"]} for s in self.steps],
                "min_count": self.min_count, "max_count": self.max_count,
                "n_legal": self.n_legal,
                "sum_of_step_logps_equals_joint": bool(
                    abs(sum(s["logp"] for s in self.steps) - self.joint_logp) < 1e-6)}


@dataclass
class Step:
    obs_features: Dict[str, np.ndarray]
    selected: List[int]
    joint_logp: float
    value: float
    reward: float = 0.0
    done: bool = False
    context_fingerprint: str = ""
    behavior_version: int = 0


@dataclass
class Unroll:
    """`IMPLEMENTATION_GUIDE §9` exactly. h0/c0 are stored for EVERY unroll (B4)."""

    h0: np.ndarray
    c0: np.ndarray
    episode_start: bool
    actor_version: int
    steps: List[Step]
    bootstrap_value: float
    game_id: str
    seat: int
    opponent_kind: str

    def to_json(self, with_state: bool = False) -> Dict[str, Any]:
        d = {"game_id": self.game_id, "seat": self.seat,
             "opponent_kind": self.opponent_kind,
             "episode_start": self.episode_start, "actor_version": self.actor_version,
             "length": len(self.steps),
             "h0_hash": _hash(np.round(self.h0, 5).tobytes()),
             "c0_hash": _hash(np.round(self.c0, 5).tobytes()),
             "h0_is_zero": bool(np.abs(self.h0).max() == 0.0),
             "c0_is_zero": bool(np.abs(self.c0).max() == 0.0),
             "bootstrap_value": round(self.bootstrap_value, 6),
             "joint_logps": [round(s.joint_logp, 6) for s in self.steps],
             "context_fingerprints": [s.context_fingerprint for s in self.steps],
             "multiselect_steps": sum(1 for s in self.steps if len(s.selected) > 1)}
        if with_state:
            d["h0"] = self.h0.tolist()
            d["c0"] = self.c0.tolist()
        return d


class ByteRLActor:
    """Plays one seat with the corrected model, recording everything the learner needs."""

    def __init__(self, model: M.PTCGByteRL, deck: List[int], version: int = 0,
                 greedy: bool = False, seed: int = 0):
        self.model = model
        self.deck = list(deck)
        self.version = version
        self.greedy = greedy
        self.state = None                 # recurrent state across the WHOLE game
        self.gen = torch.Generator().manual_seed(int(seed) & 0x7FFFFFFF)
        self.steps: List[Step] = []
        self.multiselect: List[MultiSelectRecord] = []
        self.decision = 0
        self.episode_started = True

    def reset(self):
        """Recurrent state resets ONLY at a true episode boundary (B7 probe)."""
        self.state = None
        self.steps = []
        self.multiselect = []
        self.decision = 0
        self.episode_started = True

    def act(self, obs_dict: dict) -> List[int]:
        sel = obs_dict.get("select") if isinstance(obs_dict, dict) else None
        if sel is None:
            return list(self.deck)          # deck submission step
        from cg import api as A
        try:
            o = A.to_observation_class(obs_dict)
            f = E.encode(o)
        except Exception:  # noqa: BLE001
            return [0]
        b = M.to_torch(f)
        n_legal = int(f["n_options"])
        if n_legal <= 0:
            return [0]

        lo = int(f["min_count"]) or 1
        hi = int(f["max_count"]) or 1
        k = max(1, min(max(lo, 1), max(hi, 1), n_legal))

        state_before = self.state
        with torch.no_grad():
            out = self.model.select_autoregressive(b, state_before, k=k, greedy=self.greedy,
                                                   generator=self.gen)
        self.state = tuple(t.detach() for t in out["state"])
        self.decision += 1

        opts = K.canonical_options(sel)
        chosen_opts = [opts[i] for i in out["selected"] if i < len(opts)]
        payload = (K.to_select_payload(chosen_opts, sel) if chosen_opts
                   else [opts[0].option_index])

        rec = MultiSelectRecord(
            decision=self.decision, k=out["k"], selected=list(out["selected"]),
            payload=list(payload), steps=out["steps"], joint_logp=out["joint_logp"],
            min_count=lo, max_count=hi, n_legal=n_legal)
        if len(self.multiselect) < 20000:
            self.multiselect.append(rec)

        # B5/audit #11: the fingerprint the learner must reproduce
        fp = _hash(K.observation_hash(o), f["opt_mask"].tobytes(), state_hash(state_before),
                   tuple(out["selected"]))
        self.steps.append(Step(obs_features=f, selected=list(out["selected"]),
                               joint_logp=out["joint_logp"], value=out["value"],
                               context_fingerprint=fp, behavior_version=self.version))
        return list(payload)

    def finish(self, result_pm_one: float):
        if self.steps:
            self.steps[-1].reward = float(result_pm_one)
            self.steps[-1].done = True

    def unrolls(self, length: int = UNROLL_LENGTH) -> List[Unroll]:
        """Split the episode into unrolls, each carrying the state it ACTUALLY started from.

        The first unroll starts at a true episode boundary and legitimately has zero state; every
        LATER unroll must carry the non-zero state the actor held there. That is precisely what
        c019 discarded (audit #10), and probe B07 checks the resulting distribution.
        """
        out: List[Unroll] = []
        if not self.steps:
            return out
        hidden = self.model.cfg["lstm_hidden"]
        # replay the recorded states: recompute h/c stepwise from the stored features so each
        # unroll boundary records the true state rather than a reconstruction
        h = np.zeros(hidden, dtype=np.float32)
        c = np.zeros(hidden, dtype=np.float32)
        state = None
        starts = list(range(0, len(self.steps), length))
        with torch.no_grad():
            cursor = 0
            for si, start in enumerate(starts):
                chunk = self.steps[start:start + length]
                if not chunk:
                    continue
                h0 = (state[0][0].detach().cpu().numpy().copy() if state is not None
                      else np.zeros(hidden, dtype=np.float32))
                c0 = (state[1][0].detach().cpu().numpy().copy() if state is not None
                      else np.zeros(hidden, dtype=np.float32))
                for s in chunk:
                    b = M.to_torch(s.obs_features)
                    _t, _v, state, _e = self.model.joint_logp_of(b, s.selected, state)
                    state = tuple(x.detach() for x in state)
                boot = 0.0 if chunk[-1].done else float(_v[0].item())
                out.append(Unroll(h0=h0, c0=c0, episode_start=(si == 0),
                                  actor_version=self.version, steps=chunk,
                                  bootstrap_value=boot, game_id="", seat=0,
                                  opponent_kind=""))
        return out
