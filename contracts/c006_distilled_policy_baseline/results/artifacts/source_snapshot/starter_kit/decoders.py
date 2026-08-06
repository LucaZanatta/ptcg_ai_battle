"""Context-aware action decoding for the distilled student (c006 AC-05 / §11).

Maps per-legal-option model scores to a legal action set, according to the
selection FORM:

    SINGLE_CHOICE          maxCount == 1                      -> masked argmax (softmax CE)
    FIXED_MULTISELECT      minCount == maxCount > 1           -> masked top-k (per-option BCE)
    VARIABLE_MULTISELECT   minCount < maxCount, maxCount > 1  -> per-option keep + [lo,hi] clamp
    EMPTY                  maxCount == 0                      -> [] (forced)
    ORDERED                known ordered context              -> deterministic safe fallback

No ORDERED multi-select form occurs in the c005 data (SKILL_ORDER count == 0), so
ordered selections are never misrepresented as unordered BCE; if one is ever seen
at runtime it is routed to the deterministic safe fallback.
"""

from __future__ import annotations

from typing import List

import numpy as np

SINGLE_CHOICE = "SINGLE_CHOICE"
FIXED_MULTISELECT = "FIXED_MULTISELECT"
VARIABLE_MULTISELECT = "VARIABLE_MULTISELECT"
EMPTY = "EMPTY"
ORDERED = "ORDERED"

# Contexts whose multi-select is order-dependent (none present in c005 data).
ORDERED_CONTEXTS = {"SKILL_ORDER"}


def classify_form(select_context: str, lo: int, hi: int, n_options: int) -> str:
    if select_context in ORDERED_CONTEXTS and hi > 1:
        return ORDERED
    if hi == 0:
        return EMPTY
    if hi == 1:
        return SINGLE_CHOICE
    if lo == hi:
        return FIXED_MULTISELECT
    return VARIABLE_MULTISELECT


def safe_fallback(lo: int, hi: int, n_options: int) -> List[int]:
    """Deterministic legal fallback: the first ``hi`` option indices (engine-sanctioned)."""
    k = max(0, min(hi, n_options))
    return list(range(k))


def decode(scores: np.ndarray, lo: int, hi: int, form: str) -> List[int]:
    """Return a legal set of option indices from per-option ``scores`` (higher=better).

    For SINGLE/FIXED, ``scores`` are ranking logits. For VARIABLE, ``scores`` are
    per-option keep-logits (kept when sigmoid>0.5), clamped to [lo, hi] by rank.
    """
    n = len(scores)
    if form == EMPTY or hi == 0 or n == 0:
        return []
    order = list(np.argsort(-scores, kind="stable"))  # best first
    if form == SINGLE_CHOICE:
        return [int(order[0])]
    if form == FIXED_MULTISELECT:
        k = min(hi, n)
        return sorted(int(i) for i in order[:k])
    if form == VARIABLE_MULTISELECT:
        kept = [int(i) for i in order if scores[i] > 0.0]   # sigmoid(logit)>0.5
        # enforce cardinality bounds using score rank
        if len(kept) < lo:
            for i in order:
                if int(i) not in kept:
                    kept.append(int(i))
                    if len(kept) >= lo:
                        break
        if len(kept) > hi:
            kept = [int(i) for i in order if int(i) in set(kept)][:hi]
        return sorted(kept)
    # ORDERED or unknown -> caller should use safe_fallback
    return safe_fallback(lo, hi, n)
