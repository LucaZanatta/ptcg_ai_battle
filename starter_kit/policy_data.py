"""Featurization, batching, and agreement evaluation for the distilled students.

Featurizes the ordered sequence dataset ONCE (train/val here; test is featurized
only by the frozen offline-eval step). Builds form-aware labels and importance
weights (FORCED decisions get weight 0 — the safety layer bypasses the model on
them). Provides S1 (flat, padded minibatch) and S2 (per-game) collation and an
agreement evaluator that decodes exactly as the runtime agent will.
"""

from __future__ import annotations

import gzip
import json
import os
from typing import Any, Dict, List

import numpy as np

from cg import decoders as D
from cg.decision_taxonomy import classify, importance_weight
from cg.policy_features import ODENSE, PREV, featurize_decision


def _build_labels(rec, form, n):
    lo = rec["min_count"] or 0
    hi = rec["max_count"] or 0
    teacher = list(rec["teacher_action_indices"])
    tset = frozenset(teacher)
    single = 1.0 if form in (D.SINGLE_CHOICE, D.EMPTY) else 0.0
    target_idx = teacher[0] if (single and teacher) else 0
    multi = np.zeros(n, dtype=np.float32)
    for i in teacher:
        if 0 <= i < n:
            multi[i] = 1.0
    return single, target_idx, multi, tset, lo, hi


def featurize_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Featurize an ordered list of decision records (one split). Returns decisions
    with features + labels, carrying game_id/order for grouping."""
    out = []
    prev_ctx = {}          # game_id -> previous select_context value
    prev_cnt = {}          # game_id -> previous selected count
    for rec in records:
        gid = rec["game_id"]
        obs = rec["observation"]
        ctx_val = (obs.get("select") or {}).get("context")
        feat = featurize_decision(obs, prev_ctx.get(gid), prev_cnt.get(gid, 0))
        n = feat["n_options"]
        tax = classify(rec)
        form = D.classify_form(rec["select_context"], rec["min_count"], rec["max_count"], n)
        single, tgt, multi, tset, lo, hi = _build_labels(rec, form, n)
        w = 0.0 if tax["forced"] else importance_weight(tax["importance_class"])
        out.append({
            "game_id": gid, "example_id": rec["example_id"],
            "decision_index": rec["decision_index"],
            "gdense": feat["gdense"], "grows": feat["grows"],
            "odense": feat["odense"], "orows": feat["orows"], "prev": feat["prev"],
            "n": n, "form": form, "lo": lo, "hi": hi,
            "single_mask": single, "target_idx": tgt, "multi_target": multi,
            "teacher_set": tset, "weight": w,
            "importance": tax["importance_class"], "semantic": tax["semantic_type"],
            "select_context": rec["select_context"],
            "terminal_outcome": rec.get("terminal_outcome"),
        })
        prev_ctx[gid] = ctx_val
        prev_cnt[gid] = len(rec["teacher_action_indices"])
    return out


def load_split(seq_dir: str, split: str) -> List[Dict[str, Any]]:
    recs = []
    with gzip.open(os.path.join(seq_dir, f"{split}.jsonl.gz"), "rt") as fh:
        for line in fh:
            recs.append(json.loads(line))
    return recs


def group_by_game(decisions: List[Dict[str, Any]]) -> Dict[str, List[int]]:
    g: Dict[str, List[int]] = {}
    for i, d in enumerate(decisions):
        g.setdefault(d["game_id"], []).append(i)
    for gid in g:
        g[gid].sort(key=lambda i: decisions[i]["decision_index"])
    return g


def _pad_collate(subset: List[Dict[str, Any]], recurrent: bool) -> Dict[str, Any]:
    N = len(subset)
    K = max(1, max(d["n"] for d in subset))
    GD = subset[0]["gdense"].shape[0]
    gdense = np.zeros((N, GD), dtype=np.float64)
    grows = np.zeros((N, 2), dtype=np.int64)
    odense = np.zeros((N, K, ODENSE), dtype=np.float64)
    orows = np.zeros((N, K, 2), dtype=np.int64)
    legal_mask = np.zeros((N, K), dtype=np.float64)
    prev = np.zeros((N, PREV), dtype=np.float64)
    single = np.zeros(N); target = np.zeros(N, dtype=np.int64)
    multi = np.zeros((N, K)); weight = np.zeros(N)
    for i, d in enumerate(subset):
        n = d["n"]
        gdense[i] = d["gdense"]; grows[i] = d["grows"]; prev[i] = d["prev"]
        if n > 0:
            odense[i, :n] = d["odense"]; orows[i, :n] = d["orows"]; legal_mask[i, :n] = 1.0
            multi[i, :n] = d["multi_target"]
        single[i] = d["single_mask"]; target[i] = d["target_idx"]; weight[i] = d["weight"]
    batch = {"gdense": gdense, "grows": grows, "odense": odense, "orows": orows,
             "legal_mask": legal_mask, "single": single, "target": target,
             "multi": multi, "weight": weight}
    if recurrent:
        batch["prev"] = prev
    return batch


def collate_ff(subset):
    return _pad_collate(subset, recurrent=False)


def collate_game(game_decisions):
    return _pad_collate(game_decisions, recurrent=True)


def _decode_pred(scores: np.ndarray, d: Dict[str, Any]) -> frozenset:
    form = d["form"]
    if form == D.ORDERED:
        return frozenset(D.safe_fallback(d["lo"], d["hi"], d["n"]))
    return frozenset(D.decode(scores, d["lo"], d["hi"], form))


def evaluate_agreement(model, decisions, game_index, recurrent: bool) -> Dict[str, Any]:
    """Compute exact-match + importance-weighted agreement over decisions."""
    import collections
    exact_w_num = 0.0; exact_w_den = 0.0
    exact_all = 0; n_all = 0
    exact_nonforced = 0; n_nonforced = 0
    by_imp = collections.defaultdict(lambda: [0, 0])
    for gid, idxs in game_index.items():
        hidden = None
        for i in idxs:
            d = decisions[i]
            feat = {"gdense": d["gdense"], "grows": d["grows"], "odense": d["odense"],
                    "orows": d["orows"], "n_options": d["n"], "prev": d["prev"]}
            scores, hidden = model.np_scores(feat, hidden)
            if d["n"] == 0:
                pred = frozenset()
            else:
                pred = _decode_pred(scores, d)
            match = int(pred == d["teacher_set"])
            n_all += 1; exact_all += match
            b = by_imp[d["importance"]]; b[1] += 1; b[0] += match
            if d["weight"] > 0:
                exact_w_num += d["weight"] * match; exact_w_den += d["weight"]
                n_nonforced += 1; exact_nonforced += match
    return {
        "importance_weighted_agreement": exact_w_num / exact_w_den if exact_w_den else 0.0,
        "overall_exact_agreement": exact_all / n_all if n_all else 0.0,
        "nonforced_exact_agreement": exact_nonforced / n_nonforced if n_nonforced else 0.0,
        "by_importance": {k: v[0] / v[1] for k, v in by_imp.items()},
        "n_decisions": n_all,
    }
