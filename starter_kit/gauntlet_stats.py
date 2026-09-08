"""Statistics for the c004 competitive gauntlet (stdlib only, deterministic).

- Draws count as 0.5.
- Seat-balanced win rate = equal-weight mean of a candidate's win rate as seat 0
  and as seat 1 — a mean of two proportions with different n, so its CI is a
  STRATIFIED BOOTSTRAP (resample within each seat orientation), NOT a Wilson
  interval (Wilson assumes a single binomial). Per-seat Wilson is provided as a
  supplementary single-orientation summary.
- Global ranking: regularized Bradley-Terry (MM/Zermelo) with a symmetric
  pseudo-count so lopsided/all-win matchups do not send strengths to infinity.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple


def wilson_interval(wins: float, n: int, z: float = 1.96) -> Tuple[float, float, float]:
    """Wilson score interval (approximate when `wins` is fractional due to draws)."""
    if n == 0:
        return (0.0, 1.0, 0.5)
    p = wins / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half), p)


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.5


def seat_balanced_rate(seat0: List[float], seat1: List[float]) -> float:
    """Equal-weight mean of the two per-seat win rates (each in [0,1])."""
    parts = []
    if seat0:
        parts.append(_mean(seat0))
    if seat1:
        parts.append(_mean(seat1))
    return sum(parts) / len(parts) if parts else 0.5


def stratified_bootstrap_ci(seat0: List[float], seat1: List[float], *, n_boot: int,
                            rng, alpha: float = 0.05) -> Tuple[float, float, float]:
    """Percentile bootstrap CI for the seat-balanced rate. Resamples WITHIN each
    seat orientation (stratified). Returns (lo, hi, point)."""
    point = seat_balanced_rate(seat0, seat1)
    if not seat0 and not seat1:
        return (0.0, 1.0, point)
    rates = []
    n0, n1 = len(seat0), len(seat1)
    for _ in range(n_boot):
        if n0:
            b0 = _mean([seat0[rng.randrange(n0)] for _ in range(n0)])
        if n1:
            b1 = _mean([seat1[rng.randrange(n1)] for _ in range(n1)])
        if n0 and n1:
            rates.append(0.5 * (b0 + b1))
        elif n0:
            rates.append(b0)
        else:
            rates.append(b1)
    rates.sort()
    lo = rates[int((alpha / 2) * n_boot)]
    hi = rates[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return (lo, hi, point)


def bradley_terry(cands: List[str], pair_wins: Dict[Tuple[str, str], float],
                  pair_games: Dict[Tuple[str, str], float], *, pseudocount: float = 1.0,
                  iters: int = 200, tol: float = 1e-9) -> Dict[str, float]:
    """Regularized Bradley-Terry strengths (normalized to geometric mean 1).

    `pair_wins[(a,b)]` = a's win-equivalents vs b; `pair_games[(a,b)]` = games.
    A symmetric pseudo-count adds `pseudocount` virtual games per unordered pair
    (half won each way), preventing separation -> infinite strengths.
    """
    idx = {c: i for i, c in enumerate(cands)}
    n = len(cands)
    W = [[0.0] * n for _ in range(n)]   # W[i][j] = i's wins vs j
    N = [[0.0] * n for _ in range(n)]   # games between i and j
    for (a, b), w in pair_wins.items():
        W[idx[a]][idx[b]] += w
    for (a, b), g in pair_games.items():
        N[idx[a]][idx[b]] += g
    # symmetrize game counts and add pseudo-games
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            total = N[i][j] + N[j][i]
            N[i][j] = total  # symmetric total games between i and j
        for j in range(n):
            if i != j:
                N[i][j] += pseudocount
                W[i][j] += pseudocount / 2.0

    wins = [sum(W[i][j] for j in range(n) if j != i) for i in range(n)]
    s = [1.0] * n
    for _ in range(iters):
        new = [0.0] * n
        for i in range(n):
            denom = 0.0
            for j in range(n):
                if i == j:
                    continue
                denom += N[i][j] / (s[i] + s[j])
            new[i] = wins[i] / denom if denom > 0 else s[i]
        # normalize to geometric mean 1
        logmean = sum(math.log(x) for x in new if x > 0) / n
        gm = math.exp(logmean)
        new = [x / gm for x in new]
        if max(abs(new[i] - s[i]) for i in range(n)) < tol:
            s = new
            break
        s = new
    return {c: s[idx[c]] for c in cands}


def bootstrap_ranking(cands: List[str], games: List[dict], *, n_boot: int, rng,
                      pseudocount: float = 1.0) -> Dict:
    """Bootstrap Bradley-Terry ranking. `games` items: {a, b, a_result} where
    a_result in {1,0,0.5} (a's result vs b). Resamples games with replacement,
    refits BT, records strengths and ranks."""
    strengths_samples = {c: [] for c in cands}
    rank_freq = {c: {r: 0 for r in range(1, len(cands) + 1)} for c in cands}
    ng = len(games)
    for _ in range(n_boot):
        pw, pg = {}, {}
        for _k in range(ng):
            g = games[rng.randrange(ng)]
            a, b, r = g["a"], g["b"], g["a_result"]
            pw[(a, b)] = pw.get((a, b), 0.0) + r
            pw[(b, a)] = pw.get((b, a), 0.0) + (1.0 - r)
            pg[(a, b)] = pg.get((a, b), 0.0) + 1.0
        s = bradley_terry(cands, pw, pg, pseudocount=pseudocount)
        for c in cands:
            strengths_samples[c].append(s[c])
        order = sorted(cands, key=lambda c: s[c], reverse=True)
        for rank, c in enumerate(order, 1):
            rank_freq[c][rank] += 1

    def pct(xs, p):
        xs = sorted(xs)
        return xs[min(len(xs) - 1, int(p * len(xs)))]

    out = {}
    for c in cands:
        ss = strengths_samples[c]
        out[c] = {
            "strength_mean": sum(ss) / len(ss),
            "strength_ci95": [pct(ss, 0.025), pct(ss, 0.975)],
            "rank_frequency": {str(r): rank_freq[c][r] / n_boot for r in rank_freq[c]},
        }
    return out
