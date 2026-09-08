# c012 — Fixed-Deck Self-Play Curriculum and Claude Teacher Qualification — SUMMARY

**STATUS = PASS (16/16 acceptance criteria)**

```text
C011_REPAIR            = COMPLETE
TRUE_INCUMBENT         = SOUP_622+633
OPPONENT_OVERLAP       = SUPPORTED
CURRICULUM_RESULT      = TIED
SELF_PLAY_LOOP         = NOT_EXTENDED
CLAUDE_BRANCHING       = INCONCLUSIVE
CLAUDE_TEACHER_STATUS  = REJECTED
BEST_AGENT             = TRUE_INCUMBENT
SUBMISSION_F           = DO_NOT_SUBMIT
PROMOTION_DECISION     = KEEP_TRUE_INCUMBENT
NEXT_STEP              = REDESIGN_FIXED_DECK_AGENT
```

## The result in one paragraph

The single largest gain in this contract required no training at all. An arithmetic average of two c011 seeds' weights, `SOUP_622+633`, scores **0.380** against the frozen teacher and **0.390** on the strategic field, against 0.270/0.353 for c011's best single policy — a +0.11 teacher gain for zero compute. Six PPO seeds then trained 181,184 completed games from that soup under two different opponent populations, and **neither arm beat it on teacher score**. The curriculum comparison came out `TIED` and the self-play loop `NOT_EXTENDED`. The binding constraint is therefore not the opponent curriculum and not compute: it is that this PPO configuration cannot exceed a point that weight-space averaging reaches for free.

## Machine and dependencies (AC-01)
```text
AMD Ryzen 9 7900X 12-Core Processor, 24 threads, 62.0 GiB
NVIDIA GeForce RTX 5070 11752 MiB, driver 595.71.05
PyTorch 2.13.0+cu132 / CUDA 13.2, Python 3.13.13
frozen deck fingerprint 676849e9a1f8ce0cc594a7242aba1fcc...
frozen teacher sha256   ef8936859fd215e6c704071042e5438d...
c011 checkpoints hash-verified: 62
```

## c011 defects repaired (AC-02)

- **active_rng_not_restored** (§7) — c011_trainer_state.py saved np.random.get_state() (the legacy GLOBAL RNG) and re-seeded with np.random.seed(); the trainer sampled from a separate np.random.default_rng(seed) object, so restore restored nothing it used. *Repair:* One Generator drives opponent draws, seats, per-game seeds and the PPO minibatch permutation, saved/restored via rng.bit_generator.state.
- **continuation_test_used_precomputed_orders** (§7) — c011's continuation test passed precomputed minibatch permutations to both runs, which masks exactly the RNG divergence the test should detect. *Repair:* Permutations are drawn from the live Generator inside the update; the test compares opponent draws, seats, requested seeds, permutations, losses and parameters across a save/restore boundary, and includes a NEGATIVE CONTROL proving a broken restore would be caught.
- **budget_counted_trainable_not_completed_games** (§8) — games_done counted only games with trainable decisions, excluding completed games that contained only forced decisions. *Repair:* completed_games is the budget quantity; completed_games, games_with_trainable_decisions and trainable_decisions are tracked separately in every summary and update record.
- **early_stopping_could_never_fire** (§9) — all evaluation ran after training finished, so the registered stop rules had no data during the run. *Repair:* Registered evaluations run DURING training at every registered point and feed the stop rules.
  - **Residual:** A path-keyed hash cache made those in-run evaluations return no scored games after game 0 in the executed run; see failures/DEFECT_inrun_evaluation_stale_hash.md. The mechanism is implemented and fixed, but was NOT exercised by this run's P1 arm.
- **scale_bootstrap_used_max_significance** (§10) — c011's scale decision took the MAXIMUM bootstrap significance across any seed/metric pair as its 'one median improvement' condition. *Repair:* c012 computes the registered MEDIAN best-per-seed improvement for both teacher and field, and reports the medians explicitly in curriculum_decision.json.

## Phase 0 — elite combinations and the frozen incumbent (AC-03/04/05)

- 4 weight soups and 4 logit ensembles registered **before** any combination was evaluated (§12).
- **TRAINING_INCUMBENT = SOUP_622+633**, EVALUATION_ELITE = SOUP_622+633, ELITE_POOL = ['SOUP_622+633', 'S_622_g39983', 'S_633_g10224', 'S_611_g40127']
- Selected from 66 correctly confirmed candidates on equal 500-game footing.

## Phase 1 — overlap analysis (AC-06/07)

**OPPONENT_OVERLAP = SUPPORTED** — mean top-1 agreement **0.843** across 15 policy pairs on identical frozen states. Learned elites agree with one another far more than they agree with the rule teacher, so an elite-only population would narrow the state distribution. That is the risk the adaptive curriculum caps elite share at 45% to manage.

## Phase 2 — controlled curriculum (AC-08/09/10)

| arm/seed | completed | trainable | updates | stage | stop |
|---|---:|---:|---:|---:|---|
| P0_711 | 30,000 | 30,000 | 70 | 0 | budget_reached |
| P0_722 | 30,320 | 30,320 | 71 | 0 | budget_reached |
| P0_733 | 30,336 | 30,336 | 71 | 0 | budget_reached |
| P1_811 | 30,224 | 30,223 | 72 | 0 | budget_reached |
| P1_822 | 30,048 | 30,048 | 72 | 0 | budget_reached |
| P1_833 | 30,256 | 30,256 | 72 | 0 | budget_reached |

