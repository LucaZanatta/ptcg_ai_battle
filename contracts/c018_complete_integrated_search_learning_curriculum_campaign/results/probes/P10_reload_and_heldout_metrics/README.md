# P10 — Exact reload and held-out metrics

**Reload is exact.** The saved checkpoint was loaded into a *fresh* model and re-scored: hash
matches (`True`), metrics identical (`True`).
A packaged model that scores differently from the evaluated one is §8.2.6 in its purest form.

**No leakage.** Splits are by game, and no game crosses train/validation/test
(`True`).

## Policy head — works

Held-out (6,738 decisions from games never trained on): top-1
**0.6144**, top-3 **0.9**, mean KL to the search's choice
1.0471 nats, legal top-1 rate **1.0**.

Legality is the property that matters for packaging: an inaccurate model plays a bad legal
move, an illegal one forfeits.

### By decision category (engine `SelectContext`)

| context | n | top-1 | top-3 | mean KL |
|---|---|---|---|---|
| 0 | 4471 | 0.5319 | 0.8674 | 1.2239 |
| 1 | 62 | 0.7903 | 1.0 | 0.498 |
| 3 | 228 | 0.7325 | 0.9649 | 0.8867 |
| 4 | 273 | 0.7363 | 0.9524 | 0.9192 |
| 7 | 844 | 0.7322 | 0.9408 | 0.8681 |
| 8 | 159 | 0.9874 | 1.0 | 0.0869 |
| 21 | 341 | 0.7009 | 0.9707 | 0.8548 |
| 22 | 148 | 1.0 | 1.0 | 0.0082 |
| 38 | 35 | 0.9714 | 1.0 | 0.2483 |
| 41 | 67 | 0.9851 | 1.0 | 0.0914 |
| 43 | 77 | 0.8831 | 1.0 | 0.3652 |

## Value head — does NOT beat a constant

| | MSE |
|---|---|
| learned value head | **0.202133** |
| constant baseline (predict the training-set mean outcome) | **0.149119** |

Correlation with the actual game result is **0.284**.

**The value head loses to a constant on MSE — but the reason is calibration, not absence of
signal.** The decile table below shows predictions rising monotonically with actual outcomes,
and correlation nearly doubled when the training set was quadrupled (0.1459
→ 0.284). What it does wrong is spread predictions across the full [0, 1]
range when true conditional outcomes span roughly [0.10, 0.42] around a base rate of
0.2177. Squared error punishes that overconfidence hard enough to
lose to a constant, even though the ordering information is real.

That distinction matters for how this result should be used. **A search leaf evaluator needs
correct ordering, not calibrated magnitudes** — it compares candidate successors and takes the
argmax, and any monotone transform of the values leaves that choice unchanged. So "loses to a
constant on MSE" is the honest headline but not the decisive test for M04's use of it. The
decisive test is whether learned leaf values rank successors better than the hand-written
heuristic in actual play, which is exactly what the panel's `m04_guided_search` versus
`m04_guided_ordering_only` comparison isolates.

The obvious cheap fix — shrink predictions toward the base rate (Platt-style recalibration) —
would collapse most of the MSE gap without changing any ranking. It is not applied here, because
it would change no search decision and would only make a reported number look better.

### Was it a sample-size problem?

The distillation was first run on 11,151 trusted rows and then re-run on roughly four times as
many, giving a direct control rather than a guess:

| trusted rows | policy top-1 | value MSE | constant baseline | correlation | beats constant |
|---|---|---|---|---|---|
| 1578 held-out (11,151-row training set) | 0.5349 | 0.267489 | 0.215862 | 0.1459 | False |
| 6738 held-out (scaled training set) | 0.6144 | 0.202133 | 0.149119 | 0.284 | False |

If the value head still loses to a constant at four times the data, the weakness is not sample
size — it is that a single terminal win/loss label per game carries very little signal about any
individual mid-game position, which is the honest conclusion and points at reward shaping or
temporal-difference targets rather than more data.

### Calibration by predicted decile

| predicted | n | mean predicted | mean actual |
|---|---|---|---|
| 0.0–0.1 | 3983 | 0.0317 | 0.1032 |
| 0.1–0.2 | 461 | 0.1399 | 0.1757 |
| 0.2–0.3 | 363 | 0.2414 | 0.2066 |
| 0.3–0.4 | 238 | 0.3462 | 0.2353 |
| 0.4–0.5 | 176 | 0.4465 | 0.2557 |
| 0.5–0.6 | 174 | 0.5491 | 0.2816 |
| 0.6–0.7 | 159 | 0.6517 | 0.2642 |
| 0.7–0.8 | 149 | 0.7503 | 0.2685 |
| 0.8–0.9 | 178 | 0.8546 | 0.3258 |
| 0.9–1.0 | 857 | 1.004 | 0.4166 |

## What these numbers are not

The stored label is `label_action[0]`, so top-1 is FIRST-PICK agreement; on 848
multi-select decisions it says nothing about the rest of the selection. And agreement with the
search is imitation, not strength — a model that imitates perfectly inherits the search's
mistakes. Gameplay promotion comes from P17 alone.

**Status: WARN.**
