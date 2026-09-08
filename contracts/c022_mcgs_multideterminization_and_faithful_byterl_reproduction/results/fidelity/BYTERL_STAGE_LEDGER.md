# ByteRL stage ledger

`FIDELITY_RULES §4` fixes the published stage meanings, and they are mandatory:

```text
B0   end-to-end baseline ByteRL system
B1   B0 with gamma changed to 1.0
B1.5 B1 with published random initial deck-construction selections
B2   B1.5 with bounded blocking FIFO and balanced actor production/learner consumption
B3   B2 with two-sided clipped V-trace and PPO-style clipped policy objective
```

and adds: "OSFP, UPGO, recurrence, action masking, autoregression, and end-to-end deck
construction are foundational ByteRL components; they are **not** redefined as separate later
rungs merely for convenience."

That last sentence is the one c021 violated. Its rungs carried locally invented meanings, so a
c021 "B3" and a c022 `BR3` are different systems that happen to share a name.

## The ladder as implemented

One codebase, one table, machine-verifiable. `tools/c022_byterl_train.py::STAGES`:

| stage | gamma | random initial construction | bounded blocking FIFO | two-sided + PPO |
|---|---:|---|---|---|
| `BR0` | 0.99 | no | no | no |
| `BR1` | 1.00 | no | no | no |
| `BR1_5` | 1.00 | **yes** | no | no |
| `BR2` | 1.00 | yes | **yes** | no |
| `BR3` | 1.00 | yes | yes | **yes** |

Adjacent pairs and their single permitted delta:

| pair | delta |
|---|---|
| `BR0 → BR1` | `gamma` |
| `BR1 → BR1_5` | `random_initial_construction` |
| `BR1_5 → BR2` | `bounded_blocking_fifo` |
| `BR2 → BR3` | `two_sided_and_ppo` |

`tests/test_c022_stage_ladder.py` compares each adjacent pair field by field and requires the set
of changed keys to EQUAL the named delta. `PROBE_MATRIX B14` says "tests must reject extra
changes", so one test deliberately injects an unpublished second change into `BR2` and asserts
the comparison catches it — a stage test that only checks "the named field changed" passes
happily while a second field changes alongside it.

## Foundational, present at EVERY rung

These are not rungs. Making any of them a rung would be the convenience redefinition
`FIDELITY_RULES §4` forbids, and would also make every lower rung a strawman.

| component | where | verified by |
|---|---|---|
| LSTM-256 recurrence | `c022_byterl_model.ByteRLRecurrentNet` | B01 |
| shared card embeddings | `SharedCardEmbedding`, used by slots, hand, discard, options | B01 |
| distinct active/bench/side slot identity | `SlotEncoder` | B02 |
| masked autoregressive complete actions | `c022_byterl_action` | B04, B05 |
| UPGO | `c022_byterl_learn.upgo_returns` | B12 |
| V-trace | `c022_byterl_learn.vtrace` | B11 |
| OSFP with immutable history | `c022_byterl_learn.OSFP` | B15, B16, B17 |
| end-to-end deck construction | `EpisodeRunner.build_deck` | B18, B19 |
| asynchronous versioned actors | `c022_byterl_actor`, `actor_loop` | B10 |
| stored recurrent unroll starts | `Unroll.h0/c0/h_end/c_end` | B06, B07 |

## Why BR0–BR1_5 still have an actor–learner split and a queue

The b2 delta is the queue being **bounded and blocking**, not the queue existing. The lower rungs
run the same machinery with an effectively unbounded queue (65,536) and no production throttle,
so the rung difference is the CONTROL POLICY rather than the architecture.

If BR0 had no actor–learner split at all, "B2 improves things" would be confounded with "B2 has
an actor–learner split" — which is exactly the kind of multi-change rung the probe matrix exists
to prevent.

## The b3 delta, stated precisely

`B4` names ordinary PPO a hard failure, so the b3 change has to be stated as two things:

1. **Two-sided importance-ratio clipping.** Standard V-trace clips from above only:
   `rho = min(rho_bar, pi/mu)`. b3 clips both sides: `rho = clip(pi/mu, 0.001, 1.007)`. The lower
   bound stops a sample the current policy has nearly abandoned from contributing a vanishing but
   unbounded-variance correction; the 1.007 upper bound is far tighter than IMPALA's usual
   convention and makes the value target strongly on-policy.
2. **A PPO-style clipped surrogate driven by the V-TRACE advantage.** Ordinary PPO uses a GAE
   advantage from the same trajectory. Here the advantage is
   `rho_t · (r_t + gamma·v_{t+1} − V(s_t))`, and the surrogate is
   `min(ratio·A, clip(ratio, 1−eps, 1+eps)·A)` with `eps = 0.2`.

`test_b13_ordinary_ppo_and_byterl_b3_differ_by_the_ADVANTAGE_not_only_the_clip` constructs a
strongly off-policy case where the V-trace advantage and a plain TD advantage differ, and asserts
they do — so the test would fail if the objective had been built on the plain advantage.

Both bounds apply to the COMPLETE autoregressive joint ratio. Applying them to the first token
alone is `B4`'s "first-token-only ratios" hard failure, and nothing downstream could detect it
because the shapes are identical — which is why B05 checks the joint at its source instead.

## Arms

`MANDATORY_IMPLEMENTATION B6` requires two:

```text
FIXED_DECK_BATTLE_CONTROL                 --learn-construction 0
END_TO_END_DECK_CONSTRUCTION_AND_BATTLE   --learn-construction 1
```

`TRAINING_AND_EVALUATION §2` orders them: `BR3_FIXED_DECK` first, because c021 demonstrated
battle-learning signal there, then `BR3_END_TO_END`. Both implementations and at least a
nontrivial end-to-end run remain mandatory whatever the compute outcome.
