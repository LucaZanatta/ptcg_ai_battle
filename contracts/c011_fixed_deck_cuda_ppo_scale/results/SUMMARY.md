# c011 — Fixed-Deck CUDA PPO Scale and Source Audit Bundle — SUMMARY

**STATUS = PASS (16/16 acceptance criteria)**

```text
C010_EVIDENCE_REPAIR = REPAIRED
CUDA_BACKEND_PARITY  = PASS
CUDA_EXECUTION_MODE  = FP32_CUDA
CUDA_SPEEDUP         = MATERIAL
INCUMBENT_ID         = C_522_g20220
SCALE_RESULT         = EXTENDED
BEST_AGENT           = S_633_g30176
TRAINING_LOOP_STATUS = VALIDATED
SUBMISSION_F         = DO_NOT_SUBMIT
PROMOTION_DECISION   = PROMOTE_NEW_AGENT
NEXT_STEP            = CONTINUE_FIXED_DECK_RL
```

## The result in one paragraph

The fixed-deck PPO loop **does scale**: three independent seeds, each continuing the repaired
c010 incumbent for ~40,000 additional games on a parity-validated CUDA backend, all beat that
incumbent on every metric, and `SCALE_RESULT = EXTENDED` on all seven registered conditions.
The promoted agent `S_633_g30176` reaches **0.335** against the frozen
teacher and **0.367** on the strategic field. It is still not submittable, and the
reason is the finding this contract was written to surface: measured on the *same panel*, the
frozen teacher scores **0.545** on that field. c010 never made that measurement.

## Machine and dependencies (AC-01)

```text
AMD Ryzen 9 7900X 12-Core Processor, 24 threads, 62.0 GiB RAM
NVIDIA GeForce RTX 5070 11752 MiB, driver 595.71.05
PyTorch 2.13.0+cu132 / CUDA 13.2 / cuDNN 92000, Python 3.13.13
frozen deck fingerprint 676849e9a1f8ce0cc594a7242aba1fcc...
frozen teacher sha256   ef8936859fd215e6c704071042e5438d...
```

The registered profile declares PyTorch 2.12.1+cu130 / CUDA 13.0; the installed stack is
**2.13.0+cu132 / CUDA 13.2**. The observed values govern every decision and the diff is
recorded in `hardware_environment.json` rather than silently reconciled. 42 c010
checkpoint hashes verified; c010's final aggregates reproduce from its raw games; c005–c010
unmodified.

## c010 evidence repair (AC-02)

- **42 saved c010 checkpoints enumerated** programmatically from c010's own screening CSV
  and registries — the contract's approximate example IDs are deliberately unused (§7.1).
- **29 promising**, of which **9 had never been confirmed**; all nine received a 500-game panel.
- **Repaired incumbent `C_522_g20220`** (teacher 0.310, field 0.303),
  chosen from 41 correctly confirmed candidates by the §7.3 ordering, frozen and hashed.
- Full governance record in `artifacts/c010_governance_repair.md`.

The teacher-as-candidate path had never been exercised: c009's worker leaves
`verified_checkpoint_sha256` null for `frozen_teacher` while the identity assertion requires it
to match, so every teacher game would have failed. c011 fixed this **without weakening the
assertion** — the worker re-hashes the teacher module it actually executes.

## Backend parity (AC-03/04/05)

| check | float64 | float32 | registered bar |
|---|---:|---:|---:|
| max abs logit error | 1.07e-14 | 5.43e-06 | 1e-5 |
| max abs value error | 7.77e-16 | 3.15e-07 | 1e-5 |
| multiselect summed logprob | 2.44e-15 | 1.38e-06 | 1e-5 |
| max PPO loss error | — | 1.27e-08 | 1e-4 |
| min per-tensor update cosine | 1.000000000000 | 0.999999839 | 0.999 |
| NPZ round trip | 0.0 | — | 1e-5 |

Illegal-action probability is exactly zero, legal masks and argmax are identical, and the
trainer-state round trip is **exact** (weights and AdamW moments both 0.0 difference), with the
resumed update matching an uninterrupted control to 0.0.

