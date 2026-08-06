"""Compact structured action-scorer policies (c006 §10): S1 (stateless) and
S2 (recurrent GRU), built on the numpy autograd (cg.micrograd).

Both score every currently-legal option: score_i = MLP([context ; option_i]).
S2 adds one small GRU over the game's decision sequence (reset at game start,
previous context/action as explicit inputs) whose hidden state augments the
context. Decoding/loss are form-aware (single-choice softmax CE, unordered
multi-select per-option BCE) via cg.decoders / :func:`policy_loss`.

Training uses the autograd Node forward; inference uses an equivalent pure-numpy
forward (:meth:`np_scores`) — a parity test asserts they agree, so the model that
is evaluated and shipped is the model that was trained.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from cg.card_vocab import build_vocab
from cg.micrograd import Node, concat, gather_rows, param
from cg.policy_features import FEATURE_DIMS

GDENSE = FEATURE_DIMS["GDENSE"]
ODENSE = FEATURE_DIMS["ODENSE"]
PREV = FEATURE_DIMS["PREV"]

DEFAULT_CFG = {
    "emb": 32, "h": 160, "h2": 128,          # shared scorer sizes
    "cc": 64, "hr": 128,                       # S2 GRU compression + hidden
    "recurrent": False,
}


def _relu(x):
    return np.maximum(x, 0.0)


class PolicyModel:
    def __init__(self, cfg: Dict[str, Any], seed: int = 0):
        self.cfg = dict(DEFAULT_CFG)
        self.cfg.update(cfg or {})
        self.recurrent = bool(self.cfg["recurrent"])
        self.seed = seed
        rng = np.random.default_rng(seed)
        v = build_vocab()
        self.vocab_size = v["vocab_size"]
        E = self.cfg["emb"]; H = self.cfg["h"]; H2 = self.cfg["h2"]
        Cc = self.cfg["cc"]; Hr = self.cfg["hr"]
        gin = GDENSE + 2 * E
        oin = ODENSE + 2 * E
        ctx_dim = H + (Hr if self.recurrent else 0)
        sin = ctx_dim + oin
        p = {}
        p["E"] = param((self.vocab_size, E), 0.05, rng)
        p["Wg"] = param((gin, H), (1.0 / gin) ** 0.5, rng); p["bg"] = Node(np.zeros(H), requires_grad=True)
        p["W1"] = param((sin, H2), (1.0 / sin) ** 0.5, rng); p["b1"] = Node(np.zeros(H2), requires_grad=True)
        p["W3"] = param((H2, 1), (1.0 / H2) ** 0.5, rng); p["b3"] = Node(np.zeros(1), requires_grad=True)
        if self.recurrent:
            p["Wc"] = param((H, Cc), (1.0 / H) ** 0.5, rng); p["bc"] = Node(np.zeros(Cc), requires_grad=True)
            din = Cc + PREV
            for g in ("z", "r", "n"):
                p[f"W{g}"] = param((din, Hr), (1.0 / din) ** 0.5, rng)
                p[f"U{g}"] = param((Hr, Hr), (1.0 / Hr) ** 0.5, rng)
                p[f"b{g}"] = Node(np.zeros(Hr), requires_grad=True)
        self.p = p

    # ---------------- param utils ----------------
    def params(self) -> List[Node]:
        return [n for n in self.p.values() if n.requires_grad]

    def param_count(self) -> int:
        return int(sum(n.data.size for n in self.params()))

    def state_dict(self) -> Dict[str, np.ndarray]:
        return {k: v.data.copy() for k, v in self.p.items()}

    def load_state(self, sd: Dict[str, np.ndarray]):
        for k, arr in sd.items():
            self.p[k].data = np.asarray(arr, dtype=np.float64)

    def save(self, path: str):
        meta = np.array([self.cfg["emb"], self.cfg["h"], self.cfg["h2"], self.cfg["cc"],
                         self.cfg["hr"], int(self.recurrent), self.seed], dtype=np.int64)
        np.savez(path, __meta__=meta, **self.state_dict())

    @staticmethod
    def load(path: str) -> "PolicyModel":
        d = np.load(path, allow_pickle=False)
        m = d["__meta__"]
        cfg = {"emb": int(m[0]), "h": int(m[1]), "h2": int(m[2]), "cc": int(m[3]),
               "hr": int(m[4]), "recurrent": bool(m[5])}
        model = PolicyModel(cfg, seed=int(m[6]))
        model.load_state({k: d[k] for k in d.files if k != "__meta__"})
        return model

    # ---------------- Node forward (training) ----------------
    def _emb(self, rows_2d: np.ndarray) -> Node:
        # rows_2d [M,2] -> [M, 2E]
        M = rows_2d.shape[0]
        e = gather_rows(self.p["E"], rows_2d.reshape(-1))       # [2M, E]
        return e.reshape((M, 2 * self.cfg["emb"]))

    def _gctx(self, gdense: np.ndarray, grows: np.ndarray) -> Node:
        G = concat([Node(gdense), self._emb(grows)], axis=1)
        return (G.matmul(self.p["Wg"]) + self.p["bg"]).relu()

    def _score(self, ctx_rep: Node, odense_flat: np.ndarray, orows_flat: np.ndarray) -> Node:
        opt = concat([Node(odense_flat), self._emb(orows_flat)], axis=1)
        sin = concat([ctx_rep, opt], axis=1)
        h1 = (sin.matmul(self.p["W1"]) + self.p["b1"]).relu()
        return h1.matmul(self.p["W3"]) + self.p["b3"]              # [M,1]

    def _gru_step(self, x_t: Node, h_prev: Node) -> Node:
        p = self.p
        z = (x_t.matmul(p["Wz"]) + h_prev.matmul(p["Uz"]) + p["bz"]).sigmoid()
        r = (x_t.matmul(p["Wr"]) + h_prev.matmul(p["Ur"]) + p["br"]).sigmoid()
        n = (x_t.matmul(p["Wn"]) + (r * h_prev).matmul(p["Un"]) + p["bn"]).tanh()
        return z.one_minus() * n + z * h_prev

    def forward_ff(self, batch: Dict[str, np.ndarray]) -> Node:
        """Feed-forward (S1) scores for a padded batch. Returns Node [N,K]."""
        N, K = batch["legal_mask"].shape
        gctx = self._gctx(batch["gdense"], batch["grows"])        # [N,H]
        rep = np.repeat(np.arange(N), K)
        ctx_rep = gather_rows(gctx, rep)                          # [N*K,H]
        scores = self._score(ctx_rep,
                             batch["odense"].reshape(N * K, ODENSE),
                             batch["orows"].reshape(N * K, 2))
        return scores.reshape((N, K))

    def forward_game(self, game: Dict[str, np.ndarray]) -> Node:
        """Recurrent (S2) scores for one game's ordered decisions. Node [T,K]."""
        T, K = game["legal_mask"].shape
        Hr = self.cfg["hr"]
        gctx = self._gctx(game["gdense"], game["grows"])          # [T,H]
        xcomp = (gctx.matmul(self.p["Wc"]) + self.p["bc"]).relu()  # [T,Cc]
        x_seq = concat([xcomp, Node(game["prev"])], axis=1)        # [T,Cc+PREV]
        h = Node(np.zeros((1, Hr)))
        hs = []
        for t in range(T):
            x_t = gather_rows(x_seq, np.array([t]))
            h = self._gru_step(x_t, h)
            hs.append(h)
        h_all = concat(hs, axis=0)                                # [T,Hr]
        ctx2 = concat([gctx, h_all], axis=1)                      # [T,H+Hr]
        rep = np.repeat(np.arange(T), K)
        ctx_rep = gather_rows(ctx2, rep)
        scores = self._score(ctx_rep,
                             game["odense"].reshape(T * K, ODENSE),
                             game["orows"].reshape(T * K, 2))
        return scores.reshape((T, K))

    # ---------------- numpy forward (inference) ----------------
    def _np_emb(self, rows_2d):
        E = self.p["E"].data
        M = rows_2d.shape[0]
        return E[rows_2d.reshape(-1)].reshape(M, 2 * self.cfg["emb"])

    def _np_gctx(self, gdense, grows):
        G = np.concatenate([gdense, self._np_emb(grows)], axis=1)
        return _relu(G @ self.p["Wg"].data + self.p["bg"].data)

    def _np_scores_from_ctx(self, ctx_rep, odense_flat, orows_flat):
        opt = np.concatenate([odense_flat, self._np_emb(orows_flat)], axis=1)
        sin = np.concatenate([ctx_rep, opt], axis=1)
        h1 = _relu(sin @ self.p["W1"].data + self.p["b1"].data)
        return (h1 @ self.p["W3"].data + self.p["b3"].data)[:, 0]

    def _np_gru_step(self, x_t, h_prev):
        p = self.p
        sig = lambda a: 1.0 / (1.0 + np.exp(-a))
        z = sig(x_t @ p["Wz"].data + h_prev @ p["Uz"].data + p["bz"].data)
        r = sig(x_t @ p["Wr"].data + h_prev @ p["Ur"].data + p["br"].data)
        n = np.tanh(x_t @ p["Wn"].data + (r * h_prev) @ p["Un"].data + p["bn"].data)
        return (1 - z) * n + z * h_prev

    def np_scores(self, feat: Dict[str, Any], hidden: Optional[np.ndarray] = None):
        """Pure-numpy per-option scores for ONE decision. Returns (scores[n_opt], new_hidden).

        For S2 pass the running ``hidden`` (None at game start); the returned hidden
        must be fed to the next decision in the same game.
        """
        gdense = feat["gdense"][None, :]
        grows = feat["grows"][None, :]
        gctx = self._np_gctx(gdense, grows)                      # [1,H]
        new_hidden = hidden
        if self.recurrent:
            Hr = self.cfg["hr"]
            h_prev = np.zeros((1, Hr)) if hidden is None else hidden
            xcomp = _relu(gctx @ self.p["Wc"].data + self.p["bc"].data)
            x_t = np.concatenate([xcomp, feat["prev"][None, :]], axis=1)
            new_hidden = self._np_gru_step(x_t, h_prev)
            ctx = np.concatenate([gctx, new_hidden], axis=1)     # [1,H+Hr]
        else:
            ctx = gctx
        n = feat["n_options"]
        if n == 0:
            return np.zeros(0), new_hidden
        ctx_rep = np.repeat(ctx, n, axis=0)
        scores = self._np_scores_from_ctx(ctx_rep, feat["odense"], feat["orows"])
        return scores, new_hidden


