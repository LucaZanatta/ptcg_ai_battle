"""PTCG_BYTERL_V0 — recurrent masked policy, inference only.

No MCTS and no search API (§9.6). Recurrent state carries across atomic decisions and resets at
the game boundary. The deck is frozen outside the model (§9.1), so the deck-submission step
returns the fixed list rather than a policy output.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import torch

from cg import api as A
from cg import c019_core as K, c019_byterl_encode as E, c019_byterl_model as M

_DECK = None
_MODEL = None
_STATE = [None]
STATS = {"decisions": 0, "policy_ok": 0, "fallbacks": 0, "resets": 0}


def _deck():
    global _DECK
    if _DECK is None:
        import csv
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deck.csv")
        with open(p) as fh:
            _DECK = [int(r[0]) for r in csv.reader(fh) if r and r[0].strip().isdigit()]
    return _DECK


def _model():
    global _MODEL
    if _MODEL is None:
        torch.set_num_threads(1)
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "policy.pt")
        m = M.PTCGByteRL()
        m.load_state_dict(torch.load(p, map_location="cpu")["state_dict"])
        m.eval()
        _MODEL = m
    return _MODEL


def agent(obs_dict):
    sel = obs_dict.get("select") if isinstance(obs_dict, dict) else None
    if sel is None:
        # deck submission also marks a new game: reset recurrent state (B02)
        _STATE[0] = None
        STATS["resets"] += 1
        return list(_deck())
    STATS["decisions"] += 1
    try:
        m = _model()
        o = A.to_observation_class(obs_dict)
        f = E.encode(o)
        b = M.to_torch(f)
        with torch.no_grad():
            logits, _v, nxt = m.forward(b, _STATE[0])
            probs = M.masked_probs(logits, b["opt_mask"])[0]
        _STATE[0] = (nxt[0].detach(), nxt[1].detach())
        k = min(int(f["n_options"]), E.N_OPT)
        if k <= 0:
            return []
        lo = int(sel.get("minCount") or 0)
        hi = int(sel.get("maxCount") or 1)
        n_pick = max(1, min(lo if lo > 0 else 1, hi if hi > 0 else 1, k))
        p = probs[:k]
        s = float(p.sum())
        picks = (list(range(n_pick)) if s <= 0 else
                 torch.topk(p / p.sum(), n_pick).indices.tolist())
        opts = K.canonical_options(sel)
        chosen = [opts[i] for i in sorted(picks) if i < len(opts)]
        if chosen:
            STATS["policy_ok"] += 1
            return K.to_select_payload(chosen, sel)
    except Exception:
        pass
    STATS["fallbacks"] += 1
    n = len(sel.get("option") or [])
    lo = max(1, int(sel.get("minCount") or 1))
    return list(range(min(lo, n))) if n else []
