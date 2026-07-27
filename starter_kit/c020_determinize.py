"""c020 A7 — legal determinization with an explicit unknown-archetype prior mixture.

c019 line 151 of `c019_determinize.py` reads:

    pool_arch = arch if arch in decks else ("dragapult" if "dragapult" in decks else "__own__")

which is audit finding #5 exactly: when the opponent's archetype cannot yet be identified, EVERY
sampled world assumed Dragapult. The search then optimized against one specific opponent it had no
evidence for, and did so with full confidence. `MANDATORY_CHANGES A7` forbids the silent default
and requires a recorded prior mixture over frozen known archetypes plus an `unknown` fallback
built only from legal generic assumptions.

The multiplicity machinery from c019 was correct (exact counts, no filler duplication, rejection
and resampling of impossible worlds) and is reused unchanged; only the archetype selection is
corrected, so the change is attributable.
"""

from __future__ import annotations

import collections
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_core as K  # noqa: E402
from cg import c019_determinize as D19  # noqa: E402

ARCHETYPES = D19.ARCHETYPES

# Registered prior over archetypes when the opponent has revealed nothing distinguishing.
# Uniform over the frozen known field plus an explicit `unknown` mass: with no evidence there is
# no justification for preferring any one archetype, and the `unknown` mass exists so the search
# is exposed to worlds not drawn from any specific known list.
ARCHETYPE_PRIOR: Dict[str, float] = {
    "dragapult": 0.22,
    "mega_lucario": 0.22,
    "iono": 0.22,
    "mega_abomasnow": 0.22,
    "unknown": 0.12,
}
PRIOR_VERSION = "c020.archetype_prior.v1"

# Confidence below which the observation is treated as not yet identifying the archetype.
IDENTIFY_CONFIDENCE = 0.35


@dataclass
class ArchetypeDraw:
    """One sampled archetype, with the evidence and prior that produced it."""

    archetype: str                 # the label believed (may be "unknown")
    pool_archetype: str            # the concrete list actually sampled from
    confidence: float
    source: str                    # "identified" | "prior_mixture"
    prior_used: Dict[str, float]
    revealed_cards: int

    def to_json(self) -> Dict[str, Any]:
        return {"archetype": self.archetype, "pool_archetype": self.pool_archetype,
                "confidence": round(self.confidence, 4), "source": self.source,
                "prior_used": self.prior_used, "revealed_cards": self.revealed_cards,
                "prior_version": PRIOR_VERSION}


def sample_archetype(view: K.VisibleObservation, rng) -> ArchetypeDraw:
    """A7: identify from revealed cards, else DRAW from the recorded prior mixture.

    The critical difference from c019 is the `else` branch. c019 forced one archetype; here a
    different archetype may be drawn per determinization, so a set of determinizations represents
    the actual uncertainty instead of one confident guess.
    """
    arch, conf, revealed = D19.classify_archetype(view)
    decks = D19.archetype_decks()
    n_revealed = sum(revealed.values()) if isinstance(revealed, dict) else 0

    if arch in decks and conf >= IDENTIFY_CONFIDENCE:
        return ArchetypeDraw(archetype=arch, pool_archetype=arch, confidence=conf,
                             source="identified", prior_used={arch: 1.0},
                             revealed_cards=n_revealed)

    names = [a for a in ARCHETYPE_PRIOR if a == "unknown" or a in decks]
    weights = [ARCHETYPE_PRIOR[a] for a in names]
    tot = sum(weights) or 1.0
    weights = [w / tot for w in weights]
    r, acc = rng.random(), 0.0
    drawn = names[-1]
    for name, w in zip(names, weights):
        acc += w
        if r <= acc:
            drawn = name
            break

    if drawn == "unknown":
        # A7: the fallback uses only legal generic assumptions. Sampling from our OWN legal
        # decklist is the one generic pool guaranteed to respect card legality and multiplicity
        # without asserting anything about the opponent's list.
        return ArchetypeDraw(archetype="unknown", pool_archetype="__own__", confidence=conf,
                             source="prior_mixture",
                             prior_used=dict(zip(names, [round(w, 4) for w in weights])),
                             revealed_cards=n_revealed)
    return ArchetypeDraw(archetype="unknown", pool_archetype=drawn, confidence=conf,
                         source="prior_mixture",
                         prior_used=dict(zip(names, [round(w, 4) for w in weights])),
                         revealed_cards=n_revealed)


def determinize(view: K.VisibleObservation, my_deck: List[int], rng,
                archetype: Optional[str] = None):
    """One legal world. Multiplicity/rejection machinery is c019's, verified and unchanged."""
    draw = sample_archetype(view, rng) if archetype is None else ArchetypeDraw(
        archetype=archetype, pool_archetype=archetype, confidence=1.0, source="forced",
        prior_used={archetype: 1.0}, revealed_cards=0)

    det = D19.determinize(view, my_deck, rng,
                          archetype=None if draw.pool_archetype == "__own__"
                          else draw.pool_archetype)
    # attach the c020 provenance so every trace shows WHY this world was sampled
    try:
        det.archetype = draw.archetype
        det.archetype_confidence = draw.confidence
    except Exception:  # noqa: BLE001
        pass
    return det, draw


def prior_report() -> Dict[str, Any]:
    return {"prior_version": PRIOR_VERSION, "prior": ARCHETYPE_PRIOR,
            "identify_confidence": IDENTIFY_CONFIDENCE,
            "note": "c019 defaulted to dragapult whenever the archetype was unidentified "
                    "(C019_AUDIT_FINDINGS #5); c020 draws from this mixture per determinization"}
