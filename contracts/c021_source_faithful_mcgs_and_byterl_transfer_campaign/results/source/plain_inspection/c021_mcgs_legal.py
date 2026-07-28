"""c021 A10 — MCGS_2019_PTCG_LEGAL_CORRECTED.

A SEPARATELY NAMED branch. `MCGS_2019_OFFICIAL_SOURCE_PORT` is not modified by anything here; the
two are configured independently and measured against each other, so a gain can be attributed to
a specific correction rather than folded into the port and lost.

Each correction addresses a place where faithfully porting Hearthstone code produces PTCG-illegal
or PTCG-blind behaviour. Nothing here is a strength heuristic.

## C1 — multi-select actions are SETS, not padded singletons

A PTCG select carries `minCount..maxCount`. The source's action is a single `PlayerTask`, so the
port emits one option and, when `minCount > 1`, pads with the first `minCount - 1` other options
to make the payload legal.

That payload is legal but ARBITRARY: the padding is deterministic, so for a context with
`minCount = 2` over 10 options the search explores 10 of the 45 legal pairs and is structurally
blind to the other 35. The action space it searches is not the action space it plays in. C1 makes
the SET the action, so distinct combinations are distinct edges.

## C2 — category filter on target side

`Filters.CategoryBasedFilter` drops options whose target is on the wrong side: a card harmful to
its target may not aim at your own characters, one beneficial to its target may not aim at the
opponent's. The Hearthstone card-ID sets do not transfer, but the STRUCTURE does. PTCG names the
valence in `api.SelectContext` (DAMAGE, DAMAGE_COUNTER, HEAL, REMOVE_DAMAGE_COUNTER) and the
target's owner in the option's `playerIndex`, so C2 uses those two fields and fires nowhere else.

If filtering would empty the option list the filter is skipped entirely, which is the source's
behaviour when every target would be removed.

## C3 — obliged actions

When the select offers exactly as many options as `minCount` requires, the action is forced. The
source's tree-phase pruning collapses such nodes rather than spending simulations proving the only
legal move is the only legal move.
"""

from __future__ import annotations

import itertools
import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_core as K  # noqa: E402

BRANCH = "MCGS_2019_PTCG_LEGAL_CORRECTED"

# How many distinct combinations a multi-select node may expand. Unbounded enumeration of
# C(n, k) is not affordable; the cap is a MECHANICAL_ADAPTER and every activation is counted.
MAX_COMBINATIONS = 24

DEFAULT_CORRECTIONS = {"C1_multiselect_sets": True,
                       "C2_category_filter": True,
                       "C3_obliged_actions": True}


def select_bounds(sel) -> Tuple[int, int]:
    lo = int(getattr(sel, "minCount", 1) or 1)
    hi = int(getattr(sel, "maxCount", 1) or 1)
    lo = max(1, lo)
    hi = max(lo, hi)
    return lo, hi


def is_obliged(sel, opts: Sequence[Any]) -> bool:
    """C3. The select admits exactly one legal answer."""
    lo, hi = select_bounds(sel)
    if not opts:
        return False
    if len(opts) == 1:
        return True
    return lo >= len(opts) and hi >= len(opts)


# Contexts whose target is unambiguously HARMFUL to the Pokemon it names, and contexts whose
# target is unambiguously BENEFICIAL. Taken from `api.SelectContext`, which documents each one.
HARMFUL_CONTEXTS = {13, 14, 15}      # DAMAGE_COUNTER, DAMAGE_COUNTER_ANY, DAMAGE
BENEFICIAL_CONTEXTS = {16, 17}       # REMOVE_DAMAGE_COUNTER, HEAL


def _target_owner(opt) -> Optional[int]:
    """Which PLAYER owns the option's target, from the engine's `playerIndex` field.

    An earlier version read `inPlayArea` and mapped low values to "mine". That was wrong:
    `api.AreaType` enumerates the ZONE -- DECK, HAND, DISCARD, ACTIVE, BENCH, PRIZE, ... -- and
    carries no ownership at all, so the filter was pruning on a meaningless criterion. It removed
    866 legal options in a single game. `playerIndex` is the field that names the owner.
    """
    from cg import c020_byterl_encode as E
    i = E._F.get("playerIndex")
    if i is None:
        return None
    f = getattr(opt, "fields", None)
    if not f or i >= len(f):
        return None
    pi = int(f[i])
    return None if pi < 0 else pi