Reporting both dtypes is deliberate: float64 proves the port is *semantically* exact, so the
float32 row measures precision cost alone. No tolerance was widened.

## CUDA decision (AC-06/07)

| backend | update seconds | speedup |
|---|---:|---:|
| numpy_micrograd | 2.1689 | 1.0x |\n| torch_cpu_fp32 | 0.6166 | 3.518x |\n| torch_cuda_fp32 | 0.1646 | 13.179x |\n| torch_cuda_bf16 | 0.1718 | 12.627x |\n

At the selected **16 workers**: PPO-update **14.178x**, end-to-end
**2.869x** (36199 games/hour, CV 0.042). Both §11.2
criteria for MATERIAL are met, so the verdict rests on wall-clock throughput, not on GPU
utilisation being nonzero.

Worker count was chosen over **3 repeated windows** because a single window picked
different winners on different runs; §11.1's 5%-variance rule decides it. BF16 measured
*slower* than FP32 (0.1718s vs 0.1646s), so it was declined on
evidence and its 2,000-game smoke was never spent. FP16 prohibited and unused;
`torch.compile` unused.

## Scale training (AC-08/09/10)

| seed | games | updates | rate | invalid | exceptions |
|---|---:|---:|---:|---:|---:|
| 611 | 40,127 | 92 | 39,142 g/h | 0 | 0 |\n| 622 | 39,983 | 93 | 39,256 g/h | 0 | 0 |\n| 633 | 40,064 | 92 | 39,966 g/h | 0 | 0 |\n

**120,174 training games**; 123,066 including calibration and smoke, against the
**124,000 hard maximum** — the per-seed budget was derived from actual spend *before* launch
(`training_budget_derivation.json`) precisely so rollout granularity could not breach it.

All three seeds are **warm restarts** and say so: the c010 incumbent stores policy weights
only. From the first c011 update every registered checkpoint carries full trainer state
(weights, AdamW moments, step, LR/entropy schedule, four RNG streams, opponent-sampler state,
lagged registry), so the next continuation can be literal.

## Final panel — 1,000 games per policy candidate (AC-13)

| candidate | teacher | strategic field | composite | held-out Abomasnow |
|---|---:|---:|---:|---:|
| **frozen teacher** | — | **0.545** | — | 0.515 |
| S_633_g30176 | 0.3350 | 0.3667 | 0.3493 | 0.270 |\n| S_622_g39983 | 0.2925 | 0.3767 | 0.3304 | 0.230 |\n| S_611_g40127 | 0.3075 | 0.3467 | 0.3251 | 0.275 |\n| C_522_g20220 | 0.2350 | 0.3350 | 0.2800 | 0.245 |\n

`SCALE_RESULT = EXTENDED` — all seven §21 conditions met: median teacher gain
+0.075 and field gain +0.068 over the incumbent, max bootstrap
significance 0.9922, no majority Abomasnow regression, reliability clean.

Milestones: M1 (teacher ≥0.35 and field ≥0.36) **False**, M2 **False**,
M3 (teacher LB95 ≥0.47) **False** — best LB95 measured 0.290.

## Where the difficulty lives (AC-12)

Value quality scored against **actual terminal outcomes**, by game phase, averaged over seeds:

| phase | Brier | AUC | accuracy | EV vs outcome | advantage SNR |
|---|---:|---:|---:|---:|---:|
| 0-20 | 0.2285 | 0.672 | 0.624 | 0.094 | 0.1036 |\n| 20-40 | 0.2010 | 0.757 | 0.690 | 0.198 | 0.0773 |\n| 40-60 | 0.1669 | 0.834 | 0.756 | 0.332 | 0.0448 |\n| 60-80 | 0.1278 | 0.903 | 0.821 | 0.489 | 0.0416 |\n| 80-100 | 0.0860 | 0.958 | 0.884 | 0.659 | 0.1037 |\n

The value head explains **0.094** of outcome variance in the opening fifth of a game
against **0.659** in the closing fifth — a seven-fold gap — and 40,000 games per seed did not
move it. c010 measured explained variance against GAE lambda-returns, which is a
self-consistency check: a value head can look calibrated against its own bootstrap while
predicting the eventual winner poorly. Scoring against realised outcomes separates those, and
shows the loop is improving the policy while the early-game value signal stays weak.

