"""c007 data pipeline for State Encoder v2: featurize stored decisions (history
threaded per game), collate to a dense model batch + form-aware labels, and evaluate
teacher-action agreement exactly as the runtime hybrid decodes.

Works on both the c006 sequence dataset (back-evaluation; no plan labels) and the
richer c007 v2 dataset (adds privileged plan labels for the V2-B auxiliary heads).
"""

from __future__ import annotations

import gzip
import json
from typing import Any, Dict, List, Optional

import numpy as np

from cg import decoders, decision_taxonomy as dt
from cg import state_encoder_v2 as enc
from cg import micrograd as mg

N_PLAN = (1 + enc.N_OPP_BENCH) + 1  # main-target buckets: none + active + 5 bench


# -------------------- featurize --------------------

def _plan_bucket(plan_a_attack: Optional[int]) -> int:
    if plan_a_attack is None or plan_a_attack < 0:
        return 0                      # no plan
    return min(int(plan_a_attack) + 1, N_PLAN - 1)  # 0(active)->1, k(bench)->k+1


def featurize_record(rec: Dict[str, Any], prev_state) -> Dict[str, Any]:
    obs = rec["observation"]
    feat = enc.encode(obs, prev_state)
    info = dt.classify(rec)
    lo = int(rec.get("min_count") or 0)
    hi = int(rec.get("max_count") or 0)
    n = feat["n_options"]
    form = decoders.classify_form(rec["select_context"], lo, hi, n)
    weight = 0.0 if info["forced"] else dt.importance_weight(info["importance_class"])
    labels = rec.get("plan_labels") or {}
    aux = {
        "plan_target": _plan_bucket(labels.get("plan_a_attack")),
        "use_support": 1.0 if (labels.get("use_support") or 0) > 0 else 0.0,
        "value": float(rec.get("terminal_outcome", 0.5)),
        "has_plan": 1.0 if labels else 0.0,
    }
    return {
        "game_id": rec["game_id"],
        "decision_index": rec.get("decision_index", 0),
        "feat": feat,
        "action": list(rec["teacher_action_indices"]),
        "form": form, "lo": lo, "hi": hi, "n": n,
        "weight": weight,
        "importance_class": info["importance_class"],
        "semantic_type": info["semantic_type"],
        "select_context": rec["select_context"],
        "forced": info["forced"],
        "aux": aux,
    }


def load_split(path: str) -> List[Dict[str, Any]]:
    recs = []
    with gzip.open(path, "rt") as fh:
        for line in fh:
            recs.append(json.loads(line))
    return recs


