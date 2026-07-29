# The external gate, tested out of sample — and a flaw in my own selection design

All figures below are the **same protocol**: 256 games, four frozen scripted opponents, balanced
seats, fresh seed 555001 — independent of the 64-game panel used to *select*.

| checkpoint | selection panel (64g) | out-of-sample (256g) | 95% Wilson |
|---|---|---|---|
| **pre-extension b2** (recovered from git `fbbd9ac`) | — | **0.0742** | [0.048, 0.113] |
| post-extension b2 **final** (iteration 600) | 0.2500 | **0.2578** | [0.2081, 0.3147] |
| post-extension b2 **it0160** ← *selected* | 0.3594 | **0.1953** | [0.1514, 0.2482] |

## 1. The external gate PASSES

Pre-extension **0.0742** → post-extension **0.2578**, with **non-overlapping 95% intervals**
([0.048, 0.113] vs [0.2081, 0.3147]). That is a 3.5× improvement, far beyond the 6.4-point
reproducibility bound the gate requires it to clear. The four-hour extension produced a genuinely
stronger policy, and the improvement survives an out-of-sample test.

## 2. My selection rule picked the wrong checkpoint

The preregistered rule chose **it0160** on its 64-game panel score of 0.3594. Out of sample that
checkpoint scores **0.1953** — while the *final* checkpoint, which the rule ranked lower, scores
**0.2578**.

The cause is winner's curse, and it was predictable: 121 candidates × 64 games each, at a binomial
SE of ≈0.054, means the maximum of the panel is inflated by roughly 2–3 SE. The observed inflation
is 0.3594 → 0.1953, i.e. **16 points**. The between-candidate differences the rule was trying to
resolve are smaller than the noise it measured them with.

**This is a defect in my protocol, not in the training.** The rule was preregistered and followed
exactly; it was simply underpowered. A sound version would have used a two-stage design — a coarse
screen over all candidates, then a high-game-count re-evaluation of the top few — or far more games
per candidate.

## 3. What this does NOT license

The transfer arms were run with **it0160**, the checkpoint the rule selected, and the transfer gate
failed. It is tempting to re-run them with the final checkpoint, which is ~6 points stronger out of
sample.

**That would be gate-shopping**, and it is exactly what preregistration exists to prevent: choosing
the checkpoint after seeing which choice makes the gate pass. The transfer result stands as
measured. The correct record is that the transfer test was conducted with a checkpoint that
out-of-sample is weaker than the best available, *because my selection rule was underpowered*, and
that this limits what the negative transfer result can be taken to mean.

## 4. Status consequences

- **External gate: PASS.** Out-of-sample, non-overlapping, well beyond the reproducibility bound.
- **Transfer gate: FAIL.** No arm's lower bound exceeds the control's upper bound.
- `OVERALL` requires **both**, so it remains **PARTIAL**.

The honest one-line summary: *ByteRL learned — decisively and verifiably — and it still did not
transfer into MCGS.*
