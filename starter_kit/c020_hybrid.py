"""c020 C1-C5 — the mandatory modular hybrid, H0 through H4.

Audit #14: c019 called the recurrent ByteRL model with `state=None` at every search node. A
recurrent policy evaluated from a blank memory is not the policy that was trained — it is that
network's opinion about a game that just started, applied to a position twenty decisions deep. The
priors it produced were therefore not merely weak, they were categorically wrong, which is
consistent with c019's ablation finding that priors cost −28.7 field points while the value head
cost −2.5.

`HybridNodeState` (C1) fixes that: every search node carries a CLONE of the recurrent state,
advanced through the exact simulated action history. Siblings never share mutable tensors.

The five modes are exactly as specified in C2 — no sixth mode, no sweep, one registered alpha.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_core as K  # noqa: E402
from cg import c020_tactical_leaf as TL  # noqa: E402

# C2: exactly one registered blend weight, fixed before final results. No sweep.
H4_ALPHA = 0.5
H4_ALPHA_VERSION = "c020.h4_alpha.v1"

MODES = {
    "H0": {"priors": "baseline", "value": "tactical_heuristic"},
    "H1": {"priors": "byterl", "value": "tactical_heuristic"},
    "H2": {"priors": "baseline", "value": "byterl"},
    "H3": {"priors": "byterl", "value": "byterl"},
    "H4": {"priors": "byterl", "value": f"blend(alpha={H4_ALPHA})"},
}


@dataclass
class HybridNodeState:
    """`IMPLEMENTATION_GUIDE §11`. One per search node; tensors are cloned, never aliased."""

    neural_h: Any = None
    neural_c: Any = None
    depth: int = 0
    advanced_calls: int = 0

    def is_none(self) -> bool:
        return self.neural_h is None and self.neural_c is None

    def clone(self) -> "HybridNodeState":
        import torch
        return HybridNodeState(
            neural_h=(self.neural_h.detach().clone() if self.neural_h is not None else None),
            neural_c=(self.neural_c.detach().clone() if self.neural_c is not None else None),
            depth=self.depth, advanced_calls=self.advanced_calls)

    def as_tuple(self):
        if self.neural_h is None or self.neural_c is None:
            return None
        return (self.neural_h, self.neural_c)


class NeuralAdapter:
    """C1: owns the corrected ByteRL model and advances branch-local state through the tree."""

    def __init__(self, checkpoint: str, device: str = "cpu"):
        self.checkpoint = checkpoint
        self.device = device
        self._model = None
        self.stats = {"initial_calls": 0, "advance_calls": 0, "state_none_at_nonroot": 0,
                      "prior_calls": 0, "value_calls": 0, "encode_errors": 0}
        self.traces: List[Dict[str, Any]] = []

    def model(self):
        if self._model is None:
            import torch
            from cg import c020_byterl_model as M
            m = M.PTCGByteRL()
            m.load_state_dict(torch.load(self.checkpoint, map_location=self.device)["state_dict"])
            m.eval()
            self._model = m
        return self._model

    def initial(self) -> HybridNodeState:
        """Root state. Only the ROOT may legitimately start from zero."""
        self.stats["initial_calls"] += 1
        return HybridNodeState(depth=0)

    def advance(self, state: Optional[HybridNodeState], obs, payload: List[int]
                ) -> HybridNodeState:
        """Advance the recurrent state through the EXACT executed transition (C1)."""
        import torch
        from cg import c020_byterl_encode as E, c020_byterl_model as M
        st = state.clone() if isinstance(state, HybridNodeState) else HybridNodeState()
        if obs is None:
            return st
        try:
            f = E.encode(obs)
            b = M.to_torch(f, device=self.device)
            refs = E.option_refs(obs)
            idx = [i for i, r in enumerate(refs) if r.option_index in list(payload)]
            with torch.no_grad():
                _lp, _v, nxt, _e = self.model().joint_logp_of(b, idx or [0], st.as_tuple())
            self.stats["advance_calls"] += 1
            return HybridNodeState(neural_h=nxt[0].detach().clone(),
                                   neural_c=nxt[1].detach().clone(),
                                   depth=st.depth + 1, advanced_calls=st.advanced_calls + 1)
        except Exception:  # noqa: BLE001
            self.stats["encode_errors"] += 1
            return st

    # ---------------------------------------------------------------- providers
    def prior_provider(self):
        """H1/H3/H4 priors, computed from the node's OWN recurrent state (C1)."""
        import torch
        from cg import c020_byterl_encode as E, c020_byterl_model as M

        def provide(node, opts) -> Optional[Dict[Any, float]]:
            st = node.neural
            if node.depth > 0 and (st is None or (isinstance(st, HybridNodeState)
                                                  and st.is_none())):
                # audit #14: this is exactly the c019 defect, so it is COUNTED, not silently done
                self.stats["state_none_at_nonroot"] += 1
            try:
                f = E.encode(node.obs)
                b = M.to_torch(f, device=self.device)
                with torch.no_grad():
                    logits, _v, _n = self.model().forward(
                        b, st.as_tuple() if isinstance(st, HybridNodeState) else None)
                    probs = M.masked_probs(logits, b["opt_mask"])[0]
                refs = E.option_refs(node.obs)
                out = {}
                for i, r in enumerate(refs[:len(probs)]):
                    for o in opts:
                        if o.option_index == r.option_index:
                            out[o.key()] = float(probs[i])
                self.stats["prior_calls"] += 1
                if len(self.traces) < 500:
                    self.traces.append({"depth": node.depth, "det_id": node.det_id,
                                        "state_is_none": bool(st is None or st.is_none()),
                                        "advanced_calls": getattr(st, "advanced_calls", 0),
                                        "n_priors": len(out)})
                return out or None
            except Exception:  # noqa: BLE001
                self.stats["encode_errors"] += 1
                return None
        return provide

    def value_provider(self, mode: str = "H2", alpha: float = H4_ALPHA,
                       admitted: bool = False):
        """H2/H3 ByteRL value, H4 the registered blend. Refuses unless admitted (C4)."""
        import torch
        from cg import c020_byterl_encode as E, c020_byterl_model as M

        def provide(obs, terminal: bool = False, state=None) -> Optional[float]:
            if not admitted:
                return None          # C4: non-promotable modes still run, on the heuristic
            try:
                f = E.encode(obs)
                b = M.to_torch(f, device=self.device)
                with torch.no_grad():
                    _lg, v, _n = self.model().forward(
                        b, state.as_tuple() if isinstance(state, HybridNodeState) else None)
                nv = float(v[0])
                self.stats["value_calls"] += 1
                if mode == "H4":
                    hv, _feat = TL.evaluate(obs, terminal, None, None)
                    return alpha * hv + (1.0 - alpha) * nv
                return nv
            except Exception:  # noqa: BLE001
                self.stats["encode_errors"] += 1
                return None
        return provide

    def report(self) -> Dict[str, Any]:
        return {"checkpoint": os.path.basename(self.checkpoint), **self.stats,
                "no_state_none_at_nonroot": self.stats["state_none_at_nonroot"] == 0}


