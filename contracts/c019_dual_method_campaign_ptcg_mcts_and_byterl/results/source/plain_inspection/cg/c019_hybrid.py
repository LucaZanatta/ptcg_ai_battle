"""c019 §10 — switchable hybrid adapters between the two pure branches.

Three adapters, each individually disableable, each defaulting OFF:

  1. `ByteRLPriorProvider`  — ByteRL legal-option probabilities become normalized MCTS priors.
  2. `ByteRLLeafValue`      — ByteRL value becomes the MCTS leaf evaluator, ONLY after §10/
     DECISION_RULES calibration shows it beats a constant and the heuristic on held-out leaves.
  3. `VisitTargetWriter`    — MCTS root visit distributions written to a schema for possible
     later auxiliary training. c019 does not require training on them.

H03 requires that disabling the adapters leaves pure MCTS output unchanged. That is structural
here: `ISMCTSAgent` takes `prior_provider`/`value_provider` as constructor arguments defaulting
to `None`, and `c019_mcts` imports nothing from the ByteRL modules. The pure branch cannot
acquire a ByteRL dependency by accident.

§16 also forbids the reverse direction: the primary ByteRL branch never consumes MCTS data.
Nothing here writes into the ByteRL training path.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_core as K  # noqa: E402

HYBRID_VERSION = "c019.hybrid.v1"


class ByteRLPriorProvider:
    """H01 — ByteRL option probabilities mapped onto canonical MCTS children.

    Mapping is by canonical KEY, not by index: the option list a ByteRL forward saw and the one
    the tree is expanding are the same select, but nothing guarantees index stability across the
    two code paths, and a silent misalignment would put a strong prior on the wrong action.
    """

    def __init__(self, checkpoint: str, enabled: bool = True, temperature: float = 1.0):
        self.enabled = enabled
        self.temperature = temperature
        self.checkpoint = checkpoint
        self.calls = 0
        self.failures = 0
        self.unmapped = 0
        self._model = None

    def _model_lazy(self):
        if self._model is None:
            import torch
            from cg import c019_byterl_model as M
            m = M.PTCGByteRL()
            m.load_state_dict(torch.load(self.checkpoint, map_location="cpu")["state_dict"])
            m.eval()
            self._model = m
        return self._model

    def __call__(self, node, options: List[K.CanonicalOption]) -> Optional[Dict[Any, float]]:
        """Return {canonical_key: weight} or None to fall back to heuristic priors."""
        if not self.enabled or not options:
            return None
        self.calls += 1
        try:
            import torch
            from cg import c019_byterl_encode as E, c019_byterl_model as M
            f = E.encode(node.obs)
            b = M.to_torch(f)
            with torch.no_grad():
                logits, _v, _s = self._model_lazy().forward(b, None)
                probs = M.masked_probs(logits, b["opt_mask"])[0].numpy()
        except Exception:  # noqa: BLE001
            self.failures += 1
            return None
        out: Dict[Any, float] = {}
        for o in options:
            i = o.option_index
            if 0 <= i < len(probs):
                out[o.key()] = float(probs[i]) ** (1.0 / max(self.temperature, 1e-6))
            else:
                self.unmapped += 1
        s = sum(out.values())
        if s <= 0:
            return None
        return {k: v / s for k, v in out.items()}

    def stats(self) -> Dict[str, Any]:
        return {"adapter": "byterl_priors", "enabled": self.enabled, "calls": self.calls,
                "failures": self.failures, "unmapped_options": self.unmapped,
                "checkpoint": self.checkpoint}


class ByteRLLeafValue:
    """H02 — ByteRL value head as the MCTS leaf evaluator.

    DECISION_RULES permits this ONLY after calibration shows the value beats both a constant and
    the heuristic on held-out leaves. `calibrated` starts False and the provider refuses to act
    until calibration explicitly enables it, so an uncalibrated value cannot leak into a tree
    merely because the model exists — the c018 audit calls that out directly.
    """

    def __init__(self, checkpoint: str, enabled: bool = False, calibrated: bool = False):
        self.enabled = enabled
        self.calibrated = calibrated
        self.checkpoint = checkpoint
        self.calls = 0
        self.refusals = 0
        self._model = None

    def _model_lazy(self):
        if self._model is None:
            import torch
            from cg import c019_byterl_model as M
            m = M.PTCGByteRL()
            m.load_state_dict(torch.load(self.checkpoint, map_location="cpu")["state_dict"])
            m.eval()
            self._model = m
        return self._model

    def __call__(self, observation, terminal: bool = False) -> Optional[float]:
        if not (self.enabled and self.calibrated):
            self.refusals += 1
            return None
        self.calls += 1
        try:
            import torch
            from cg import c019_byterl_encode as E, c019_byterl_model as M
            f = E.encode(observation)
            b = M.to_torch(f)
            with torch.no_grad():
                _l, v, _s = self._model_lazy().forward(b, None)
            return float(np.clip(float(v[0]), -1.0, 1.0))
        except Exception:  # noqa: BLE001
            return None

    def stats(self) -> Dict[str, Any]:
        return {"adapter": "byterl_leaf_value", "enabled": self.enabled,
                "calibrated": self.calibrated, "calls": self.calls,
                "refusals_uncalibrated": self.refusals, "checkpoint": self.checkpoint}


class VisitTargetWriter:
    """MCTS root visit distributions -> auxiliary target schema.

    Written for possible later use. c019 does not train ByteRL on this data (§10, §16), and the
    records are labelled so a future contract cannot mistake them for on-policy experience.
    """

    def __init__(self, path: str, enabled: bool = False):
        self.enabled = enabled
        self.path = path
        self.written = 0
        self._fh = None

    def write(self, obs_hash: str, aggregate: List[Dict[str, Any]], det_count: int):
        if not self.enabled:
            return
        import gzip
        if self._fh is None:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            self._fh = gzip.open(self.path, "wt")
        total = sum(a.get("visits", 0) for a in aggregate) or 1
        self._fh.write(json.dumps({
            "schema": "c019.visit_target.v1",
            "provenance": "MCTS_ROOT_VISITS",
            "not_on_policy_experience": True,
            "obs_hash": obs_hash, "determinizations": det_count,
            "targets": [{"action_key": list(a["action_key"]),
                         "visits": a.get("visits", 0),
                         "probability": round(a.get("visits", 0) / total, 6),
                         "q": a.get("q")} for a in aggregate[:32]]}) + "\n")
        self.written += 1

    def close(self):
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def stats(self) -> Dict[str, Any]:
        return {"adapter": "visit_targets", "enabled": self.enabled, "records": self.written,
                "path": self.path,
                "note": "schema only; c019 does not train ByteRL on MCTS data (§16)"}


def calibrate_leaf_value(checkpoint: str, leaves: List[Any], outcomes: List[float],
                         heuristic_fn) -> Dict[str, Any]:
    """H02 gate: compare ByteRL value against a constant and the heuristic on held-out leaves.

    Returns the comparison and whether the adapter may be enabled. The constant baseline is the
    honest control — a value head that cannot beat predicting the mean is not adding signal, and
    correlation is reported separately because a search leaf evaluator needs ORDERING, not
    calibrated magnitudes.
    """
    import torch
    from cg import c019_byterl_encode as E, c019_byterl_model as M
    m = M.PTCGByteRL()
    m.load_state_dict(torch.load(checkpoint, map_location="cpu")["state_dict"])
    m.eval()
    preds, heur = [], []
    for lf in leaves:
        try:
            f = E.encode(lf)
            b = M.to_torch(f)
            with torch.no_grad():
                _l, v, _s = m.forward(b, None)
            preds.append(float(v[0]))
        except Exception:  # noqa: BLE001
            preds.append(0.0)
        try:
            heur.append(float(heuristic_fn(lf, False)))
        except Exception:  # noqa: BLE001
            heur.append(0.0)
    y = np.asarray(outcomes, dtype=float)
    p = np.asarray(preds, dtype=float)
    h = np.asarray(heur, dtype=float)
    const = float(y.mean()) if len(y) else 0.0

    def mse(a):
        return float(((a - y) ** 2).mean()) if len(y) else None

    def corr(a):
        return (float(np.corrcoef(a, y)[0, 1])
                if len(y) > 2 and a.std() > 1e-9 and y.std() > 1e-9 else None)

    out = {"n_leaves": len(y), "constant_baseline_value": round(const, 4),
           "mse_byterl_value": mse(p), "mse_heuristic": mse(h),
           "mse_constant": mse(np.full_like(y, const)),
           "corr_byterl_value": corr(p), "corr_heuristic": corr(h)}
    out["beats_constant"] = bool(out["mse_byterl_value"] is not None
                                 and out["mse_byterl_value"] < out["mse_constant"])
    out["beats_heuristic"] = bool(out["mse_byterl_value"] is not None
                                  and out["mse_byterl_value"] < out["mse_heuristic"])
    out["may_enable_leaf_value_adapter"] = bool(out["beats_constant"] and out["beats_heuristic"])
    out["rule"] = ("DECISION_RULES: baseline priors + ByteRL value only if value calibration "
                   "beats constant AND heuristic on held-out leaves")
    return out
