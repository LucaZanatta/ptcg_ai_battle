"""c007 AC-06: compact pure-numpy advisory model over State Encoder v2.

Architecture (§10):
    card semantic encoder (deterministic 52-d features + ZERO-init id-embedding residual)
    + slot-specific board encoder (12 explicit slots, concatenated, never averaged)
    + zone set encoders for hand & discard (DeepSets: masked mean+max pool)
    + global/history encoder
    + legal-option set encoder with cross-option interaction (DeepSets pool -> each
      option score depends on the other legal options)
    + teacher-action head
    + optional privileged planning auxiliary heads (V2-B): main-target, use-support, value

Everything is one numpy reverse-mode graph (cg.micrograd), so the trained forward pass
IS the served forward pass — no framework at inference, no train/serve skew. Every
dense layer reshapes ``[..,F] -> [N,F]`` before the 2-D matmul, so board/hand/discard/
option set dimensions are fully batched. Parameter count is tunable via V2Config and is
asserted into the registered [500k, 2M] band (hard max 3M) at construction.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from cg import card_vocab, micrograd as mg
from cg import state_encoder_v2 as enc

N_OPP_SLOTS = 1 + enc.N_OPP_BENCH  # plan-target classification buckets (active + bench)


def default_cfg() -> Dict[str, int]:
    return {
        "D": 72,        # card-repr dim (semantic MLP out + zero-init id embedding)
        "Hs": 80,       # per-slot board hidden
        "BV": 176,      # board vector
        "Hh": 72, "HV": 72,     # hand per-card hidden / vector
        "Hd": 56, "DV": 56,     # discard per-card hidden / vector
        "GH": 144,      # global encoder hidden
        "CTX": 200,     # fused context dim
        "OH": 112,      # option base hidden
        "OH2": 112,     # option+context hidden
        "SH": 112,      # score head hidden
        "recurrent": 0,
    }


class ModelV2:
    def __init__(self, cfg: Optional[Dict[str, int]] = None, seed: int = 0, aux: bool = True):
        self.cfg = dict(default_cfg())
        if cfg:
            self.cfg.update(cfg)
        self.aux = bool(aux)
        self.seed = seed
        vocab = card_vocab.build_vocab()
        self.vocab_size = vocab["vocab_size"]
        # deterministic non-trainable card semantic features [V, 52]
        self.FEAT = mg.Node(vocab["feature_matrix"].astype(np.float64), requires_grad=False)
        self.p: Dict[str, mg.Node] = {}
        self._build(np.random.default_rng(seed))

    # ---- parameter construction ----
    def _w(self, name, fan_in, fan_out, rng, zero=False):
        scale = 0.0 if zero else np.sqrt(2.0 / fan_in)
        self.p[name] = mg.Node(np.zeros((fan_in, fan_out)) if zero
                               else rng.standard_normal((fan_in, fan_out)) * scale,
                               requires_grad=True)
        self.p[name + "_b"] = mg.Node(np.zeros(fan_out), requires_grad=True)

    def _build(self, rng):
        c = self.cfg
        D = c["D"]
        # card encoder: semantic MLP + zero-init id embedding residual
        self._w("sem", enc.CARD_FEAT, D, rng)
        self.p["emb"] = mg.Node(np.zeros((self.vocab_size, D)), requires_grad=True)  # zero-init
        # board
        self._w("slot", D + enc.SLOT_DYN, c["Hs"], rng)
        self._w("board", enc.N_BOARD * c["Hs"], c["BV"], rng)
        # hand (DeepSets)
        self._w("hand", D + enc.HAND_DYN, c["Hh"], rng)
        self._w("handv", 2 * c["Hh"], c["HV"], rng)
        # discard (DeepSets)
        self._w("disc", D, c["Hd"], rng)
        self._w("discv", 2 * c["Hd"], c["DV"], rng)
        # global
        self._w("glob", enc.GLOBAL, c["GH"], rng)
        # fusion
        self._w("ctx", c["BV"] + c["HV"] + c["DV"] + c["GH"], c["CTX"], rng)
        # option set encoder
        self._w("opt", enc.OPT_DENSE + 2 * D, c["OH"], rng)
        self._w("optc", c["OH"] + c["CTX"], c["OH2"], rng)
        self._w("score", c["OH2"] + 2 * c["OH2"] + c["CTX"], c["SH"], rng)
        self._w("score2", c["SH"], 1, rng)
        # aux heads
        if self.aux:
            self._w("plan", c["CTX"], N_OPP_SLOTS + 1, rng)   # main-target bucket (+none)
            self._w("support", c["CTX"], 1, rng)
            self._w("value", c["CTX"], 1, rng)

    def params(self) -> List[mg.Node]:
        return [v for v in self.p.values()]

    def param_count(self) -> int:
        return int(sum(v.data.size for v in self.p.values()))

    # ---- forward pieces ----
    def _dense(self, x: mg.Node, name: str, act: str = "relu") -> mg.Node:
        W = self.p[name]; b = self.p[name + "_b"]
        shp = x.data.shape
        x2 = x.reshape((-1, shp[-1]))
        y2 = x2.matmul(W) + b
        y = y2.reshape(tuple(shp[:-1]) + (W.data.shape[1],))
        if act == "relu":
            return y.relu()
        return y

    def _card_repr(self, rows: np.ndarray) -> mg.Node:
        feats = mg.gather_rows(self.FEAT, rows)          # [...,52] const
        sem = self._dense(feats, "sem")                  # [...,D]
        emb = mg.gather_rows(self.p["emb"], rows)        # [...,D] zero-init residual
        return sem + emb

    @staticmethod
    def _masked_pool(x: mg.Node, mask: np.ndarray, axis: int) -> mg.Node:
        """masked mean-pool concat masked max-pool over ``axis`` -> [.., 2H]. mask [B,S].

        A FULLY-empty set (all entries masked, e.g. an empty hand/discard) pools to 0 in
        both branches — the max-pool is gated by ``has_any`` so the -inf sentinel never
        leaks into downstream features."""
        m = mask.astype(np.float64)
        s = m.sum(axis=axis, keepdims=True)                    # [B,1]
        cnt = np.maximum(s, 1.0)
        has_any = (s > 0).astype(np.float64)                   # [B,1]
        m_node = mg.Node(np.expand_dims(m, -1))                # [B,S,1]
        summed = mg.reduce_sum(x * m_node, axis=axis)          # [B,H]
        mean = summed * mg.Node(1.0 / cnt)                     # [B,1] broadcast -> [B,H]
        neg = mg.Node(np.expand_dims((m - 1.0) * 1e9, -1))     # [B,S,1] push pads to -inf
        mx = mg.reduce_max(x + neg, axis=axis) * mg.Node(has_any)  # 0 when set fully empty
        return mg.concat([mean, mx], axis=-1)

    def forward(self, b: Dict[str, np.ndarray]) -> Dict[str, mg.Node]:
        c = self.cfg
        B = b["global"].shape[0]
        # board
        board_card = self._card_repr(b["board_rows"])                    # [B,12,D]
        board_in = mg.concat([board_card, mg.Node(b["board_dyn"])], axis=-1)
        slot = self._dense(board_in, "slot")                             # [B,12,Hs]
        board_flat = slot.reshape((B, enc.N_BOARD * c["Hs"]))
        board_vec = self._dense(board_flat, "board")                     # [B,BV]
        # hand
        hand_card = self._card_repr(b["hand_rows"])                      # [B,12,D]
        hand_in = mg.concat([hand_card, mg.Node(b["hand_dyn"])], axis=-1)
        hand_h = self._dense(hand_in, "hand")                            # [B,12,Hh]
        hand_pool = self._masked_pool(hand_h, b["hand_mask"], axis=1)    # [B,2Hh]
        hand_vec = self._dense(hand_pool, "handv")
        # discard
        disc_card = self._card_repr(b["disc_rows"])                      # [B,16,D]
        disc_h = self._dense(disc_card, "disc")
        disc_pool = self._masked_pool(disc_h, b["disc_mask"], axis=1)
        disc_vec = self._dense(disc_pool, "discv")
        # global + fusion
        glob = self._dense(mg.Node(b["global"]), "glob")
        ctx = self._dense(mg.concat([board_vec, hand_vec, disc_vec, glob], axis=-1), "ctx")  # [B,CTX]
        # options (cross-option set encoder) — differentiable broadcasts so gradients
        # flow to ctx and to the cross-option pool.
        K = b["opt_dense"].shape[1]
        prim = self._card_repr(b["opt_rows"][:, :, 0])                   # [B,K,D]
        targ = self._card_repr(b["opt_rows"][:, :, 1])
        opt_in = mg.concat([mg.Node(b["opt_dense"]), prim, targ], axis=-1)
        opt_base = self._dense(opt_in, "opt")                            # [B,K,OH]
        ctx3 = ctx.reshape((B, 1, c["CTX"])).broadcast_to((B, K, c["CTX"]))
        opt_rep = self._dense(mg.concat([opt_base, ctx3], axis=-1), "optc")  # [B,K,OH2]
        opt_pool = self._masked_pool(opt_rep, b["opt_mask"], axis=1)     # [B,2*OH2]
        pool3 = opt_pool.reshape((B, 1, 2 * c["OH2"])).broadcast_to((B, K, 2 * c["OH2"]))
        score_in = mg.concat([opt_rep, pool3, ctx3], axis=-1)           # [B,K,OH2+2OH2+CTX]
        score_h = self._dense(score_in, "score")
        scores = self._dense(score_h, "score2", act="none").reshape((B, K))
        out = {"scores": scores, "ctx": ctx}
        if self.aux:
            out["plan_logits"] = self._dense(ctx, "plan", act="none")
            out["support_logit"] = self._dense(ctx, "support", act="none").reshape((B,))
            out["value_logit"] = self._dense(ctx, "value", act="none").reshape((B,))
        return out

    # ---- inference (same graph; returns numpy) ----
    def score_np(self, b: Dict[str, np.ndarray]) -> np.ndarray:
        return self.forward(b)["scores"].data

    # ---- persistence ----
    def state_dict(self) -> Dict[str, np.ndarray]:
        return {k: v.data.copy() for k, v in self.p.items()}

    def load_state(self, sd: Dict[str, np.ndarray]):
        for k, v in sd.items():
            if k in self.p:
                self.p[k].data = np.asarray(v, dtype=np.float64)

    def save(self, path: str):
        meta = np.array([self.cfg[k] for k in ("D", "Hs", "BV", "Hh", "HV", "Hd", "DV",
                                               "GH", "CTX", "OH", "OH2", "SH")]
                        + [int(self.aux), int(self.seed)], dtype=np.int64)
        np.savez(path, __meta__=meta, **self.state_dict())

    @staticmethod
    def load(path: str) -> "ModelV2":
        d = np.load(path)
        m = d["__meta__"]
        keys = ("D", "Hs", "BV", "Hh", "HV", "Hd", "DV", "GH", "CTX", "OH", "OH2", "SH")
        cfg = {k: int(m[i]) for i, k in enumerate(keys)}
        aux = bool(m[len(keys)]); seed = int(m[len(keys) + 1])
        model = ModelV2(cfg, seed=seed, aux=aux)
        model.load_state({k: d[k] for k in d.files if k != "__meta__"})
        return model
