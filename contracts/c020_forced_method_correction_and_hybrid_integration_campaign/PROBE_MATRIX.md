# c020 Probe Matrix

Probes are non-blocking observability by default. Preserve inputs, outputs, source/config hashes, raw traces, and taint propagation.

## P00 — Parent and control freeze

Verify parent resolution, c019 control hashes, baseline package, deck, and immutability.

## M01 — Information-set key privacy

Create several determinizations of the same visible state. Their information-set keys must match while private native/world IDs differ. Changing visible legal information must change the key.

## M02 — Shared statistics across determinizations

Prove the same shared action statistic receives visits/backups from at least two distinct determinization IDs.

## M03 — Availability-aware action accounting

An action unavailable in one world but available in another must not be treated as a zero-value visit. Verify availability counts and selection denominator.

## M04 — Branch-local memory parity and independence

- search disabled reproduces original baseline actions;
- sibling branches do not mutate each other;
- override advances memory using executed action;
- module globals are absent from simulated decisions.

## M05 — Non-root PUCT lifecycle

Runtime trace shows selection, non-root expansion, rollout/evaluation, and backup across multiple depths with changing Q/N.

## M06 — Tactical evaluator fixtures

Fixtures for lethal, KO, typed-energy readiness, active/bench identity, target prize value, resource reservation, productive attack, and unproductive end turn. Log full feature decomposition.

## M07 — Evaluator anti-reward-hacking

Reproduce c019 end-turn-over-card-play examples. Corrected evaluator/override must retain productive baseline action unless a preregistered tactical reason is proven.

## M08 — Legal determinization and unknown-archetype prior

No filler duplication; exact multiplicity; invalid worlds rejected; unknown opponent uses recorded prior mixture rather than silent Dragapult default.

## M09 — Conservative override ablation

Compare:

```text
baseline
corrected MCTS with overrides disabled
corrected MCTS without conservative veto
corrected MCTS with conservative veto
```

Same seeds/seats. Log every override and outcome.

## M10 — Native lifecycle and match clock

No leaked search IDs, release errors, or unsafe cumulative time.

## B01 — Slot identity preservation

Swapping active and bench while keeping card multiset constant must change encoding and relevant option logits.

## B02 — Typed energy/status/tool sensitivity

Changing attached energy type, status, or tool must change the referenced Pokémon representation and relevant option score.

## B03 — Option-to-target alignment

Two identical card IDs in different slots/damage states must produce distinguishable target-option embeddings/logits.

## B04 — Canonical action round trip

Every legal single- and multi-select option reconstructs exact environment payload.

## B05 — Autoregressive multi-select joint probability

Hand-computed two- and three-pick fixtures verify mask updates, conditional probabilities, joint log probability, STOP legality, and learner loss on all picks.

## B06 — Actor/learner recurrent replay

Using stored actor checkpoint and `h0/c0`, learner replay reproduces behavior logits/joint log probabilities for mid-game unrolls within tolerance.

## B07 — Episode boundary reset

Recurrent state resets only at true episode boundaries; 100% of mid-game unrolls carry non-default stored state unless mathematically zero by chance.

## B08 — V-trace numerical fixtures

Single action, multi-select, terminal, truncated recurrent sequence, clipping bounds.

## B09 — UPGO numerical and live contribution

Hand-computed fixture and nonzero live auxiliary gradients/loss.

## B10 — Fresh initialization and optimizer

Corrected ByteRL model/optimizer hashes differ from c019 and from each other as expected; no c019 weight load.

## B11 — OSFP period reset

Each period's G/C starts at zero. Payoff games cite one frozen checkpoint hash only.

## B12 — Promotion integrity

Performance promotion uses frozen checkpoint versus historical population. Force-add is labeled separately. Historical hashes remain immutable.

## B13 — Requested versus actual opponent mixture

Compare planned and completed games by opponent/checkpoint/seat; explain deviations.

## B14 — Package recurrent/action parity

Extracted package reproduces repository logits, full selected payload, recurrent transition, and value on fixed sequences.

## H01 — Branch-local neural state

Sibling search nodes carry independent recurrent states; non-root calls do not use `state=None`.

## H02 — Prior action alignment and floor

ByteRL probabilities map exactly to MCTS action keys, normalize, and preserve nonzero floor for credible actions.

## H03 — Value admission

Compare corrected value to constant, c019 value, random ranking, and tactical heuristic on held-out leaves.

## H04 — Controlled H0/H1 prior ablation

Same tree budget/seeds; only priors differ.

## H05 — Controlled H0/H2 value ablation

Same tree/budget/seeds; only leaf value differs.

## H06 — H3/H4 integration

Priors + value and preregistered blend execute with branch-local recurrent state and exact mode manifests.

## F01 — Complete integrated smoke

All corrected pure and hybrid blocks execute before the consolidated repair pass.

## F02 — One repair pass audit

Record ranked root defects, selected maximum five, files changed, rerun scope, and no second repair cycle.

## F03 — Identity-safe final panel

Candidate/opponent/seat/seed mapping is explicit and raw-game-derived.

## F04 — Package/source identity

Each package references exact source/config/checkpoint manifest and clean extraction test.

## F05 — Semantic evidence validator

Inject or fixture every known c019 defect and prove the validator rejects it.

## F06 — Full source bundle

Complete final repository, focused c020 bundle, plain inspection copies, milestone snapshots, patch, manifests, and hashes open successfully.
