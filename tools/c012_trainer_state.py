"""c012 §7 — resumable trainer state built around the ACTIVE numpy Generator.

The c011 defect this repairs: `c011_trainer_state.py` saved `np.random.get_state()` -- the
legacy *global* RNG -- and re-seeded it with `np.random.seed()`. Neither touches the
`np.random.default_rng(seed)` object the trainer actually samples opponents, seats,
per-game seeds and minibatch permutations from. Restoring that state therefore restored
nothing that mattered, and c011's continuation test only appeared to pass because it fed
both runs a precomputed minibatch permutation (§7: "A test using precomputed minibatch
orders is insufficient").

Here a SINGLE Generator drives every stochastic choice in training, and it is saved and
restored through `rng.bit_generator.state` exactly as §7 requires.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import torch

REQUIRED_FIELDS = (
    "policy_weights", "value_weights", "adam_moments", "optimizer_step",
    "completed_games", "games_with_trainable_decisions", "trainable_decisions",
    "entropy_schedule_definition", "entropy_schedule_progress",
    "numpy_generator_type", "numpy_generator_state",
    "torch_cpu_rng", "torch_cuda_rng", "python_random_state",
    "lagged_registry", "curriculum_state", "branch_checkpoint_registry",
)


@dataclass
class TrainerState:
    seed: int
    completed_games: int = 0
    games_with_trainable_decisions: int = 0
    trainable_decisions: int = 0
    updates: int = 0
    lagged: List[Dict[str, str]] = field(default_factory=list)
    curriculum_state: Dict[str, Any] = field(default_factory=dict)
    branch_checkpoints: Dict[str, Any] = field(default_factory=dict)
    entropy_schedule: Dict[str, Any] = field(default_factory=dict)
    trainer_state_id: Optional[str] = None

    @staticmethod
    def new_rng(seed: int) -> np.random.Generator:
        """The one Generator that drives opponent draws, seats, per-game seeds and the PPO
        minibatch permutation. Nothing else may consume randomness."""
        return np.random.default_rng(seed)

    def save(self, path: str, model, opt, rng: np.random.Generator, lr: float,
             entropy_coef: float, extra: Optional[Dict[str, Any]] = None) -> str:
        sd = model.state_dict()
        value_keys = [k for k in sd if k.startswith(("vW1", "vW2"))]
        blob = {
            "policy_weights": {k: v.detach().cpu() for k, v in sd.items() if k not in value_keys},
            "value_weights": {k: sd[k].detach().cpu() for k in value_keys},
            "full_module_state": {k: v.detach().cpu() for k, v in sd.items()},
            "adam_moments": opt.state_dict(),
            "optimizer_step": int(self.updates),
            "learning_rate": float(lr),
            "entropy_coef": float(entropy_coef),
            "entropy_schedule_definition": dict(self.entropy_schedule),
            "entropy_schedule_progress": {
                "completed_games": int(self.completed_games),
                "fraction": float(self.entropy_schedule.get("fraction", 0.0))},
            "completed_games": int(self.completed_games),
            "games_with_trainable_decisions": int(self.games_with_trainable_decisions),
            "trainable_decisions": int(self.trainable_decisions),
            "updates": int(self.updates),
            # §7: the ACTIVE Generator, not the legacy global state
            "numpy_generator_type": type(rng.bit_generator).__name__,
            "numpy_generator_state": rng.bit_generator.state,
            "torch_cpu_rng": torch.get_rng_state(),
            "torch_cuda_rng": (torch.cuda.get_rng_state_all()
                               if torch.cuda.is_available() else None),
            "python_random_state": random.getstate(),
            "lagged_registry": list(self.lagged),
            "curriculum_state": dict(self.curriculum_state),
            "branch_checkpoint_registry": dict(self.branch_checkpoints),
            "seed": int(self.seed),
            "trainer_state_id": self.trainer_state_id,
            "model_cfg": dict(model.cfg),
        }
        if extra:
            blob.update(extra)
        torch.save(blob, path)
        return path

    @staticmethod
    def load(path: str, model, opt, device: str = "cpu"):
        """Returns (TrainerState, Generator). The Generator is reconstructed and its
        bit-generator state restored, so the resumed run draws the identical sequence."""
        blob = torch.load(path, map_location=device, weights_only=False)
        model.load_state_dict({k: v.to(device) for k, v in blob["full_module_state"].items()})
        opt.load_state_dict(blob["adam_moments"])
        rng = np.random.default_rng()
        rng.bit_generator.state = blob["numpy_generator_state"]
        torch.set_rng_state(blob["torch_cpu_rng"].cpu()
                            if hasattr(blob["torch_cpu_rng"], "cpu") else blob["torch_cpu_rng"])
        if blob.get("torch_cuda_rng") is not None and torch.cuda.is_available():
            try:
                torch.cuda.set_rng_state_all([s.cpu() for s in blob["torch_cuda_rng"]])
            except Exception:  # noqa: BLE001
                pass
        if blob.get("python_random_state") is not None:
            random.setstate(blob["python_random_state"])
        st = TrainerState(
            seed=blob["seed"], completed_games=blob["completed_games"],
            games_with_trainable_decisions=blob["games_with_trainable_decisions"],
            trainable_decisions=blob["trainable_decisions"], updates=blob["updates"],
            lagged=list(blob["lagged_registry"]),
            curriculum_state=dict(blob["curriculum_state"]),
            branch_checkpoints=dict(blob["branch_checkpoint_registry"]),
            entropy_schedule=dict(blob["entropy_schedule_definition"]),
            trainer_state_id=blob.get("trainer_state_id"))
        return st, rng


def schema() -> Dict[str, Any]:
    return {"required_fields": list(REQUIRED_FIELDS),
            "numpy_generator": "saved via rng.bit_generator.state (§7); the legacy global "
                               "np.random state is deliberately NOT used",
            "note": "One Generator drives opponent draws, seats, per-game seeds and the PPO "
                    "minibatch permutation, so a restored run reproduces all of them."}