def featurize_split(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Featurize, threading history per game (ordered by decision_index)."""
    games: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        games.setdefault(r["game_id"], []).append(r)
    out = []
    for gid, rs in games.items():
        rs.sort(key=lambda r: r.get("decision_index", 0))
        prev = enc.initial_prev_state()
        for r in rs:
            out.append(featurize_record(r, prev))
            prev = enc.derive_prev_state(r["observation"], r["teacher_action_indices"])
    return out


# -------------------- collate --------------------

def collate(batch: List[Dict[str, Any]]) -> Dict[str, np.ndarray]:
    B = len(batch)
    K = max(max(d["n"], 1) for d in batch)
    b: Dict[str, np.ndarray] = {}
    b["board_rows"] = np.stack([d["feat"]["board_rows"] for d in batch])
    b["board_dyn"] = np.stack([d["feat"]["board_dyn"] for d in batch])
    b["hand_rows"] = np.stack([d["feat"]["hand_rows"] for d in batch])
    b["hand_dyn"] = np.stack([d["feat"]["hand_dyn"] for d in batch])
    b["hand_mask"] = np.stack([d["feat"]["hand_mask"] for d in batch])
    b["disc_rows"] = np.stack([d["feat"]["disc_rows"] for d in batch])
    b["disc_mask"] = np.stack([d["feat"]["disc_mask"] for d in batch])
    b["global"] = np.stack([d["feat"]["global"] for d in batch])
    od = np.zeros((B, K, enc.OPT_DENSE)); orw = np.zeros((B, K, 2), dtype=np.int64)
    om = np.zeros((B, K))
    single = np.zeros(B); tgt = np.zeros(B, dtype=np.int64)
    multi = np.zeros((B, K)); weight = np.zeros(B)
    plan_t = np.zeros(B, dtype=np.int64); supp = np.zeros(B); val = np.zeros(B); hasp = np.zeros(B)
    for i, d in enumerate(batch):
        f = d["feat"]; n = d["n"]
        od[i, :f["opt_dense"].shape[0]] = f["opt_dense"]
        orw[i, :f["opt_rows"].shape[0]] = f["opt_rows"]
        om[i, :n] = 1.0
        weight[i] = d["weight"]
        if d["form"] in ("SINGLE_CHOICE", "EMPTY", "ORDERED"):
            single[i] = 1.0
            tgt[i] = d["action"][0] if d["action"] else 0
        else:  # FIXED/VARIABLE MULTISELECT
            for a in d["action"]:
                if 0 <= a < K:
                    multi[i, a] = 1.0
        plan_t[i] = d["aux"]["plan_target"]; supp[i] = d["aux"]["use_support"]
        val[i] = d["aux"]["value"]; hasp[i] = d["aux"]["has_plan"]
    b.update({"opt_dense": od, "opt_rows": orw, "opt_mask": om,
              "single": single, "target": tgt, "multi": multi, "weight": weight,
              "plan_target": plan_t, "support": supp, "value": val, "has_plan": hasp})
    return b


# -------------------- loss --------------------

def policy_loss(model, out: Dict[str, mg.Node], b: Dict[str, np.ndarray],
                aux_coef: Dict[str, float]) -> mg.Node:
    scores = out["scores"]
    w = b["weight"]
    single = b["single"]
    loss_s, _ = mg.softmax_ce_masked(scores, b["target"], b["opt_mask"], weight=w * single)
    loss_m, _ = mg.bce_with_logits_masked(scores, b["multi"], b["opt_mask"],
                                          weight=w * (1.0 - single))
    loss = loss_s + loss_m
    if model.aux and "plan_logits" in out:
        hp = b["has_plan"]
        lp, _ = mg.softmax_ce_masked(out["plan_logits"], b["plan_target"],
                                     np.ones_like(out["plan_logits"].data), weight=hp)
        ls, _ = mg.bce_with_logits_masked(out["support_logit"].reshape((-1, 1)),
                                          b["support"].reshape((-1, 1)),
                                          np.ones((len(hp), 1)), weight=hp)
        lv, _ = mg.bce_with_logits_masked(out["value_logit"].reshape((-1, 1)),
                                          b["value"].reshape((-1, 1)), np.ones((len(hp), 1)))
        loss = (loss + mg.Node(aux_coef.get("plan", 0.3)) * lp
                + mg.Node(aux_coef.get("support", 0.3)) * ls
                + mg.Node(aux_coef.get("value", 0.3)) * lv)
    return loss


# -------------------- decode + agreement --------------------

def decode_pred(scores: np.ndarray, lo: int, hi: int, form: str) -> List[int]:
    if form == "ORDERED":
        return decoders.safe_fallback(lo, hi, len(scores))
    return decoders.decode(scores, lo, hi, form)


def evaluate_agreement(model, decisions: List[Dict[str, Any]], batch_size: int = 256) -> Dict[str, Any]:
    """Exact + importance-weighted teacher-action agreement, decoded as the runtime hybrid."""
    n = len(decisions)
    exact = 0
    iw_num = iw_den = 0.0
    nonforced = nf_match = 0
    by_imp: Dict[str, List[int]] = {}
    by_sem: Dict[str, List[int]] = {}
    for s in range(0, n, batch_size):
        sub = decisions[s:s + batch_size]
        b = collate(sub)
        scores = model.score_np(b)
        for i, d in enumerate(sub):
            nopt = d["n"]
            pred = decode_pred(scores[i, :nopt], d["lo"], d["hi"], d["form"])
            match = sorted(pred) == sorted(d["action"])
            exact += int(match)
            w = dt.importance_weight(d["importance_class"])
            iw_num += w * match; iw_den += w
            if not d["forced"]:
                nonforced += 1; nf_match += int(match)
            by_imp.setdefault(d["importance_class"], [0, 0])
            by_imp[d["importance_class"]][0] += int(match); by_imp[d["importance_class"]][1] += 1
            by_sem.setdefault(d["semantic_type"], [0, 0])
            by_sem[d["semantic_type"]][0] += int(match); by_sem[d["semantic_type"]][1] += 1
    return {
        "n": n,
        "exact_agreement": exact / n if n else 0.0,
        "importance_weighted_agreement": iw_num / iw_den if iw_den else 0.0,
        "nonforced_agreement": nf_match / nonforced if nonforced else 0.0,
        "by_importance": {k: {"match": v[0], "n": v[1], "acc": v[0] / v[1] if v[1] else 0.0}
                          for k, v in by_imp.items()},
        "by_semantic_type": {k: {"match": v[0], "n": v[1], "acc": v[0] / v[1] if v[1] else 0.0}
                             for k, v in sorted(by_sem.items(), key=lambda kv: -kv[1][1])},
    }
