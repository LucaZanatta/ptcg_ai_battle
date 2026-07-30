"""c022 A2 — fresh legal hidden worlds from one fixed public root.

`MANDATORY_IMPLEMENTATION A2` requires a deterministic harness that can request repeated
`search_begin` sessions from the same public root state while varying ONLY the environment RNG
seed, and that verifies for every generated world:

    public observation identical · hidden completion legal · card multiplicities legal ·
    no root-player-inaccessible information reaches the agent · terminal/result semantics match
    the live simulator · world identity logged without revealing hidden contents to policy code

This module is the whole hidden-information surface of the c022 MCGS branch. Every world the
search ever sees is built here, so the guarantees are enforced in one place instead of being
re-argued at each call site.

Two design points are deliberate and load-bearing.

**World seeds come from a dedicated stream.** `world_seeds()` derives seeds from
`(base_seed, decision_index)` through a SHA-256 mix, not by drawing from the agent's own
generator. If world seeds were drawn from the agent RNG, adding a second world would shift every
later draw in that generator, and the K=1 arm would stop reproducing c021 for a reason that has
nothing to do with the algorithm. Probe M04 depends on this.

**World identity is a hash, and hidden contents never leave.** `WorldHandle.world_id` is a digest
over the sampled zones, which is the source's own idea (`PIMC.DeterminizationHash` hashes own
deck order, opponent deck order and opponent hand). It is what gets logged. The zone lists
themselves are handed to `api.search_begin` and to nothing else — in particular never to a policy,
a prior provider or a feature encoder. `assert_no_leakage` makes that a checked property rather
than a convention.
"""

from __future__ import annotations

import hashlib
import os
import struct
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import api as A  # noqa: E402
from cg import c019_core as K  # noqa: E402
from cg import c020_determinize as DT  # noqa: E402

WORLD_SEED_STREAM = "c022.world_seed.v1"

# The zones a determinization fills in. Everything here is hidden from the root player and must
# never reach policy code; `LEAKY_FIELDS` is the checked list.
HIDDEN_FIELDS = ("your_deck", "your_prize", "opponent_deck", "opponent_prize",
                 "opponent_hand", "opponent_active")


def world_seeds(base_seed: int, decision_index: int, k: int) -> List[int]:
    """K distinct world seeds for one decision, from a stream independent of the agent RNG.

    Deterministic in `(base_seed, decision_index, k)`, so a decision replays identically and the
    K=1 arm consumes the agent's own generator exactly as the c021 control did.
    """
    out = []
    for i in range(k):
        h = hashlib.sha256(
            f"{WORLD_SEED_STREAM}|{int(base_seed)}|{int(decision_index)}|{i}".encode()).digest()
        out.append(struct.unpack("<Q", h[:8])[0] & ((1 << 63) - 1))
    return out


@dataclass
class WorldHandle:
    """One sampled hidden world. Identity is public; contents are not.

    `zones` is the only place the hidden lists live. `summary()` and `__repr__` deliberately do
    not include it, so a world cannot be logged into an artifact by accident.
    """

    index: int
    seed: int
    world_id: str
    zones: Dict[str, List[int]] = field(repr=False, default_factory=dict)
    archetype: str = "unknown"
    archetype_confidence: float = 0.0
    legal: bool = True
    rejection: Optional[str] = None
    multiplicity_ok: bool = True
    multiplicity_detail: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> Dict[str, Any]:
        """What may be written to a trace. Contains no card identity from a hidden zone."""
        return {
            "index": self.index, "seed": self.seed, "world_id": self.world_id,
            "archetype": self.archetype,
            "archetype_confidence": round(float(self.archetype_confidence), 4),
            "legal": self.legal, "rejection": self.rejection,
            "multiplicity_ok": self.multiplicity_ok,
            "sizes": {f: len(self.zones.get(f, [])) for f in HIDDEN_FIELDS},
        }

    def begin_args(self) -> Tuple[List[int], ...]:
        return tuple(list(self.zones.get(f, [])) for f in HIDDEN_FIELDS)


