"""c022 B1/B2 — the published ByteRL recurrent policy/value network, from fresh random weights.

Authority (`FIDELITY_RULES §1`): no author implementation exists — c021's search is reproduced and
extended in `results/fidelity/byterl_source_search.md` — so the authorities are, in order, the
LOCM ByteRL paper (arXiv:2303.04096), the Hearthstone improvements paper (arXiv:2303.05197), and
IMPALA (arXiv:1802.01561) where those two explicitly inherit from it. This is PAPER fidelity and
is reported as such; claiming source fidelity for ByteRL would be false.

What `CONTRACT.md §3.4` says c021 lacked, and this module supplies:

* **LSTM recurrence, hidden size 256.** c021 was a feed-forward residual stack with no state
  crossing timesteps, verified in the reconciliation by the absence of `nn.LSTM` and `nn.GRU`.
  `MANDATORY_IMPLEMENTATION B1` forbids a feed-forward substitute, and `FIDELITY_RULES §4` fixes
  the hidden size at 256.
* **Shared representations.** One card/Pokémon embedding table is shared by every slot, the hand,
  the discard and the construction pool, so a card learned in one place is known in all of them.
* **Explicit active slot and ORDERED bench slots.** Slot role and bench index are separate
  embeddings; c020 collapsed them and the network could not distinguish attacking with the active
  from attacking with a benched Pokémon.
* **A complete autoregressive action.** A PTCG decision is a variable-length token sequence, not
  an index. See `c022_byterl_action.py`; this module supplies the per-step scoring the sequence
  consumes, conditioned on the recurrent state and on the tokens already emitted this step.

The recurrent contract, which `PROBE_MATRIX B06/B07` check:

    the LSTM advances ONCE PER ENVIRONMENT DECISION, not once per action token.

A PTCG decision emits several tokens; if the hidden state advanced per token, an unroll's
timestep count would depend on how many tokens each decision happened to need, and the learner
could not replay it from a stored `(h0, c0)` without also replaying the tokenization. Within a
decision the autoregressive head conditions on the tokens already chosen through a separate,
stateless summary. So the recurrence is over decisions and the autoregression is within one.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

NEG_INF = -1e9

# FIDELITY_RULES §4: "LSTM hidden size = 256".
LSTM_HIDDEN = 256


def masked_log_softmax(logits: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """Log-softmax over legal entries only.

    Masking must happen INSIDE the distribution. Sampling and then rejecting leaves probability
    mass on illegal actions, and every gradient flowing through that mass is wrong.
    """
    logits = logits.masked_fill(mask <= 0, NEG_INF)
    return F.log_softmax(logits, dim=-1)


class ResidualBlock(nn.Module):
    def __init__(self, width: int):
        super().__init__()
        self.fc1 = nn.Linear(width, width)
        self.fc2 = nn.Linear(width, width)
        self.ln1 = nn.LayerNorm(width)
        self.ln2 = nn.LayerNorm(width)

    def forward(self, x):
        h = F.relu(self.ln1(self.fc1(x)))
        h = self.ln2(self.fc2(h))
        return F.relu(x + h)


class SharedCardEmbedding(nn.Module):
    """One embedding table for every place a card can appear.

    `MANDATORY_IMPLEMENTATION B1` requires "shared card/Pokémon embeddings". Sharing is what makes
    the construction stage and the battle stage teach each other: choosing a card during deck
    construction and later playing it index the same row.
    """

    def __init__(self, n_cards: int, dim: int):
        super().__init__()
        # index 0 is the reserved EMPTY card, so an absent slot is a real embedding rather than a
        # zero vector that collides with a genuinely zero-valued card.
        self.emb = nn.Embedding(n_cards + 1, dim, padding_idx=0)
        self.dim = dim
        self.n_cards = n_cards

    def forward(self, ids: torch.Tensor) -> torch.Tensor:
        return self.emb(ids.clamp(min=0, max=self.n_cards))


class SlotEncoder(nn.Module):
    """Board encoding with distinct active/bench roles and ORDERED bench positions."""

    ACTIVE, BENCH = 0, 1

    def __init__(self, feat_dim: int, width: int, card_dim: int, max_bench: int = 5):
        super().__init__()
        self.max_bench = max_bench
        self.slot_role = nn.Embedding(2, width)               # active vs bench: never collapsed
        self.slot_index = nn.Embedding(max_bench + 1, width)  # WHICH bench seat
        self.side = nn.Embedding(2, width)                    # mine vs theirs
        self.proj = nn.Linear(feat_dim + card_dim, width)
        self.block = ResidualBlock(width)

    def forward(self, slots, roles, indices, sides, card_vec) -> torch.Tensor:
        h = self.proj(torch.cat([slots, card_vec], dim=-1))
        h = h + self.slot_role(roles) + self.slot_index(indices) + self.side(sides)
        return self.block(h)


class ByteRLRecurrentNet(nn.Module):
    """Shared torso -> LSTM(256) -> policy and value heads.

    Both heads read the RECURRENT features (`MANDATORY_IMPLEMENTATION B1`: "policy and value heads
    using recurrent features"), so a value that is right only because it saw the whole history is
    a value the policy gradient can actually use.
    """

    def __init__(self, global_dim: int, slot_dim: int, option_dim: int, pool_dim: int,
                 n_cards: int = 4096, card_dim: int = 64, width: int = 256,
                 blocks: int = 3, lstm_hidden: int = LSTM_HIDDEN, max_bench: int = 5,
                 n_token_types: int = 8):
        super().__init__()
        self.width = width
        self.lstm_hidden = int(lstm_hidden)
        self.global_dim = global_dim
        self.slot_dim = slot_dim
        self.option_dim = option_dim
        self.pool_dim = pool_dim
        self.n_cards = n_cards

        self.cards = SharedCardEmbedding(n_cards, card_dim)
        self.slots = SlotEncoder(slot_dim, width, card_dim, max_bench)
        self.global_proj = nn.Linear(global_dim, width)
        self.stage_embed = nn.Embedding(2, width)           # 0 = battle, 1 = construction
        # hand / discard / visible construction context, all through the SHARED card table
        self.hand_proj = nn.Linear(card_dim, width)
        self.discard_proj = nn.Linear(card_dim, width)
        self.torso = nn.ModuleList([ResidualBlock(width) for _ in range(blocks)])

        # ---- recurrence. batch_first, one step per ENVIRONMENT DECISION.
        self.lstm = nn.LSTM(width, self.lstm_hidden, num_layers=1, batch_first=True)
        self.post = nn.Linear(self.lstm_hidden, width)

        # ---- battle policy: score each legal option against the recurrent state
        self.option_card = nn.Linear(card_dim, width)
        self.option_proj = nn.Sequential(nn.Linear(option_dim, width), nn.ReLU(),
                                         nn.Linear(width, width))
        self.query = nn.Linear(width, width)
        self.option_bias = nn.Linear(width, 1)
        # within-decision autoregression: what has been picked so far, and which token slot we
        # are on. Both are STATELESS with respect to the LSTM, by design (see module docstring).
        self.selected_summary = nn.Linear(width, width)
        self.token_type = nn.Embedding(n_token_types, width)

        # ---- construction policy: one logit per pool card
        self.pool_head = nn.Sequential(nn.Linear(width, width), nn.ReLU(),
                                       nn.Linear(width, pool_dim))

        # ---- SEPARATE value heads per stage (B6): 60 near-zero-information construction
        # prefixes per episode must not swamp the battle value gradient.
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
        for name, p in self.lstm.named_parameters():
            if "weight_ih" in name or "weight_hh" in name:
                nn.init.orthogonal_(p)
            elif "bias" in name:
                nn.init.zeros_(p)
                # forget-gate bias to 1: the standard LSTM initialisation, so the state is not
                # erased before the network has learned anything worth keeping.
                n = p.shape[0] // 4
                p.data[n:2 * n].fill_(1.0)
        for head in (self.value_battle, self.value_construction, self.pool_head):
            nn.init.orthogonal_(head[-1].weight, gain=0.01)
            nn.init.zeros_(head[-1].bias)
        nn.init.orthogonal_(self.option_bias.weight, gain=0.01)
        nn.init.zeros_(self.option_bias.bias)

    # ------------------------------------------------------------------ state
    def initial_state(self, batch: int = 1, device=None) -> Tuple[torch.Tensor, torch.Tensor]:
        """`(h0, c0)` for a fresh episode. Stored with every unroll (`B3`)."""
        z = torch.zeros(1, batch, self.lstm_hidden,
                        device=device or next(self.parameters()).device)
        return z.clone(), z.clone()

    # ------------------------------------------------------------------ trunk
    def observe(self, g, slots, roles, indices, sides, slot_cards, hand_cards,
                discard_cards, stage) -> torch.Tensor:
        """Per-decision observation embedding, BEFORE recurrence. Shape (B, T, W).

        Accepts either (B, ...) for a single step or (B, T, ...) for an unroll; a single step is
        promoted to T=1 so the learner and the actor run the SAME code path. Two code paths is
        how a learner/actor mismatch gets shipped, and probe B06 exists because that mismatch is
        silent when it happens.
        """
        squeeze = (g.dim() == 2)
        if squeeze:
            g = g.unsqueeze(1)
            slots = slots.unsqueeze(1)
            roles = roles.unsqueeze(1)
            indices = indices.unsqueeze(1)
            sides = sides.unsqueeze(1)
            slot_cards = slot_cards.unsqueeze(1)
            hand_cards = hand_cards.unsqueeze(1)
            discard_cards = discard_cards.unsqueeze(1)
            stage = stage.unsqueeze(1)
        B, T = g.shape[0], g.shape[1]
        S = slots.shape[2]

        cv = self.cards(slot_cards.reshape(B * T, S))
        s = self.slots(slots.reshape(B * T, S, -1), roles.reshape(B * T, S),
                       indices.reshape(B * T, S), sides.reshape(B * T, S), cv)
        s = s.mean(dim=1)

        hv = self.cards(hand_cards.reshape(B * T, -1))
        # masked mean over the hand: index 0 is EMPTY, so padding must not drag the mean to zero
        hm = (hand_cards.reshape(B * T, -1) > 0).float().unsqueeze(-1)
        hv = (hv * hm).sum(1) / hm.sum(1).clamp(min=1.0)

        dv = self.cards(discard_cards.reshape(B * T, -1))
        dm = (discard_cards.reshape(B * T, -1) > 0).float().unsqueeze(-1)
        dv = (dv * dm).sum(1) / dm.sum(1).clamp(min=1.0)

        h = (self.global_proj(g.reshape(B * T, -1)) + s
             + self.hand_proj(hv) + self.discard_proj(dv)
             + self.stage_embed(stage.reshape(B * T)))
        for b in self.torso:
            h = b(h)
        return h.reshape(B, T, self.width)

    def recur(self, x: torch.Tensor, state: Tuple[torch.Tensor, torch.Tensor]
              ) -> Tuple[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """Advance the LSTM over T decisions. Returns per-step features and the final state."""
        y, new_state = self.lstm(x, state)
        return F.relu(self.post(y)), new_state

    def step(self, obs_parts: Dict[str, torch.Tensor],
             state: Tuple[torch.Tensor, torch.Tensor]
             ) -> Tuple[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """One decision: observe -> recur. Returns (B, W) features and the new state."""
        x = self.observe(**obs_parts)
        y, ns = self.recur(x, state)
        return y[:, -1], ns

    # ------------------------------------------------------------------ heads
    def battle_logits(self, h: torch.Tensor, options: torch.Tensor, option_cards: torch.Tensor,
                      selected_mask: Optional[torch.Tensor] = None,
                      token_type: Optional[torch.Tensor] = None) -> torch.Tensor:
        """Score every option against the recurrent state and the tokens already emitted."""
        o = self.option_proj(options) + self.option_card(self.cards(option_cards))
        q = self.query(h)
        if token_type is not None:
            q = q + self.token_type(token_type)
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


def count_parameters(m: nn.Module) -> int:
    return sum(p.numel() for p in m.parameters() if p.requires_grad)


def fresh(global_dim: int, slot_dim: int, option_dim: int, pool_dim: int,
          n_cards: int = 4096, width: int = 256, blocks: int = 3,
          lstm_hidden: int = LSTM_HIDDEN, seed: int = 0) -> ByteRLRecurrentNet:
    """FRESH RANDOM WEIGHTS.

    `CONTRACT.md §2` forbids initializing from the c021 fixed-deck B2 checkpoint, and
    `TRAINING_AND_EVALUATION §2` repeats it: "Do not warm-start from c021 weights." A warm start
    would make every learning-period comparison meaningless, and the c021 network is a different
    architecture besides — it has no recurrent parameters at all.
    """
    torch.manual_seed(seed)
    return ByteRLRecurrentNet(global_dim, slot_dim, option_dim, pool_dim,
                              n_cards=n_cards, width=width, blocks=blocks,
                              lstm_hidden=lstm_hidden)
