"""c023 — mine our own Kaggle ladder replays.

Everything else in this campaign measures the champion against a panel we assembled. This
measures it against the ladder it actually played on: the Kaggle episode API returns the full
replay of every public game a submission played, and a replay contains **both decks** — each
agent's 60-card list is its own first action.

So for each of our submissions we can recover, first-hand:

* which archetypes the ladder actually paired us against, and how often;
* our win rate against each of them;
* how long those games ran.

That is the same question `META_REPORT §2` answers from a third-party classifier over other
people's replays, except these are our games and our results.

Replays are ~4 MB each. Each is parsed and then **deleted**, so mining a hundred games costs a few
hundred megabytes of transfer and nothing on disk. Requests are paced; the API is shared.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

OUT = os.path.join(_REPO, "results", "c023_autonomous_meta_first_competition_sprint")
LADDER = os.path.join(OUT, "ladder_replays")

# Archetype signatures, most specific first. Card IDs are from the competition's own card data
# and the public score-band census (META_REPORT §2).
SIGNATURES: List[Tuple[str, int]] = [
    ("Marnie Grimmsnarl", 648),
    ("Mega Lopunny", 849),
    ("Teal Mask Ogerpon", 96),
    ("Cynthia Garchomp", 381),
    ("Team Rocket Mewtwo", 431),
    ("Mega Kangaskhan", 756),
    ("Mega Froslass", 861),
    ("N's Zoroark", 293),
    ("Iono Bellibolt", 269),
    ("Archaludon", 190),
    ("Mega Lucario", 678),
    ("Mega Abomasnow", 723),
    ("Alakazam", 743),
    ("Dragapult", 121),
    ("Crustle Wall", 345),
    ("Festival Lead", 93),
]

OUR_SUBMISSIONS = {
    54948560: "official_dragapult (c005)",
    55011215: "official_mega_lucario (c017)",
    55004756: "c014 archaludon expert",
    55005237: "c015 anti-meta expert",
}


def classify(deck: List[int]) -> str:
    s = set(deck)
    for name, cid in SIGNATURES:
        if cid in s:
            return name
    return "unclassified"


def deck_sha(deck: List[int]) -> str:
    return hashlib.sha256(",".join(str(c) for c in deck).encode()).hexdigest()


def mine(api, submission_id: int, limit: int, pace: float, our_deck_sha: Optional[str],
         workdir: str) -> Dict[str, Any]:
    eps = api.competition_list_episodes(submission_id=submission_id) or []
    rows: List[Dict[str, Any]] = []
    for i, e in enumerate(eps[:limit]):
        time.sleep(pace)
        try:
            api.competition_episode_replay(episode_id=e.id, path=workdir, quiet=True)
        except Exception as exc:  # noqa: BLE001
            rows.append({"episode": e.id, "error": f"{type(exc).__name__}: {exc}"})
            continue
        path = os.path.join(workdir, f"episode-{e.id}-replay.json")
        if not os.path.exists(path):
            rows.append({"episode": e.id, "error": "replay file missing"})
            continue
        try:
            d = json.load(open(path))
            steps = d.get("steps") or []
            decks = [None, None]
            for st in steps[:4]:
                for p in (0, 1):
                    a = st[p].get("action")
                    if isinstance(a, list) and len(a) == 60 and decks[p] is None:
                        decks[p] = [int(x) for x in a]
                if all(x is not None for x in decks):
                    break
            rewards = d.get("rewards") or [None, None]
            # Identify our seat by deck hash where we know it, else by the submission's reward.
            mine_idx = None
            if our_deck_sha:
                for p in (0, 1):
                    if decks[p] is not None and deck_sha(decks[p]) == our_deck_sha:
                        mine_idx = p
            if mine_idx is None:
                agents = list(getattr(e, "agents", None) or [])
                for p, ag in enumerate(agents[:2]):
                    if getattr(ag, "submission_id", None) == submission_id:
                        mine_idx = p
            row = {
                "episode": e.id,
                "type": str(getattr(e, "type", None)),
                "create_time": str(getattr(e, "create_time", None)),
                "steps": len(steps),
                "rewards": rewards,
                "our_seat": mine_idx,
                "our_deck_sha12": deck_sha(decks[mine_idx])[:12] if (mine_idx is not None and decks[mine_idx]) else None,
                "opponent_deck_sha12": (deck_sha(decks[1 - mine_idx])[:12]
                                        if (mine_idx is not None and decks[1 - mine_idx]) else None),
                "opponent_archetype": (classify(decks[1 - mine_idx])
                                       if (mine_idx is not None and decks[1 - mine_idx]) else None),
                "our_archetype": (classify(decks[mine_idx])
                                  if (mine_idx is not None and decks[mine_idx]) else None),
            }
            if mine_idx is not None and rewards[mine_idx] is not None:
                r = rewards[mine_idx]
                row["score"] = 1.0 if r == 1 else (0.5 if r == 0 else 0.0)
            rows.append(row)
        except Exception as exc:  # noqa: BLE001
            rows.append({"episode": e.id, "error": f"parse: {type(exc).__name__}: {exc}"})
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
        if (i + 1) % 10 == 0:
            print(f"    {i+1}/{min(limit, len(eps))} episodes", flush=True)

    scored = [r for r in rows if r.get("score") is not None]
    by_arch: Dict[str, List[float]] = collections.defaultdict(list)
    for r in scored:
        by_arch[r["opponent_archetype"] or "unknown"].append(r["score"])
    summary = {
        "submission_id": submission_id,
        "label": OUR_SUBMISSIONS.get(submission_id),
        "episodes_listed": len(eps),
        "episodes_parsed": len(rows),
        "episodes_scored": len(scored),
        "overall_score_rate": round(sum(r["score"] for r in scored) / len(scored), 4) if scored else None,
        "mean_steps": round(sum(r.get("steps") or 0 for r in scored) / len(scored), 1) if scored else None,
        "by_opponent_archetype": {
            a: {"games": len(v), "score_rate": round(sum(v) / len(v), 4),
                "share": round(len(v) / len(scored), 4)}
            for a, v in sorted(by_arch.items(), key=lambda kv: -len(kv[1]))},
        "our_archetype": collections.Counter(r.get("our_archetype") for r in scored).most_common(3),
        "errors": [r for r in rows if r.get("error")][:10],
    }
    return {"summary": summary, "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--submissions", default="54948560")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--pace", type=float, default=2.0)
    ap.add_argument("--workdir", default="/tmp/c023_replays")
    a = ap.parse_args()

    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    os.makedirs(a.workdir, exist_ok=True)
    os.makedirs(LADDER, exist_ok=True)

    from cg import c023_players as P
    known = {}
    for pid in ("official_dragapult", "official_mega_lucario"):
        try:
            d = P.resolve(pid)
            deck = [int(x) for x in open(os.path.join(d, "deck.csv")) if x.strip()]
            known[pid] = deck_sha(deck)
        except Exception:
            pass
    sha_for = {54948560: known.get("official_dragapult"),
               55011215: known.get("official_mega_lucario")}

    allsum = []
    for sid in [int(x) for x in a.submissions.split(",") if x]:
        print(f"[replays] submission {sid} ({OUR_SUBMISSIONS.get(sid)})", flush=True)
        res = mine(api, sid, a.limit, a.pace, sha_for.get(sid), a.workdir)
        with open(os.path.join(LADDER, f"submission_{sid}.json"), "w") as fh:
            json.dump(res, fh, indent=2)
        s = res["summary"]
        allsum.append(s)
        print(f"  {s['episodes_scored']} scored, overall {s['overall_score_rate']}", flush=True)
        for arch, v in s["by_opponent_archetype"].items():
            print(f"     {arch:22s} n={v['games']:4d}  share={v['share']:.3f}  "
                  f"score={v['score_rate']:.3f}", flush=True)
    with open(os.path.join(LADDER, "LADDER_SUMMARY.json"), "w") as fh:
        json.dump({"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "submissions": allsum}, fh, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
