# Project wrap-up through c013

This closes the fixed-Dragapult research programme as a **completed phase**, not an abandoned
one. c005–c013 built the measurement apparatus that made the c014 pivot legible; without it the
pivot would be a guess.

## The c005–c013 arc

| contract | what it established |
|---|---|
| c005 | imported the frozen Dragapult teacher, packaged it, and **submitted it** — ref 54948560, public score **719.7**. Still the project's only external measurement |
| c006–c007 | distilled policy baseline; hybrid teacher-residual and state encoder V2 |
| c008–c009 | teacher-anchored RL; the identity-safe evaluation protocol (every worker re-hashes the checkpoint it loaded, no positional reattachment after `imap_unordered`) |
| c010 | the RL loop at scale; found the "22% ceiling" was not a ceiling. Disclosed a rollout-granularity budget overshoot and a float tie that flipped a registered threshold |
| c011 | custom PyTorch/CUDA PPO with full FP32/PPO/NPZ/trainer-state parity before scale training; benchmarked CPU worker counts and chose the stable backend over the faster-looking one |
| c012 | self-play curriculum and Claude teacher qualification. Its in-run evaluations were silently empty for an entire 90,000-game arm — a per-path hash cache in persistent workers — so its curriculum result was never actually measured |
| c013 | policy combination and learnability, under repaired infrastructure |

## Corrected c013 status

**`PARTIAL`**, honestly, not for lack of execution: all 16 acceptance criteria ran, content-aware
validation passed 52 of 54 checks, and the two shortfalls are documented — a 112-game curriculum
smoke overshoot (rollout granularity) and a Claude preflight covering 6 of §27's 10 categories.

Headline results:

- `COMBINATION_RESULT = WEIGHT_SOUP_WINS`. **Averaging weights offline beat running every
  component network at inference time.** Online ensembles ranked 3rd and 4th of five.
- `SOUP_LEARNABILITY = NOT_IMPROVED`. No registered method (direct continuation, value-head
  reinit + refit, separate component continuation + recombination) produced a confirmed
  improvement within ~12,000 games per arm. c012's negative conclusion survives repair — but
  c012 reached it with an instrument that was scoring nothing, so it had been right for the
  wrong reason.
- `OPPONENT_OVERLAP = INCONCLUSIVE` for the teacher–Lucario hypothesis. The unlooked-for finding
  was stronger: **the official opponents resemble each other far more than any resembles the
  teacher** — Mega Lucario and Mega Abomasnow choose identically on all 98 promotion decisions.
- `SUBMISSION_G = DO_NOT_SUBMIT`. Teacher non-inferiority needs a one-sided 95% lower bound of
  0.47; the best agent measured 0.360.

## Pareto policy roles (preserved, not retired)

| policy | role |
|---|---|
| `SOUP13_SOUP+P1_822` | teacher/Lucario specialist — c013's true and package-feasible best |
| `P0_711` | broad-field / Iono / Abomasnow specialist |
| `C012_SOUP_622_633` | prior stable reference |
| S622, S633, P1_822, P1_833 | components and historical checkpoints |
| frozen Dragapult teacher | **control and evaluation opponent**, and the only agent with an external score |

All remain immutable and are used in c014 only as opponents and controls.

## Infrastructure that remains useful

- the identity-safe evaluation protocol (c009) — every game re-verifies the artifact it played;
- content-aware validation: recompute headline claims from raw records with an *independent*
  seed rather than reading the file that published them;
- pre-registration of decision rules before results are visible;
- `cg.gameplay.play_one` — deck-and-agent agnostic, already counts invalid selections,
  exceptions, timeouts and latency. **c014 is built on this**, not on the neural evaluation stack;
- the discipline of disclosing defects that changed a published number.

## Why c014 pivots to deck-agent co-design

The competition scores a **deck-agent pair**. c005–c013 optimised the *agent* while holding the
*deck* fixed, and the measured result is that this variable is close to exhausted: six seeds and
181,184 games of PPO produced nothing better than averaging two checkpoints' weights for free,
and the frozen teacher still outscores every RL agent on the strategic field (≈0.55 vs ≈0.37).

The Archaludon deck makes the argument concretely. Three of its rules cannot be discovered by
any amount of policy optimisation over the Dragapult list, because the cards they concern do not
exist in that deck:

1. Cinderace is a Stage 2 with no Raboot in the deck — it is playable only through *Explosiveness*;
2. discarding Basic {M} Energy is a **gain**, because *Assemble Alloy* recovers it from the discard;
3. energy attachment must outrank card plays, or {M}{M}{M} is never assembled.

## The c014 deck-agent thesis

> Open with Cinderace in the Active Spot to attack for 50 while it loads three Basic Energy onto
> a benched Duraludon, then evolve into Archaludon ex — which recovers two more {M} from the
> discard as it evolves — and win the damage race with a 220-damage attack that also cancels its
> own Fire weakness.

Deck SHA-256 `42165967b565dd42ec426ecccfe79bfa7d72aa8306590e149dface0ee8bd530e`.

## The three-branch operating model

| branch | status |
|---|---|
| **Meta-proven** (Archaludon ex / Cinderace) | implemented and submitted in c014 |
| **Anti-meta** | provisional thesis only; implementation begins after the meta-proven v0 is submitted |
| **Dragapult** | preserved control, fallback, and evaluation opponent — never the submitted result |

## Champion / challenger / archive rule

- **Champion**: the agent with the best *external* evidence. Today that is still the frozen
  Dragapult teacher at 719.7, because it is the only agent with a public score.
- **Challenger**: c014's Archaludon v0 — validated, packaged, submitted, score pending. It
  becomes champion only on external evidence, never on local score rate.
- **Archive**: everything else stays immutable and reusable as an opponent or control.

No champion is declared on local games. c013's own history is the argument for that rule: an
in-run signal of 0.275→0.425 evaporated on a properly powered panel.

## The single next loss mode

> Cinderace's *Explosiveness* opener is available in only a minority of games, so *Turbo Flare* —
> the deck's only energy accelerator — is usually absent, and the deck must reach {M}{M}{M}
> through one manual attachment per turn.

Chosen because it is upstream of the bench-liability and all three matchup loss categories.

## Why no more blind Dragapult PPO is authorized

Because it has been measured, not assumed:

- 181,184 games across six seeds in c011/c012 produced no candidate better than a free
  weight average;
- c013's three registered learnability methods each failed to produce a confirmed improvement;
- the binding constraint is not policy quality but the ≈0.18 strategic-field gap to a
  *rule-based* teacher, which no combination or continuation method has moved.

Further PPO on this deck would spend a large compute budget re-measuring a negative result that
now has three independent confirmations. Compute goes to deck-agent co-design instead.
