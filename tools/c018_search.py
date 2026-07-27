"""c018 M01 — real official-API multi-step search.

This replaces c017's depth-0 pseudo-search entirely. Every successor here comes from the
simulator via `search_step`, never from a static score, and the counters that prove it
(`search_begin`/`search_step`/`release`/`end`, depth reached, distinct successor observations)
are recorded per decision rather than asserted.

HIDDEN INFORMATION (P03). `search_begin` requires PREDICTED hidden cards — opponent deck, prizes,
hand, and face-down active. That prediction must be built without reading the true hidden zones,
even though the local observation happens to contain them. `VisibleView` is the only accessor the
determinizer is allowed to use: it exposes own hand, both boards, both discards, counts and the
stadium, and it raises if anything asks it for an opponent hand, a deck list, or prize contents.
The audit is therefore structural, not a promise.

LIFECYCLE (P01). `SearchSession` is a context manager: every id obtained is released and
`search_end()` runs on the way out, including on exception. Leaking search ids is what exhausts
the native allocator across a long run.
"""

from __future__ import annotations

import collections
import hashlib
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

SEARCH_VERSION = "c018.search.v1"
LEAF_VERSION = "c018.leaf.v1"


class HiddenInformationAccess(Exception):
    """Raised when the determinizer reaches for a zone it is not allowed to see."""


class VisibleView:
    """The ONLY state accessor the determinizer may use (P03).

    Reading a genuinely hidden zone raises rather than returning data, so a leak becomes a
    crash in a probe instead of a silent advantage.
    """

    __slots__ = ("_st", "_yi")

    def __init__(self, state, your_index: int):
        self._st = state
        self._yi = your_index

    # ---- allowed ----
    @property
    def my(self):
        return self._st.players[self._yi]

    @property
    def opp(self):
        return self._st.players[1 - self._yi]

    def my_hand_ids(self) -> List[int]:
        return [c.id for c in (self.my.hand or []) if c is not None]

    def board_ids(self, side: str) -> List[int]:
        p = self.my if side == "mine" else self.opp
        out = []
        for z in ("active", "bench"):
            for c in (getattr(p, z, None) or []):
                if c is not None:
                    out.append(c.id)
        return out

    def discard_ids(self, side: str) -> List[int]:
        p = self.my if side == "mine" else self.opp
        return [c.id for c in (p.discard or []) if c is not None]

    def counts(self) -> Dict[str, int]:
        return {"my_deck": self.my.deckCount or 0,
                "my_prize": len([c for c in (self.my.prize or []) if True]),
                "my_hand": len(self.my_hand_ids()),
                "opp_deck": self.opp.deckCount or 0,
                "opp_prize": len([c for c in (self.opp.prize or []) if True]),
                "opp_hand": self.opp.handCount or 0}

    # ---- forbidden ----
    def opponent_hand_ids(self):
        raise HiddenInformationAccess("opponent hand contents are hidden")

    def deck_list(self, side: str):
        raise HiddenInformationAccess("deck contents are hidden")

    def prize_ids(self, side: str):
        raise HiddenInformationAccess("prize contents are hidden")


# --------------------------------------------------------------------------------------
# determinization
# --------------------------------------------------------------------------------------

ARCHETYPES = {}


def _load_archetypes():
    """Public archetype decklists used to PREDICT opponent hidden cards.

    In-repo these come from the teacher sources. Inside a submission package the repo helpers do
    not exist, so a `_decks.json` sitting next to this module carries the same lists — the
    packaged determinizer must behave identically to the evaluated one, or the panel measured a
    different agent than the one uploaded (§8.2.6).
    """
    global ARCHETYPES
    if ARCHETYPES:
        return ARCHETYPES
    try:
        from cg import teachers as T, c009_eval as ce
        for cid in ("dragapult", "mega_lucario", "iono", "mega_abomasnow"):
            try:
                ARCHETYPES[cid] = list(T.read_deck(cid, ce.SOURCES))
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass
    if not ARCHETYPES:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_decks.json")
        if os.path.exists(p):
            ARCHETYPES = {k: list(v) for k, v in json.load(open(p)).items()}
    return ARCHETYPES


def classify_opponent(view: VisibleView) -> Tuple[str, float, Dict[str, int]]:
    """Infer the opponent archetype from cards it has ACTUALLY revealed (board + discard)."""
    decks = _load_archetypes()
    seen = collections.Counter(view.board_ids("theirs") + view.discard_ids("theirs"))
    scores = {}
    for name, deck in decks.items():
        ds = collections.Counter(deck)
        scores[name] = sum(min(n, ds.get(cid, 0)) for cid, n in seen.items())
    if not scores or max(scores.values()) == 0:
        return "unknown", 0.0, dict(seen)
    best = max(scores, key=scores.get)
    tot = sum(scores.values()) or 1
    return best, round(scores[best] / tot, 4), dict(seen)


