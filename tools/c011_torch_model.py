"""c011 §9 — the existing c007/c008 policy+value architecture, in PyTorch.

This is a BACKEND port, not a new model (§5): identical layers, identical activations,
identical masked-pool semantics, identical masked action factorisation. Weights are the same
NPZ tensors; nothing is re-parameterised and no layer is added or removed.

Deliberately dtype-parameterised. The legacy micrograd graph is float64 throughout, so
FP32-vs-float64 comparison conflates two questions: "is the port semantically correct?" and
"how much does single precision cost?". Running this module in float64 answers the first
exactly (expect ~1e-12); running it in float32 measures the second. §10.1's tolerance applies
to the FP32 configuration, and the float64 row is the diagnosis §10.1 demands if FP32 is
tight -- not an excuse to widen the bar.

Reproduced exactly from the legacy implementation:
  * `_masked_pool`: mean divides by max(count, 1); max adds (mask-1)*1e9 and is then gated by
    `has_any`, so a fully-empty set pools to 0 in both branches rather than leaking a
    sentinel;
  * `masked_log_softmax`: illegal entries are forced to -1e30 BEFORE the max subtraction and
    their probability is exactly 0;
  * multi-select: sequential without-replacement picks over [K options + STOP], summing
    per-step masked log-probs; entropy is the FIRST-step entropy only.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, Optional

import numpy as np
import torch
import torch.nn as nn

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import card_vocab, state_encoder_v2 as enc  # noqa: E402
from cg import policy_model_v2 as pm  # noqa: E402

NEG = 1e30
POOL_NEG = 1e9


class TorchPolicy(nn.Module):
    """ModelV2 trunk (V2-A) + value head + global STOP logit."""

    def __init__(self, cfg: Optional[Dict[str, int]] = None, dtype=torch.float32,
                 device="cpu"):
        super().__init__()
        self.cfg = dict(pm.default_cfg())
        if cfg:
            self.cfg.update(cfg)
        self.dt = dtype
        vocab = card_vocab.build_vocab()
        self.vocab_size = vocab["vocab_size"]
        # deterministic, non-trainable card semantics [V,52]
        self.register_buffer("FEAT", torch.tensor(vocab["feature_matrix"], dtype=dtype))
        c = self.cfg
        D = c["D"]

        def lin(fi, fo):
            m = nn.Linear(fi, fo, bias=True, dtype=dtype)
            return m

        self.sem = lin(enc.CARD_FEAT, D)
        self.emb = nn.Parameter(torch.zeros(self.vocab_size, D, dtype=dtype))
        self.slot = lin(D + enc.SLOT_DYN, c["Hs"])
        self.board = lin(enc.N_BOARD * c["Hs"], c["BV"])
        self.hand = lin(D + enc.HAND_DYN, c["Hh"])
        self.handv = lin(2 * c["Hh"], c["HV"])
        self.disc = lin(D, c["Hd"])
        self.discv = lin(2 * c["Hd"], c["DV"])
        self.glob = lin(enc.GLOBAL, c["GH"])
        self.ctx = lin(c["BV"] + c["HV"] + c["DV"] + c["GH"], c["CTX"])
        self.opt = lin(enc.OPT_DENSE + 2 * D, c["OH"])
        self.optc = lin(c["OH"] + c["CTX"], c["OH2"])
        self.score = lin(c["OH2"] + 2 * c["OH2"] + c["CTX"], c["SH"])
        self.score2 = lin(c["SH"], 1)
        self.vW1 = lin(c["CTX"], 128)
        self.vW2 = lin(128, 1)
        self.stop = nn.Parameter(torch.zeros(1, dtype=dtype))
        self.to(device)
        self.dev = device

    # ---- weight interchange with the legacy NPZ layout ----
    _TRUNK = {"sem": "sem", "slot": "slot", "board": "board", "hand": "hand", "handv": "handv",
              "disc": "disc", "discv": "discv", "glob": "glob", "ctx": "ctx", "opt": "opt",
              "optc": "optc", "score": "score", "score2": "score2"}
    _PV = {"vW1": "vW1", "vW2": "vW2"}

    def load_legacy_state(self, sd: Dict[str, np.ndarray]):
        """Accepts an RLPolicy.state_dict() (trunk::NAME / pv::NAME). Legacy stores weights
        as [fan_in, fan_out]; nn.Linear stores [fan_out, fan_in], so every matrix is
        transposed exactly once."""
        with torch.no_grad():
            for lname, attr in self._TRUNK.items():
                W = sd[f"trunk::{lname}"]
                b = sd[f"trunk::{lname}_b"]
                mod = getattr(self, attr)
                mod.weight.copy_(torch.tensor(np.ascontiguousarray(W.T), dtype=self.dt))
                mod.bias.copy_(torch.tensor(b, dtype=self.dt))
            self.emb.copy_(torch.tensor(sd["trunk::emb"], dtype=self.dt))
            for lname, attr in self._PV.items():
                W = sd[f"pv::{lname}"]              # vW1 / vW2
                b = sd[f"pv::vb{lname[-1]}"]        # vb1 / vb2
                mod = getattr(self, attr)
                mod.weight.copy_(torch.tensor(np.ascontiguousarray(W.T), dtype=self.dt))
                mod.bias.copy_(torch.tensor(b, dtype=self.dt))
            self.stop.copy_(torch.tensor(sd["pv::stop"], dtype=self.dt))
        return self

    def export_legacy_state(self) -> Dict[str, np.ndarray]:
        """Back to the runtime NPZ layout (§9: export to the existing NPZ format)."""
        sd = {}
        with torch.no_grad():
            for lname, attr in self._TRUNK.items():
                mod = getattr(self, attr)
                sd[f"trunk::{lname}"] = mod.weight.detach().cpu().double().numpy().T.copy()
                sd[f"trunk::{lname}_b"] = mod.bias.detach().cpu().double().numpy().copy()
            sd["trunk::emb"] = self.emb.detach().cpu().double().numpy().copy()
            for lname, attr in self._PV.items():
                mod = getattr(self, attr)
                sd[f"pv::{lname}"] = mod.weight.detach().cpu().double().numpy().T.copy()
                sd[f"pv::vb{lname[-1]}"] = mod.bias.detach().cpu().double().numpy().copy()
            sd["pv::stop"] = self.stop.detach().cpu().double().numpy().copy()
        return sd

    # ---- forward pieces ----
    def _card_repr(self, rows: torch.Tensor) -> torch.Tensor:
        feats = self.FEAT[rows]                      # [...,52]
        sem = torch.relu(self.sem(feats))
        return sem + self.emb[rows]

    @staticmethod
    def _masked_pool(x: torch.Tensor, mask: torch.Tensor, axis: int) -> torch.Tensor:
        """mean-pool ++ max-pool, matching the legacy sentinel handling exactly."""
        m = mask.to(x.dtype)
        s = m.sum(dim=axis, keepdim=True)                       # [B,1]
        cnt = torch.clamp(s, min=1.0)
        has_any = (s > 0).to(x.dtype)
        m3 = m.unsqueeze(-1)
        summed = (x * m3).sum(dim=axis)
        mean = summed / cnt
        neg = ((m - 1.0) * POOL_NEG).unsqueeze(-1)
        mx = (x + neg).max(dim=axis).values * has_any
        return torch.cat([mean, mx], dim=-1)

    def forward(self, b: Dict[str, torch.Tensor]):
        c = self.cfg
        B = b["global"].shape[0]
        board_card = self._card_repr(b["board_rows"])
        board_in = torch.cat([board_card, b["board_dyn"]], dim=-1)
        slot = torch.relu(self.slot(board_in))
        board_vec = torch.relu(self.board(slot.reshape(B, enc.N_BOARD * c["Hs"])))

        hand_card = self._card_repr(b["hand_rows"])
        hand_in = torch.cat([hand_card, b["hand_dyn"]], dim=-1)
        hand_h = torch.relu(self.hand(hand_in))
        hand_vec = torch.relu(self.handv(self._masked_pool(hand_h, b["hand_mask"], 1)))

        disc_card = self._card_repr(b["disc_rows"])
        disc_h = torch.relu(self.disc(disc_card))
        disc_vec = torch.relu(self.discv(self._masked_pool(disc_h, b["disc_mask"], 1)))

        glob = torch.relu(self.glob(b["global"]))
        ctx = torch.relu(self.ctx(torch.cat([board_vec, hand_vec, disc_vec, glob], dim=-1)))

        K = b["opt_dense"].shape[1]
        prim = self._card_repr(b["opt_rows"][:, :, 0])
        targ = self._card_repr(b["opt_rows"][:, :, 1])
        opt_in = torch.cat([b["opt_dense"], prim, targ], dim=-1)
        opt_base = torch.relu(self.opt(opt_in))
        ctx3 = ctx.unsqueeze(1).expand(B, K, c["CTX"])
        opt_rep = torch.relu(self.optc(torch.cat([opt_base, ctx3], dim=-1)))
        opt_pool = self._masked_pool(opt_rep, b["opt_mask"], 1)
        pool3 = opt_pool.unsqueeze(1).expand(B, K, 2 * c["OH2"])
        score_h = torch.relu(self.score(torch.cat([opt_rep, pool3, ctx3], dim=-1)))
        scores = self.score2(score_h).reshape(B, K)

        vh = torch.relu(self.vW1(ctx))
        value = self.vW2(vh).reshape(B)
        return scores, value, ctx

    def aug_scores(self, scores: torch.Tensor) -> torch.Tensor:
        B = scores.shape[0]
        return torch.cat([scores, self.stop.reshape(1, 1).expand(B, 1)], dim=-1)


def masked_log_softmax(aug: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """Legacy semantics: illegal -> -1e30 before the max subtraction, probability exactly 0."""
    neg = mask == 0
    z = aug.masked_fill(neg, -NEG)
    zmax = z.max(dim=-1, keepdim=True).values
    zc = z - zmax
    ez = torch.exp(zc).masked_fill(neg, 0.0)
    s = ez.sum(dim=-1, keepdim=True)
    logp = zc - torch.log(s)
    return logp.masked_fill(neg, -NEG)


def evaluate(model: TorchPolicy, b: Dict[str, torch.Tensor], act: Dict[str, torch.Tensor]):
    """Differentiable PPO evaluate: summed masked log-prob, first-step entropy, value.

    Mirrors RLPolicy.evaluate step for step, including that the running mask drops a chosen
    option only for valid, non-STOP picks, and that entropy is the first-step entropy over
    the BASE mask.
    """
    scores, value, _ = model(b)
    B, K = scores.shape
    aug = model.aug_scores(scores)
    base_mask = act["aug_mask"]
    seq = act["action_seq"]
    seq_len = act["seq_len"]
    L = seq.shape[1]
    running = base_mask.clone()
    logprob = torch.zeros(B, dtype=aug.dtype, device=aug.device)
    entropy = torch.zeros(B, dtype=aug.dtype, device=aug.device)
    first_logp = None
    ar = torch.arange(B, device=aug.device)
    for t in range(L):
        logp_all = masked_log_softmax(aug, running)
        valid = (t < seq_len).to(aug.dtype)
        a_t = torch.where(seq[:, t] >= 0, seq[:, t], torch.zeros_like(seq[:, t]))
        step_lp = logp_all[ar, a_t]
        logprob = logprob + step_lp * valid
        if t == 0:
            first_logp = logp_all
            p = torch.exp(logp_all)
            entropy = -(p * logp_all * base_mask).sum(dim=1)
        # drop chosen (valid, non-STOP) options from the running mask
        drop = (t < seq_len) & (seq[:, t] != K) & (seq[:, t] >= 0)
        if drop.any():
            running = running.clone()
            idx = ar[drop]
            running[idx, seq[idx, t]] = 0.0
    return logprob, entropy, value, first_logp


def to_torch_batch(b: Dict[str, np.ndarray], dtype, device) -> Dict[str, torch.Tensor]:
    """NumPy collate output -> tensors. Index arrays stay integer; everything else takes the
    model dtype."""
    INT = {"board_rows", "hand_rows", "disc_rows", "opt_rows"}
    out = {}
    for k, v in b.items():
        if k in INT:
            out[k] = torch.as_tensor(np.asarray(v), dtype=torch.long, device=device)
        else:
            out[k] = torch.as_tensor(np.asarray(v), dtype=dtype, device=device)
    return out


def to_torch_act(arr: Dict[str, np.ndarray], dtype, device) -> Dict[str, torch.Tensor]:
    return {"aug_mask": torch.as_tensor(arr["aug_mask"], dtype=dtype, device=device),
            "action_seq": torch.as_tensor(arr["action_seq"], dtype=torch.long, device=device),
            "seq_len": torch.as_tensor(arr["seq_len"], dtype=torch.long, device=device),
            "K": arr["K"]}
