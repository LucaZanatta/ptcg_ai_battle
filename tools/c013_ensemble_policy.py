"""c013 §9 — true ONLINE ensembles over the existing policy population.

An online ensemble is not a weight soup. A soup evaluates one network at averaged parameters;
an online ensemble evaluates every component network and combines their outputs. For a
non-linear network those are different functions, and §2 forbids claiming they are equivalent.
`test_c013_ensemble_math.py` demonstrates the difference numerically rather than asserting it.

Two combination rules are registered, and the difference between them is real:

  LOGIT ensemble        average the components' raw option logits, then mask and softmax.
  PROBABILITY ensemble  mask and softmax EACH component first, then average the resulting
                        distributions.

They coincide only when components agree up to an additive constant. They also diverge
differently under sequential multi-select: §9 requires each component distribution to be
RECOMPUTED after every selected item. For a logit ensemble that is renormalising one averaged
logit vector over the shrinking legal set; for a probability ensemble it is renormalising each
component over the shrinking set and re-averaging, which is not the same distribution.

Forced decisions bypass ensemble scoring entirely (§9), exactly as the single-policy runtime
does, so the ensemble never changes behaviour where no choice exists.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import rl_policy as rlp, policy_data_v2 as pd  # noqa: E402

NEG = 1e30


def _masked_softmax(z: np.ndarray, mask: np.ndarray) -> np.ndarray:
    zz = np.where(mask > 0, z, -NEG)
    zz = zz - zz.max()
    e = np.exp(zz) * (mask > 0)
    s = e.sum()
    return e / s if s > 0 else mask / max(mask.sum(), 1)


class EnsemblePolicy:
    """Drop-in replacement for RLPolicy at the `act()` interface used by the runtime agent.

    `mode` is 'logit' or 'prob'. Components are frozen; nothing here trains.
    """

    def __init__(self, components: List[rlp.RLPolicy], mode: str = "logit",
                 component_ids=None, component_sha256=None):
        assert mode in ("logit", "prob"), mode
        assert len(components) >= 2, "an ensemble needs at least two components"
        self.components = components
        self.mode = mode
        self.component_ids = list(component_ids or [f"c{i}" for i in range(len(components))])
        self.component_sha256 = list(component_sha256 or [])
        self.weights = np.full(len(components), 1.0 / len(components))   # equal weight only
        self.last_diagnostics: Dict[str, Any] = {}
        # exposed so RLAgent's fallback paths behave as with a single policy
        self.pv = components[0].pv
        self.trunk = components[0].trunk

    # ---- per-component raw outputs on the IDENTICAL encoded state (§9) ----
    def _component_outputs(self, feat):
        b = pd.collate([rlp._stub(feat)])
        logits, values = [], []
        for p in self.components:
            out = p.trunk.forward(b)
            sc = out["scores"].data[0]
            stop = float(p.pv["stop"].data[0])
            logits.append(np.concatenate([sc, [stop]]))
            values.append(float(p._value(out["ctx"]).data[0]))
        return np.asarray(logits), np.asarray(values)

    def _combine(self, logits: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """One combined distribution over the CURRENT legal set.

        Called again after every multi-select pick, which is what makes the probability rule
        differ from the logit rule (§9).
        """
        if self.mode == "logit":
            avg = (self.weights[:, None] * logits).sum(axis=0)
            return _masked_softmax(avg, mask)
        probs = np.stack([_masked_softmax(l, mask) for l in logits])
        p = (self.weights[:, None] * probs).sum(axis=0)
        s = p.sum()
        return p / s if s > 0 else mask / max(mask.sum(), 1)

    def act(self, feat: Dict[str, Any], form: str, lo: int, hi: int, rng, greedy: bool = False):
        n = feat["n_options"]
        logits, values = self._component_outputs(feat)
        K = logits.shape[1] - 1
        mask = np.zeros(K + 1)
        mask[:n] = 1.0
        stop_legal = (form == "VARIABLE_MULTISELECT")
        if stop_legal:
            mask[K] = 1.0

        # §9: forced decisions bypass ensemble scoring
        if int(mask.sum()) <= 1:
            a = int(np.argmax(mask))
            return {"action": [a] if a != K else [], "action_seq": [a], "logprob": 0.0,
                    "value": float((self.weights * values).sum()), "entropy": 0.0,
                    "form": form, "lo": lo, "hi": hi, "n_options": n,
                    "ensemble": {"mode": self.mode, "forced": True}}

        seq, logp, ent0 = [], 0.0, 0.0
        running = mask.copy()
        max_picks = 1 if form in ("SINGLE_CHOICE", "EMPTY") else hi
        disagreement = []
        for j in range(max(max_picks, 1)):
            p = self._combine(logits, running)          # recomputed every step (§9)
            per_comp = np.stack([_masked_softmax(l, running) for l in logits])
            if j == 0:
                ent0 = float(-(p[p > 0] * np.log(p[p > 0])).sum())
                tops = [int(np.argmax(c)) for c in per_comp]
                disagreement.append({
                    "step": j,
                    "component_top1": tops,
                    "unanimous": len(set(tops)) == 1,
                    "pairwise_disagreement_rate": float(
                        sum(1 for x in range(len(tops)) for y in range(x + 1, len(tops))
                            if tops[x] != tops[y]) / max(1, len(tops) * (len(tops) - 1) / 2)),
                    "component_entropies": [float(-(c[c > 0] * np.log(c[c > 0])).sum())
                                            for c in per_comp],
                    "mean_total_variation": float(np.mean(
                        [0.5 * np.abs(per_comp[x] - per_comp[y]).sum()
                         for x in range(len(per_comp)) for y in range(x + 1, len(per_comp))]))
                    if len(per_comp) > 1 else 0.0,
                })
            a = int(np.argmax(p)) if greedy else int(rng.choice(len(p), p=p))
            logp += float(np.log(p[a] + 1e-30))
            seq.append(a)
            if a == K:
                break
            running[a] = 0.0
            if form in ("SINGLE_CHOICE", "EMPTY"):
                break
            if form == "FIXED_MULTISELECT" and len(seq) >= hi:
                break
        chosen = [a for a in seq if a != K]
        self.last_diagnostics = {"mode": self.mode, "steps": disagreement}
        return {"action": chosen, "action_seq": seq, "logprob": logp,
                "value": float((self.weights * values).sum()),
                "component_values": values.tolist(),
                "entropy": ent0, "form": form, "lo": lo, "hi": hi, "n_options": n,
                "ensemble": {"mode": self.mode, "forced": False,
                             "component_ids": self.component_ids,
                             "diagnostics": disagreement}}


def build(component_paths: List[str], mode: str, component_ids=None, component_sha256=None):
    comps = [rlp.RLPolicy.load(p) for p in component_paths]
    cfgs = {tuple(sorted(c.trunk.cfg.items())) for c in comps}
    assert len(cfgs) == 1, "ensemble components must share an architecture"
    return EnsemblePolicy(comps, mode=mode, component_ids=component_ids,
                          component_sha256=component_sha256)


def weight_soup(component_paths: List[str], out_path: str, seed: int = 0) -> str:
    """Equal arithmetic weight average. Architecture-identical components only (§8.4)."""
    pols = [rlp.RLPolicy.load(p) for p in component_paths]
    cfgs = {tuple(sorted(p.trunk.cfg.items())) for p in pols}
    assert len(cfgs) == 1, "weight soup requires architecture-identical checkpoints"
    sds = [p.state_dict() for p in pols]
    keys = set(sds[0])
    assert all(set(s) == keys for s in sds), "checkpoint key sets differ"
    avg = {k: np.mean([s[k] for s in sds], axis=0) for k in keys}
    base = pols[0]
    meta = np.array([base.trunk.cfg[k] for k in
                     ("D", "Hs", "BV", "Hh", "HV", "Hd", "DV", "GH", "CTX", "OH", "OH2", "SH")]
                    + [seed], dtype=np.int64)
    np.savez(out_path, __meta__=meta, **avg)
    return out_path