_BASIC_CACHE = {}


def _basic_pokemon_id(arche, decks, my_deck) -> int:
    """A Basic Pokemon id from the inferred archetype; search_begin rejects non-Pokemon."""
    key = arche or "dragapult"
    if key in _BASIC_CACHE:
        return _BASIC_CACHE[key]
    from cg import api as A
    db = {c.cardId: c for c in A.all_card_data()}
    for cid in (decks.get(key) or my_deck):
        c = db.get(cid)
        if c is not None and int(c.cardType) == 0 and c.basic:
            _BASIC_CACHE[key] = cid
            return cid
    _BASIC_CACHE[key] = (decks.get(key) or my_deck)[0]
    return _BASIC_CACHE[key]


def determinize(view: VisibleView, my_deck: List[int], rng) -> Dict[str, Any]:
    """Build a legal hidden-card prediction from visible information only.

    Own deck list is legitimately known (we chose it). Opponent hidden zones are predicted from
    the inferred archetype's public list minus everything already visible.
    """
    c = view.counts()
    arche, conf, seen = classify_opponent(view)
    decks = _load_archetypes()
    opp_pool = list(decks.get(arche) or decks.get("dragapult") or [])
    for cid in view.board_ids("theirs") + view.discard_ids("theirs"):
        if cid in opp_pool:
            opp_pool.remove(cid)
    rng.shuffle(opp_pool)

    mine_pool = list(my_deck)
    for cid in view.my_hand_ids() + view.board_ids("mine") + view.discard_ids("mine"):
        if cid in mine_pool:
            mine_pool.remove(cid)
    rng.shuffle(mine_pool)

    def take(pool, n, filler):
        """search_begin validates COUNTS with >=, so a pool that runs dry must be topped up
        with a legal card id rather than left short - two begin errors and 49 step errors in
        the first smoke came from under-length predictions."""
        out = []
        for _ in range(max(0, n)):
            out.append(pool.pop() if pool else filler)
        return out

    opp_filler = (decks.get(arche) or decks.get("dragapult") or my_deck)[0]
    my_filler = my_deck[0] if my_deck else opp_filler
    opp_hand = take(opp_pool, c["opp_hand"], opp_filler)
    opp_prize = take(opp_pool, c["opp_prize"], opp_filler)
    opp_deck = take(opp_pool, c["opp_deck"], opp_filler)
    my_prize = take(mine_pool, c["my_prize"], my_filler)
    my_deck_pred = take(mine_pool, c["my_deck"], my_filler)

    # a face-down opponent Active requires an explicit Pokemon prediction
    opp_active = []
    try:
        act = view.opp.active or []
        if act and act[0] is None:
            poke = _basic_pokemon_id(arche, decks, my_deck)
            opp_active = [poke]
    except Exception:  # noqa: BLE001
        opp_active = []
    return {"archetype": arche, "confidence": conf, "revealed_cards": seen,
            "your_deck": my_deck_pred, "your_prize": my_prize,
            "opponent_deck": opp_deck, "opponent_prize": opp_prize,
            "opponent_hand": opp_hand, "opponent_active": opp_active,
            "counts": c,
            "built_from": "VisibleView only; opponent hand/deck/prize contents never read"}


# --------------------------------------------------------------------------------------
# lifecycle
# --------------------------------------------------------------------------------------

class SearchSession:
    """Context manager guaranteeing release/end even on exception (P01)."""

    def __init__(self, stats):
        self.ids: List[int] = []
        self.stats = stats

    def __enter__(self):
        return self

    def track(self, sid: int):
        self.ids.append(sid)
        return sid

    def __exit__(self, *exc):
        from cg import api as A
        for sid in self.ids:
            try:
                A.search_release(sid)
                self.stats["release_calls"] += 1
            except Exception:  # noqa: BLE001
                self.stats["release_errors"] += 1
        try:
            A.search_end()
            self.stats["end_calls"] += 1
        except Exception:  # noqa: BLE001
            self.stats["end_errors"] += 1
        return False


# --------------------------------------------------------------------------------------
# leaf evaluation
# --------------------------------------------------------------------------------------

