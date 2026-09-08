# c006 Training Specification — Distilled Student (behavioral cloning)

Concrete, buildable spec for the first student that clones the frozen c005 teacher
`dragapult` on its exact deck (`sha256:8055443275c86…`). **No training is done in
c005.** The student is trained on the frozen `teacher_dataset/` splits (test split
frozen for c006). Companion machine-readable config: `c006_training_config.json`.

## 1. Input representation
Each example is one teacher decision. The model scores each **legal option**.

**State/entity features** (from `observation`, all present in schema-v2 snapshots):
- Global: turn number, whose-turn, both players' prize counts, deck/hand/discard
  sizes, energy zone sizes.
- Per-Pokémon (active + up to 5 bench, both players): card_id (embedding),
  HP / remaining-HP, energy attached (per type count), status conditions,
  evolution stage, tool attached (bool). Fixed max-bench padding with a mask.
- Card identity uses a learned embedding table keyed by `card_id` over the union
  of card IDs in the teacher deck + all card IDs observed in the dataset
  (`all_card_data()` provides the static card feature table: HP, type, weakness,
  retreat, attack ids/damage — concatenated to the embedding).

**Deck representation:** a fixed multiset vector over the teacher's 60-card deck
(counts per card_id), shared across all examples (single deck in c006).

**SelectContext representation:** a learned embedding of the `select_context`
(49-way `SelectContext` enum) concatenated to the state encoding.

**Legal-option representation:** each option in `legal_options` is encoded by its
`OptionType` (embedding) + type-specific fields (area/index → the referenced
Pokémon's state features; attackId → attack damage/energy cost; cardId → card
embedding; number/count → scalar). Variable-length list per example.

**Masking rules:** the policy produces one score per legal option; there is no
fixed action space — only the `legal_options` present in the record are scored,
so illegal actions are structurally impossible. For multi-select contexts
(`max_count > 1`) the loss targets the recorded `teacher_action_indices` set
(see §3). Padding positions are masked out of the softmax and the loss.

**Missing/unknown handling:** unknown `card_id` → a shared `<UNK>` embedding;
absent optional fields → zero + a "present" indicator bit; `null` scalars → 0
with a mask bit. `importance_class` is a feature-free label used only for
weighting/eval, not fed to the model.

## 2. Initial model (default)
Structured legal-option scorer, **1–5M parameters**:
- **Shared state encoder:** card/entity embeddings → per-Pokémon MLP → mean/attention
  pool over each player's board → concat global scalars → 2–3 layer MLP (d≈256).
- **Context embedding:** `SelectContext` → d≈64, concatenated to the state vector.
- **Option encoder:** per-option feature MLP (d≈128) that also cross-attends to
  the shared state vector (option ↔ state).
- **Policy head:** dot-product / small MLP producing **one scalar score per legal
  option**; softmax over the (masked) option list.
- **Value head:** DISABLED for the first cloning baseline (config flag
  `value_head=false`).

## 3. Training
- **Objective:** behavioral cloning. Single-select contexts: cross-entropy of the
  option softmax vs the recorded `teacher_action_indices[0]`. Multi-select
  (`max_count>1`): multi-label binary cross-entropy over options with the recorded
  index set as positives (documented; ~small fraction of records).
- **Batch construction for variable option lists:** pad options to the batch max,
  carry a boolean option-mask; group by similar option-count buckets to reduce
  padding; ragged collate.
- **Optimizer:** AdamW, weight_decay 0.01. **LR:** 3e-4 with cosine decay + 500-step
  warmup. **Budget:** up to 30 epochs / early stop. **Batch:** 256 decisions.
- **Early stopping:** on validation exact-action agreement, patience 4 epochs.
- **Class/context weighting:** upweight `importance_class=="high"` decisions
  (weight 2.0) and inverse-frequency weight rare high-impact contexts (ATTACK,
  SWITCH, EVOLVE) so MAIN does not dominate.
- **Seed handling:** fixed seeds for init/shuffle; log seed; deterministic dataloader.
- **Checkpointing:** best-val checkpoint + last; save option/card vocab with the model.
- **CPU inference target:** the student must run within the cabt per-move budget on
  CPU (teacher P99 ≈ 0.3 ms is the reference; student target **P99 < 50 ms**).
- **Package-size target:** submission archive **< 100 MB** (model + `cg/` + deck);
  quantize/prune if needed.

## 4. Evaluation gates (before a Submission B decision)
- **Exact action agreement** on the frozen test split (target ≥ 0.75 overall).
- **Top-k agreement** (k=2) on test (target ≥ 0.90).
- **High-impact-context agreement** on test (ATTACK/SWITCH/EVOLVE/MAIN; report each).
- **Forced-context agreement**: agreement conditioned on each high-impact context.
- **Full-game student-vs-teacher comparison**: student plays the frozen teacher on
  the same deck; report seat-balanced win rate + action-match rate.
- **Strategic gauntlet comparison**: run the student through the c004/c005 gauntlet
  protocol vs the frozen teachers; regularized BT strength + worst-matchup.
- **Reliability**: zero invalid actions / attributable exceptions / timeouts.
- **P99 latency**: < 50 ms on CPU.
- **Submission decision criteria (Submission B):** SUBMIT only if reliability gate
  passes AND student's seat-balanced win rate vs the frozen teacher has a 95%
  bootstrap CI not below 0.45 (student is not clearly worse) AND exact-agreement
  ≥ 0.75; otherwise iterate before submitting.

## 5. Data
- Train/validation/test = `teacher_dataset/{train,validation,test}.jsonl.gz`
  (whole-game split, stratified by opponent/seat/outcome; **test frozen for c006**).
- Labels = `teacher_action_indices`; inputs = `observation` + `legal_options` +
  `select_context`. Teacher losses are retained (learn from losing lines too).
