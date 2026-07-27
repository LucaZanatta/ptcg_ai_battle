"""c019 Branch B — PTCG-ByteRL recurrent masked policy/value network.

METHOD_FIDELITY B: card embeddings + scalars, visible zones both sides, current select context,
per-option encoding with typed references, **LSTM hidden size 256**, dynamic legal-option logits
with exact-zero probability for unavailable options, and a value head.

The option scorer is a bilinear interaction between the recurrent context and each option's
features rather than a fixed-width output layer. PTCG's legal option set changes size and meaning
every decision, so a fixed head would have to learn a positional convention the engine does not
guarantee — the same reason `c019_core` identifies options by key rather than index.

Fresh random initialization is mandatory (§9.1): this is not a continuation of c018's distilled
or PPO checkpoints.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_byterl_encode as E  # noqa: E402

MODEL_VERSION = "c019.byterl.model.v1"
LSTM_HIDDEN = 256          # registered source value (Hearthstone ByteRL); do not change silently
NEG_INF = -1e9


class PTCGByteRL(nn.Module):
    def __init__(self, d_card: int = 64, d_zone: int = 96, d_ctx: int = 192,
                 lstm_hidden: int = LSTM_HIDDEN, d_opt: int = 96):
        super().__init__()
        self.cfg = {"d_card": d_card, "d_zone": d_zone, "d_ctx": d_ctx,
                    "lstm_hidden": lstm_hidden, "d_opt": d_opt,
                    "version": MODEL_VERSION, "encoder": E.ENCODER_VERSION}
        V = E.vocab_size()
        CF = E.card_feature_dim()
        self.register_buffer("FEAT", torch.tensor(E._vocab()[1], dtype=torch.float32))
        self.emb = nn.Embedding(V, d_card)
        self.sem = nn.Linear(CF, d_card)
        self.card_dyn = nn.Linear(d_card + E.CARD_DYN, d_card)

        # one encoder per zone: a hand card and an opposing benched Pokemon play different roles
        self.z_hand = nn.Linear(2 * d_card, d_zone)
        self.z_board = nn.Linear(2 * d_card, d_zone)
        self.z_opp = nn.Linear(2 * d_card, d_zone)
        self.z_disc = nn.Linear(2 * d_card, d_zone)
        self.z_odisc = nn.Linear(2 * d_card, d_zone)
        self.glob = nn.Linear(E.GLOBAL_DIM, d_zone)
        self.fuse = nn.Linear(6 * d_zone, d_ctx)

        self.lstm = nn.LSTMCell(d_ctx, lstm_hidden)

        self.opt_enc = nn.Linear(E.OPT_DIM + d_card, d_opt)
        self.opt_ctx = nn.Linear(lstm_hidden, d_opt)
        self.score = nn.Linear(2 * d_opt, 1)

        self.v1 = nn.Linear(lstm_hidden, 128)
        self.v2 = nn.Linear(128, 1)

    # ---------------------------------------------------------------- helpers
    def _card_repr(self, rows: torch.Tensor, dyn: torch.Tensor) -> torch.Tensor:
        base = self.emb(rows) + torch.relu(self.sem(self.FEAT[rows]))
        return torch.relu(self.card_dyn(torch.cat([base, dyn], dim=-1)))

    @staticmethod
    def _pool(x: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        """mean ++ max over occupied slots; an empty zone pools to exactly zero."""
        m = mask.unsqueeze(-1)
        s = m.sum(dim=1)
        mean = (x * m).sum(dim=1) / s.clamp(min=1.0)
        neg = x.masked_fill(m == 0, -1e9)
        mx = neg.max(dim=1).values
        has = (s > 0).float()
        return torch.cat([mean * has, mx * has], dim=-1)

    def initial_state(self, batch: int, device="cpu") -> Tuple[torch.Tensor, torch.Tensor]:
        h = torch.zeros(batch, self.cfg["lstm_hidden"], device=device)
        return h, h.clone()

    # ---------------------------------------------------------------- forward
    def forward(self, b: Dict[str, torch.Tensor],
                state: Optional[Tuple[torch.Tensor, torch.Tensor]] = None):
        B = b["global"].shape[0]
        dev = b["global"].device
        if state is None:
            state = self.initial_state(B, dev)

        hand = self._pool(self._card_repr(b["hand_rows"], b["hand_dyn"]), b["hand_mask"])
        board = self._pool(self._card_repr(b["board_rows"], b["board_dyn"]), b["board_mask"])
        opp = self._pool(self._card_repr(b["opp_rows"], b["opp_dyn"]), b["opp_mask"])
        disc = self._pool(self._card_repr(b["disc_rows"], b["disc_dyn"]), b["disc_mask"])
        odisc = self._pool(self._card_repr(b["odisc_rows"], b["odisc_dyn"]), b["odisc_mask"])

        z = torch.cat([torch.relu(self.z_hand(hand)), torch.relu(self.z_board(board)),
                       torch.relu(self.z_opp(opp)), torch.relu(self.z_disc(disc)),
                       torch.relu(self.z_odisc(odisc)),
                       torch.relu(self.glob(b["global"]))], dim=-1)
        ctx = torch.relu(self.fuse(z))

        h, c = self.lstm(ctx, state)

        K = b["opt_feat"].shape[1]
        opt_card = self.emb(b["opt_rows"]) + torch.relu(self.sem(self.FEAT[b["opt_rows"]]))
        oe = torch.relu(self.opt_enc(torch.cat([b["opt_feat"], opt_card], dim=-1)))
        hc = torch.relu(self.opt_ctx(h)).unsqueeze(1).expand(B, K, self.cfg["d_opt"])
        logits = self.score(torch.cat([oe, hc], dim=-1)).squeeze(-1)

        # B01: unavailable options receive EXACTLY zero probability after masking
        logits = logits.masked_fill(b["opt_mask"] == 0, NEG_INF)
        value = self.v2(torch.relu(self.v1(h))).squeeze(-1)
        return logits, value, (h, c)

    # ---------------------------------------------------------------- inference
    @torch.no_grad()
    def act(self, feats: Dict[str, np.ndarray],
            state: Optional[Tuple[torch.Tensor, torch.Tensor]] = None,
            greedy: bool = False, device="cpu", generator=None):
        b = to_torch(feats, device)
        logits, value, nxt = self.forward(b, state)
        probs = masked_probs(logits, b["opt_mask"])
        n = int(feats["n_options"]) if np.ndim(feats["n_options"]) == 0 else 1
        k = min(n, E.N_OPT)
        if k <= 0:
            return 0, 0.0, logits[0], value.item(), nxt
        p = probs[0, :k]
        p = p / p.sum().clamp(min=1e-12)
        idx = int(torch.argmax(p)) if greedy else int(
            torch.multinomial(p, 1, generator=generator))
        return idx, float(p[idx]), logits[0], float(value[0]), nxt


def masked_probs(logits: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """Softmax that gives masked entries exactly 0.0, not a small positive number."""
    z = logits.masked_fill(mask == 0, NEG_INF)
    p = F.softmax(z, dim=-1)
    return p * mask


# Per-sample rank of every tensor. Inferring "is this batched?" from ndim alone silently
# mis-broadcasts a 1-D mask against a 3-D card tensor, so the ranks are stated explicitly.
SAMPLE_NDIM = {
    "global": 1,
    "hand_rows": 1, "hand_dyn": 2, "hand_mask": 1,
    "board_rows": 1, "board_dyn": 2, "board_mask": 1,
    "opp_rows": 1, "opp_dyn": 2, "opp_mask": 1,
    "disc_rows": 1, "disc_dyn": 2, "disc_mask": 1,
    "odisc_rows": 1, "odisc_dyn": 2, "odisc_mask": 1,
    "opt_feat": 2, "opt_rows": 1, "opt_mask": 1,
}


def to_torch(feats, device="cpu") -> Dict[str, torch.Tensor]:
    """One encoded decision (or an already-stacked batch) -> tensors with a batch dim."""
    out = {}
    for k in E.TENSOR_KEYS:
        v = np.asarray(feats[k])
        if v.ndim == SAMPLE_NDIM[k]:
            v = v[None, ...]
        elif v.ndim != SAMPLE_NDIM[k] + 1:
            raise ValueError(f"{k}: expected per-sample ndim {SAMPLE_NDIM[k]} or batched "
                             f"{SAMPLE_NDIM[k] + 1}, got shape {v.shape}")
        out[k] = torch.as_tensor(
            np.ascontiguousarray(v),
            dtype=(torch.long if k in E.LONG_KEYS else torch.float32), device=device)
    return out


def new_model(seed: int = 1901, device="cpu") -> PTCGByteRL:
    """§9.1: fresh random weights. Never a continuation of a c018 checkpoint."""
    torch.manual_seed(seed)
    m = PTCGByteRL()
    m.to(device)
    return m