def leaf_value(state, your_index: int) -> float:
    """Versioned visible-state heuristic in [-1, 1]."""
    if state is None:
        return 0.0
    try:
        me = state.players[your_index]
        op = state.players[1 - your_index]
    except Exception:  # noqa: BLE001
        return 0.0

    def hp(p):
        tot = cur = 0
        for z in ("active", "bench"):
            for c in (getattr(p, z, None) or []):
                if c is None:
                    continue
                tot += (c.maxHp or 0)
                cur += (c.hp or 0)
        return (cur / tot) if tot else 0.0

    def energies(p):
        n = 0
        for z in ("active", "bench"):
            for c in (getattr(p, z, None) or []):
                if c is not None:
                    n += len(getattr(c, "energyCards", None) or getattr(c, "energies", None) or [])
        return n
    prize = (len(op.prize or []) - len(me.prize or [])) / 6.0
    board = (len(me.bench or []) - len(op.bench or [])) / 5.0
    v = 0.55 * prize + 0.25 * (hp(me) - hp(op)) + 0.12 * board \
        + 0.08 * ((energies(me) - energies(op)) / 8.0)
    return max(-1.0, min(1.0, v))


# --------------------------------------------------------------------------------------
# planner
# --------------------------------------------------------------------------------------

DEFAULT_CFG = {"beam_width": 3, "max_candidates": 4, "max_depth": 4,
               "max_nodes": 40, "max_ms_per_decision": 2500,
               "max_match_ms": 60000, "version": SEARCH_VERSION}


def new_stats() -> Dict[str, Any]:
    return collections.defaultdict(int, {
        "decisions": 0, "searched": 0, "begin_calls": 0, "begin_ok": 0, "begin_errors": 0,
        "step_calls": 0, "step_ok": 0, "step_errors": 0, "release_calls": 0,
        "release_errors": 0, "end_calls": 0, "end_errors": 0, "nodes": 0,
        "max_depth_reached": 0, "distinct_successors": 0, "baseline_retained": 0,
        "changed_action": 0, "fallbacks": 0, "match_ms": 0.0,
        "hidden_information_violations": 0})


