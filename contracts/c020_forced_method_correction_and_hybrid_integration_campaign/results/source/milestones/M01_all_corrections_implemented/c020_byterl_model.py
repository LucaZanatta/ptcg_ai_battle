"""c020 B2/B3 — option scorer over gathered source/target objects, autoregressive multi-select.

Two corrections live here.

**B2** — the policy scores each legal option against the state AND the object representations it
references, by GATHERING the source/target board tokens by index. c019 scored options against a
pooled board summary, so two options differing only in which bench slot they touched were
indistinguishable. A learned null token (index `BOARD_SLOTS`) stands in for "no source" or "no
target", rather than zeros, so absence is a value the network can learn rather than an ambiguity.

**B3** — a decision selecting k items is modelled autoregressively: pick 1, update the mask,
pick 2 conditioned on pick 1, and so on, accumulating a JOINT log probability. c019 stored the
first index and its probability only (audit #9), which makes the importance ratio in V-trace wrong
for every multi-select decision — it compares the probability of a fragment against the
probability of a fragment under a different policy, while the environment executed the whole set.
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c020_byterl_encode as E  # noqa: E402

LSTM_HIDDEN = 256          # registered source default (CONTRACT §6)
MODEL_VERSION = "c020.byterl.model.v1"

# explicit per-tensor ranks so a 1-D mask is never broadcast against a 3-D tensor
SAMPLE_NDIM = {"board": 2, "hand": 2, "global": 1, "opt": 2, "opt_mask": 1,
               "opt_src": 1, "opt_tgt": 1, "n_options": 0, "min_count": 0, "max_count": 0}


def to_torch(f: Dict[str, np.ndarray], device="cpu") -> Dict[str, torch.Tensor]:
    """One encoded observation -> a batch of size 1, with correct ranks."""
    out = {}
    for k, v in f.items():
        t = torch.as_tensor(np.asarray(v), device=device)
        if t.dtype in (torch.float64,):
            t = t.float()
        out[k] = t.unsqueeze(0)
    return out


class PTCGByteRL(nn.Module):
    """Slot-aware encoder, LSTM memory, option scorer with gathered source/target, value head."""

    def __init__(self, d_board: int = 96, d_hand: int = 64, d_ctx: int = 192,
                 lstm_hidden: int = LSTM_HIDDEN, d_opt: int = 96):
        super().__init__()
        self.cfg = {"d_board": d_board, "d_hand": d_hand, "d_ctx": d_ctx,
                    "lstm_hidden": lstm_hidden, "d_opt": d_opt,
                    "version": MODEL_VERSION, "encoder": E.schema()["version"]}
        self.board_enc = nn.Sequential(nn.Linear(E.BOARD_DIM, d_board), nn.ReLU(),
                                       nn.Linear(d_board, d_board), nn.ReLU())
        self.hand_enc = nn.Sequential(nn.Linear(E.HAND_DIM, d_hand), nn.ReLU())
        # learned NULL board token for options with no source/target (B2)
        self.null_board = nn.Parameter(torch.zeros(d_board))
        # explicit slot position embedding -- slot identity must survive pooling (B1)
        self.slot_pos = nn.Parameter(torch.randn(E.BOARD_SLOTS, d_board) * 0.02)

        self.ctx = nn.Sequential(
            nn.Linear(E.GLOBAL_DIM + d_board * 2 + d_hand, d_ctx), nn.ReLU(),
            nn.Linear(d_ctx, d_ctx), nn.ReLU())
        self.lstm = nn.LSTMCell(d_ctx, lstm_hidden)

        self.opt_enc = nn.Sequential(nn.Linear(E.OPT_DIM, d_opt), nn.ReLU())
        # autoregressive context: what has already been picked in THIS decision (B3)
        self.pick_ctx = nn.Sequential(nn.Linear(d_opt + 2, d_opt), nn.ReLU())
        self.policy = nn.Sequential(
            nn.Linear(lstm_hidden + d_opt + d_board * 2 + d_opt, 256), nn.ReLU(),
            nn.Linear(256, 1))
        self.value = nn.Sequential(nn.Linear(lstm_hidden, 128), nn.ReLU(), nn.Linear(128, 1))

    # ---------------------------------------------------------------- encoding
    def encode_state(self, b: Dict[str, torch.Tensor]):
        board = self.board_enc(b["board"])                       # (B, 12, d)
        board = board + self.slot_pos.unsqueeze(0)               # explicit slot identity
        hand = self.hand_enc(b["hand"])                          # (B, H, d)
        # summaries are used only for CONTEXT; option scoring gathers per-object below
        my = board[:, :1 + E.BENCH_SLOTS].mean(dim=1)
        op = board[:, 1 + E.BENCH_SLOTS:].mean(dim=1)
        hs = hand.mean(dim=1)
        ctx = self.ctx(torch.cat([b["global"], my, op, hs], dim=-1))
        return ctx, board

    def forward(self, b: Dict[str, torch.Tensor], state=None,
                picked: Optional[torch.Tensor] = None):
        """Returns (option_logits, value, next_state)."""
        ctx, board = self.encode_state(b)
        B = ctx.shape[0]
        if state is None:
            h = torch.zeros(B, self.cfg["lstm_hidden"], device=ctx.device, dtype=ctx.dtype)
            c = torch.zeros_like(h)
        else:
            h, c = state
        h, c = self.lstm(ctx, (h, c))

        opt = self.opt_enc(b["opt"])                             # (B, N_OPT, d_opt)
        # B2: GATHER the referenced source/target objects, with a learned null
        board_ext = torch.cat([board, self.null_board.view(1, 1, -1).expand(B, 1, -1)], dim=1)
        src = torch.gather(board_ext, 1,
                           b["opt_src"].unsqueeze(-1).expand(-1, -1, board_ext.shape[-1]))
        tgt = torch.gather(board_ext, 1,
                           b["opt_tgt"].unsqueeze(-1).expand(-1, -1, board_ext.shape[-1]))

        n = opt.shape[1]
        hh = h.unsqueeze(1).expand(B, n, h.shape[-1])
        if picked is None:
            picked = torch.zeros(B, n, self.cfg["d_opt"], device=ctx.device, dtype=ctx.dtype)
        logits = self.policy(torch.cat([hh, opt, src, tgt, picked], dim=-1)).squeeze(-1)
        v = torch.tanh(self.value(h)).squeeze(-1)
        return logits, v, (h, c)

    # ---------------------------------------------------------------- B3
    def select_autoregressive(self, b: Dict[str, torch.Tensor], state=None,
                              k: int = 1, greedy: bool = False,
                              generator: Optional[torch.Generator] = None
                              ) -> Dict[str, Any]:
        """Pick k items one at a time, each conditioned on the previous picks.

        Returns the full ordered selection, per-step probabilities, and the JOINT log
        probability — the quantity V-trace actually needs (B5).
        """
        ctx, board = self.encode_state(b)
        B = ctx.shape[0]
        assert B == 1, "autoregressive selection is per-decision"
        mask = b["opt_mask"].clone()
        n_avail = int(mask.sum().item())
        k = max(1, min(k, max(1, n_avail)))

        opt_raw = self.opt_enc(b["opt"])
        picked_sum = torch.zeros(B, self.cfg["d_opt"], device=ctx.device, dtype=ctx.dtype)
        selected: List[int] = []
        steps: List[Dict[str, Any]] = []
        joint_logp = 0.0
        h, c = (state if state is not None else
                (torch.zeros(B, self.cfg["lstm_hidden"], device=ctx.device, dtype=ctx.dtype),
                 torch.zeros(B, self.cfg["lstm_hidden"], device=ctx.device, dtype=ctx.dtype)))
        h, c = self.lstm(ctx, (h, c))

        board_ext = torch.cat([board, self.null_board.view(1, 1, -1).expand(B, 1, -1)], dim=1)
        src = torch.gather(board_ext, 1,
                           b["opt_src"].unsqueeze(-1).expand(-1, -1, board_ext.shape[-1]))
        tgt = torch.gather(board_ext, 1,
                           b["opt_tgt"].unsqueeze(-1).expand(-1, -1, board_ext.shape[-1]))
        n = opt_raw.shape[1]

        for step in range(k):
            ctx_feat = torch.cat([picked_sum,
                                  torch.full((B, 1), step / 8.0, device=ctx.device),
                                  torch.full((B, 1), (k - step) / 8.0, device=ctx.device)],
                                 dim=-1)
            picked_vec = self.pick_ctx(ctx_feat).unsqueeze(1).expand(B, n, self.cfg["d_opt"])
            hh = h.unsqueeze(1).expand(B, n, h.shape[-1])
            logits = self.policy(torch.cat([hh, opt_raw, src, tgt, picked_vec],
                                           dim=-1)).squeeze(-1)
            logits = logits.masked_fill(mask <= 0, float("-inf"))
            logp = F.log_softmax(logits, dim=-1)
            probs = logp.exp()
            if greedy:
                idx = int(torch.argmax(probs, dim=-1).item())
            else:
                idx = int(torch.multinomial(probs[0], 1, generator=generator).item())
            joint_logp += float(logp[0, idx].item())
            steps.append({"step": step, "chosen": idx,
                          "logp": float(logp[0, idx].item()),
                          "prob": float(probs[0, idx].item()),
                          "entropy": float(-(probs[0] * logp[0].clamp(min=-30)).nansum().item()),
                          "n_legal": int((mask[0] > 0).sum().item())})
            selected.append(idx)
            mask = mask.clone()
            mask[0, idx] = 0.0                      # B3: mask update between picks
            picked_sum = picked_sum + opt_raw[:, idx]
            if int(mask.sum().item()) == 0:
                break

        v = torch.tanh(self.value(h)).squeeze(-1)
        return {"selected": selected, "steps": steps, "joint_logp": joint_logp,
                "value": float(v[0].item()), "state": (h, c), "k": len(selected)}

    def joint_logp_of(self, b: Dict[str, torch.Tensor], selected: List[int],
                      state=None) -> Tuple[torch.Tensor, torch.Tensor, Any]:
        """Recompute the JOINT log probability of an ALREADY CHOSEN ordered selection.

        This is what the learner calls, and it must walk the same autoregressive path the actor
        walked — same masks, same order, same recurrent state — or the V-trace ratio is comparing
        two different quantities (audit #11). Differentiable.
        """
        ctx, board = self.encode_state(b)
        B = ctx.shape[0]
        h, c = (state if state is not None else
                (torch.zeros(B, self.cfg["lstm_hidden"], device=ctx.device, dtype=ctx.dtype),
                 torch.zeros(B, self.cfg["lstm_hidden"], device=ctx.device, dtype=ctx.dtype)))
        h, c = self.lstm(ctx, (h, c))
        opt_raw = self.opt_enc(b["opt"])
        board_ext = torch.cat([board, self.null_board.view(1, 1, -1).expand(B, 1, -1)], dim=1)
        src = torch.gather(board_ext, 1,
                           b["opt_src"].unsqueeze(-1).expand(-1, -1, board_ext.shape[-1]))
        tgt = torch.gather(board_ext, 1,
                           b["opt_tgt"].unsqueeze(-1).expand(-1, -1, board_ext.shape[-1]))
        n = opt_raw.shape[1]
        mask = b["opt_mask"].clone()
        picked_sum = torch.zeros(B, self.cfg["d_opt"], device=ctx.device, dtype=ctx.dtype)
        total = torch.zeros(B, device=ctx.device, dtype=ctx.dtype)
        ent = torch.zeros(B, device=ctx.device, dtype=ctx.dtype)
        k = max(1, len(selected))
        for step, idx in enumerate(selected or [0]):
            ctx_feat = torch.cat([picked_sum,
                                  torch.full((B, 1), step / 8.0, device=ctx.device),
                                  torch.full((B, 1), (k - step) / 8.0, device=ctx.device)],
                                 dim=-1)
            picked_vec = self.pick_ctx(ctx_feat).unsqueeze(1).expand(B, n, self.cfg["d_opt"])
            hh = h.unsqueeze(1).expand(B, n, h.shape[-1])
            logits = self.policy(torch.cat([hh, opt_raw, src, tgt, picked_vec],
                                           dim=-1)).squeeze(-1)
            logits = logits.masked_fill(mask <= 0, float("-inf"))
            logp = F.log_softmax(logits, dim=-1)
            i = int(idx)
            if i < logp.shape[-1] and torch.isfinite(logp[:, i]).all():
                total = total + logp[:, i]
                p = logp.exp()
                ent = ent - (p * logp.clamp(min=-30)).nan_to_num(0.0).sum(dim=-1)
            mask = mask.clone()
            if i < mask.shape[-1]:
                mask[:, i] = 0.0
            picked_sum = picked_sum + opt_raw[:, i]
        v = torch.tanh(self.value(h)).squeeze(-1)
        return total, v, (h, c), ent / max(1, k)


def masked_probs(logits: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    return F.softmax(logits.masked_fill(mask <= 0, float("-inf")), dim=-1)


def architecture_report(model: "PTCGByteRL") -> Dict[str, Any]:
    return {"version": MODEL_VERSION, "cfg": model.cfg,
            "parameters": sum(p.numel() for p in model.parameters()),
            "encoder": E.schema(),
            "corrects": ["#7 slot pooling (slot_pos + per-slot gather)",
                         "#8 typed energy/status/tool/target (encoder + opt_src/opt_tgt)",
                         "#9 first-pick-only (select_autoregressive / joint_logp_of)"]}