def category_filter(opts: List[Any], sel=None, your_index: Optional[int] = None,
                    stats: Optional[Dict[str, Any]] = None) -> List[Any]:
    """C2. Drop options whose target OWNER contradicts what the select context does.

    Structural throughout: the context comes from `api.SelectContext` and the owner from the
    option's `playerIndex`. Never a name match, and never an inference from zone type.

    The filter is deliberately narrow. It fires only for contexts whose valence is unambiguous
    from the engine's own documentation -- placing damage, dealing damage, removing damage
    counters, healing -- and is a no-op everywhere else. A wider filter would need PTCG card
    semantics the source's Hearthstone card-ID sets cannot supply, and pruning a legal option the
    search should have considered is strictly worse than not pruning at all.
    """
    if len(opts) <= 1 or sel is None or your_index is None:
        return list(opts)
    ctx = int(getattr(sel, "context", -1) or -1)
    if ctx not in HARMFUL_CONTEXTS and ctx not in BENEFICIAL_CONTEXTS:
        return list(opts)
    harmful = ctx in HARMFUL_CONTEXTS
    kept = []
    for o in opts:
        owner = _target_owner(o)
        if owner is not None:
            mine = (owner == your_index)
            if harmful and mine:
                continue          # do not place damage on my own Pokemon
            if (not harmful) and (not mine):
                continue          # do not heal the opponent's Pokemon
        kept.append(o)
    if not kept:
        # the source skips the filter entirely rather than emptying the option list
        if stats is not None:
            stats["legal_filter_skipped_empty"] = stats.get("legal_filter_skipped_empty", 0) + 1
        return list(opts)
    if stats is not None and len(kept) < len(opts):
        stats["legal_filter_pruned"] = stats.get("legal_filter_pruned", 0) + len(opts) - len(kept)
        stats["legal_filter_activations"] = stats.get("legal_filter_activations", 0) + 1
    return kept


def combinations(sel, opts: Sequence[Any], rng,
                 stats: Optional[Dict[str, Any]] = None) -> List[List[int]]:
    """C1. The action set for this select: a list of option-index TUPLES.

    Single-select degenerates to one index per option, which is exactly the source's behaviour,
    so C1 changes nothing at ordinary nodes and only bites where `minCount > 1`.
    """
    n = len(opts)
    if n == 0:
        return []
    lo, hi = select_bounds(sel)
    if lo <= 1:
        return [[i] for i in range(n)]
    k = min(lo, n)
    total = 1
    for j in range(k):
        total = total * (n - j) // (j + 1)
    if total <= MAX_COMBINATIONS:
        combos = [list(c) for c in itertools.combinations(range(n), k)]
    else:
        if stats is not None:
            stats["legal_combination_capped"] = stats.get("legal_combination_capped", 0) + 1
            stats["legal_combinations_dropped"] = (
                stats.get("legal_combinations_dropped", 0) + total - MAX_COMBINATIONS)
        seen, combos = set(), []
        guard = 0
        while len(combos) < MAX_COMBINATIONS and guard < MAX_COMBINATIONS * 20:
            guard += 1
            pick = tuple(sorted(rng.choice(n, size=k, replace=False).tolist()))
            if pick not in seen:
                seen.add(pick)
                combos.append(list(pick))
    if stats is not None:
        stats["legal_multiselect_nodes"] = stats.get("legal_multiselect_nodes", 0) + 1
    return combos


def payload_for(sel, opts: Sequence[Any], combo: Sequence[int]) -> List[int]:
    """Serialize a chosen SET. Honours minCount..maxCount by construction."""
    chosen = [opts[i] for i in combo]
    try:
        return K.to_select_payload(chosen, sel)
    except Exception:  # noqa: BLE001
        return [getattr(o, "option_index", 0) for o in chosen]


def corrections_manifest(cfg: Dict[str, Any]) -> Dict[str, Any]:
    c = {**DEFAULT_CORRECTIONS, **{k: v for k, v in cfg.items() if k in DEFAULT_CORRECTIONS}}
    return {"branch": BRANCH, "corrections": c,
            "max_combinations": MAX_COMBINATIONS,
            "note": "Separately named from MCGS_2019_OFFICIAL_SOURCE_PORT, which is unmodified."}
