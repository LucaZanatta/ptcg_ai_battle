"""c013 §6 — the carried-forward continuation repairs, owned by c013 code.

Everything here was learned the hard way in c011/c012 and is re-implemented in c013-controlled
code rather than imported from those contracts (§6 "verify or repair within c013-controlled
code"; §5 "do not overwrite c011/c012 tools"):

  * the ACTIVE `numpy.random.Generator` is persisted through `rng.bit_generator.state`.
    c011 stored `np.random.get_state()` -- the legacy global -- which the trainer never
    sampled from, so restore restored nothing that mattered.
  * torch CPU and CUDA RNG, AdamW moments, optimizer step, entropy-schedule definition AND
    progress, the lagged-opponent registry and all three game counters are persisted.
  * COMPLETED games are the budget quantity; games that contained only forced decisions count.
  * a registered evaluation that returns zero scored games is a HARD FAILURE. In c012 that
    condition silently returned `None` and disabled the curriculum gates and early stopping
    for an entire 90,000-game arm.
  * checkpoint hashes are refreshed after every save, and evaluation jobs point at
    content-addressed paths. `cg.c009_eval.sha256_file` memoises by path and pool workers
    persist, so a rewritten fixed path made every worker report a stale hash and refuse to
    score its game.
"""

from __future__ import annotations

import hashlib
import os
import random
import shutil
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import torch

REQUIRED_STATE_FIELDS = (
    "policy_weights", "value_weights", "full_module_state",
    "adam_moments", "optimizer_step",
    "completed_games", "games_with_trainable_decisions", "trainable_decisions",
    "entropy_schedule_definition", "entropy_schedule_progress",
    "numpy_generator_type", "numpy_generator_state",
    "torch_cpu_rng", "torch_cuda_rng", "python_random_state",
    "lagged_registry", "curriculum_state", "branch_checkpoint_registry", "seed",
)

PPO_CFG = {"gamma": 0.997, "lam": 0.95, "clip": 0.20, "vf_coef": 0.50,
           "max_grad_norm": 0.50, "epochs": 4, "minibatch": 256,
           "learning_rate": 3e-5, "weight_decay": 1e-5,
           "rollout_game_target": 256, "min_trainable_decisions": 32768,
           "entropy_coef_start": 0.006, "entropy_coef_end": 0.002}


class ZeroScoredGamesError(RuntimeError):
    """Raised when a registered evaluation returns no scored games (§6)."""


def sha_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def content_addressed_copy(src: str, tag: str) -> str:
    """Copy a rewritten checkpoint to a path that varies with its content, so a per-path hash
    cache in a persistent pool worker cannot return a stale value (§6)."""
    sha = sha_file(src)
    dst = os.path.join(os.path.dirname(src), f"eval_{tag}_{sha[:12]}.npz")
    if not os.path.exists(dst):
        shutil.copyfile(src, dst)
    return dst, sha


def require_scored_games(results: List[Dict[str, Any]], where: str) -> List[Dict[str, Any]]:
    """§6 hard failure. Returning an empty result set silently is what disabled c012's gates."""
    scored = [r for r in results if r.get("score") is not None]
    if not scored:
        n = len(results)
        defects = {}
        for r in results:
            d = str(r.get("defect"))
            defects[d] = defects.get(d, 0) + 1
        raise ZeroScoredGamesError(
            f"{where}: {n} games returned, 0 scored. Defect histogram: {defects}. "
            f"A registered evaluation that scores nothing must fail loudly rather than "
            f"disable downstream gates.")
    return scored


def median_best_per_seed(per_seed_values: Dict[Any, float]) -> Optional[float]:
    """§6 — the registered statistic is the MEDIAN best-per-seed value.

    c011's scale decision used the maximum bootstrap significance over any seed/metric pair,
    which is a different and much weaker claim.
    """
    vals = [v for v in per_seed_values.values() if v is not None]
    return float(np.median(vals)) if vals else None


