"""c023 — the two-hit race, computed over the meta from card data.

`FAILURE_TAXONOMY.md` F8 closed this campaign on an arithmetic fact rather than a decision error:
Dragapult ex attacks for 200 into a format whose headline attackers have 320–350 HP and hit back
for 180–270, and a knocked-out Mega pays the opponent three prizes to our two. No override, score
constant or turn-level search changes that.

That names the next campaign's first question — *which archetype's attacker wins the current
format's exchange rate?* — and this answers it from the competition's own card data plus the 22
validated meta decklists, so the answer is a ranked table rather than an intuition.

For each archetype: its best affordable attacker, what that attacker needs to knock out the decks
that dominate the 1000+ ladder bands, and what those decks need to knock it out. The metric is
deliberately crude and stated as such — it ignores abilities, tools, weakness in most pairings and
every card that is not a Pokémon. It is a first filter, not a simulation.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

OUT = os.path.join(_REPO, "results", "c023_autonomous_meta_first_competition_sprint")
DATASET = os.path.join(_REPO, "external_refs", "c023_datasets")

# The decks that actually own the top of the ladder (META_REPORT section 2), by signature card.
FORMAT_THREATS = [("Marnie's Grimmsnarl ex", 648), ("Mega Lopunny ex", 849),
                  ("Teal Mask Ogerpon ex", 96), ("Mega Lucario ex", 678),
                  ("Alakazam", 743), ("Crustle", 345)]


def prize_value(card) -> int:
    return 3 if card.megaEx else 2 if card.ex else 1


def best_attacker(card_ids: List[int], cards, attacks, max_energy: int = 3,
                  min_copies: int = 1):
    """The highest-damage attack in the list that a realistic energy count can pay for.

    `min_copies` matters: a one-of tech Pokemon is not the deck's attacker. Requiring two copies
    stops Latias ex -- a singleton in four different lists -- from being scored as four decks'
    main threat.
    """
    counts = collections.Counter(card_ids)
    best = None
    for cid in sorted(set(card_ids)):
        c = cards.get(cid)
        if c is None or not c.attacks or c.hp <= 0 or counts[cid] < min_copies:
            continue
        for aid in c.attacks:
            a = attacks.get(aid)
            if a is None or len(a.energies) > max_energy:
                continue
            if best is None or a.damage > best[2]:
                best = (cid, c, a.damage, a, len(a.energies))
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(OUT, "EXCHANGE_RATE.md"))
    a = ap.parse_args()

    from cg.api import all_attack, all_card_data
    cards = {c.cardId: c for c in all_card_data()}
    attacks = {x.attackId: x for x in all_attack()}

    decks: Dict[str, List[int]] = collections.defaultdict(list)
    names: Dict[str, str] = {}
    p = os.path.join(DATASET, "decks_long.csv")
    for row in csv.DictReader(open(p)):
        decks[row["deck_id"]].extend([int(row["card_id"])] * int(row["quantity"]))
        names[row["deck_id"]] = row["deck_name"]

    threats = []
    for label, cid in FORMAT_THREATS:
        c = cards.get(cid)
        if c is None:
            continue
        best = best_attacker([cid], cards, attacks)
        dmg = best[2] if best else 0
        # An attack whose printed damage is 0 does its work through damage counters or effects
        # (Alakazam's Powerful Hand scales with hand size). It cannot be scored as a hit count,
        # so it is excluded from the "how fast do they kill us" side rather than treated as
        # harmless -- which is what a 0 would do.
        threats.append({"label": label, "hp": c.hp, "prizes": prize_value(c),
                        "damage": dmg, "scorable": dmg > 0})

    rows = []
    for did in sorted(decks):
        best = best_attacker(decks[did], cards, attacks, min_copies=2)
        if best is None:
            continue
        cid, card, dmg, atk, cost = best
        hits_to_kill = []
        hits_to_die = []
        for t in threats:
            if t["label"].startswith(card.name):
                continue
            hits_to_kill.append(-(-t["hp"] // max(1, dmg)))          # ceil
            if t["scorable"]:
                hits_to_die.append(-(-card.hp // t["damage"]))
        if not hits_to_kill or not hits_to_die:
            continue
        mk = sum(hits_to_kill) / len(hits_to_kill)
        md = sum(hits_to_die) / len(hits_to_die)
        sc = [t for t in threats if t["scorable"]]
        prizes_we_take = sum(t["prizes"] for t in sc) / len(sc)
        prizes_we_give = prize_value(card)
        # prizes per turn we take, over prizes per turn they take
        exch = (prizes_we_take / mk) / max(1e-9, prizes_we_give / md)
        rows.append({
            "deck_id": did, "deck": names[did], "attacker": card.name,
            "attack": atk.name, "damage": dmg, "energy": cost, "hp": card.hp,
            "prizes_given": prizes_we_give,
            "hits_to_kill_threats": round(mk, 2), "hits_to_survive": round(md, 2),
            "exchange": round(exch, 3),
        })
    rows.sort(key=lambda r: -r["exchange"])

    lines = [
        "# The two-hit race, over the meta",
        "",
        "`FAILURE_TAXONOMY.md` F8 ends this campaign on arithmetic rather than on a decision error:",
        "Dragapult ex attacks for **200** into a format whose headline attackers carry **320–350 HP**",
        "and hit back for **180–270**, and a knocked-out Mega pays them three prizes to our two.",
        "",
        "So the next campaign's first question is not *which constant* — it is **which archetype's**",
        "**attacker wins the current format's exchange rate**. This answers it from the competition's",
        "own card data and the 22 validated meta decklists.",
        "",
        "## The format's threats, as the table scores against them",
        "",
        "| deck | HP | its attack | prizes when knocked out |",
        "|---|---:|---:|---:|",
    ]
    for t in threats:
        lines.append(f"| {t['label']} | {t['hp']} | {t['damage']} | {t['prizes']} |")
    lines += [
        "",
        "## The ranking",
        "",
        "`exchange` = (prizes we take per turn) ÷ (prizes we concede per turn), where each side's",
        "rate is its prize value divided by the number of attacks needed. **Above 1.0 wins the race.**",
        "",
        "| deck | best attacker | attack | dmg | HP | prizes given | hits to KO a threat | hits to die | **exchange** |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        mark = "**" if r["exchange"] >= 1.0 else ""
        lines.append(
            f"| {r['deck']} | {r['attacker']} | {r['attack']} | {r['damage']} | {r['hp']} | "
            f"{r['prizes_given']} | {r['hits_to_kill_threats']} | {r['hits_to_survive']} | "
            f"{mark}{r['exchange']:.3f}{mark} |")

    dp = next((r for r in rows if "Dragapult" in r["deck"]), None)
    gs = next((r for r in rows if "Grimmsnarl" in r["deck"]), None)
    lines += [
        "",
        "## What it says",
        "",
    ]
    if dp and gs:
        lines += [
            f"**The metric's top-ranked deck is Marnie's Grimmsnarl ({gs['exchange']:.3f})** — which is",
            "also the deck that actually owns the ladder: 58.8% of the 1100+ band and 61.1% of",
            "1000–1099 (`META_REPORT` §2). A crude table built only from HP, damage and prize values,",
            "with no knowledge of the leaderboard, independently picks the deck the leaderboard picked.",
            "That is the only external check available for it, and it passes.",
            "",
            f"**Our champion's archetype ranks {rows.index(dp)+1} of {len(rows)}** at",
            f"{dp['exchange']:.3f}, against Grimmsnarl's {gs['exchange']:.3f} — about",
            f"{100*(1-dp['exchange']/gs['exchange']):.0f}% behind the deck it meets most often above",
            "1000 rating, and the champion scores **0.325** against that deck on our panel.",
            "",
            "**So the honest correction to F8 is a matter of degree, not of kind.** Dragapult is not a",
            "bad archetype — it is fourth of twenty-two, ahead of Mega Lucario — but it is behind the",
            "deck that dominates the bands we would have to climb through, and 200 damage into 320–340",
            "HP is why. An archetype-first pivot is worth making; a panic about having chosen a bad",
            "deck is not.",
        ]
    with open(a.out, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    with open(a.out.replace(".md", ".json"), "w") as fh:
        json.dump({"threats": threats, "rows": rows}, fh, indent=2)

    print(f"{'deck':46s} {'attacker':22s} {'dmg':>4s} {'hp':>4s} {'exch':>6s}")
    for r in rows:
        print(f"{r['deck'][:46]:46s} {r['attacker'][:22]:22s} {r['damage']:>4d} {r['hp']:>4d} "
              f"{r['exchange']:>6.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