**181,184 completed training games** against §48's 184,000 ceiling; zero invalid actions and zero exceptions across all six seeds.

| | median teacher | median field |
|---|---:|---:|
| P0 control | 0.325 | 0.36000000000000004 |
| P1 elite self-play | 0.325 | 0.37333333333333335 |

`CURRICULUM_RESULT = TIED`, `SELF_PLAY_LOOP = NOT_EXTENDED`.

> **Caveat that limits this result.** P1 ran the stage-0 mixture (15% elite) for its entire budget: the in-run evaluation defect recorded in failures/ left the curriculum gates without scores, so the 15->25->35->45% escalation was never exercised. P0 vs P1 therefore compares unchanged population against FIXED 15% elite self-play, not against the adaptive schedule.

## Final panel — 1,000 games per candidate (AC-14)

| candidate | teacher | strategic field |
|---|---:|---:|
| SOUP_622+633 | 0.3600 | 0.3883 |
| P0_711_g20144 | 0.3800 | 0.3542 |
| P1_822_g5120 | 0.3350 | 0.3617 |
| P1_833_g15232 | 0.3150 | 0.3625 |
| P0_722_g20048 | 0.3100 | 0.3567 |
| P0_733_g15056 | 0.3000 | 0.3500 |
| P1_811_g25216 | 0.2875 | 0.3442 |
| T_teacher | — | 0.5450 |

The **frozen teacher scores 0.5449999999999999 on the same strategic field** where the best agent manages 0.38833333333333336. `BEST_AGENT = TRUE_INCUMBENT`, `KEEP_TRUE_INCUMBENT`.

## Phase 3 — hard-state benchmark (AC-11)

- 240 primary + 48 repeat states, no category above 25% (§34 cap 25%)
- **240/240 hidden-information clean**; hash-locked `fe3afe54591b5ac3dff77fe11d4bc835...` before any Claude call

## Phase 4 — Claude Opus qualification (AC-12/13)

- model requested `opus`, resolved `claude-opus-5`, verified per call from `modelUsage` output tokens; tools disabled; sequential; frozen prompt and schema
- **17 primary labels** (0 subprocess timeouts reported separately), 13 repeats, $4.54 total
- schema-valid **0.92**, legal-action **1.0**, hidden-information violations **0**, repeated top-1 consistency **1.0**
- `CLAUDE_BRANCHING = INCONCLUSIVE` — The simulator exposes a forward-search API, but no observation captured through the standard agent interface carried the `search_begin_input` payload that `search_begin` requires, so a saved position could not be restored and branched under matched stochastic conditions.
- **`CLAUDE_TEACHER_STATUS = REJECTED`.** §42 — QUALIFIED_* requires valid branching AND objective superiority. With branching INVALID the ceiling is PROMISING_UNVALIDATED regardless of how good the labels look; agreement and rationale quality are explicitly not evidence of teacher quality (§5).
- Claude labels were **not** used to update any policy weights (§2).

## Submission (AC-14)

`SUBMISSION_F = DO_NOT_SUBMIT`, `KAGGLE_UPLOAD = SKIPPED_BY_GATE`. Teacher non-inferiority needs a one-sided 95% lower bound of 0.47; measured 0.32. The agent must also beat the frozen teacher's same-panel field score of 0.5449999999999999; it does not. Nothing was uploaded and no archive was built. Teacher ref 54948560 was refreshed read-only (public score 712.6).

## Evidence integrity (AC-15)

- **91 content-aware checks, 0 failed** — hashes recomputed, aggregates rebuilt from raw games, budgets recounted, curriculum lock re-hashed
- 30,260 evaluation games, identity assertions passing on every batch, 0 defects
- source bundle `c012_python_source_bundle.zip` sha256 `60c61b5290978ef3353ac1c1571da878...` (18 checks, 0 failed)

## Next step and blocker

`NEXT_STEP = REDESIGN_FIXED_DECK_AGENT`.

**Highest-leverage blocker (one, measured):** PPO continuation has stopped adding value from this initialisation. Neither arm beat the frozen incumbent on teacher score at 500 games (incumbent 0.380; best P0 0.325, best P1 0.345), while a zero-cost weight average of two c011 seeds gained +0.11 teacher over c011's best single policy. The binding constraint is the optimiser's inability to exceed a point that parameter averaging reaches for free -- not opponent curriculum, not compute.

**Hypotheses, labelled as such and untested here:** that weight-space averaging keeps paying over more diverse seeds; that the escalating elite schedule would behave differently from the fixed 15% actually run; that a different optimiser or value target would pass the point averaging reaches.

## Known limitations

- P1 ran the stage-0 mixture (fixed 15% elite) for its entire budget: a path-keyed checkpoint-hash cache left every in-run evaluation after game 0 without scores, so the 15->25->35->45% escalation and the §24 advance gates were never exercised. See failures/DEFECT_inrun_evaluation_stale_hash.md. Re-running P1 would have breached §48's 184,000-game ceiling, so the limitation is carried into the result.
- Early stopping was implemented and wired but received no in-run scores for the same reason, so no branch could stop early; every seed ran to budget.
- CLAUDE_BRANCHING is INCONCLUSIVE: the simulator exposes a forward-search API but no observation captured through the agent interface carried the search_begin_input payload search_begin requires, so objective action adjudication was not possible and no superiority claim is made.
- Claude labelling used a bounded registered subset rather than the §48 maxima, because the measured cost was ~$0.23/call.
- Games are engine random_device-seeded and not bit-reproducible; conclusions are stated with bootstrap intervals over the recorded games.
