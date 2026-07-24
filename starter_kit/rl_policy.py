"""c008 RL policy: the c007 State-Encoder-v2 trunk (V2-A architecture) plus a value head,
with masked action distributions for PPO.

Action forms (from the c007 data, §9): SINGLE_CHOICE (96%), FIXED_MULTISELECT (k=lo=hi,
2.9%), VARIABLE_MULTISELECT (lo=0, hi<=4, 1.2%). ORDERED / EMPTY do not occur; if an
ORDERED decision is ever observed the caller must BLOCK (§9.5).

All forms are one sequential factorization over an augmented option set [K legal options
+ a STOP token]:
  - single-choice = one masked-categorical pick;
  - fixed multiselect = k picks without replacement (mask excludes chosen), STOP illegal;
  - variable multiselect = up to hi picks without replacement, STOP legal (a learned global
    stop logit) so selection can terminate.
The action log-probability is the sum of the sub-step masked log-probs; illegal options
have exactly zero probability. Gradient-checked against numeric estimates.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from cg import micrograd as mg, policy_model_v2 as pm, policy_data_v2 as pd
from cg import decoders


class RLPolicy:
    def __init__(self, cfg: Optional[Dict[str, int]] = None, seed: int = 0):
        self.trunk = pm.ModelV2(cfg, seed=seed, aux=False)  # V2-A architecture (no aux heads)
        CTX = self.trunk.cfg["CTX"]
        rng = np.random.default_rng(seed + 987654)
        self.pv: Dict[str, mg.Node] = {
            "vW1": mg.Node(rng.standard_normal((CTX, 128)) * np.sqrt(2.0 / CTX), requires_grad=True),
            "vb1": mg.Node(np.zeros(128), requires_grad=True),
            "vW2": mg.Node(rng.standard_normal((128, 1)) * np.sqrt(2.0 / 128), requires_grad=True),
            "vb2": mg.Node(np.zeros(1), requires_grad=True),
            "stop": mg.Node(np.zeros(1), requires_grad=True),  # global STOP logit for variable multiselect
        }
        self.seed = seed

    # ---- params / persistence ----
    def params(self) -> List[mg.Node]:
        return self.trunk.params() + list(self.pv.values())

    def state_dict(self) -> Dict[str, np.ndarray]:
        sd = {f"trunk::{k}": v.data.copy() for k, v in self.trunk.p.items()}
        sd.update({f"pv::{k}": v.data.copy() for k, v in self.pv.items()})
        return sd

    def load_state(self, sd: Dict[str, np.ndarray]):
        for k, v in sd.items():
            if k.startswith("trunk::") and k[7:] in self.trunk.p:
                self.trunk.p[k[7:]].data = np.asarray(v, dtype=np.float64)
            elif k.startswith("pv::") and k[4:] in self.pv:
                self.pv[k[4:]].data = np.asarray(v, dtype=np.float64)

    def save(self, path: str):
        meta = np.array([self.trunk.cfg[k] for k in ("D", "Hs", "BV", "Hh", "HV", "Hd", "DV",
                                                     "GH", "CTX", "OH", "OH2", "SH")] + [self.seed],
                        dtype=np.int64)
        np.savez(path, __meta__=meta, **self.state_dict())

    @staticmethod
    def load(path: str) -> "RLPolicy":
        d = np.load(path)
        m = d["__meta__"]
        keys = ("D", "Hs", "BV", "Hh", "HV", "Hd", "DV", "GH", "CTX", "OH", "OH2", "SH")
        cfg = {k: int(m[i]) for i, k in enumerate(keys)}
        pol = RLPolicy(cfg, seed=int(m[len(keys)]))
        pol.load_state({k: d[k] for k in d.files if k != "__meta__"})
        return pol

    def init_from_v2a(self, path: str):
        """Load the trunk (encoder + policy head) from a c007 V2-A checkpoint. Value head
        and stop logit are initialised separately (§7 R1/R2)."""
        m2 = pm.ModelV2.load(path)
        assert not m2.aux, "V2-A checkpoint must be aux=False"
        self.trunk.cfg = dict(m2.cfg)
        self.trunk.load_state(m2.state_dict())

    # ---- forward ----
    def _value(self, ctx: mg.Node) -> mg.Node:
        h = (ctx.matmul(self.pv["vW1"]) + self.pv["vb1"]).relu()
        v = h.matmul(self.pv["vW2"]) + self.pv["vb2"]           # [B,1]
        return v.reshape((ctx.data.shape[0],))

    def forward(self, b: Dict[str, np.ndarray]):
        out = self.trunk.forward(b)
        return out["scores"], self._value(out["ctx"]), out["ctx"]

    def _scores_np(self, b):
        return self.trunk.score_np(b)

    # ---- augmented (option + STOP) scores ----
    def _aug(self, scores: mg.Node, B: int):
        stop_col = self.pv["stop"].reshape((1, 1)).broadcast_to((B, 1))
        return mg.concat([scores, stop_col], axis=-1)          # [B, K+1]

    # ---- sampling (numpy, rollout) ----
    def act(self, feat: Dict[str, Any], form: str, lo: int, hi: int, rng, greedy: bool = False):
        b = pd.collate([_stub(feat)])
        out = self.trunk.forward(b)
        scores = out["scores"].data[0]                          # [K] numpy
        value = float(self._value(out["ctx"]).data[0])
        n = feat["n_options"]
        K = scores.shape[0]
        stop_logit = float(self.pv["stop"].data[0])
        aug = np.concatenate([scores, [stop_logit]])            # [K+1]
        mask = np.zeros(K + 1); mask[:n] = 1.0
        stop_legal = (form == "VARIABLE_MULTISELECT")
        if stop_legal:
            mask[K] = 1.0
        seq, logp, ent0 = [], 0.0, 0.0
        running = mask.copy()
        max_picks = (1 if form in ("SINGLE_CHOICE", "EMPTY") else hi)
        for j in range(max(max_picks, 1)):
            z = aug.copy(); z[running == 0] = -1e30
            z -= z.max(); e = np.exp(z); e[running == 0] = 0.0; p = e / e.sum()
            if j == 0:
                ent0 = float(-(p[p > 0] * np.log(p[p > 0])).sum())
            a = int(np.argmax(p)) if greedy else int(rng.choice(len(p), p=p))
            logp += float(np.log(p[a] + 1e-30))
            seq.append(a)
            if a == K:            # STOP
                break
            running[a] = 0.0
            if form == "SINGLE_CHOICE" or form == "EMPTY":
                break
            if form == "FIXED_MULTISELECT" and len(seq) >= hi:
                break
        chosen = [a for a in seq if a != K]
        return {"action": chosen, "action_seq": seq, "logprob": logp, "value": value,
                "entropy": ent0, "form": form, "lo": lo, "hi": hi, "n_options": n}

    # ---- differentiable evaluate (PPO) ----
    def evaluate(self, b: Dict[str, np.ndarray], act_arrays: Dict[str, np.ndarray]):
        scores, value, _ = self.forward(b)                      # scores[B,K], value[B]
        B, K = scores.data.shape
        aug = self._aug(scores, B)                              # [B,K+1]
        base_mask = act_arrays["aug_mask"]                      # [B,K+1] numpy {0,1}
        seq = act_arrays["action_seq"]                          # [B,L] int (pad = -1)
        seq_len = act_arrays["seq_len"]                         # [B]
        L = seq.shape[1]
        running = base_mask.copy()
        logprob = mg.Node(np.zeros(B))
        entropy = mg.Node(np.zeros(B))
        rows = np.arange(B)
        for t in range(L):
            logp_all, p = mg.masked_log_softmax(aug, running)   # Node[B,K+1], p numpy
            valid = (t < seq_len).astype(np.float64)            # [B]
            a_t = np.where(seq[:, t] >= 0, seq[:, t], 0)        # safe index
            step_lp = mg.gather_per_row(logp_all, a_t)          # Node[B]
            logprob = logprob + step_lp * mg.Node(valid)
            if t == 0:
                ent = mg.reduce_sum(mg.exp(logp_all) * logp_all * mg.Node(base_mask), axis=1)
                entropy = ent * mg.Node(-1.0)                   # H = -sum p log p (first step)
            # remove chosen (only for valid, non-STOP picks) from running mask
            upd = running.copy()
            for bi in range(B):
                if t < seq_len[bi] and seq[bi, t] != K:
                    upd[bi, seq[bi, t]] = 0.0
            running = upd
        return logprob, entropy, value


def _stub(feat):
    return {"feat": feat, "n": feat["n_options"], "form": "SINGLE_CHOICE", "lo": 0, "hi": 1,
            "action": [], "weight": 0.0,
            "aux": {"plan_target": 0, "use_support": 0.0, "value": 0.5, "has_plan": 0.0}}


def collate_rl(transitions: List[Dict[str, Any]]):
    """Model batch + action/PPO arrays for a list of RL transitions."""
    stubs = [_stub(t["feat"]) for t in transitions]
    b = pd.collate(stubs)
    B = len(transitions)
    K = b["opt_dense"].shape[1]
    L = max(len(t["action_seq"]) for t in transitions)
    aug_mask = np.zeros((B, K + 1))
    seq = np.full((B, L), -1, dtype=np.int64)
    seq_len = np.zeros(B, dtype=np.int64)
    for i, t in enumerate(transitions):
        n = t["n_options"]
        aug_mask[i, :n] = 1.0
        if t["form"] == "VARIABLE_MULTISELECT":
            aug_mask[i, K] = 1.0
        # act() encodes STOP as the decision-local n_options; remap to the batch-global K
        s = [K if a == t["n_options"] else a for a in t["action_seq"]]
        seq[i, :len(s)] = s
        seq_len[i] = len(s)
    return b, {"aug_mask": aug_mask, "action_seq": seq, "seq_len": seq_len, "K": K}