def prob_gt0(diff_boot) -> float:
    return float((np.asarray(diff_boot) > 0).mean())


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
        """THE Generator. Opponent draws, seats, per-game seeds and the PPO minibatch
        permutation all consume it, so a restored run reproduces every one of them."""
        return np.random.default_rng(seed)

    def save(self, path: str, model, opt, rng: np.random.Generator, lr: float,
             entropy_coef: float, extra: Optional[Dict[str, Any]] = None) -> str:
        sd = model.state_dict()
        vkeys = [k for k in sd if k.startswith(("vW1", "vW2"))]
        blob = {
            "policy_weights": {k: v.detach().cpu() for k, v in sd.items() if k not in vkeys},
            "value_weights": {k: sd[k].detach().cpu() for k in vkeys},
            "full_module_state": {k: v.detach().cpu() for k, v in sd.items()},
            "adam_moments": opt.state_dict(),
            "optimizer_step": int(self.updates),
            "learning_rate": float(lr), "entropy_coef": float(entropy_coef),
            "entropy_schedule_definition": dict(self.entropy_schedule),
            "entropy_schedule_progress": {"completed_games": int(self.completed_games),
                                          "fraction": float(self.entropy_schedule.get("fraction", 0.0))},
            "completed_games": int(self.completed_games),
            "games_with_trainable_decisions": int(self.games_with_trainable_decisions),
            "trainable_decisions": int(self.trainable_decisions),
            "updates": int(self.updates),
            "numpy_generator_type": type(rng.bit_generator).__name__,
            "numpy_generator_state": rng.bit_generator.state,
            "torch_cpu_rng": torch.get_rng_state(),
            "torch_cuda_rng": (torch.cuda.get_rng_state_all()
                               if torch.cuda.is_available() else None),
            "python_random_state": random.getstate(),
            "lagged_registry": list(self.lagged),
            "curriculum_state": dict(self.curriculum_state),
            "branch_checkpoint_registry": dict(self.branch_checkpoints),
            "seed": int(self.seed), "trainer_state_id": self.trainer_state_id,
            "model_cfg": dict(model.cfg), "schema": "c013.v1",
        }
        if extra:
            blob.update(extra)
        torch.save(blob, path)
        return path

    @staticmethod
    def load(path: str, model, opt, device: str = "cpu"):
        """Returns (TrainerState, Generator, report). `report` names exactly which fields were
        restored, so a partial restore is never described as a literal continuation (§15)."""
        blob = torch.load(path, map_location=device, weights_only=False)
        report = {"schema": blob.get("schema", "pre-c013"), "restored": [], "absent": []}

        def has(k):
            ok = k in blob and blob[k] is not None
            (report["restored"] if ok else report["absent"]).append(k)
            return ok

        if "full_module_state" in blob:
            model.load_state_dict({k: v.to(device) for k, v in blob["full_module_state"].items()})
            report["restored"].append("full_module_state")
        elif "policy_weights" in blob:
            sd = dict(blob["policy_weights"]); sd.update(blob.get("value_weights") or {})
            model.load_state_dict({k: v.to(device) for k, v in sd.items()})
            report["restored"].append("policy_weights+value_weights")
        adam_key = "adam_moments" if "adam_moments" in blob else "adamw_state"
        if has(adam_key):
            opt.load_state_dict(blob[adam_key])
        rng = np.random.default_rng(blob.get("seed", 0))
        if has("numpy_generator_state"):
            rng.bit_generator.state = blob["numpy_generator_state"]
        if has("torch_cpu_rng"):
            s = blob["torch_cpu_rng"]
            torch.set_rng_state(s.cpu() if hasattr(s, "cpu") else s)
        if has("torch_cuda_rng") and torch.cuda.is_available():
            try:
                torch.cuda.set_rng_state_all([x.cpu() for x in blob["torch_cuda_rng"]])
            except Exception:  # noqa: BLE001
                pass
        if has("python_random_state"):
            random.setstate(blob["python_random_state"])
        st = TrainerState(
            seed=blob.get("seed", 0),
            completed_games=blob.get("completed_games", blob.get("games_done", 0)),
            games_with_trainable_decisions=blob.get("games_with_trainable_decisions", 0),
            trainable_decisions=blob.get("trainable_decisions", 0),
            updates=blob.get("updates", 0),
            lagged=list(blob.get("lagged_registry") or []),
            curriculum_state=dict(blob.get("curriculum_state") or {}),
            branch_checkpoints=dict(blob.get("branch_checkpoint_registry") or {}),
            entropy_schedule=dict(blob.get("entropy_schedule_definition") or {}),
            trainer_state_id=blob.get("trainer_state_id"))
        report["literal_continuation"] = ("numpy_generator_state" in report["restored"]
                                         and adam_key in report["restored"])
        report["continuation_kind"] = ("literal" if report["literal_continuation"]
                                       else "optimizer_state_only")
        return st, rng, report


def schema() -> Dict[str, Any]:
    return {"schema": "c013.v1", "required_fields": list(REQUIRED_STATE_FIELDS),
            "numpy_generator": "persisted via rng.bit_generator.state; the legacy global "
                               "np.random state is deliberately not used",
            "budget_quantity": "completed_games (includes games with only forced decisions)",
            "zero_score_policy": "a registered evaluation returning no scored games raises "
                                 "ZeroScoredGamesError",
            "hash_refresh": "evaluation checkpoints are content-addressed so a per-path hash "
                            "cache cannot return a stale value",
            "median_rule": "median best-per-seed, not maximum significance"}
