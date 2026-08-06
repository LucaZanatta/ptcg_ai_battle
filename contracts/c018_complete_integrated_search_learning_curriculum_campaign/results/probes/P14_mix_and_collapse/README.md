# P14 — Curriculum mixture and collapse

The realised opponent mix is recounted from the raw per-game opponent labels, not copied from
the plan. Realised self-play share by block:
{"0": 0.0, "1": 0.0, "2": 0.0, "3": 0.0, "4": 0.0, "5": 0.0, "6": 0.0, "7": 0.0, "8": 0.092, "9": 0.119, "10": 0.085, "11": 0.096, "12": 0.082, "13": 0.1, "14": 0.103, "15": 0.108, "16": 0.102, "17": 0.101, "18": 0.096, "19": 0.122, "20": 0.296, "21": 0.308, "22": 0.3, "23": 0.289, "24": 0.292, "25": 0.29, "26": 0.3, "27": 0.31, "28": 0.289, "29": 0.293, "30": 0.312, "31": 0.283, "32": 0.322, "33": 0.284, "34": 0.286, "35": 0.304, "36": 0.532, "37": 0.489, "38": 0.538, "39": 0.513, "40": 0.496, "41": 0.518, "42": 0.519, "43": 0.486, "44": 0.496, "45": 0.494, "46": 0.472, "47": 0.495, "48": 0.51, "49": 0.482, "50": 0.484, "51": 0.499, "52": 0.506, "53": 0.529, "54": 0.515, "55": 0.503, "56": 0.702, "57": 0.705, "58": 0.697, "59": 0.699, "60": 0.684, "61": 0.7, "62": 0.685, "63": 0.731, "64": 0.684, "65": 0.706, "66": 0.681, "67": 0.706, "68": 0.679, "69": 0.684, "70": 0.706, "71": 0.706, "72": 0.699, "73": 0.702, "74": 0.714, "75": 0.705, "76": 0.704, "77": 0.718, "78": 0.683, "79": 0.688}. Maximum absolute deviation from the
planned mixture across all blocks and categories is
0.0381 (mean 0.0085) — sampling noise
around the schedule, not a schedule that was never applied.

5 distinct opponent categories appear throughout, so the
field never collapsed to self-play alone.

## §26 compliance — this curriculum makes no strategic claim

| | |
|---|---|
| transition reasons | {"FALLBACK_SCHEDULE": 80} |
| `PERFORMANCE_PROMOTION` transitions | **0** |
| §26 conservative cap | 0.3 |
| max realised self-play | **0.7314** |
| blocks above the cap | 49 |

§26 states that **only `PERFORMANCE_PROMOTION` supports a strategic curriculum claim**, and caps
a non-performance-gated schedule at 20–30% self-play. c018's schedule advanced on block index
alone — no evaluation gated any transition — so every transition is `FALLBACK_SCHEDULE`-grade,
and the schedule nonetheless ran above the cap.

**Consequence, stated plainly:** the curriculum is evidence that real PPO training ran at scale
— real games, real optimiser steps, moving weights — and nothing more. c018 does **not** claim
the self-play schedule improved the policy. Fixing this needs a per-block frozen-panel
evaluation gating each self-play increment. Full per-interval record:
`artifacts/curriculum_audit.json`.

## The rising within-block win rate is NOT evidence of improvement

As the self-play share grows the opponent field changes: the policy is increasingly measured
against *itself* rather than against the public archetype teachers. Win rates across blocks are
not comparable. The frozen panel (P17) is the only like-for-like comparison.

**Status: WARN.**