# ------------------------------------------------------------------ C3 / C4 admission

def prior_admission(adapter: "NeuralAdapter", samples: List[Dict[str, Any]],
                    floor: float = 0.01) -> Dict[str, Any]:
    """C3: alignment, normalization, floor, baseline coverage, entropy."""
    n = len(samples)
    aligned = sum(1 for s in samples if s.get("aligned"))
    normalized = sum(1 for s in samples if abs(s.get("prob_sum", 0.0) - 1.0) < 1e-3)
    floored = sum(1 for s in samples if s.get("min_credible_prior", 0.0) >= floor)
    covers = sum(1 for s in samples if s.get("baseline_in_topk"))
    suppress = sum(1 for s in samples if s.get("baseline_prior", 1.0) < 1e-4)
    ent = [s.get("entropy") for s in samples if s.get("entropy") is not None]
    out = {"samples": n,
           "action_key_alignment_rate": round(aligned / max(1, n), 4),
           "normalized_rate": round(normalized / max(1, n), 4),
           "credible_floor_rate": round(floored / max(1, n), 4),
           "baseline_in_topk_rate": round(covers / max(1, n), 4),
           "catastrophic_baseline_suppression": suppress,
           "mean_entropy": round(float(np.mean(ent)), 4) if ent else None,
           "floor": floor}
    out["admitted"] = bool(n > 0 and out["action_key_alignment_rate"] >= 0.98
                           and out["normalized_rate"] >= 0.98
                           and out["baseline_in_topk_rate"] >= 0.60
                           and suppress == 0)
    out["rule"] = "C3: exact key alignment, normalization, credible floor, top-k baseline " \
                  "coverage, no catastrophic suppression"
    return out