def _world_id(zones: Dict[str, List[int]]) -> str:
    """Digest over the sampled world, mirroring `PIMC.DeterminizationHash`.

    The source hashes: own deck ORDER, opponent deck ORDER, and opponent hand CONTENTS (sorted).
    Order matters for the decks because draw order is part of the world; the hand is a set, so it
    is sorted before hashing. Reproducing that distinction matters — hashing the hand in order
    would call two identical hands different worlds and defeat deduplication.
    """
    h = hashlib.sha256()
    h.update(b"c022.world_id.v1")
    for f in ("your_deck", "opponent_deck"):                 # ordered
        h.update(f.encode())
        h.update(np.asarray(zones.get(f, []), dtype=np.int64).tobytes())
    for f in ("opponent_hand", "opponent_active", "your_prize", "opponent_prize"):  # unordered
        h.update(f.encode())
        h.update(np.asarray(sorted(zones.get(f, [])), dtype=np.int64).tobytes())
    return h.hexdigest()[:16]


def check_multiplicity(zones: Dict[str, List[int]], my_deck: List[int]) -> Tuple[bool, Dict]:
    """Card multiplicities must be legal in every sampled world.

    Two rules are checked, and both have bitten this repository before:

    1. **The root player's own zones must be a partition of the root player's own deck.** The
       agent knows its own decklist exactly, so a world that gives it a 61st card or a fifth copy
       of a capped card is not merely unlikely, it is impossible, and searching it is searching
       a state the engine can never reach.
    2. **No card may exceed 4 copies** across the opponent's sampled zones, except basic energy.
       `c021_byterl_deck.is_basic_energy` is the structural test (cardType == 5 and no skills);
       a name match would classify *Energy Retrieval* as uncapped, which is the defect family
       recorded in c020's substring-classification finding.
    """
    from cg import c021_byterl_deck as DK

    detail: Dict[str, Any] = {}
    ok = True

    mine = Counter(zones.get("your_deck", [])) + Counter(zones.get("your_prize", []))
    declared = Counter(my_deck)
    # The agent's hand/board/discard are already out of the deck at this point, so the sampled
    # own-zones must be a SUBSET of the declared deck, never a superset.
    excess = {c: n - declared.get(c, 0) for c, n in mine.items() if n > declared.get(c, 0)}
    detail["own_zone_excess"] = excess
    if excess:
        ok = False

    opp = Counter()
    for f in ("opponent_deck", "opponent_prize", "opponent_hand", "opponent_active"):
        opp += Counter(zones.get(f, []))
    over = {}
    for cid, n in opp.items():
        if n <= 4:
            continue
        cd = None
        try:
            from cg import c020_cards as CD
            cd = CD.card(cid)
        except Exception:  # noqa: BLE001
            cd = None
        if not DK.is_basic_energy(cd):
            over[cid] = n
    detail["opponent_over_copy_limit"] = over
    if over:
        ok = False

    detail["opponent_total_cards"] = int(sum(opp.values()))
    detail["own_total_sampled"] = int(sum(mine.values()))
    return ok, detail


def sample_world(view, my_deck: List[int], seed: int, index: int) -> WorldHandle:
    """Draw one legal hidden world from the PUBLIC view alone.

    `view` is a `c019_core.VisibleObservation`, which by construction exposes only what the root
    player can see. Passing the raw observation instead would let the determinizer read the
    opponent's real hand out of the environment and produce a world that is not a guess at all —
    the kind of leak that makes a search look brilliant in evaluation and useless in play.
    """
    rng = np.random.default_rng(seed)
    det, draw = DT.determinize(view, my_deck, rng)
    zones = {f: [int(x) for x in (getattr(det, f, None) or [])] for f in HIDDEN_FIELDS}
    mult_ok, mult_detail = check_multiplicity(zones, my_deck)
    return WorldHandle(
        index=index, seed=int(seed), world_id=_world_id(zones), zones=zones,
        archetype=str(getattr(det, "archetype", draw.archetype)),
        archetype_confidence=float(getattr(det, "archetype_confidence", draw.confidence)),
        legal=bool(getattr(det, "legal", True)),
        rejection=getattr(det, "rejection", None),
        multiplicity_ok=mult_ok, multiplicity_detail=mult_detail)


