# An accidental exact replication, and what it says about every field score in this contract

## The observation

`ft_k8` and `fpw_k8` are **the same configuration**:

```text
ft_k8    fixed_total,     96 simulations / decision, K=8  ->  96/8 = 12 per world
fpw_k8   fixed_per_world, 12 simulations / world,    K=8  ->  12*8 = 96 total
```

`simulations_per_world()` returns `[12]*8` for both. Same seed (90210), same 32 game indices,
same world-seed derivation, same agent seeds, same decision budget, same guard, same opponent
panel, same seats. Their `sims_per_decision` both measure 96.0 and their `mean_k_used` both 8.0.

They are not a K comparison. They are a **replication**.

| | `ft_k8` | `fpw_k8` | difference |
|---|---:|---:|---:|
| field score | 0.0938 | 0.2188 | **12.5 pp** |
| Brier | 0.2002 | 0.1625 | 0.0377 |
| log-loss | 0.9041 | 0.6598 | 0.244 |
| overconfidence | 30.0 pp | 19.5 pp | 10.5 pp |
| games differing in outcome | — | — | **10 of 32** |

## Why the games differ

Not the agent. The environment.

```python
for trial in range(3):
    random.seed(1234); np.random.seed(1234)
    env = make("cabt"); env.run([scripted_a, scripted_b])
```

Three runs of two **scripted, deterministic** agents with identical Python-level seeds:

```text
(DONE, DONE)  rewards (1, -1)   157 steps
(DONE, DONE)  rewards (-1, 1)   135 steps
(DONE, DONE)  rewards (-1, 1)   148 steps
```

Different winners, different lengths. The stochasticity — initial deck shuffle, prize
assignment, coin flips — lives inside the native engine and is not reachable from Python. There
is no exposed environment seed: the `cabt` configuration has no seed field.

## What this means for `M13`'s "matched seeds"

It cannot mean "the same games". It means what c022 actually controls:

- the same **hidden worlds** (world-seed stream keyed on game index),
- the same **agent RNG** (seeded from the job index alone, defect D09),
- the same **opponent, seat, and game count**.

The underlying game — the shuffle each side gets — is redrawn every run and cannot be pinned.
This is a real limitation of the target environment, and it belongs in the report rather than in
a footnote, because it bounds what any field-score comparison in this contract can establish.

## The consequence, stated plainly

**A one-sample estimate of run-to-run variation at 32 games is 12.5 field-score points.**

Set the observed K effects against it:

| protocol | Δfield vs K=1 | inside the 12.5 pp replication difference? |
|---|---:|---|
| fixed_total K=2 | +6.25 pp | yes |
| fixed_total K=4 | −3.12 pp | yes |
| fixed_total K=8 | −3.12 pp | yes |
| fixed_per_world K=2 | +9.38 pp | yes |
| fixed_per_world K=4 | +6.26 pp | yes |
| fixed_per_world K=8 | +6.26 pp | yes |

**Every one.** No field-score claim can be made from the 32-game sweep — which is exactly what
the sweep was registered as: a shortlist. `TRAINING_AND_EVALUATION §5` requires at least 200
paired games before claiming a six-point effect, and this measurement is the concrete reason why.

The calibration metrics are better placed but not immune. They are computed per DECISION
(n ≈ 1,200 per arm rather than 32), yet the same two arms differ by ΔBrier 0.038 — larger than
every fixed-total K effect (−0.010 to −0.015). So:

- **fixed-total calibration effects are inside the replication difference and establish nothing.**
- fixed-per-world effects at K=8 (ΔBrier −0.105, Δlog-loss −2.45) are roughly three times the
  replication difference and are the only calibration signal that survives this comparison —
  and even that must be re-established against a properly replicated noise floor, not against a
  single accidental pair.

## What is done about it

1. A **registered noise floor**: three nominally identical arms at the paired-arm game count,
   differing only in seed, giving a real distribution rather than this one-sample estimate. The
   transfer protocol already requires this (`T05`); it is now needed for the MCGS comparison too.
2. The **200-game paired arms** proceed as registered. They were already on the never-cut list.
3. Every field-score comparison in the final report carries this replication alongside it.

## Why this was not caught earlier

Nothing was wrong. Two arms in different protocol directories, with different `--sims` arguments
and different `budget_protocol` strings, happen to describe the same search. The equivalence is
arithmetic — `total/K` in one protocol equals `per_world` in the other at the crossing point —
and it only becomes visible when the two tables are read side by side.

It is worth keeping deliberately: **`ft_k8` and `fpw_k8` are a free replication at the one
configuration the two protocols share**, and future sweeps should keep that crossing point
rather than tune it away.
