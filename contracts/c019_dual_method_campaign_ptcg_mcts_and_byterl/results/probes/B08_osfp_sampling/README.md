# B08 — OSFP sampling

Opponents are sampled PER GAME, never scheduled. 51,265 current-self-play games and 28,735 historical payoff samples; observed current-self-play fraction 0.6408 against a registered p = 0.6.

The fraction is 1.0 during the first learning period because H is empty and there is nothing to sample from — Algorithm 1's own condition, not a schedule.

CONTRACT §16 forbids 'self-play percentage changing with block number'. There is no block number here; there is a Bernoulli draw and a payoff-weighted categorical.

**Status: PASS.**
