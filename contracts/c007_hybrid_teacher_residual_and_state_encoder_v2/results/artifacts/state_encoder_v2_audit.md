# State Encoder v2 — Completeness Audit (AC-03, §7)

**Decision: `STATE_ENCODER_V2 = ACCEPT`.**

State Encoder v2 (`cg.state_encoder_v2`) directly targets every representational
weakness the c006 review named. It consumes the raw cabt observation dict — the same
object offline and at runtime — and emits fixed-shape tensors so the pure-numpy v2
model trains on dense batches. All 19,050 stored c006 decisions encode with **0
errors, 0 non-finite values, and byte-identical determinism** on re-encode
(`state_encoder_v2_tests.txt`).

## What changed vs c006 (the diagnosis, point by point)

| c006 weakness | v2 fix |
|---|---|
| dynamic in-play state omitted | full per-slot HP/damage/remaining-fraction, energy count + 12 energy-type counts, tools, evolution-stack depth, appeared-this-turn, status conditions, KO-range flags, prize-yield |
| exact hand/bench/discard collapsed (bag means) | **12 explicit board slots (self active + 5 bench, opp active + 5 bench), never averaged**; hand & discard as exact multisets fed to DeepSets set encoders |
| weak card semantics | deterministic 52-d card features for every legal card + a **zero-initialised id-embedding residual** (unseen legal cards fall back to feature-derived semantics — no random untrained id vectors, §7.6) |
| independent option scoring | **cross-option set encoder** (DeepSets mean+max pool over the legal-option set), so one option's score depends on the other available options (§7.5) |
| incomplete previous-action identity | history carries the **actual previously-selected option identity** — its card id (52-d semantics), attack id, and option type — not just the index, and resets at game start (§7.4) |
| limited data | addressed by the expanded ≥600-game v2 dataset (AC-05) |

## §7.7 field-by-field classification

`c006_vs_v2_feature_diff.json` classifies every observed source field as
`represented_directly` (22), `deterministically_transformed` (10),
`intentionally_omitted` (3), or `unavailable_hidden_or_privileged` (2). Each omission
carries a strategic justification; the load-bearing ones:

- **`current.result` — intentionally omitted from inputs.** It is the terminal outcome;
  feeding it would leak the label. It is used only as the value-head training target.
- **`search_begin_input` — intentionally omitted as a model input.** It is an opaque
  engine-state blob used solely for the branch-and-rollout capability probe (AC-08),
  never featurized.
- **`select.effect` — intentionally omitted from the global vector.** The one place it
  matters (Crispin reverse-scoring) is already captured through the option set; it is a
  documented candidate future field.
- **opponent hand / deck order / face-down prize identities —
  `unavailable_hidden_or_privileged`.** Hidden-information discipline: only counts are
  used. The teacher's remaining-deck-composition inference is a *privileged label*
  (auxiliary training target), never a runtime input.
- **`deterministically_transformed`** covers exact energy-card / tool / stadium
  identities (compressed to counts and type/presence), discard beyond the recent window
  (per-card-type count summary), and the full event log (compressed to the previous
  action identity). These are lossy-by-choice compressions whose omitted detail is
  low-leverage relative to its dimensionality cost, and the strategically relevant cases
  (energy TYPE, tool presence, the specific stadium) are recoverable from the retained
  features or the option set.

## Hidden-information handling (§7.3)

The encoder never reads the opponent's hand (a `None` in the observation; only
`handCount` is used), never reads face-down prize identities, and never reads deck
order. The only "deck knowledge" is the public `deckCount` for each player. This keeps
the runtime model strictly within the information set a real agent observes; the
teacher's privileged plan/deck inferences enter training exclusively as auxiliary
labels (V2-B), which the hybrid evaluation confirms are never runtime inputs.

## Model consumption (why the representation is usable, not just present)

`cg.policy_model_v2` (538,770 params, inside the registered [500k, 2M] band) consumes
the schema with a shared card encoder (semantic MLP + zero-init id residual), a
slot-specific board encoder (12 slots concatenated), DeepSets zone encoders for hand
and discard, a global/history encoder, and a cross-option set encoder that pools over
the legal options before scoring each — so the representation's structure is exercised
end to end. Gradients are numerically checked (`tests/test_c007_models.py`).
