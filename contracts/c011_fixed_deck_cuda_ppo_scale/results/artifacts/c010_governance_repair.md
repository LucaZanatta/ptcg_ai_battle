# c010 governance defects, repaired under c011 (§7.4)

c010 files are not modified (§4). Everything below is recorded here.

## 1. The submission gate compared against a teacher score from a different panel

c010's §23 gate asked whether the agent showed "reproducible strategic improvement over the
frozen teacher", but c010 never evaluated the frozen teacher **as a candidate** on its own
strategic panel. The teacher's field strength was therefore never measured under the same
conditions as the candidates it was being compared with.

c011 measured it. On the identical panel, opponents, seat balance and identity protocol:

```text
frozen teacher strategic-field score      0.545   (600 games, final panel)
c011 best agent  S_633_g30176             0.367   (1,000 games, final panel)
c010 best agent  C_522_g20220             0.335
```

The teacher is far stronger on the strategic field than any RL agent produced so far. c010's
comparison could not have revealed that, because the number it compared against did not exist.

**Mechanically, running the teacher as a candidate was impossible in c010's evaluator**:
`cg/c009_eval.py::run_job` skips checkpoint hashing when `candidate_kind == "frozen_teacher"`,
leaving `verified_checkpoint_sha256 = None`, while `assert_identity` requires it to equal
`checkpoint_sha256`. Every teacher game would have failed identity. c011 fixed this **without
weakening the assertion**: the worker re-hashes `teacher_sources/dragapult/main.py`, the module
`make_fresh` actually executes, so registry and worker hashes must still agree
(`ef8936859fd2...`). See `cg/c011_eval_core.py`.

## 2. Best confirmed checkpoint vs strongest saved checkpoint

c010 confirmed 30 of its 42 saved checkpoints. c011's §7.1 enumeration found **9 promising
checkpoints that were never confirmed**, several of them late in their branch:

```text
A_322_g10115  C_511_g10316  C_511_g15108  C_522_g7624   C_522_g10236
C_522_g15424  C_533_g5052   C_533_g7720   C_533_g10356
```

All nine received a c011 500-game confirmation panel. One of them, `C_522_g10236`, confirms at
composite **0.3185** — higher than the composite of the agent c010 promoted. It does not become
the incumbent only because §7.3 ranks teacher head-to-head first, where `C_522_g20220` leads
(0.310 vs 0.290). The repaired incumbent is therefore the same agent c010 chose, but now
selected from properly confirmed evidence across 41 candidates rather than from a partially
evaluated set.

## 3. c010 "continuation" was a warm restart, not full-state continuation

c010 checkpoints store policy weights only. Every c010 continuation arm (B and C) therefore
restarted AdamW moments, the entropy schedule, all RNG streams and the opponent sampler from
scratch. They were warm restarts described as continuations.

c011's three scale seeds are **also** warm restarts, for the same reason — they start from a
c010 checkpoint that has no trainer state to restore — and each seed's summary records
`continuation_kind: "warm_restart"` explicitly. From the first c011 update onward every
registered checkpoint carries full trainer state (weights, AdamW moments, optimizer step,
LR/entropy schedule, Python/NumPy/torch-CPU/torch-CUDA RNGs, opponent-sampler state, lagged
registry), verified by an exact save/restore round trip. The next continuation can be literal.

## 4. Post-result decision-rule changes in c010

c010 recorded three, each disclosed in its own `failures/` note rather than left in the diff:

- the per-arm budget check was renamed after observing rollout-granularity overshoot;
- `next_step` was rewritten after `REDESIGN` emerged from Arm A/B evidence;
- a floating-point tie fix changed `STABILIZED_CONTINUATION` from `INCONCLUSIVE` to
  `EXTENDED`, and consequently `NEXT_STEP` from `REDESIGN` to `SCALE`.

The third is the one to weigh: the underlying arithmetic was genuinely an exact tie
(47/150 − 17/60 = 3/100) and the fix was applied uniformly to every registered threshold, but
it was made after the numbers were visible. c011 does not revisit those decisions; it records
that they were made post-result so a reader can discount them appropriately.

## What c011 changed as a result

- The frozen teacher is a first-class evaluation candidate, so §24's comparison is same-panel.
- Every promising saved checkpoint is confirmed before an incumbent is chosen.
- Full trainer state is written from the first update, ending the warm-restart chain.
