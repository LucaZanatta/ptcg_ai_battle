"""c023 — mine the champion's real ladder LOSSES, turn by turn.

`tools/c023_replays.py` used these replays for two things: the decks, and the reward. Everything
inside the game went unread. This reads it.

A Kaggle replay carries the full observation stream — every state either agent saw and every
action it took — so the same features `tools/c023_mine.py` extracts from local games can be
extracted from real ladder games instead. The difference is what generated them: real opponents,
at our rating, playing decks nobody on our panel plays.

Wins are contrasted against losses on features that map onto a decision, and the contrast is read
with the same caution the local mining needed: losing games are shorter, so every *count* falls in
losses as an arithmetic consequence of losing. Rates and turn-indices are the features that
survive that confound.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import statistics
import sys
import time
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

OUT = os.path.join(_REPO, "results", "c023_autonomous_meta_first_competition_sprint")
LADDER = os.path.join(OUT, "ladder_replays")

SIGNATURES = [("Marnie Grimmsnarl", 648), ("Mega Lopunny", 849), ("Teal Mask Ogerpon", 96),
              ("Cynthia Garchomp", 381), ("Team Rocket Mewtwo", 431), ("Mega Kangaskhan", 756),
              ("Mega Froslass", 861), ("N's Zoroark", 293), ("Iono Bellibolt", 269),
              ("Archaludon", 190), ("Mega Lucario", 678), ("Mega Abomasnow", 723),
              ("Alakazam", 743), ("Dragapult", 121), ("Crustle Wall", 345),
              ("Festival Lead", 93)]


def classify(deck: List[int]) -> str:
    s = set(deck)
    for name, cid in SIGNATURES:
        if cid in s:
            return name
    return "unclassified"


def game_features(replay: Dict[str, Any], my_deck_sha: str) -> Optional[Dict[str, Any]]:
    from cg.api import OptionType, SelectContext, to_observation_class

    steps = replay.get("steps") or []
    decks = [None, None]
    for st in steps[:4]:
        for p in (0, 1):
            a = st[p].get("action")
            if isinstance(a, list) and len(a) == 60 and decks[p] is None:
                decks[p] = [int(x) for x in a]
        if all(d is not None for d in decks):
            break
    if not all(d is not None for d in decks):
        return None
    me = None
    for p in (0, 1):
        h = hashlib.sha256(",".join(str(c) for c in decks[p]).encode()).hexdigest()
        if h == my_deck_sha:
            me = p
    if me is None:
        return None
    rewards = replay.get("rewards") or [None, None]
    if rewards[me] is None:
        return None

    f = {
        "opponent_archetype": classify(decks[1 - me]),
        "score": 1.0 if rewards[me] == 1 else (0.5 if rewards[me] == 0 else 0.0),
        "steps": len(steps),
        "decisions": 0, "main_decisions": 0,
        "attack_available": 0, "attack_taken": 0,
        "retreat_available": 0, "retreat_taken": 0,
        "first_attack_turn": None, "last_turn": 0,
        "active_zero_energy_main": 0,
        "bench_sum": 0, "hand_sum": 0, "deck_sum": 0, "samples": 0,
        "my_prize_min": 6, "op_prize_min": 6,
        "turns_seen": set(), "turns_attacked": set(), "turns_attack_available": set(),
        "prize_lead_by_turn": {},
    }
    for st in steps:
        cell = st[me]
        obs_d = cell.get("observation") or {}
        act = cell.get("action")
        if not obs_d.get("select"):
            continue
        try:
            obs = to_observation_class(obs_d)
        except Exception:
            continue
        sel, cur = obs.select, obs.current
        if sel is None or cur is None:
            continue
        mp = cur.players[cur.yourIndex]
        op = cur.players[1 - cur.yourIndex]
        t = int(cur.turn)
        f["decisions"] += 1
        f["turns_seen"].add(t)
        f["last_turn"] = max(f["last_turn"], t)
        f["my_prize_min"] = min(f["my_prize_min"], len(mp.prize))
        f["op_prize_min"] = min(f["op_prize_min"], len(op.prize))
        f["bench_sum"] += len(mp.bench)
        f["hand_sum"] += len(mp.hand)
        f["deck_sum"] += int(mp.deckCount)
        f["samples"] += 1
        f["prize_lead_by_turn"][t] = len(op.prize) - len(mp.prize)
        if sel.context != SelectContext.MAIN:
            continue
        f["main_decisions"] += 1
        types = [o.type for o in sel.option]
        if OptionType.ATTACK in types:
            f["attack_available"] += 1
            f["turns_attack_available"].add(t)
        if OptionType.RETREAT in types:
            f["retreat_available"] += 1
        chosen = [sel.option[i].type for i in (act or []) if 0 <= i < len(sel.option)]
        if OptionType.ATTACK in chosen:
            f["attack_taken"] += 1
            f["turns_attacked"].add(t)
            if f["first_attack_turn"] is None:
                f["first_attack_turn"] = t
        if OptionType.RETREAT in chosen:
            f["retreat_taken"] += 1
        a0 = mp.active[0] if mp.active else None
        if a0 is not None and len(a0.energies) == 0:
            f["active_zero_energy_main"] += 1

    f["turns"] = len(f.pop("turns_seen"))
    f["turns_attacked_n"] = len(f.pop("turns_attacked"))
    f["turns_attack_available_n"] = len(f.pop("turns_attack_available"))
    f["missed_attack_turns"] = f["turns_attack_available_n"] - f["turns_attacked_n"]
    n = max(1, f.pop("samples"))
    f["mean_bench"] = round(f.pop("bench_sum") / n, 3)
    f["mean_hand"] = round(f.pop("hand_sum") / n, 3)
    f["mean_deck"] = round(f.pop("deck_sum") / n, 3)
    pl = f.pop("prize_lead_by_turn")
    for k in (3, 5, 7, 9):
        near = [v for t, v in pl.items() if t <= k]
        f[f"prize_lead_by_turn_{k}"] = near[-1] if near else None
    return f


NUMERIC = ["turns", "last_turn", "decisions", "main_decisions", "attack_available",
           "attack_taken", "turns_attacked_n", "turns_attack_available_n",
           "missed_attack_turns", "retreat_available", "retreat_taken", "first_attack_turn",
           "active_zero_energy_main", "mean_bench", "mean_hand", "mean_deck",
           "my_prize_min", "op_prize_min", "steps",
           "prize_lead_by_turn_3", "prize_lead_by_turn_5", "prize_lead_by_turn_7",
           "prize_lead_by_turn_9"]


def contrast(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    won = [r for r in rows if r["score"] == 1.0]
    lost = [r for r in rows if r["score"] == 0.0]
    out = {"won": len(won), "lost": len(lost), "features": {}}
    for k in NUMERIC:
        wv = [r[k] for r in won if r.get(k) is not None]
        lv = [r[k] for r in lost if r.get(k) is not None]
        if len(wv) < 3 or len(lv) < 3:
            continue
        mw, ml = statistics.mean(wv), statistics.mean(lv)
        sd = statistics.pstdev(wv + lv) or 1e-9
        out["features"][k] = {"won_mean": round(mw, 3), "lost_mean": round(ml, 3),
                              "delta": round(ml - mw, 3), "std": round((ml - mw) / sd, 3),
                              "won_n": len(wv), "lost_n": len(lv)}
    out["ranked"] = sorted(out["features"], key=lambda k: -abs(out["features"][k]["std"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--submission", type=int, default=54948560)
    ap.add_argument("--player", default="official_dragapult")
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--pace", type=float, default=1.2)
    ap.add_argument("--workdir", default="/tmp/c023_rmine")
    a = ap.parse_args()

    from kaggle.api.kaggle_api_extended import KaggleApi
    from cg import c023_players as P

    d = P.resolve(a.player)
    deck = [int(x) for x in open(os.path.join(d, "deck.csv")) if x.strip()]
    sha = hashlib.sha256(",".join(str(c) for c in deck).encode()).hexdigest()

    api = KaggleApi(); api.authenticate()
    os.makedirs(a.workdir, exist_ok=True)
    os.makedirs(LADDER, exist_ok=True)

    eps = api.competition_list_episodes(submission_id=a.submission) or []
    rows = []
    for i, e in enumerate(eps[:a.limit]):
        time.sleep(a.pace)
        try:
            api.competition_episode_replay(episode_id=e.id, path=a.workdir, quiet=True)
            p = os.path.join(a.workdir, f"episode-{e.id}-replay.json")
            f = game_features(json.load(open(p)), sha)
            if f:
                f["episode"] = e.id
                rows.append(f)
        except Exception as exc:  # noqa: BLE001
            print(f"  episode {e.id}: {type(exc).__name__}: {str(exc)[:80]}", flush=True)
        finally:
            try:
                os.remove(os.path.join(a.workdir, f"episode-{e.id}-replay.json"))
            except OSError:
                pass
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{min(a.limit,len(eps))}", flush=True)

    overall = contrast(rows)
    by_arch = {}
    for arch in sorted({r["opponent_archetype"] for r in rows}):
        sub = [r for r in rows if r["opponent_archetype"] == arch]
        if len(sub) >= 6:
            by_arch[arch] = contrast(sub)

    payload = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "submission": a.submission, "player": a.player, "games": len(rows),
               "overall": overall, "by_archetype": by_arch, "rows": rows}
    with open(os.path.join(LADDER, f"loss_mining_{a.submission}.json"), "w") as fh:
        json.dump(payload, fh, indent=2)

    print(f"\n{a.player}: {overall['won']} won / {overall['lost']} lost, {len(rows)} parsed")
    print(f"{'feature':30s} {'won':>9s} {'lost':>9s} {'delta':>9s} {'std':>7s}")
    for k in overall["ranked"]:
        v = overall["features"][k]
        print(f"{k:30s} {v['won_mean']:>9.3f} {v['lost_mean']:>9.3f} {v['delta']:>9.3f} {v['std']:>7.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
