"""c011 §10.6/§14 — full trainer state, so continuation can be literal rather than a warm restart.

c010 saved policy weights only. Every c010 "continuation" therefore restarted the optimizer
moments, the schedules, the RNG streams and the opponent sampler from scratch -- a warm
restart, which is why §14 requires c011 seeds to be labelled as warm restarts too (they start
from a c010 checkpoint that has no trainer state to restore).

From the first c011 update onward every registered checkpoint carries the whole state below,
so a future contract can resume exactly where this one stopped.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import torch


@dataclass
class TrainerState:
    seed: int
    games_done: int = 0
    updates: int = 0
    lagged: List[Dict[str, str]] = field(default_factory=list)
    opponent_sampler_state: Dict[str, Any] = field(default_factory=dict)
    trainer_state_id: Optional[str] = None

    REQUIRED_FIELDS = (
        "policy_weights", "value_weights", "adamw_state", "optimizer_step",
        "learning_rate", "entropy_coef", "games_done", "updates",
        "python_rng", "numpy_rng", "torch_cpu_rng", "torch_cuda_rng",
        "opponent_sampler_state", "lagged_registry", "seed",
    )

    def seed_all(self):
        random.seed(self.seed)
        np.random.seed(self.seed % (2 ** 32))
        torch.manual_seed(self.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(self.seed)

    def save(self, path: str, model, opt, entropy_coef: float, lr: float,
             extra: Optional[Dict[str, Any]] = None) -> str:
        sd = model.state_dict()
        # policy vs value weights are recorded separately so the manifest can show both were
        # preserved, but both are restored from the single module state_dict.
        value_keys = [k for k in sd if k.startswith(("vW1", "vW2"))]
        blob = {
            "policy_weights": {k: v.detach().cpu() for k, v in sd.items()
                               if k not in value_keys},
            "value_weights": {k: sd[k].detach().cpu() for k in value_keys},
            "full_module_state": {k: v.detach().cpu() for k, v in sd.items()},
            "adamw_state": opt.state_dict(),
            "optimizer_step": int(self.updates),
            "learning_rate": float(lr),
            "entropy_coef": float(entropy_coef),
            "games_done": int(self.games_done),
            "updates": int(self.updates),
            "python_rng": random.getstate(),
            "numpy_rng": np.random.get_state(),
            "torch_cpu_rng": torch.get_rng_state(),
            "torch_cuda_rng": (torch.cuda.get_rng_state_all()
                               if torch.cuda.is_available() else None),
            "opponent_sampler_state": dict(self.opponent_sampler_state),
            "lagged_registry": list(self.lagged),
            "seed": int(self.seed),
            "model_cfg": dict(model.cfg),
            "dtype": str(model.dt),
        }
        if extra:
            blob.update(extra)
        torch.save(blob, path)
        return path

    @staticmethod
    def load(path: str, model, opt, device: str = "cpu") -> "TrainerState":
        blob = torch.load(path, map_location=device, weights_only=False)
        model.load_state_dict({k: v.to(device) for k, v in blob["full_module_state"].items()})
        opt.load_state_dict(blob["adamw_state"])
        random.setstate(blob["python_rng"])
        np.random.set_state(blob["numpy_rng"])
        torch.set_rng_state(blob["torch_cpu_rng"].cpu()
                            if hasattr(blob["torch_cpu_rng"], "cpu") else blob["torch_cpu_rng"])
        if blob.get("torch_cuda_rng") is not None and torch.cuda.is_available():
            try:
                torch.cuda.set_rng_state_all([s.cpu() for s in blob["torch_cuda_rng"]])
            except Exception:  # noqa: BLE001
                pass
        st = TrainerState(seed=blob["seed"], games_done=blob["games_done"],
                          updates=blob["updates"],
                          lagged=list(blob["lagged_registry"]),
                          opponent_sampler_state=dict(blob["opponent_sampler_state"]))
        return st