# ---------------- unified form-aware policy loss ----------------

def policy_loss(logits: Node, single_mask, target_idx, multi_target, legal_mask, weight):
    """Weighted loss: single-choice rows use masked softmax CE, multi-select rows
    use masked per-option BCE. Returns (loss_node, probs) with manual backward.

    Shapes: logits[N,K]; single_mask[N]∈{0,1}; target_idx[N] (single rows);
    multi_target[N,K] (multi rows); legal_mask[N,K]; weight[N] (0 => ignored).
    """
    x = logits.data
    N, K = x.shape
    sm = np.asarray(single_mask, dtype=np.float64)
    lm = np.asarray(legal_mask, dtype=np.float64)
    w = np.asarray(weight, dtype=np.float64)
    tgt = np.asarray(target_idx, dtype=np.int64)
    mt = np.asarray(multi_target, dtype=np.float64)
    wsum = w.sum() if w.sum() > 0 else 1.0

    # softmax probs (masked) for single rows
    z = x.copy(); z[lm == 0] = -1e30
    z = z - z.max(axis=1, keepdims=True)
    ez = np.exp(z); psoft = ez / ez.sum(axis=1, keepdims=True)
    # sigmoid for multi rows
    ssig = 1.0 / (1.0 + np.exp(-x))
    per_row_n = np.maximum(lm.sum(axis=1), 1.0)

    row_loss = np.zeros(N)
    grad = np.zeros_like(x)
    for i in range(N):
        if w[i] == 0:
            continue
        if sm[i] == 1:
            row_loss[i] = -np.log(psoft[i, tgt[i]] + 1e-30)
            g = psoft[i].copy(); g[tgt[i]] -= 1.0
            grad[i] = g * (w[i] / wsum)
        else:
            bce = np.log1p(np.exp(-np.abs(x[i]))) + np.maximum(x[i], 0) - x[i] * mt[i]
            row_loss[i] = (bce * lm[i]).sum() / per_row_n[i]
            grad[i] = ((ssig[i] - mt[i]) * lm[i] / per_row_n[i]) * (w[i] / wsum)
    loss = (w * row_loss).sum() / wsum
    out = Node(loss, _parents=(logits,), _backward=None)

    def bw(g):
        if logits.requires_grad:
            logits._accum(g * grad)
    out._backward = bw
    return out, np.where(sm[:, None] == 1, psoft, ssig)
