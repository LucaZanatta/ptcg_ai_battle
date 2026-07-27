"""c019 Branch B — Optimistic Smooth Fictitious Play (Algorithm 1).

METHOD_FIDELITY B: immutable historical pool `H`, learning periods defined by ACTUAL completed
games, current-self-play probability `p = 0.6`, payoff-driven sampling from `H`, real `G`/`C`
tables, promotion at `xi = 0.55`, and forced addition after more than `c = 6` learning periods
without promotion — labelled `FORCED_MAX_LP` and never as performance.

CONTRACT §16 and the c018 audit both single out the failure this replaces: "self-play percentage
changing with block number is not OSFP." c018 raised its self-play share on a fixed schedule with
zero performance-driven promotions. Here the opponent is *sampled* every game, the schedule does
not exist, and promotion is decided from measured payoffs.

The paper leaves the sampling function `f` abstract. One implementation is registered here before
scaled training, per §9.4 — no sampler tournament.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

OSFP_VERSION = "c019.osfp.v1"


class ImmutableCheckpointCollision(Exception):
    """Raised rather than overwriting a promoted historical checkpoint."""

# Registered source values (arXiv 2303.05197 Table IV)
P_CURRENT_SELF_PLAY = 0.6
XI_PROMOTION = 0.55
MAX_LP_WITHOUT_ADD = 6
MIN_GAMES_PER_HISTORICAL = 20      # "sufficiently sampled" -- registered, not tuned

# Registered payoff sampler constants (§9.4 / IMPLEMENTATION_GUIDE §12)
TEMPERATURE = 0.25
BETA_UNCERTAINTY = 1.0
EPSILON = 1e-3


def sample_probabilities(G: List[float], C: List[int]) -> List[float]:
    """Registered payoff function `f`: harder and less-sampled opponents are drawn more.

        win_i        = (G_i / C_i + 1) / 2
        hardness_i   = exp((0.5 - win_i) / temperature)
        uncertainty_i= sqrt(log(1 + sum C) / (1 + C_i))
        weight_i     = hardness_i * (1 + beta * uncertainty_i) + epsilon
    """
    n = len(C)
    if n == 0:
        return []
    total_c = float(sum(C))
    w = []
    for i in range(n):
        c_i = float(C[i])
        win = ((G[i] / c_i) + 1.0) / 2.0 if c_i > 0 else 0.5
        hardness = float(np.exp((0.5 - win) / TEMPERATURE))
        uncertainty = float(np.sqrt(np.log(1.0 + total_c) / (1.0 + c_i)))
        w.append(hardness * (1.0 + BETA_UNCERTAINTY * uncertainty) + EPSILON)
    s = sum(w)
    return [x / s for x in w]


def promotion_decision(G: List[float], C: List[int], xi: float = XI_PROMOTION,
                       min_games: int = MIN_GAMES_PER_HISTORICAL,
                       lps_without_add: int = 0,
                       max_lp: int = MAX_LP_WITHOUT_ADD) -> Dict[str, Any]:
    """Algorithm 1's add-to-H decision.

    Returns the reason explicitly, because a forced addition carries no strength evidence and
    must never be reported as a performance promotion.
    """
    if not C:
        return {"add": True, "reason": "FIRST_HISTORICAL",
                "detail": "H is empty; the first checkpoint seeds the pool"}
    winrates = [(G[i] / C[i]) if C[i] else None for i in range(len(C))]
    sufficiently_sampled = all(c >= min_games for c in C)
    beats_all = sufficiently_sampled and all(
        w is not None and w > xi for w in winrates)
    if beats_all:
        return {"add": True, "reason": "PERFORMANCE", "winrates": winrates,
                "xi": xi, "sufficiently_sampled": True}
    if lps_without_add > max_lp:
        return {"add": True, "reason": "FORCED_MAX_LP", "winrates": winrates,
                "lps_without_add": lps_without_add, "max_lp": max_lp,
                "note": "implementation evidence only; carries NO strategic strength claim"}
    return {"add": False, "reason": "NO_PROMOTION", "winrates": winrates, "xi": xi,
            "sufficiently_sampled": sufficiently_sampled,
            "lps_without_add": lps_without_add}


@dataclass
class HistoricalCheckpoint:
    """An IMMUTABLE member of H. Its hash is recorded at add time and re-verified on load."""

    index: int
    path: str
    sha256: str
    added_after_lp: int
    reason: str
    learner_version: int

    def verify(self) -> bool:
        if not os.path.exists(self.path):
            return False
        h = hashlib.sha256()
        with open(self.path, "rb") as fh:
            for c in iter(lambda: fh.read(1 << 20), b""):
                h.update(c)
        return h.hexdigest() == self.sha256


class OSFPScheduler:
    """Maintains H, samples opponents, accumulates G/C, and decides promotion."""

    def __init__(self, ckpt_dir: str, rng, p_current: float = P_CURRENT_SELF_PLAY,
                 xi: float = XI_PROMOTION, max_lp: int = MAX_LP_WITHOUT_ADD,
                 min_games: int = MIN_GAMES_PER_HISTORICAL):
        self.dir = ckpt_dir
        os.makedirs(ckpt_dir, exist_ok=True)
        self.rng = rng
        self.p_current = p_current
        self.xi = xi
        self.max_lp = max_lp
        self.min_games = min_games
        self.H: List[HistoricalCheckpoint] = []
        self.G: List[float] = []
        self.C: List[int] = []
        self.lps_without_add = 0
        self.lp_index = 0
        self.samples: List[Dict[str, Any]] = []
        self.promotions: List[Dict[str, Any]] = []

    # ---------------------------------------------------------------- opponents
    def sample_opponent(self) -> Dict[str, Any]:
        """Sampled per GAME. There is no schedule and no block number."""
        if not self.H or self.rng.random() < self.p_current:
            rec = {"lp": self.lp_index, "kind": "CURRENT_SELF_PLAY", "index": None,
                   "path": None, "p_current": self.p_current}
        else:
            probs = sample_probabilities(self.G, self.C)
            i = int(self.rng.choice(len(probs), p=probs))
            rec = {"lp": self.lp_index, "kind": "HISTORICAL_PAYOFF_SAMPLE", "index": i,
                   "path": self.H[i].path, "probability": round(probs[i], 6),
                   "all_probabilities": [round(x, 6) for x in probs]}
        self.samples.append(rec)
        return rec

    def record_result(self, opponent: Dict[str, Any], return_pm_one: float):
        """G accumulates +1/-1 results; C counts games. Only historical games count."""
        if opponent.get("kind") == "HISTORICAL_PAYOFF_SAMPLE":
            i = opponent["index"]
            self.G[i] += float(return_pm_one)
            self.C[i] += 1

    # ---------------------------------------------------------------- promotion
    def end_learning_period(self, learner_path: str, learner_version: int) -> Dict[str, Any]:
        d = promotion_decision(self.G, self.C, self.xi, self.min_games,
                               self.lps_without_add, self.max_lp)
        d["lp"] = self.lp_index
        d["G"] = list(self.G)
        d["C"] = list(self.C)
        d["learner_version"] = learner_version
        if d["add"]:
            idx = len(self.H)
            dst = os.path.join(self.dir,
                               f"historical_{idx:03d}_lp{self.lp_index:03d}"
                               f"_v{learner_version:06d}.pt")
            if os.path.exists(dst):
                # A promoted checkpoint is immutable. Silently overwriting one would let a
                # re-run replace history that earlier payoff numbers were measured against,
                # which is exactly the "mutable historical checkpoints" the validator rejects.
                raise ImmutableCheckpointCollision(
                    f"historical checkpoint already exists and may not be overwritten: {dst}")
            shutil.copyfile(learner_path, dst)
            os.chmod(dst, 0o444)          # immutable in practice as well as in policy
            h = hashlib.sha256()
            with open(dst, "rb") as fh:
                for c in iter(lambda: fh.read(1 << 20), b""):
                    h.update(c)
            cp = HistoricalCheckpoint(idx, dst, h.hexdigest(), self.lp_index, d["reason"],
                                      learner_version)
            self.H.append(cp)
            self.G.append(0.0)
            self.C.append(0)
            self.lps_without_add = 0
            d["added"] = {"index": idx, "path": dst, "sha256": cp.sha256}
        else:
            self.lps_without_add += 1
        self.promotions.append(d)
        self.lp_index += 1
        return d

    # ---------------------------------------------------------------- evidence
    def payoff_table(self) -> Dict[str, Any]:
        return {"lp": self.lp_index,
                "entries": [{"historical_index": i, "path": self.H[i].path,
                             "sha256": self.H[i].sha256,
                             "added_after_lp": self.H[i].added_after_lp,
                             "reason": self.H[i].reason,
                             "G": self.G[i], "C": self.C[i],
                             "winrate": (self.G[i] / self.C[i]) if self.C[i] else None}
                            for i in range(len(self.H))],
                "sampling_probabilities": sample_probabilities(self.G, self.C)}

    def verify_immutability(self) -> Dict[str, Any]:
        bad = [{"index": c.index, "path": c.path} for c in self.H if not c.verify()]
        return {"historical": len(self.H), "verified": len(self.H) - len(bad),
                "mutated_or_missing": bad, "all_immutable": not bad}

    def observed_self_play_fraction(self) -> Optional[float]:
        if not self.samples:
            return None
        cur = sum(1 for s in self.samples if s["kind"] == "CURRENT_SELF_PLAY")
        return round(cur / len(self.samples), 4)
