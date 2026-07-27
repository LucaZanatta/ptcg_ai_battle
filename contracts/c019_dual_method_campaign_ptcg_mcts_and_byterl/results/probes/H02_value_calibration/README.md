# H02 — Value calibration

`ByteRLLeafValue` starts uncalibrated and REFUSES to return a value until calibration explicitly enables it. The gate was RUN, not assumed: 1847 held-out leaves drawn from 400 baseline games the checkpoint never trained on, each labelled with the eventual result from the snapshotted seat.

| evaluator | MSE vs outcome | correlation |
|---|---|---|
| ByteRL value head | 0.8914 | 0.2842 |
| hand-written heuristic | 0.9462 | 0.1689 |
| constant (predict the mean) | 0.9543 | — |

Beats constant: **True**. Beats heuristic: **True**. Adapter may be enabled: **True**.

Two things about the leaf distribution have to be said together, because either alone misleads. These leaves come from games the frozen baseline played, which is the *correct* distribution for the intended use — a leaf evaluator inside an MCTS that wraps that baseline. It is simultaneously out-of-distribution relative to training, which was roughly balanced self-play. The value head carries ordering signal on positions it never trained on, and that is the claim being made — not that it is calibrated.

**Status: PASS** — gate implemented and exercised on real leaves.