def sample_worlds(view, my_deck: List[int], base_seed: int, decision_index: int, k: int,
                  dedupe: bool = True, max_attempts_factor: int = 8) -> List[WorldHandle]:
    """K worlds for one decision, deduplicated by world id.

    Deduplication is the source's behaviour: `GenerateDeterminizationsAtOnce` drops a
    determinization whose `DeterminizationHash` it has already seen, so the ensemble is a set of
    DISTINCT worlds. Without it, K=8 could quietly be four copies of two worlds and the
    "world diversity" arm would measure nothing.

    Unlike the source — which simply returns a shorter array — this keeps drawing from the seed
    stream until it has K distinct legal worlds or exhausts its attempt budget, so the K arms
    really do differ in K and not in luck. Any shortfall is visible: the returned list is short,
    and the caller records `len(worlds)`.
    """
    want = max(1, int(k))
    attempts = want * max(1, int(max_attempts_factor))
    seeds = world_seeds(base_seed, decision_index, attempts)
    out: List[WorldHandle] = []
    seen = set()
    for i, s in enumerate(seeds):
        if len(out) >= want:
            break
        w = sample_world(view, my_deck, s, len(out))
        if not w.legal or not w.multiplicity_ok:
            continue
        if dedupe and w.world_id in seen:
            continue
        seen.add(w.world_id)
        out.append(w)
    return out


# ------------------------------------------------------------------ leakage guarantee
LEAKY_FIELDS = HIDDEN_FIELDS


def assert_no_leakage(payload: Any, where: str = "") -> None:
    """Raise if a structure about to leave the search carries hidden zone CONTENTS.

    Called on every trace record and every payload handed to a prior provider.

    What counts as a leak is card IDENTITY, not zone size. `len(opponent_deck)` is public — a
    PTCG player can see how many cards remain in the opponent's deck — and recording it is
    positive evidence that the sampled world matches the real public counts. So a hidden field
    name carrying a SCALAR passes, and the same name carrying a collection does not.

    Drawing the line at the name alone was this function's first version, and it rejected
    `WorldHandle.summary()`'s own `sizes` block. That would have pushed the sizes out of the
    trace, removing the evidence that worlds are legally sized, to prevent a disclosure that
    cannot occur. The rule below is narrower and still catches the disguised case: any list of
    20+ integers is treated as a sampled zone whatever key it hides under.
    """
    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                ks = str(k).lower()
                named = k in LEAKY_FIELDS or any(
                    t in ks for t in ("hand", "deck", "prize", "zone"))
                if named and not isinstance(v, (int, float, str, bool, type(None))):
                    raise LeakageError(
                        f"{where}: hidden field {k!r} carries a {type(v).__name__} at {path}")
                walk(v, f"{path}.{k}")
        elif isinstance(o, (list, tuple)):
            if len(o) >= 20 and all(isinstance(x, int) and not isinstance(x, bool) for x in o):
                raise LeakageError(
                    f"{where}: list of {len(o)} ints at {path} looks like a sampled zone")
            for i, v in enumerate(o[:64]):
                walk(v, f"{path}[{i}]")
    walk(payload, "")


class LeakageError(RuntimeError):
    """A hidden zone was about to reach code that must not see it."""


# ------------------------------------------------------------------ session harness
@dataclass
class SessionResult:
    world: WorldHandle
    ok: bool
    error: Optional[str] = None
    root_option_signature: Optional[str] = None
    n_options: int = 0


def option_signature(sel) -> str:
    """A stable signature for the root's legal option set.

    Cross-world aggregation keys on ACTION INDEX (the source matches `edge.ActionIndex`). That is
    only sound if every world presents the same options in the same order. Public information is
    identical across worlds, so it should hold — but "should" is how index mis-maps happen, and
    this repository has already shipped one. The signature is computed per world and compared;
    a mismatch aborts the aggregate rather than silently summing statistics for different actions.
    """
    parts = [f"ctx={int(getattr(sel, 'context', -1) or -1)}",
             f"lo={int(getattr(sel, 'minCount', 0) or 0)}",
             f"hi={int(getattr(sel, 'maxCount', 0) or 0)}"]
    for o in K.canonical_options(sel):
        parts.append(o.short())
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def open_session(obs, world: WorldHandle, manual_coin: bool = True):
    """`search_begin` for one world. The zone lists reach the engine and nothing else."""
    yd, yp, od, op, oh, oa = world.begin_args()
    return A.search_begin(obs, yd, yp, od, op, oh, oa, manual_coin=bool(manual_coin))


class OptionSetMismatch(RuntimeError):
    """Two worlds presented different root options, so action indices are not comparable."""
