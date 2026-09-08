"""c024 — solve the deck-selection game, instead of searching for the single best deck.

Every contract in this project has asked *which agent is strongest*, scored it by an average over
a fixed panel, and promoted the maximum. `CALIBRATION_RETEST.md` shows why that average is the
wrong objective — it saturates below the target. This asks the other question the literature asks
about collectible card games, and that this project never has:

> **Given the matchup matrix, what mixture of decks is unexploitable, and how much does the best
> single deck lose against an opponent who knows what we play?**

A one-population matchup matrix defines a two-player zero-sum game whose value and equilibrium are
a linear program. The equilibrium support answers a question a field score cannot: whether the
format has a dominant deck at all, or whether it is genuinely rock-paper-scissors — in which case
"find the best deck" has no answer and the whole search was mis-specified.

Two things this deliberately does NOT claim:

* **The Kaggle ladder is not a deck-selection game we get to play repeatedly.** One agent is
  submitted and it meets whatever the matchmaker sends. An equilibrium mixture is not directly
  playable; it is a diagnostic of the *format*, and of how much a fixed choice can be punished.
* **The matrix is ours.** It is measured over the agents on our panel, which over-represents
  Alakazam and under-represents everything below the top of the ladder. The equilibrium describes
  this panel's meta, not Kaggle's.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import linprog

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(_REPO, "results", "c023_autonomous_meta_first_competition_sprint",
                   "raw_evaluations")
OUT = os.path.join(_REPO, "results", "c024_final_sprint")


def load_pairs(tags: List[str]) -> Dict[Tuple[str, str], List[float]]:
    """(candidate, opponent) -> scores, pooled over tags, recounted from raw games."""
    out: Dict[Tuple[str, str], List[float]] = collections.defaultdict(list)
    for t in tags:
        p = os.path.join(RAW, t, "games.jsonl")
        if not os.path.isfile(p):
            continue
        for line in open(p):
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if r.get("error") or r.get("score") is None:
                continue
            out[(r["candidate_id"], r["opponent_id"])].append(float(r["score"]))
    return out


def build_matrix(pairs, players: List[str], min_games: int):
    """Antisymmetric payoff matrix in [-1, 1]: +1 = we always win.

    Both orientations of a pairing are pooled — A-as-candidate-vs-B and B-as-candidate-vs-A are
    the same matchup measured twice, and using only one throws away half the evidence and inherits
    whichever seat balance that tag happened to run.
    """
    n = len(players)
    A = np.zeros((n, n))
    counts = np.zeros((n, n), dtype=int)
    for i, a in enumerate(players):
        for j, b in enumerate(players):
            if i == j:
                continue
            fwd = pairs.get((a, b), [])
            rev = pairs.get((b, a), [])
            s = sum(fwd) + sum(1.0 - x for x in rev)
            n_ij = len(fwd) + len(rev)
            counts[i, j] = n_ij
            if n_ij >= min_games:
                A[i, j] = 2.0 * (s / n_ij) - 1.0
    return A, counts


def solve(A: np.ndarray):
    """Maximin mixed strategy for the row player of a zero-sum game.

    max v s.t. sum_i x_i A[i,j] >= v for all j, sum x = 1, x >= 0.
    Variables are [x_0..x_{n-1}, v]; linprog minimises, so the objective is -v.
    """
    n = A.shape[0]
    c = np.zeros(n + 1)
    c[-1] = -1.0
    # -(x . A[:,j]) + v <= 0
    A_ub = np.hstack([-A.T, np.ones((n, 1))])
    b_ub = np.zeros(n)
    A_eq = np.zeros((1, n + 1))
    A_eq[0, :n] = 1.0
    b_eq = np.array([1.0])
    bounds = [(0.0, 1.0)] * n + [(None, None)]
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds,
                  method="highs")
    if not res.success:
        raise RuntimeError(res.message)
    return res.x[:n], float(res.x[-1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", default="c024_screen1,c024_calib13,c024_azam_panel1")
    ap.add_argument("--min-games", type=int, default=40)
    ap.add_argument("--out", default=os.path.join(OUT, "NASH_METAGAME.md"))
    a = ap.parse_args()

    pairs = load_pairs(a.tags.split(","))
    seen = collections.Counter()
    for (x, y), v in pairs.items():
        seen[x] += len(v)
        seen[y] += len(v)
    players = sorted(p for p in seen if seen[p] >= 200)

    A, counts = build_matrix(pairs, players, a.min_games)
    # Keep only players whose row is (nearly) complete, or the equilibrium exploits missing cells.
    keep = [i for i in range(len(players))
            if (counts[i] >= a.min_games).sum() >= len(players) - 3]
    players = [players[i] for i in keep]
    A = A[np.ix_(keep, keep)]
    counts = counts[np.ix_(keep, keep)]

    x, value = solve(A)
    # Exploitability of each pure strategy: its worst-case payoff against any single opponent.
    worst = {p: float(A[i].min()) for i, p in enumerate(players)}
    # Payoff of each pure strategy against the equilibrium mixture.
    vs_eq = {p: float(A[i] @ x) for i, p in enumerate(players)}

    order = sorted(range(len(players)), key=lambda i: -x[i])
    lines = [
        "# Solving the deck-selection game, instead of searching for the best deck",
        "",
        "Every contract here has asked *which agent is strongest* and promoted the maximum of a",
        "field score. A matchup matrix also defines a zero-sum game, and its equilibrium answers a",
        "question the average cannot: **does this format have a best deck at all?**",
        "",
        f"Pooled from `{a.tags}` — both orientations of every pairing, "
        f"minimum {a.min_games} games per cell, recounted from raw games.",
        "",
        "## The equilibrium mixture",
        "",
        "| agent | equilibrium weight | worst single matchup | vs the equilibrium |",
        "|---|---:|---:|---:|",
    ]
    for i in order:
        p = players[i]
        star = " **" if x[i] > 1e-6 else " "
        lines.append(f"|{star}{p}{star.strip()} | {x[i]:.3f} | {worst[p]:+.3f} | {vs_eq[p]:+.3f} |")
    lines += [
        "",
        f"**Game value: {value:+.4f}** (0 by construction for a symmetric game; deviation "
        "measures how far the measured matrix is from antisymmetric, i.e. sampling noise).",
        "",
        "## What the support says",
        "",
    ]
    support = [players[i] for i in order if x[i] > 1e-6]
    if len(support) == 1:
        lines += [f"**A single deck, `{support[0]}`, carries the entire equilibrium.** The format "
                  "has a dominant strategy on this panel, and 'find the best deck' is a "
                  "well-posed question."]
    else:
        lines += [
            f"**{len(support)} agents share the equilibrium support**, so no single deck is "
            "unexploitable on this panel. 'Which deck is best' has no answer here — the honest "
            "question is *which deck is least punished by the mixture we actually expect to "
            "meet*, and that depends on the ladder's composition, not on ours.",
            "",
            "This is the formal version of the rock-paper-scissors observation in "
            "`EXCHANGE_RATE_CORRECTION.md`, and it is the strongest argument that the campaign's "
            "framing — search for a maximum of a field average — was mis-specified from the start.",
        ]
    lines += [
        "",
        "## Worst-case exposure, which a field score hides entirely",
        "",
        "`worst single matchup` is what each agent scores against its *best counter* on this "
        "panel. A field average of 0.50 built from cells of 0.95 and 0.05 is a different object "
        "from one built from cells of 0.50, and only the first can be targeted by an opponent who "
        "picks their deck knowing ours.",
        "",
    ]
    for i in sorted(range(len(players)), key=lambda i: worst[players[i]]):
        lines.append(f"- `{players[i]}` — worst cell {worst[players[i]]:+.3f}")
    lines += [
        "",
        "## What this is not",
        "",
        "- **The ladder is not a deck-selection game.** One agent is submitted and meets whatever",
        "  the matchmaker sends; an equilibrium mixture is not playable. This is a diagnostic of",
        "  the format and of how exploitable a fixed choice is.",
        "- **The matrix is ours.** It over-represents Alakazam (three of the panel's agents) and",
        "  contains nothing above ~1100 ladder rating. The equilibrium describes this panel.",
        "- **Cells are 40–400 games**, so entries carry roughly ±0.1 of noise; the support is",
        "  stable in sign, not to three decimals.",
    ]
    with open(a.out, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    with open(a.out.replace(".md", ".json"), "w") as fh:
        json.dump({"players": players, "matrix": A.tolist(), "counts": counts.tolist(),
                   "equilibrium": dict(zip(players, x.tolist())), "value": value,
                   "worst_case": worst, "vs_equilibrium": vs_eq}, fh, indent=2)

    print(f"{len(players)} players, game value {value:+.4f}")
    for i in order:
        if x[i] > 1e-6:
            print(f"  {players[i]:34s} weight {x[i]:.3f}  worst {worst[players[i]]:+.3f}")
    print("support size:", len(support))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
