"""c024 — check the prize tracker against real games, with an exact oracle.

A prize deduction cannot be checked by playing better; it is either right or wrong about a fact,
and the fact is revealed later in the same game. Every prize card eventually moves PRIZE -> HAND
and the log for that move carries its card id. So:

    every card the tracker declared prized, at the moment it declared it, must be a card the game
    later takes out of the prize pile -- or must still be sitting there when the game ends.

That is a complete test, and it runs on data already in hand: the champion's own Kaggle ladder
replays, which carry the full observation stream for both seats.

The governing rule from the technique write-up is asymmetric, so the report is too. A frame where
the tracker returns unknown costs nothing. A frame where it names the wrong card is a defect, and
`violations` must be zero before any search is allowed to consume this.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

OUT = os.path.join(_REPO, "results", "c024_final_sprint")


def check_replay(replay: Dict[str, Any], my_deck: List[int], my_sha: str) -> Optional[Dict[str, Any]]:
    from cg.api import AreaType, to_observation_class
    from cg.c024_prizes import PrizeTracker

    steps = replay.get("steps") or []
    decks: List[Optional[List[int]]] = [None, None]
    for st in steps[:4]:
        for p in (0, 1):
            a = st[p].get("action")
            if isinstance(a, list) and len(a) == 60 and decks[p] is None:
                decks[p] = [int(x) for x in a]
        if all(d is not None for d in decks):
            break
    me = None
    for p in (0, 1):
        if decks[p] is None:
            continue
        h = hashlib.sha256(",".join(str(c) for c in decks[p]).encode()).hexdigest()
        if h == my_sha:
            me = p
    if me is None:
        return None

    tracker = PrizeTracker(my_deck)
    # Every declaration the tracker has ever made, as (frame_index, Counter). A declaration is
    # falsified the moment the game takes a prize card the declaration did not contain.
    declared_at: List[Dict[str, Any]] = []
    live: Optional[collections.Counter] = None
    stats = {"frames": 0, "declared_frames": 0, "prize_take_events": 0,
             "checked_takes": 0, "violations": 0, "violation_detail": [],
             "first_declaration_turn": None, "final_still_held_ok": None}

    for idx, st in enumerate(steps):
        cell = st[me]
        obs_d = cell.get("observation") or {}
        if not obs_d.get("select"):
            continue
        # A replay records BOTH seats at every step, and the seat that is not acting carries a
        # stale copy of its last observation -- select, logs and all. In one sample game player 0
        # had 59 ACTIVE frames with a selection and 94 INACTIVE ones. Replaying those repeats
        # every log, so a single prize-to-hand event is counted many times: the tracker decrements
        # the same card until the count goes negative and the set self-invalidates, and the oracle
        # then reads the re-processed event as a violation. Only ACTIVE frames are real decisions.
        if cell.get("status") != "ACTIVE":
            continue
        try:
            obs = to_observation_class(obs_d)
        except Exception:  # noqa: BLE001
            continue
        if obs.current is None or obs.select is None:
            continue
        stats["frames"] += 1

        # Oracle first, against the declaration standing BEFORE this frame's update, so a taken
        # prize is checked against what the tracker believed while it still mattered.
        for lg in (obs.logs or []):
            if (getattr(lg, "playerIndex", None) == me and lg.fromArea == AreaType.PRIZE
                    and lg.toArea == AreaType.HAND and lg.cardId is not None):
                stats["prize_take_events"] += 1
                if live is not None:
                    stats["checked_takes"] += 1
                    if live.get(int(lg.cardId), 0) <= 0:
                        stats["violations"] += 1
                        stats["violation_detail"].append(
                            {"step": idx, "card_id": int(lg.cardId),
                             "declared": dict(live)})
                    else:
                        live[int(lg.cardId)] -= 1
                        live += collections.Counter()

        tracker.update(obs, me)
        k = tracker.known()
        if k is not None:
            if live is None:
                stats["first_declaration_turn"] = int(obs.current.turn)
            stats["declared_frames"] += 1
            live = k
            declared_at.append({"step": idx, "prized": dict(k)})
        else:
            live = None

    stats["deductions"] = tracker.deductions
    stats["claims"] = tracker.claims
    stats["invalidations"] = tracker.invalidations
    stats["declarations"] = len(declared_at)
    return stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--submission", type=int, default=54948560)
    ap.add_argument("--player", default="official_dragapult")
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--pace", type=float, default=1.2)
    ap.add_argument("--cache", default=os.environ.get("C024_REPLAY_CACHE", "/tmp/c024_replays"))
    a = ap.parse_args()

    from cg import c023_players as P

    d = P.resolve(a.player)
    deck = [int(x) for x in open(os.path.join(d, "deck.csv")) if x.strip()]
    sha = hashlib.sha256(",".join(str(c) for c in deck).encode()).hexdigest()
    os.makedirs(a.cache, exist_ok=True)

    cached = sorted(f for f in os.listdir(a.cache) if f.endswith("-replay.json"))
    if not cached:
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()
        eps = api.competition_list_episodes(submission_id=a.submission) or []
        for i, e in enumerate(eps[:a.limit]):
            time.sleep(a.pace)
            try:
                api.competition_episode_replay(episode_id=e.id, path=a.cache, quiet=True)
            except Exception as exc:  # noqa: BLE001
                print(f"  episode {e.id}: {type(exc).__name__}: {str(exc)[:70]}", flush=True)
            if (i + 1) % 20 == 0:
                print(f"  downloaded {i+1}/{min(a.limit, len(eps))}", flush=True)
        cached = sorted(f for f in os.listdir(a.cache) if f.endswith("-replay.json"))

    rows = []
    for f in cached:
        try:
            r = check_replay(json.load(open(os.path.join(a.cache, f))), deck, sha)
        except Exception as exc:  # noqa: BLE001
            print(f"  {f}: {type(exc).__name__}: {str(exc)[:70]}")
            continue
        if r:
            r["replay"] = f
            rows.append(r)

    tot = {k: sum(r[k] for r in rows) for k in
           ("frames", "declared_frames", "prize_take_events", "checked_takes", "violations",
            "deductions", "claims", "invalidations", "declarations")}
    games_with = sum(1 for r in rows if r["declarations"] > 0)
    turns = [r["first_declaration_turn"] for r in rows if r["first_declaration_turn"] is not None]
    payload = {
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "player": a.player, "submission": a.submission, "games": len(rows),
        "games_with_a_declaration": games_with,
        "median_first_declaration_turn": sorted(turns)[len(turns) // 2] if turns else None,
        "totals": tot,
        "violations_detail": [v for r in rows for v in r["violation_detail"]][:20],
        "per_game": rows,
    }
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "PRIZE_ORACLE.json"), "w") as fh:
        json.dump(payload, fh, indent=2)

    print(f"\ngames parsed                 {len(rows)}")
    print(f"games with a declaration     {games_with}")
    print(f"median turn of 1st deduction {payload['median_first_declaration_turn']}")
    print(f"frames                       {tot['frames']}")
    print(f"frames with a live set       {tot['declared_frames']}  "
          f"({100*tot['declared_frames']/max(1,tot['frames']):.1f}%)")
    print(f"prize cards taken            {tot['prize_take_events']}")
    print(f"  ... while a set was live   {tot['checked_takes']}   <- the checked ones")
    print(f"deductions / claims / drops  {tot['deductions']} / {tot['claims']} / {tot['invalidations']}")
    print(f"\nVIOLATIONS                   {tot['violations']}")
    return 0 if tot["violations"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
