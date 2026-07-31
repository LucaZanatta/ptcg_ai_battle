"""c022 — a prior provider backed by the FAITHFUL recurrent ByteRL network.

`cg/c021_transfer.py`'s provider loads a `ByteRLNet`: c021's feed-forward residual stack. The
c022 model is `ByteRLRecurrentNet` with LSTM-256, so pointing the existing provider at a c022
checkpoint raises `Error(s) in loading state_dict` and the transfer arm cannot run at all.

That is not a packaging detail. `MANDATORY_IMPLEMENTATION C` asks whether a component of the
**published** system improves corrected MCGS, and c021's transfer arms are recorded in this
contract as `UNTESTED` precisely because the checkpoint they queried was indistinguishable from an
untrained floor. Transferring from the faithful network is the whole point of running these arms
again.

## The adaptation this file has to make, stated plainly

The c022 policy is **recurrent**. Its action distribution is conditioned on an LSTM state that
accumulates over an episode. An MCGS node has no episode history — the search reaches it through a
tree, not through a trajectory — so there is no state to supply.

**Every query therefore starts from the network's zero initial state.** The prior is the
distribution the policy would assign on the first decision of an episode facing this observation,
not the distribution it would assign having played the game up to here.

This is a `SEMANTIC_GAME_ADAPTER` in the ledger's vocabulary and it is a real weakening: the
recurrence is the c022 model's defining feature over c021, and this queries it with the recurrence
switched off in all but name. It is recorded in `UNRESOLVED_REFERENCE_CHOICES.md`. The honest
consequence is that a null result from these arms is evidence about *a stateless query of a
recurrent policy*, not about the recurrent policy.

The alternative — replaying each node's line from the episode root to rebuild the state — costs a
forward pass per ply per node and was not affordable at the simulation counts these arms use.

## Defensive by construction

Any failure returns `None` and the search falls back to its source behaviour, exactly as the c021
provider does. An arm that silently degraded to its control would report the control's score under
the arm's name. `calls` and `failures` are counted so the registered protocol's requirement — that
every transfer arm show a nonzero call count for the component it enables — can be checked rather
than trusted.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)


class C022RecurrentPriorProvider:
    """Queries the faithful LSTM-256 policy for option scores at an MCGS node."""

    def __init__(self, checkpoint_path: str, pool=None, device: str = "cpu",
                 temperature: float = 1.0):
        import torch
        from cg import c021_byterl_deck as DK
        from cg import c022_byterl_action as AC
        from cg import c022_byterl_encode as EN
        from cg import c022_byterl_model as M

        torch.set_num_threads(1)
        self.torch, self.EN, self.AC, self.M = torch, EN, AC, M
        self.device = device
        self.temperature = float(temperature)
        self.pool = pool or DK.CardPool.from_archetypes()

        dims = EN.dims()
        state = torch.load(checkpoint_path, map_location=device, weights_only=False)
        self.net = M.fresh(dims["global_dim"], dims["slot_dim"], dims["option_dim"],
                           self.pool.size(), n_cards=dims["n_cards"], seed=0)
        self.net.load_state_dict(state)
        self.net.eval()
        self.head = AC.BattleActionHead(self.net)

        self.checkpoint = checkpoint_path
        self.calls = 0
        self.failures = 0
        self.seconds = 0.0
        # Counted separately from `failures`: a query the encoder could not represent is a
        # different event from a query the network refused, and collapsing them would hide which.
        self.encode_failures = 0

    def option_scores(self, observation, n_options: int) -> Optional[np.ndarray]:
        """Probabilities over the first `n_options` legal options, or None on any failure.

        Same signature and same defensive contract as the c021 provider, so
        `c021_transfer.sample_untested` and `rollout_pick` consume it unchanged.
        """
        import time as _time
        _t0 = _time.perf_counter()
        self.calls += 1
        try:
            enc = self.EN.encode_battle(observation, None, None)
        except Exception:  # noqa: BLE001
            self.encode_failures += 1
            self.failures += 1
            return None
        try:
            n = min(int(enc["n_options"]), int(n_options))
            if n <= 0:
                self.failures += 1
                return None
            tt = self.EN.to_torch(enc, self.device)
            legal = tt["opt_mask"].clone()
            legal[:, n:] = 0.0
            with self.torch.no_grad():
                # ZERO STATE. See the module docstring: an MCGS node carries no episode history,
                # so this is the first-decision distribution rather than the in-context one.
                h, _ = self.net.step(self.EN.obs_parts(tt),
                                     self.net.initial_state(1, self.device))
                # The ELEMENT head scores individual options, which is what a prior over "which
                # untested action to expand" needs. The COUNT head chooses how many to pick and
                # is not a per-option quantity.
                picked = self.torch.zeros_like(legal)
                logits = self.head._element_logits(h, tt["opt"], tt["option_cards"], picked)
                logits = logits / max(self.temperature, 1e-6)
                lp = self.M.masked_log_softmax(logits, legal)
                p = lp.exp()[0, :n].detach().cpu().numpy().astype(np.float64)
            s = float(p.sum())
            if not np.isfinite(s) or s <= 0:
                self.failures += 1
                return None
            return p / s
        except Exception:  # noqa: BLE001
            self.failures += 1
            return None
        finally:
            self.seconds += _time.perf_counter() - _t0

    def report(self) -> Dict[str, Any]:
        return {"provider": "C022RecurrentPriorProvider",
                "checkpoint": os.path.basename(self.checkpoint),
                "calls": self.calls, "failures": self.failures,
                "encode_failures": self.encode_failures,
                "seconds_in_provider": round(self.seconds, 3),
                "mean_inference_ms": (round(1000 * self.seconds / self.calls, 3)
                                      if self.calls else None),
                "recurrent_state": "zeroed per query (SEMANTIC_GAME_ADAPTER)",
                "success_rate": (round(1 - self.failures / self.calls, 4)
                                 if self.calls else None)}
