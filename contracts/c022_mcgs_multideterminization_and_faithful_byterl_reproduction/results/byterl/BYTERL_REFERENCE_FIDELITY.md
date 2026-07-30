# `BYTERL_REFERENCE_FIDELITY` = PASS — the evidence

`DECISION_RULES §3` lists nine requirements. Each is answered below by an artifact, not by prose,
and each artifact is regenerable from the tree.

`CONTRACT §3.4` states what c021 lacked: LSTM recurrence, "the published b2 blocking FIFO
actor–learner balance", and "the published b3 two-sided V-trace/PPO-style objective". All three
are present and measured here.

## 1. LSTM-256 recurrence

`results/byterl/architecture/architecture.json` — every module, its shape and its parameter
count. `lstm_hidden_size_is_256: true`, over a shared torso feeding separate policy and value
heads. This is c021's defining absence; c021 substituted a feed-forward residual stack, which
`UNRESOLVED_REFERENCE_CHOICES.md` records as the deviation this contract exists to remove.

## 2. Exact complete-action autoregression

`results/byterl/action_traces/action_traces.jsonl` — real decisions, token by token: the legal
mask, the distribution over it, the chosen index, and the joint log-probability **recomputed from
the per-token factors** beside the sampler's own value. Probes B03/B04/B05 pass.

The artifact exists because `"pass": true` is not an analysis. A reader who wants to know whether
the distribution really factorises autoregressively over a masked option set can read the
factors.

## 3. Actor versions and stored recurrent starts

Probes B06/B07, and `test_c022_byterl_b06.py`, which did not exist until D19 forced it. Every
unroll carries the policy version that produced it and the actor's observed `(h0, c0)` — and,
critically, the actor's observed **end** state, so the learner's recomputed state is compared
against something it did not supply. Comparing a stored start against itself is trivially zero
and would pass under a zeroed start; a companion test asserts every unroll after the first
carries a non-zero start.

## 4. Bounded blocking FIFO and measured production/consumption

The b2 delta, across the ladder at an equal 120,000-decision budget:

| rung | queue | production/consumption |
|---|---|---:|
| BR0 | unbounded | 8.7317 |
| BR1 | unbounded | 8.2232 |
| BR1.5 | unbounded | 7.9217 |
| **BR2** | **bounded, blocking** | **1.0064** |
| **BR3** | **bounded, blocking** | **1.0073** |

And the property that matters more than the number: **it does not move with load.** D18 measured
the *unbounded* ratio travelling from 41.9 to 12.1 within a single run as competing work drained
away. Under four-way contention at roughly 20% of clean throughput, both decisive BR3 arms held
`queue_occupancy` at the 48-unroll cap, `policy_lag` under 8, and production/consumption at
**1.0022** and **1.0023** for six thousand seconds. The bounded FIFO makes the system's behaviour
reproducible, not merely balanced — a stronger claim than the ladder was designed to test, and
one it produced by accident.

## 5. Exact numerical V-trace / UPGO / b3 fixtures

`results/byterl/numerical_fixtures/fixtures.json` — **34 of 34 comparisons agree at 1e-5**, each
recording inputs, an independently transcribed reference, the implementation's value and the
difference.

The references are transcribed from the published equations and deliberately **not** imported
from the test module's copies. Two independent transcriptions agreeing is evidence; one
transcription imported twice is a tautology.

The b3 clipping bounds are recorded as values — `(0.001, 1.007)` — rather than described. The PPO
fixture pairs its reference to the implementation's own **V-trace** advantage, because
`MANDATORY_IMPLEMENTATION B4` names ordinary PPO with a GAE advantage as a hard failure: "the
clip is right" is only half the property, and which advantage it clips is the other half.

## 6. Published stage-delta tests

`tests/test_c022_stage_ladder.py`. `B7` requires that adjacent stages differ only by the published
change and that "tests must reject extra changes", so each pair is compared field by field and the
symmetric difference must equal the single named delta. One test injects an extra change and
asserts the check fires.

D17 is why a further test greps every stage flag for an implementation reader:
`random_initial_construction` was declared in the table, asserted by the delta test, and read by
nothing — so BR1 and BR1.5 were the same system while every test passed.

## 7. Recurrent replay verified at high coverage

| run | checks | coverage | failures | max logp Δ | max behaviour Δ | uniform steps seen |
|---|---:|---:|---:|---:|---:|---:|
| `fid_BR0` | 112 | 100% | 0 | 4.8e-07 | 0.0 | 0 |
| `fid_BR1` | 111 | 100% | 0 | 2.4e-07 | 0.0 | 0 |
| `fid_BR1_5` | 111 | 100% | 0 | 4.8e-07 | 0.0 | **390** |
| `fid_BR2` | 111 | 100% | 0 | 9.5e-07 | 0.0 | **380** |
| `fid_BR3` | 111 | 100% | 0 | 4.8e-07 | 0.0 | **400** |
| `br3_fixed_deck` | 112 | 100% | 0 | — | 0.0 | — |
| `br3_end_to_end` | 91 | 100% | 0 | — | 0.0 | — |

The `uniform steps seen` column is the D19 case: a B1.5-and-above rung whose checks never
encountered a uniform construction step has not exercised the situation that killed the ladder,
however green it looks. These runs encountered 380–400 each.

These runs exist because of D20 — the ladder itself verifies only ~10% of its opportunities, since
a pre-b2 rung's policy lag exceeds any blob history that fits alongside two decisive arms.
Separating "measure the rungs" from "verify replay" cost minutes instead of hours. Note the
coverage jumps from 10% to 100% at the b2 line in the ladder itself, for the same reason the
ratio does: a bounded queue keeps lag inside the retained history.

## 8. Immutable OSFP history and correct period accounting

`results/byterl/osfp/osfp_accounting.json` — history bounded at its cap across six promotions
with eviction exercised, and every surviving entry's SHA unchanged by later promotions. Self-play
probability 0.6, promotion threshold 0.55, both recorded as values.

## 9. End-to-end construction path implemented

`results/byterl/end_to_end/construction_analysis.json`, from a trained checkpoint:

- **24 of 24 decks legal**
- **24 distinct decks** — no decklist emitted twice
- **52 of 52 pool cards used**
- mean pairwise Jaccard distance **0.4602**

Diversity is measured rather than assumed because `DECISION_RULES §3` makes it the PASS/PARTIAL
line: "merely generating legal decks is partial", and a policy that emits one legal deck every
time satisfies legality while failing the requirement.

## What this status does NOT claim

`BYTERL_REFERENCE_FIDELITY` is about the implementation being the published system. It says
nothing about strength. The decisive arms reached 9.11% and 10.85% of the matched sample budget
and sat inside the random floor's interval; `BYTERL_SCALE=COMPUTE_LIMITED` and
`FIDELITY_RULES §5` forbids reading undertraining as method failure. An extension arm registered
in `PREREGISTERED_EXTENSION.json` is attempting the strength question at a substantially larger
budget.

## Validator

19 checks, 19 ran, 19 pass, **0 inert, 0 undetected injections, 0 NO_DATA**. Every check carries
an injection proving it can fail, and `NO_DATA` is a distinct outcome from `PASS` — a rule added
after the validator's own first version reported five checks with no inputs as passing.
