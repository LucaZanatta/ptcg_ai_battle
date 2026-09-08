"""Non-inferiority statistics for student-vs-teacher (c006 §14.2).

Student score per game: win=1, draw=0.5, loss=0. Seat-balanced point estimate =
mean over the two seat orientations. The gate uses a ONE-SIDED 95% lower bound
(5th percentile of a seat-balanced bootstrap), passing at >= 0.45.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np


def seat_balanced_point(seat0: List[float], seat1: List[float]) -> float:
    m0 = np.mean(seat0) if seat0 else 0.0
    m1 = np.mean(seat1) if seat1 else 0.0
    if seat0 and seat1:
        return float(0.5 * (m0 + m1))
    return float(m0 if seat0 else m1)


def one_sided_lower_bound(seat0: List[float], seat1: List[float], *, n_boot: int,
                          rng, alpha: float = 0.05) -> Dict[str, float]:
    s0 = np.asarray(seat0, dtype=float)
    s1 = np.asarray(seat1, dtype=float)
    boot = np.empty(n_boot)
    n0, n1 = len(s0), len(s1)
    for b in range(n_boot):
        m0 = s0[rng.integers(0, n0, n0)].mean() if n0 else 0.0
        m1 = s1[rng.integers(0, n1, n1)].mean() if n1 else 0.0
        boot[b] = 0.5 * (m0 + m1) if (n0 and n1) else (m0 if n0 else m1)
    return {
        "point": seat_balanced_point(seat0, seat1),
        "lower_bound_95_one_sided": float(np.percentile(boot, 100 * alpha)),
        "upper_bound_95_one_sided": float(np.percentile(boot, 100 * (1 - alpha))),
        "n_seat0": n0, "n_seat1": n1, "n_boot": n_boot,
    }
