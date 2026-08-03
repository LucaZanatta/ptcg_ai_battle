"""c023 — constrained deck co-optimization around a strong seed list.

Two rules govern what this tool will and will not do.

**Only cards the agent understands.** These sample agents dispatch on hard-coded card IDs. A card
the policy has never heard of falls through to a generic score — for the trainers that is 10000,
*above* every named Supporter in the Mega Lucario list — so adding an unknown card does not add a
tool, it adds a card the agent will misplay eagerly. Every mutation here therefore draws from the
base deck's own card set unless the wrapper is extended in the same change.

**Few mutations, each measured properly.** A one-card-swap sweep over 20 cards is ~400 arms; at a
budget that fits the deadline each arm would get ~120 games, whose standard error is ±4.5 points —
larger than the effect being looked for, so the winner would be noise with a rationale attached.
This tool instead takes a hand-written list of semantically motivated mutations, each naming the
failure or matchup it is meant to correct, and spends the budget on games per arm.

Legality is checked against the engine, not against a rulebook paraphrase: a candidate deck is
started in a real battle and rejected if `BattleStart` reports a deck error.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

OUT = os.path.join(_REPO, "results", "c023_autonomous_meta_first_competition_sprint")

# Pokémon TCG deck rules the engine enforces; checked here so a bad mutation is rejected before
# it costs games rather than after.
MAX_COPIES = 4          # except basic energy
BASIC_ENERGY_IDS = {2, 3, 4, 5, 6, 7, 8, 9, 10}


def deck_counts(deck: List[int]) -> Dict[int, int]:
    return dict(collections.Counter(deck))


def apply_mutation(deck: List[int], remove: List[int], add: List[int]) -> Optional[List[int]]:
    c = collections.Counter(deck)
    for r in remove:
        if c[r] <= 0:
            return None
        c[r] -= 1
    for a in add:
        c[a] += 1
    out: List[int] = []
    for cid, n in sorted(c.items()):
        if n < 0:
            return None
        if n > MAX_COPIES and cid not in BASIC_ENERGY_IDS:
            return None
        out.extend([cid] * n)
    return out if len(out) == 60 else None


def deck_legal(deck: List[int]) -> Tuple[bool, str]:
    """Ask the engine. A deck the engine refuses produces a null battle pointer."""
    from cg.game import battle_start, battle_finish
    try:
        obs, sd = battle_start(list(deck), list(deck))
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"
    if obs is None:
        return False, f"engine rejected deck (errorPlayer={sd.errorPlayer} errorType={sd.errorType})"
    try:
        battle_finish()
    except Exception:
        pass
    return True, "ok"


def load_mutations(path: str) -> List[Dict[str, Any]]:
    with open(path) as fh:
        muts = json.load(fh)
    for m in muts:
        for k in ("id", "remove", "add", "intent"):
            if k not in m:
                raise ValueError(f"mutation {m.get('id','?')} missing {k!r}; "
                                 f"DECK_CHANGE_LEDGER requires an intent for every change")
    return muts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="official player id used as the agent base")
    ap.add_argument("--seed-deck", help="path to a deck.csv to mutate; default = base's own deck")
    ap.add_argument("--mutations", required=True, help="path to a mutations json")
    ap.add_argument("--prefix", default="deck")
    ap.add_argument("--params", help="params.json shared by every arm")
    ap.add_argument("--build-only", action="store_true")
    a = ap.parse_args()

    from cg import c023_players as P
    sys.path.insert(0, os.path.join(_REPO, "tools"))
    import c023_build_candidate as B

    if a.seed_deck:
        with open(a.seed_deck) as fh:
            seed = [int(x) for x in fh if x.strip()]
    else:
        seed = B.base_deck(a.base)
    params = json.load(open(a.params)) if a.params else None

    muts = load_mutations(a.mutations)
    built, rejected = [], []
    for m in muts:
        deck = apply_mutation(seed, m["remove"], m["add"])
        if deck is None:
            rejected.append({**m, "reason": "count/size rule"})
            continue
        ok, why = deck_legal(deck)
        if not ok:
            rejected.append({**m, "reason": why})
            continue
        cid = f"{a.prefix}_{m['id']}"
        man = B.build(cid, a.base, deck, params, parent=a.base, rationale=m["intent"])
        built.append({"candidate_id": cid, "mutation": m, "deck_sha256": man["deck_sha256"]})
        print(f"BUILT {cid:32s} -{m['remove']} +{m['add']}  {m['intent'][:60]}")
    for r in rejected:
        print(f"REJECT {r['id']:31s} {r['reason']}")

    os.makedirs(os.path.join(OUT, "decks"), exist_ok=True)
    with open(os.path.join(OUT, "decks", f"{a.prefix}_build.json"), "w") as fh:
        json.dump({"base": a.base, "seed_deck": seed, "built": built, "rejected": rejected,
                   "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, fh, indent=2)
    print(f"\n{len(built)} built, {len(rejected)} rejected")
    print(",".join(b["candidate_id"] for b in built))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
