"""c021 B1 — the ByteRL policy/value network, from the LOCM and Hearthstone papers.

Sources (no author implementation exists; see results/fidelity/byterl_source_search.md):
  * arXiv:2303.04096 — the original LOCM ByteRL agent
  * arXiv:2303.05197 — the Hearthstone improvements

`FIDELITY_RULES §4` forbids simplifying the architecture or the algorithm to fit the hardware.
Hardware may reduce ONLY actor count, sample count, duration and achieved learning periods. So
every structural element the papers specify is present here at full width, and the reductions are
taken later, in the training loop.

Structure, and why each piece is not optional:

  * **Separate policy and value trunks.** The papers use a shared torso with distinct heads; the
    value head must not be a linear probe on the policy logits or V-trace has no independent
    baseline to correct against.
  * **Autoregressive multi-select.** A PTCG select carries `minCount..maxCount`, so an action is a
    SET, not an index. The joint log-probability is the sum of per-element conditional
    log-probabilities under the running mask -- exactly the factorization V-trace and UPGO need.
    c019 and c020 both scored multi-select actions as if they were single picks.
  * **Distinct active and bench slot tokens.** c020's encoder collapsed them, so the model could
    not tell "attack with the active" from "attack with a benched Pokemon". Slot identity enters
    as a learned embedding indexed by slot role.
  * **Legal-action masking inside the distribution**, not after sampling, so an illegal action has
    exactly zero probability and contributes no gradient.
  * **Two stages, one network.** Construction and battle share the torso and carry a stage flag,
    with separate value heads so 60 near-zero-information construction prefixes cannot swamp the
    battle gradient (B2).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

NEG_INF = -1e9


def masked_log_softmax(logits: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """Log-softmax over legal entries only.

    Masking must happen INSIDE the distribution. Sampling first and rejecting illegal actions
    afterwards leaves probability mass on illegal actions, and every gradient that flows through
    that mass is wrong.
    """
    logits = logits.masked_fill(mask <= 0, NEG_INF)
    return F.log_softmax(logits, dim=-1)


class ResidualBlock(nn.Module):
    def __init__(self, width: int, dropout: float = 0.0):
        super().__init__()
        self.fc1 = nn.Linear(width, width)
        self.fc2 = nn.Linear(width, width)
        self.ln1 = nn.LayerNorm(width)
        self.ln2 = nn.LayerNorm(width)
        self.drop = nn.Dropout(dropout) if dropout > 0 else nn.Identity()

    def forward(self, x):
        h = F.relu(self.ln1(self.fc1(x)))
        h = self.drop(h)
        h = self.ln2(self.fc2(h))
        return F.relu(x + h)


class SlotEncoder(nn.Module):
    """Board encoding with DISTINCT active and bench slot identity.

    c020 fed active and bench through the same projection with no slot token, so the network was
    structurally unable to distinguish the active Pokemon from a benched one -- and "attack with
    the active" is a different action from "attack with a benched Pokemon".
    """

    ACTIVE, BENCH = 0, 1

    def __init__(self, feat_dim: int, width: int, max_bench: int = 5):
        super().__init__()
        self.max_bench = max_bench
        self.slot_role = nn.Embedding(2, width)            # active vs bench: never collapsed
        self.slot_index = nn.Embedding(max_bench + 1, width)  # which bench seat
        self.side = nn.Embedding(2, width)                 # mine vs theirs
        self.proj = nn.Linear(feat_dim, width)
        self.block = ResidualBlock(width)

    def forward(self, slots: torch.Tensor, roles: torch.Tensor,
                indices: torch.Tensor, sides: torch.Tensor) -> torch.Tensor:
        h = self.proj(slots)
        h = h + self.slot_role(roles) + self.slot_index(indices) + self.side(sides)
        return self.block(h)


class ByteRLNet(nn.Module):
    """Policy and value network for both stages.

    `action_dim` is the per-option feature width; options are scored by a bilinear form against
    the state embedding, so the head does not assume a fixed action-set size. PTCG option counts
    vary from 2 to several hundred, and a fixed-size head would either truncate or waste.
    """

    def __init__(self, global_dim: int, slot_dim: int, option_dim: int,
                 pool_dim: int, width: int = 256, blocks: int = 4,
                 max_bench: int = 5):
        super().__init__()
        self.width = width
        self.global_dim = global_dim
        self.slot_dim = slot_dim
        self.option_dim = option_dim
        self.pool_dim = pool_dim

        self.slots = SlotEncoder(slot_dim, width, max_bench)
        self.global_proj = nn.Linear(global_dim, width)
        self.stage_embed = nn.Embedding(2, width)          # 0 = battle, 1 = construction
        self.torso = nn.ModuleList([ResidualBlock(width) for _ in range(blocks)])

        # ---- battle policy: score each legal option against the state
        self.option_proj = nn.Sequential(nn.Linear(option_dim, width), nn.ReLU(),
                                         nn.Linear(width, width))
        self.query = nn.Linear(width, width)
        self.option_bias = nn.Linear(width, 1)
        # autoregressive multi-select: what has already been picked conditions the next pick
        self.selected_summary = nn.Linear(width, width)

        # ---- construction policy: one logit per pool card
        self.pool_head = nn.Sequential(nn.Linear(width, width), nn.ReLU(),
                                       nn.Linear(width, pool_dim))

        # ---- SEPARATE value heads per stage (B2): construction credit must not swamp battle
        self.value_battle = nn.Sequential(nn.Linear(width, width), nn.ReLU(),
                                          nn.Linear(width, 1))
        self.value_construction = nn.Sequential(nn.Linear(width, width), nn.ReLU(),
                                                nn.Linear(width, 1))
        self._init()

    def _init(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=math.sqrt(2))
                nn.init.zeros_(m.bias)
        # small final layers so the initial policy is near-uniform and the initial value near 0
        for head in (self.value_battle, self.value_construction, self.pool_head):
            nn.init.orthogonal_(head[-1].weight, gain=0.01)
            nn.init.zeros_(head[-1].bias)
        nn.init.orthogonal_(self.option_bias.weight, gain=0.01)
        nn.init.zeros_(self.option_bias.bias)

    # ------------------------------------------------------------------ trunk
    def encode(self, g: torch.Tensor, slots: torch.Tensor, roles: torch.Tensor,
               indices: torch.Tensor, sides: torch.Tensor,
               stage: torch.Tensor) -> torch.Tensor:
        s = self.slots(slots, roles, indices, sides)       # (B, S, W)
        s = s.mean(dim=1)
        h = self.global_proj(g) + s + self.stage_embed(stage)
        for b in self.torso:
            h = b(h)
        return h

    # ------------------------------------------------------------------ heads
    def battle_logits(self, h: torch.Tensor, options: torch.Tensor,
                      selected_mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        """Score every option. `selected_mask` conditions on picks already made this step."""
        o = self.option_proj(options)                       # (B, A, W)
        q = self.query(h)                                   # (B, W)
        if selected_mask is not None:
            picked = (o * selected_mask.unsqueeze(-1)).sum(dim=1)
            denom = selected_mask.sum(dim=1, keepdim=True).clamp(min=1.0)
            q = q + self.selected_summary(picked / denom)
        return (o * q.unsqueeze(1)).sum(-1) / math.sqrt(self.width) + \
            self.option_bias(o).squeeze(-1)

    def construction_logits(self, h: torch.Tensor) -> torch.Tensor:
        return self.pool_head(h)

    def value(self, h: torch.Tensor, stage: torch.Tensor) -> torch.Tensor:
        vb = self.value_battle(h).squeeze(-1)
        vc = self.value_construction(h).squeeze(-1)
        return torch.where(stage > 0, vc, vb)

    # ------------------------------------------------------------------ autoregressive select
    def select_logprob(self, h: torch.Tensor, options: torch.Tensor, legal: torch.Tensor,
                       chosen: List[int]) -> torch.Tensor:
        """Joint log-probability of choosing the SET `chosen`, in order, under running masks.

        log p(a_1..a_k | s) = sum_i log p(a_i | s, a_1..a_{i-1})

        This is the factorization V-trace and UPGO require. Scoring a k-element select as a single
        index -- which c019 and c020 both did -- makes the importance ratio wrong by however much
        the remaining k-1 picks were worth, so every off-policy correction downstream is biased.
        """
        total = h.new_zeros(())
        picked = torch.zeros_like(legal)
        avail = legal.clone()
        for a in chosen:
            logits = self.battle_logits(h, options, picked)
            lp = masked_log_softmax(logits, avail)
            total = total + lp[0, a]
            # Rebuild the masks instead of writing into them. `picked` feeds the option-summary
            # term inside `battle_logits`, so its backward pass needs the tensor it actually saw;
            # an in-place `picked[0, a] = 1.0` bumps the version counter and autograd refuses the
            # earlier step's gradient ("variable needed for gradient computation has been
            # modified by an inplace operation").
            step = torch.zeros_like(legal)
            step[0, a] = 1.0
            picked = picked + step
            avail = avail * (1.0 - step)            # no PTCG select repeats an option
        return total

    @torch.no_grad()
    def sample_select(self, h: torch.Tensor, options: torch.Tensor, legal: torch.Tensor,
                      min_count: int, max_count: int, rng=None,
                      temperature: float = 1.0) -> Tuple[List[int], float]:
        """Sample a legal SET and return it with its exact joint log-probability."""
        picked = torch.zeros_like(legal)
        avail = legal.clone()
        chosen: List[int] = []
        total = 0.0
        n_legal = int(legal.sum().item())
        k_max = max(1, min(int(max_count) if max_count else 1, n_legal))
        k_min = max(1, min(int(min_count) if min_count else 1, k_max))
        # How many to take is itself a decision when min < max. The first version looped to
        # k_max unconditionally, so the policy ALWAYS took the maximum allowed -- it could never
        # learn to discard two cards instead of three. The count is sampled uniformly over the
        # legal range; the papers give no distribution for it, and it is recorded in
        # UNRESOLVED_REFERENCE_CHOICES as a Chosen decision.
        if k_max > k_min:
            k_target = int(rng.integers(k_min, k_max + 1)) if rng is not None else \
                int(torch.randint(k_min, k_max + 1, (1,)).item())
        else:
            k_target = k_min
        for i in range(k_target):
            if avail.sum() <= 0:
                break
            logits = self.battle_logits(h, options, picked) / max(temperature, 1e-6)
            lp = masked_log_softmax(logits, avail)
            p = lp.exp()[0]
            idx = int(torch.multinomial(p, 1).item()) if rng is None else \
                int(rng.choice(len(p), p=(p / p.sum()).cpu().numpy()))
            total += float(lp[0, idx].item())
            chosen.append(idx)
            step = torch.zeros_like(legal)
            step[0, idx] = 1.0
            picked = picked + step
            avail = avail * (1.0 - step)
        return chosen, total


def count_parameters(m: nn.Module) -> int:
    return sum(p.numel() for p in m.parameters() if p.requires_grad)


def fresh(global_dim: int, slot_dim: int, option_dim: int, pool_dim: int,
          width: int = 256, blocks: int = 4, seed: int = 0) -> ByteRLNet:
    """B1/B3: ByteRL starts from FRESH RANDOM WEIGHTS.

    No distillation from a scripted teacher, no warm start from a c0xx checkpoint. The papers
    train from scratch through self-play, and a warm start would make every learning-period
    comparison meaningless.
    """
    torch.manual_seed(seed)
    return ByteRLNet(global_dim, slot_dim, option_dim, pool_dim, width, blocks)
