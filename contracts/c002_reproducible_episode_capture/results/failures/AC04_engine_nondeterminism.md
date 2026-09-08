# AC-04 partial: engine trajectory is not reproducible (external limitation)

## What fails
AC-04 pass condition 3 requires that "re-running a 5-game deterministic subset
with the same base seed reproduces the same **seeds, seat assignments, decision
counts, and winners**." The **decision counts and winners cannot be reproduced**
because the cabt engine's randomness is not seedable from Python.

The other four AC-04 conditions PASS (60/60 games, unique recorded seeds, zero
invalid safe selections, every game has a terminal record), and the reproducible
half of condition 3 (seeds + seat assignments) PASSES.

## Root cause (primary-source evidence)
`starter_kit/libcg.so` seeds a `std::mt19937` from `std::random_device`
(OS entropy) and exports **no** seed function:

```
$ nm -D starter_kit/libcg.so | grep -iE "seed|rand"
  U _ZNSt13random_device7_M_finiEv@GLIBCXX_3.4.18
  W _ZNSt13random_deviceC1Ev
  W _ZNSt23mersenne_twister_engineImLm32ELm624E...E11_M_gen_randEv
# (std::random_device + std::mt19937; no exported Seed/SetSeed symbol)
```

`kaggle_environments.make("cabt", configuration={"seed": ...})` has no effect on
the engine RNG. Empirical cross-process probe with identical deterministic
`first` agents and identical `configuration.seed`:

```
run A: [(161,1,-1),(86,-1,1),(92,1,-1),(131,1,-1),(22,1,-1)]
run B: [(18,1,-1),(19,1,-1),(119,-1,1),(27,1,-1),(215,-1,1)]
```

Different step counts and winners → the engine deck shuffle / coin flips are
entropy-seeded and unseedable. See `test_logs/deterministic_replay_check.txt`.

## What IS reproducible (record-level determinism)
- Derived per-game seeds and the seat-assignment schedule reproduce exactly
  (pure functions of `--base-seed`).
- The safe agent's selection for a given recorded observation is byte-identical
  on replay (157/157 safe decisions in the subset re-derived with zero
  mismatches) — the policy is a pure function.

## Why not worked around
Controlling the engine RNG would require either modifying the native binary or
interposing `std::random_device` via `LD_PRELOAD` — both are out of scope
(prohibited/destructive/external tricks) and the contract forbids improvising
around a platform issue. Note AC-04's "unless a genuine cabt/runtime blocker is
documented" clause is attached only to the *60/60-complete* bullet, not to the
reproducibility bullet, so it does not rescue condition 3.

## Recommended repair
A narrowly scoped follow-up contract redefining AC-04 condition 3 as
**record-level determinism** (seeds + seat schedule + per-observation policy
determinism), which is fully achieved here, rather than engine-trajectory
determinism, which is externally impossible.
