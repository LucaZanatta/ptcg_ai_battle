# c022 — MCGS hidden-information repair and faithful ByteRL reproduction

Both methods were implemented to the contract's fidelity standard. One produced a negative result
about its own premise; the other produced a verified implementation whose strength question the
available compute answers only partially. `DECISION_RULES §6` forbids compressing that into a
single verdict, and this report does not.

## The eleven statuses

| status | value | the requirement that decided it |
|---|---|---|
| `SOURCE_FIDELITY` | **PASS** | 33 anchored source sites, controls re-hashing, every deviation classed |
| `MCGS_HIDDEN_INFO` | **PARTIAL** | the calibration gain is not attributable to K |
| `MCGS_COMPETITIVE` | **PARTIAL** | 45 points behind the frozen bar; 0 wins in 45 off-mirror games |
| `BYTERL_REFERENCE_FIDELITY` | **PASS** | all nine requirements, 19/19 validator checks |
| `BYTERL_FIXED_DECK` | **PARTIAL** | see the extension arm below |
| `BYTERL_E2E` | **PARTIAL** | legal and diverse construction met; external improvement not |
| `BYTERL_SCALE` | **COMPUTE_LIMITED** | 9.11% and 10.85% of the matched budget in the registered arms |
| `TRANSFER` | **NOT_RUN** | gate opened only when `BYTERL_REFERENCE_FIDELITY` passed; no time for 200-game arms |
| `PACKAGE` | **NOT_RUN** | no candidate qualified |
| `SUBMISSION` | **NOT_RUN** | `DECISION_RULES §5` forbids it without a credible gate |
| `OVERALL` | **PARTIAL** | two PASS, five PARTIAL/limited, three NOT_RUN |

`STATUS.md` computes each from artifacts, names every unmet requirement, and treats a missing
artifact as `NOT_RUN` rather than as met.

## The MCGS result, and why it is the interesting one

The contract asked for the closest legal PTCG equivalent of the source's re-determinization, on
the premise that overconfidence comes from searching one sampled hidden world too deeply. That
premise is measurable, and it was measured.

| arm | K | sims/decision | overconfidence | Brier | log-loss |
|---|---:|---:|---:|---:|---:|
| `paired_k1` | 1 | 12 | 32.3 pp | 0.29397 | 3.613 |
| `paired_k8` | 8 | 96 | 20.5 pp | 0.17224 | 0.833 |
| `paired_k1_c96` | **1** | **96** | 22.2 pp | **0.17370** | **0.599** |

Decomposed: **simulations alone, in a single world, deliver −0.12027 of the −0.12173 total Brier
improvement.** The eight-world ensemble contributes **1.2%**, four times smaller than the
difference between two accidentally identical arms, and on log-loss it is actively worse at
matched compute.

So c021's overconfidence defect is real and was reproduced — and the proposed fix is not what
fixes it. Searching the same single world eight times harder recovers essentially all of the
calibration. At 12 simulations a root value rests on a handful of rollouts and is extreme by
variance alone; the ensemble corrects between-world disagreement, which turns out to be small
next to the sampling noise it was competing with. The residual ~21 pp in both 96-simulation arms
is the floor `PREREGISTERED_AGGREGATION.json` measured **before any sweep ran**.

Three qualifications, all measured:

- **What runs here is not the source's mechanism.** The 2019 agent re-determinizes before every
  rollout, deep in the tree; eleven source sites need interior hidden-state mutation and probe
  M01b measures the PTCG API refusing it. c022 ensembles at the **root** only. The preregistration
  predicted the consequence — "cross-world root aggregation attacks it only at the root" — and
  the control confirmed it. This is evidence about the available approximation, not about the
  source's mechanism, which cannot be run here at all.
- **Simulations cost ~29 ms.** The source's own 15 s / 10 s schedule buys a **median of ~600**
  simulations per decision here (`M11_SOURCE_TIMING.md`); the Kaggle deployment clock buys **44**.
- **The scaling is too shallow to matter.** 8× the simulations bought **+0.75 pp** of field score.
  No reachable budget closes a 45-point gap on that slope.