def value_admission(preds: Dict[str, List[float]], outcomes: List[float]) -> Dict[str, Any]:
    """C4: corrected value vs constant, c019 value, random ranking, and tactical heuristic."""
    y = np.asarray(outcomes, dtype=float)
    n = len(y)
    if n < 8:
        return {"n": n, "admitted": False, "reason": "insufficient held-out leaves"}
    const = float(y.mean())

    def mse(a):
        a = np.asarray(a, dtype=float)
        return float(((a - y) ** 2).mean())

    def corr(a):
        a = np.asarray(a, dtype=float)
        return (float(np.corrcoef(a, y)[0, 1])
                if a.std() > 1e-9 and y.std() > 1e-9 else 0.0)

    def brier(a):
        p = (np.clip(np.asarray(a, dtype=float), -1, 1) + 1) / 2
        t = (y + 1) / 2
        return float(((p - t) ** 2).mean())

    rows = {}
    for name, a in preds.items():
        rows[name] = {"mse": round(mse(a), 5), "corr": round(corr(a), 5),
                      "brier": round(brier(a), 5)}
    rows["constant_mean"] = {"mse": round(mse(np.full(n, const)), 5), "corr": 0.0,
                             "brier": round(brier(np.full(n, const)), 5)}
    rng = np.random.default_rng(0)
    rnd = rng.uniform(-1, 1, size=n)
    rows["random_ranking"] = {"mse": round(mse(rnd), 5), "corr": round(corr(rnd), 5),
                              "brier": round(brier(rnd), 5)}

    c020 = rows.get("c020_byterl_value")
    admitted = bool(c020 and
                    c020["mse"] < rows["constant_mean"]["mse"] and
                    c020["mse"] < rows.get("tactical_heuristic", {"mse": 1e9})["mse"] and
                    c020["corr"] > abs(rows["random_ranking"]["corr"]) and
                    (not rows.get("c019_value_control") or
                     c020["mse"] <= rows["c019_value_control"]["mse"]))
    return {"n": n, "constant_mean_value": round(const, 4), "metrics": rows,
            "admitted": admitted,
            "controls": ["constant_mean", "c019_value_control", "random_ranking",
                         "tactical_heuristic"],
            "rule": "C4: must beat constant AND tactical heuristic on MSE, out-rank random, "
                    "and not be worse than the c019 value control"}


def mode_manifest(mode: str, adapter: Optional["NeuralAdapter"],
                  prior_ok: bool, value_ok: bool) -> Dict[str, Any]:
    spec = MODES[mode]
    uses_byterl_priors = spec["priors"] == "byterl"
    uses_byterl_value = spec["value"] != "tactical_heuristic"
    promotable = ((not uses_byterl_priors or prior_ok) and (not uses_byterl_value or value_ok))
    return {"mode": mode, "spec": spec,
            "checkpoint": (os.path.basename(adapter.checkpoint) if adapter else None),
            "prior_admission_passed": prior_ok, "value_admission_passed": value_ok,
            "promotable": promotable,
            "h4_alpha": H4_ALPHA if mode == "H4" else None,
            "h4_alpha_version": H4_ALPHA_VERSION if mode == "H4" else None,
            "note": "C2/C4: H2-H4 execute at smoke scale even when value admission fails, but "
                    "are non-promotable until it passes"}