## Submission (AC-16)

`SUBMISSION_F = DO_NOT_SUBMIT`, `KAGGLE_UPLOAD = SKIPPED_BY_GATE`. Nothing uploaded, no archive
built, package validation `NOT_APPLICABLE`. Two §24 conditions fail:

- teacher non-inferiority needs a one-sided 95% lower bound of **0.47**; measured **0.295**;
- the agent must beat the frozen teacher's **same-panel** field score: **0.367** vs **0.545**
  (gap +0.178).

The frozen teacher remains the standing submission; its reference 54948560 was refreshed
read-only this run (public score 716.0). A validated training loop is explicitly not sufficient
for submission, and this run is a clean example of both being true at once.

## Evidence integrity (AC-14/15)

- **77 content-aware checks, 0 failed.** Aggregates are recomputed from raw games with a
  different bootstrap seed, budgets recounted from raw records, parity re-checked against the
  registered tolerances, trainer-state lineage verified against checkpoints on disk.
- **22,160 evaluation games**, identity assertions passing on every batch, 0 defects,
  exact seat balance.
- **Python source bundle** `c011_python_source_bundle.zip` — sha256 `8291dd66d3923143d95fa2fab4f90936...`,
  validated by clean extraction (18 checks, 0 failed).

## Two defects found and fixed during the run

1. **Multi-threaded torch CPU float32 is not run-to-run reproducible.** A 7.6e-06 trainer-state
   discrepancy was diagnosed by running two *identical* updates, which differed by 2.6e-06.
   §9.2 requires deterministic FP32, so determinism is now pinned in every parity harness and
   the round trip became exactly 0.0. The round-trip check itself was also corrected: it had
   compared control-vs-resumed rather than the actual save→restore.
2. **B0 evaluated as the wrong candidate kind.** c010 records B0's kind in *training*
   vocabulary (`rl_ckpt_from_v2a`); the evaluator speaks *evaluation* vocabulary (`v2a_init`).
   Copied verbatim, every B0 game failed to build an agent — 100 defective games. The registry
   now translates; the games were purged and re-run.

## Next step and blocker

`NEXT_STEP = CONTINUE_FIXED_DECK_RL`. §2's deck-pipeline gate is **not** met (it requires ≥0.40
against the teacher; measured 0.335), so fixed-deck agent work continues.

**Highest-leverage blocker (exactly one, measured):** Absolute strength against the frozen teacher's own strategic field. The loop now demonstrably extends (EXTENDED, three seeds), but the promoted agent scores 0.367 on the field where the FROZEN TEACHER scores 0.545 on the identical panel -- a 0.178 gap, and the §24 submission gate additionally needs a teacher head-to-head lower bound of 0.47 against the measured 0.295. The measured mechanism is early-game credit assignment: value AUC against ACTUAL outcomes is 0.67 in the first fifth of a game versus 0.90 in the fourth fifth, and 40,000 games per seed did not move it (early Brier 0.228 against ~0.25 for a base-rate predictor). More PPO on this value head buys field score slowly; the head itself is the constraint.

**Hypotheses, labelled as such and not tested here:** that a distributional or multi-step value
target would lift early-game AUC; that opponent-conditioned value heads would reduce field
variance. Neither was evaluated in c011.

## Known limitations

- Games are engine random_device-seeded and not bit-reproducible; all conclusions are stated with bootstrap intervals and raw per-game records ship so aggregates recompute exactly.\n- Multi-threaded torch CPU float32 is not run-to-run reproducible (two identical runs differed by 2.6e-06); parity harnesses pin determinism, scale training does not need it. See failures/OBSERVATION_torch_cpu_float32_nondeterminism.md.\n- The c011 seeds are WARM RESTARTS: the c010 incumbent stores policy weights only. Full trainer state is written from the first c011 update, so the next continuation can be literal.\n- Screen panels are 100 games, so screen-level differences below ~0.10 are inside noise; only confirmation (500) and final (1,000) panels drive decisions.\n- BF16 CUDA was declined on measured throughput and therefore never received its 2,000-game smoke; that smoke could not have changed the verdict.\n
