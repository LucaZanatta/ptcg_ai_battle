"""c021 B2/B4 — the ByteRL actor: one episode is construct -> validate -> battle -> reward.

`MANDATORY_IMPLEMENTATION B2` requires the terminal reward to reach BOTH the construction and the
battle decisions of the same episode. c019 and c020 trained battle-only on a frozen deck, which is
exactly what `FIDELITY_RULES §4` forbids substituting for end-to-end play.

The actor records, per decision, everything the learner needs and nothing it can fabricate later:
the encoded observation, the chosen SET, the behaviour joint log-probability under the policy that
actually acted, and the stage. The behaviour log-probability must be stored at act time -- a
recomputation under the current weights is the learner's own policy, and using it would make every
V-trace importance ratio identically 1 and silently turn the algorithm on-policy.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_core as K  # noqa: E402
from cg import c021_byterl_deck as DK  # noqa: E402
from cg import c021_byterl_encode as EN  # noqa: E402
from cg import c021_byterl_model as M  # noqa: E402


@dataclass
class Step:
    """One recorded decision. `behaviour_logp` is the acting policy's, fixed at act time."""

    stage: int
    enc: Dict[str, np.ndarray]
    chosen: List[int]
    behaviour_logp: float
    value: float
    n_legal: int
    entropy: float = 0.0


@dataclass
class Episode:
    steps: List[Step] = field(default_factory=list)
    reward: float = 0.0
    completed: bool = False
    deck: List[int] = field(default_factory=list)
    deck_legal: bool = False
    deck_detail: Dict[str, Any] = field(default_factory=dict)
    info: Dict[str, Any] = field(default_factory=dict)

    def construction_steps(self) -> int:
        return sum(1 for s in self.steps if s.stage == EN.STAGE_CONSTRUCTION)

    def battle_steps(self) -> int:
        return sum(1 for s in self.steps if s.stage == EN.STAGE_BATTLE)