## The competitive question, settled like-for-like

| candidate | field | dragapult | mega_lucario | iono | mega_abomasnow |
|---|---:|---:|---:|---:|---:|
| frozen bar, re-run | **0.5833** | 0.533 | 0.467 | 0.867 | 0.467 |
| `mcgs_k1` | 0.1333 | 0.000 | 0.533 | 0.000 | 0.000 |
| `mcgs_k8` | 0.1167 | 0.000 | 0.467 | 0.000 | 0.000 |

The bar was **re-run rather than quoted**, and it scored 0.5833 against its recorded 0.5837 — a
0.04 pp agreement establishing that the two panels measure the same quantity, so the 45-point gap
is real and not two measuring sticks. The corrected search wins **zero of 45 games** against
three of four opponents; its entire score is the mirror match. `DECISION_RULES §2`'s alternative
route to PASS requires "a strong complementary matchup profile", and this is its opposite.

**No submission is made**, per `§5`.

## The ByteRL result

`BYTERL_REFERENCE_FIDELITY=PASS`, with one artifact per requirement
(`byterl/BYTERL_REFERENCE_FIDELITY.md`). c021 lacked LSTM recurrence, the b2 blocking FIFO
balance, and the b3 two-sided objective; all three are present and measured:

- **34/34 numerical fixtures** agree at 1e-5 against independently transcribed references
- **B06 replay fidelity at 100% coverage**, zero failures, deltas at machine epsilon, on all five
  stages and both decisive arms
- the b2 delta: production/consumption **7.92 → 1.0064**, and — the stronger property — it does
  not move with load, holding at 1.002 through six thousand seconds of four-way contention while
  D18 measured the *unbounded* ratio travelling 41.9 → 12.1 inside a single run
- end-to-end construction: **24/24 legal, 24 distinct, all 52 pool cards**, Jaccard 0.46

Strength is a separate question and the registered arms could not answer it: 9.11% and 10.85% of
the matched budget, flat inside the random floor's interval. `FIDELITY_RULES §5` forbids reading
that as method failure, so it was reported as unresolved rather than negative.

## What the extension window bought

A user-granted window to 07:00 funded two arms, registered in `PREREGISTERED_EXTENSION.json`
**before either ran**, both capable of confirming conclusions this contract had already published
against itself.

See `EXTENSION_RESULTS.md` for what they found.

## Twenty-seven defects, and the four families they fall into

`failures/DEFECT_LOG.md` records every one. They are not independent:

1. **Checks that verified nothing and reported success** — D13, D17, D19, D20, D23. An inert
   test, a declared-but-unread flag, a category error, a check starved of data, a mean of two
   outliers. **D24 is the one that mattered**: the status predicate for the contract's central
   claim was a sign test that returned PASS on a Brier difference 4% the size of the measured
   replication noise. Every other instance cost rework; that one would have cost the conclusion.
2. **Checks that failed correct behaviour** — D26 (three in one night). Worse than the first
   family, because after two or three false alarms a real one stops being investigated.
3. **A parameter from one regime applied to another** — D18, D22, D26, D27. Load bounds, my own
   tooling contaminating a quiet window an hour after I established it, bounded-versus-unbounded
   rungs, and a per-game guard sized for 96 simulations inherited by an arm running 768.
4. **Evidence that was never looked at** — D21 (the validator's inventory omitted the paired
   arms, the contract's decisive MCGS evidence, while reporting 13/13 PASS) and D25 (the final
   panel scored 0 of 180 games in two seconds and emitted a verdict anyway — the right answer,
   reached from nothing).

Every bound in this tooling now carries the measurement it came from and the regime it applies
to. Every check carries an injection proving it can fail. `NO_DATA` is a distinct outcome from
`PASS` in both the validator and the status computation.

## The honest overall reading

`DECISION_RULES §6` lists four honest outcomes. This campaign landed on the fourth — **both
methods faithful, no competitive candidate** — with a specific and useful addition: the MCGS
branch produced a *negative result about its own premise*, and that result is more valuable than
the marginal improvement it was hoping for.