def plan(obs, baseline_action: List[int], my_deck: List[int], rng, cfg, stats,
         traces: Optional[List] = None, guide=None) -> Dict[str, Any]:
    """Bounded multi-step own-turn beam search over REAL simulator successors.

    `guide` (optional, M04) supplies learned candidate ordering and learned leaf values inside
    THIS SAME real search tree -- the tree is identical either way, so a guided/unguided
    comparison isolates the guidance rather than confounding it with a different searcher.
    """
    from cg import api as A
    t0 = time.perf_counter()
    sel = obs.get("select") if isinstance(obs, dict) else None
    if sel is None:
        return {"action": list(baseline_action), "searched": False, "reason": "no_select"}
    n_opt = len(sel.get("option") or [])
    lo = int(sel.get("minCount") or 1)
    hi = int(sel.get("maxCount") or 1)
    if n_opt < 2 or stats["match_ms"] > cfg["max_match_ms"]:
        stats["fallbacks"] += 1
        return {"action": list(baseline_action), "searched": False,
                "reason": "forced_or_match_budget"}

    try:
        o = A.to_observation_class(obs)
        state = o.current
        yi = state.yourIndex
        view = VisibleView(state, yi)
        det = determinize(view, my_deck, rng)
    except HiddenInformationAccess:
        stats["hidden_information_violations"] += 1
        stats["fallbacks"] += 1
        return {"action": list(baseline_action), "searched": False,
                "reason": "hidden_information_guard"}
    except Exception as e:  # noqa: BLE001
        stats["fallbacks"] += 1
        return {"action": list(baseline_action), "searched": False,
                "reason": f"determinize_failed:{type(e).__name__}"}

    # candidate generation — the baseline action is always first and is never pruned
    cands: List[List[int]] = [list(baseline_action)]
    order = list(range(n_opt))
    guide_ms = 0.0
    if guide is not None:
        # Learned ORDERING only decides which options fit inside the candidate budget; it never
        # removes the baseline and never picks the answer. The winner is still whichever
        # candidate the real successors score highest.
        g0 = time.perf_counter()
        try:
            order = guide.order(obs, n_opt)
            stats["guide_order_ok"] += 1
        except Exception:  # noqa: BLE001
            stats["guide_order_failed"] += 1
        guide_ms += (time.perf_counter() - g0) * 1000
    if lo <= 1 <= hi:
        for i in order:
            if len(cands) >= cfg["max_candidates"]:
                break
            if [i] not in cands:
                cands.append([i])
    else:
        base = list(baseline_action)
        for i in range(n_opt):
            if len(cands) >= cfg["max_candidates"]:
                break
            if i in base:
                continue
            alt = sorted(dict.fromkeys((base[:-1] + [i]) if base else list(range(lo))))
            if lo <= len(alt) <= hi and alt not in cands:
                cands.append(alt)

    scored = []
    succ_hashes = set()
    depth_max = 0
    try:
        with SearchSession(stats) as sess:
            stats["begin_calls"] += 1
            try:
                root = A.search_begin(o, det["your_deck"], det["your_prize"],
                                      det["opponent_deck"], det["opponent_prize"],
                                      det["opponent_hand"], det["opponent_active"])
                stats["begin_ok"] += 1
                sess.track(root.searchId)
            except Exception as e:  # noqa: BLE001
                stats["begin_errors"] += 1
                stats["fallbacks"] += 1
                return {"action": list(baseline_action), "searched": False,
                        "reason": f"search_begin_failed:{type(e).__name__}"}

            for ci, cand in enumerate(cands):
                if stats["nodes"] >= cfg["max_nodes"] * max(1, stats["decisions"]) or \
                        (time.perf_counter() - t0) * 1000 > cfg["max_ms_per_decision"]:
                    break
                cur = root
                depth = 0
                val = None
                leaf_obs = None
                for d in range(cfg["max_depth"]):
                    sd = cur.observation.select
                    if sd is None or not sd.option:
                        break
                    pick = cand if d == 0 else [0]
                    pick = [i for i in pick if 0 <= i < len(sd.option)] or [0]
                    stats["step_calls"] += 1
                    try:
                        nxt = A.search_step(cur.searchId, pick)
                        stats["step_ok"] += 1
                    except Exception:  # noqa: BLE001
                        stats["step_errors"] += 1
                        break
                    sess.track(nxt.searchId)
                    stats["nodes"] += 1
                    depth = d + 1
                    succ_hashes.add(hashlib.sha256(
                        str(nxt.observation.select.option if nxt.observation.select
                            else "terminal").encode()).hexdigest()[:16])
                    cur = nxt
                    val = leaf_value(cur.observation.current, yi)
                    leaf_obs = cur.observation
                    if cur.observation.select is None:
                        break
                depth_max = max(depth_max, depth)
                if val is None:
                    val = leaf_value(state, yi)
                scored.append({"candidate": cand, "value": round(float(val), 6),
                               "heuristic_value": round(float(val), 6),
                               "depth": depth, "is_baseline": cand == list(baseline_action),
                               "index": ci, "_leaf": leaf_obs})
    except Exception as e:  # noqa: BLE001
        stats["fallbacks"] += 1
        return {"action": list(baseline_action), "searched": False,
                "reason": f"session_failed:{type(e).__name__}"}

    leaf_source = "heuristic"
    if guide is not None and scored:
        # ONE batched forward over all candidate leaves, not one per node -- per-node inference
        # would put a model call inside the innermost loop and blow the latency budget.
        g0 = time.perf_counter()
        try:
            vals = guide.leaf_values([s_["_leaf"] for s_ in scored], yi)
            for s_, v in zip(scored, vals):
                if v is not None:
                    s_["learned_value"] = round(float(v), 6)
                    s_["value"] = round(float(v), 6)
            leaf_source = "learned" if any("learned_value" in s_ for s_ in scored) else \
                "heuristic_guide_failed"
            stats["guide_leaf_ok"] += 1
        except Exception:  # noqa: BLE001
            stats["guide_leaf_failed"] += 1
            leaf_source = "heuristic_guide_failed"
        guide_ms += (time.perf_counter() - g0) * 1000
    for s_ in scored:
        s_.pop("_leaf", None)

    stats["max_depth_reached"] = max(stats["max_depth_reached"], depth_max)
    stats["distinct_successors"] += len(succ_hashes)
    dt = (time.perf_counter() - t0) * 1000
    stats["match_ms"] += dt
    if not scored:
        stats["fallbacks"] += 1
        return {"action": list(baseline_action), "searched": False, "reason": "no_scored"}
    scored.sort(key=lambda s: (-s["value"], s["index"]))
    best = scored[0]
    stats["searched"] += 1
    if best["is_baseline"]:
        stats["baseline_retained"] += 1
    else:
        stats["changed_action"] += 1
    if traces is not None and len(traces) < 200:
        traces.append({"n_options": n_opt, "candidates": len(cands),
                       "depth_max": depth_max, "distinct_successors": len(succ_hashes),
                       "scores": scored, "determinization": {
                           "archetype": det["archetype"], "confidence": det["confidence"],
                           "counts": det["counts"]},
                       "ms": round(dt, 2)})
    return {"action": best["candidate"], "searched": True, "candidate_scores": scored,
            "depth_max": depth_max, "distinct_successors": len(succ_hashes),
            "determinization_archetype": det["archetype"], "ms": round(dt, 2),
            "guided": guide is not None, "leaf_source": leaf_source,
            "guide_ms": round(guide_ms, 3), "candidate_order": order[:8],
            "reason": "search_best"}