class ByteRLActor:
    """Plays one seat. Construction is part of the episode, not a fixed preamble."""

    def __init__(self, net: M.ByteRLNet, pool: DK.CardPool, seed: int = 0,
                 temperature: float = 1.0, learn_construction: bool = True,
                 fixed_deck: Optional[List[int]] = None, device: str = "cpu"):
        self.net = net
        self.pool = pool
        self.rng = np.random.default_rng(seed)
        self.temperature = temperature
        self.learn_construction = learn_construction
        self.fixed_deck = list(fixed_deck) if fixed_deck else None
        self.device = device
        self.enc_stats = EN.EncodeStats()
        self.episode = Episode()
        self.errors: List[str] = []
        self._deck: Optional[List[int]] = None

    # ---------------------------------------------------------------- construction stage
    def build_deck(self) -> List[int]:
        """Autoregressive construction under the per-prefix legal mask.

        The control arm (`learn_construction=False`) plays the frozen permitted deck, so the
        learned arm is reported against a control rather than only in absolute terms.
        """
        if self.fixed_deck is not None:
            self._deck = list(self.fixed_deck)
            ok, detail = DK.legality(self._deck, self.pool)
            self.episode.deck, self.episode.deck_legal, self.episode.deck_detail = \
                list(self._deck), ok, detail
            return self._deck

        deck: List[int] = []
        for _t in range(DK.CONSTRUCTION_STEPS):
            enc = EN.encode_construction(deck, self.pool)
            mask = torch.from_numpy(enc["pool_mask"]).unsqueeze(0)
            with torch.no_grad():
                tt = EN.to_torch(enc, self.device)
                h = self.net.encode(tt["global"], tt["board"], tt["roles"], tt["indices"],
                                    tt["sides"], tt["stage"])
                logits = self.net.construction_logits(h) / max(self.temperature, 1e-6)
                lp = M.masked_log_softmax(logits, mask)
                p = lp.exp()[0].numpy().astype(np.float64)
                p = p / p.sum()
                idx = int(self.rng.choice(len(p), p=p))
                v = float(self.net.value(h, tt["stage"]).item())
                ent = float(-(lp.exp() * lp).sum().item())
            deck.append(self.pool.card_ids[idx])
            if self.learn_construction:
                self.episode.steps.append(Step(
                    stage=EN.STAGE_CONSTRUCTION, enc=enc, chosen=[idx],
                    behaviour_logp=float(lp[0, idx].item()), value=v,
                    n_legal=int(mask.sum().item()), entropy=ent))

        ok, detail = DK.legality(deck, self.pool)
        self.episode.deck, self.episode.deck_legal, self.episode.deck_detail = \
            list(deck), ok, detail
        if not ok:
            # Rejected, never repaired. A silently fixed deck teaches the policy that an illegal
            # construction is free.
            self.errors.append(f"illegal deck: {detail}")
        self._deck = deck
        return deck

    # ---------------------------------------------------------------- battle stage
    def act(self, obs_dict: dict) -> List[int]:
        sel = obs_dict.get("select") if isinstance(obs_dict, dict) else None
        if sel is None:
            return list(self.deck())                       # deck submission step
        try:
            from cg import api as A
            o = A.to_observation_class(obs_dict)
            opts = K.canonical_options(sel)
            if not opts:
                return [0]
            enc = EN.encode_battle(o, None, self.enc_stats)
            n = int(enc["n_options"])
            if n == 0:
                return K.to_select_payload([opts[0]], sel)
            tt = EN.to_torch(enc, self.device)
            legal = tt["opt_mask"].clone()
            legal[:, n:] = 0.0
            with torch.no_grad():
                h = self.net.encode(tt["global"], tt["board"], tt["roles"], tt["indices"],
                                    tt["sides"], tt["stage"])
                chosen, logp = self.net.sample_select(
                    h, tt["opt"], legal,
                    min_count=int(enc["min_count"]), max_count=int(enc["max_count"]),
                    rng=self.rng, temperature=self.temperature)
                v = float(self.net.value(h, tt["stage"]).item())
                lg = self.net.battle_logits(h, tt["opt"])
                lp_all = M.masked_log_softmax(lg, legal)
                ent = float(-(lp_all.exp() * lp_all).sum().item())
            kept = [c for c in chosen if c < len(opts)]
            if not kept:
                return K.to_select_payload([opts[0]], sel)
            if len(kept) != len(chosen):
                # The recorded behaviour log-probability is the joint probability of the SET the
                # policy actually sampled. If any element is dropped here, that number no longer
                # describes the recorded action, and V-trace would divide by the wrong behaviour
                # probability. Recompute it for the set that is actually played.
                with torch.no_grad():
                    logp = float(self.net.select_logprob(h, tt["opt"], legal, kept))
                self.errors.append(f"option index filter dropped "
                                   f"{len(chosen) - len(kept)} of {len(chosen)}")
            self.episode.steps.append(Step(
                stage=EN.STAGE_BATTLE, enc=enc, chosen=list(kept),
                behaviour_logp=float(logp), value=v, n_legal=n, entropy=ent))
            chosen = kept
            return K.to_select_payload([opts[c] for c in chosen], sel)
        except Exception as e:  # noqa: BLE001
            if len(self.errors) < 40:
                self.errors.append(f"{type(e).__name__}: {e}"[:200])
            opts = K.canonical_options(sel)
            return K.to_select_payload([opts[0]], sel) if opts else [0]

    def deck(self) -> List[int]:
        if self._deck is None:
            self.build_deck()
        return self._deck

    # ---------------------------------------------------------------- episode close
    def finish(self, reward: float, completed: bool, info: Optional[Dict] = None) -> Episode:
        """Attach the terminal reward. It reaches BOTH stages -- that is the point of B2."""
        self.episode.reward = float(reward)
        self.episode.completed = bool(completed)
        self.episode.info = dict(info or {})
        self.episode.info["encode_stats"] = self.enc_stats.as_dict()
        self.episode.info["errors"] = self.errors[:8]
        return self.episode

# `episode_to_tensors` used to live here: a second implementation of the learner's tensor
# construction, called by nothing. The trainer builds its tensors from the packed cross-process
# dicts instead. Two copies of the same logic drift -- the behaviour-log-probability fix for the
# option-index filter landed in the actor and would NOT have landed here -- so the dead copy is
# removed rather than left as a trap.
