# c005 — Summary

## Final status
**PASS** — 13/13. A real strategic teacher was selected, frozen, and packaged into
a validated Submission A; a model-ready distillation dataset and a concrete c006
training spec were produced.

## Candidates acquired / admitted / rejected
- **Acquired (official, reusable):** dragapult, mega_lucario, mega_abomasnow, iono
  — the four official kiyotah sample kernels (anonymous `kaggle kernels output/pull`,
  sha256 provenance).
- **Acquired (public):** `wmh/ptcg-abc` @ commit `1b31d39a` — **no license** →
  `LOCAL_BENCHMARK_ONLY`, not admitted, not in training data.
- **Admitted (strategic):** all four official teachers (4 distinct policies, 4
  distinct archetypes). Engineering controls do not count.
- **Not selected:** mega_abomasnow, iono (lower teacher_score).

## Reuse status
All four teachers are official competition samples → `OFFICIAL_REUSABLE`,
submission-eligible. The no-license public repo is local-benchmark-only. Full
rules text was not machine-retrievable (JS page); reuse basis is official-sample
provenance (`rules_and_reuse_audit.md`).

## Local ranking & external evidence
- Regularized Bradley-Terry (720 games, 2000-bootstrap): **mega_lucario ≈ dragapult
  ≫ mega_abomasnow > iono** (top three statistically tied ~0.5; iono weakest).
- external_evidence = 0.80 for **all four** (official sample benchmark tied to exact
  candidate); the reported Dragapult/Lucario "top tier" prior was not double-counted.
  Because it is identical across candidates, that 0.20 term is effectively **inert** —
  selection is driven by local strength, worst-matchup lower bound, latency/reliability,
  and (for teacher_score) the teaching-richness terms.
- `teacher_score` (0.70·competitive + 0.15·high-impact-coverage + 0.10·entropy +
  0.05·reproducibility): **dragapult 0.889 > mega_lucario 0.746 > abomasnow 0.367 > iono 0.313**.

## Primary / backup teacher
- **Primary teacher: `dragapult`** (Dragapult ex, spread_setup). BT-tied with
  lucario at the top but the richer teaching signal (8 high-impact contexts vs 6,
  higher action entropy) — matches the research prior.
- **Backup teacher: `mega_lucario`** (switch_midrange — different archetype).

## Exact frozen deck ID
`sha256:8055443275c86105b38198992c9556a642b833a47430aa97fb1a84c9ee4fdbab` (60 cards, 22 distinct).

## Submission A
- Archive `submission_A_teacher.tar.gz`, **500,422 bytes** (< limit), structure
  `main.py`/`deck.csv`/`cg/`, no secrets/training data.
- Validated from the **extracted archive**: 20 strategic smoke games vs the other
  teachers, **0 invalid / 0 non-terminal**, P99 0.33 ms.
- **Decision: SUBMIT.** Actual submission status: **not performed**
  (`PTCG_ALLOW_KAGGLE_SUBMIT` absent → upload safely skipped; exact command in
  `KAGGLE_SUBMIT_COMMAND.txt`; no credentials used).

## Dataset
- **240** completed games, **19,050** teacher decisions (≥8000; "targets_met").
- Both teacher seats (120/120); 5 required opponent types (backup, other official,
  another archetype, engineering control, mirror), 48 games each. Teacher losses
  kept (106). 0 invalid training records.
- Full schema-v2 observation snapshots + legal options + labels + lineage per record.

## Split sizes
Whole-game, stratified (opponent/seat/outcome), **test frozen**, no leakage:
- games: train 170 / validation 37 / test 33 (≈70/15/15).
- decisions: train 13,795 / validation 2,991 / test 2,264. (Test is ~14% of games
  but ~12% of decisions — the test games happened to run shorter; the split is by
  whole game, as required, so this is expected and not leakage.)

## c006 readiness
`c006_training_spec.md` + `c006_training_config.json` fully specify the student
(structured legal-option scorer, 1–5M params), features, masking, BC loss,
training schedule, CPU-inference/package targets, and evaluation gates. No model
trained in c005.

## Known limitations
- Competition rules text not machine-retrievable → conservative reuse posture;
  upload gated behind the (absent) flag.
- Strategic field is the four official reusable samples; public no-license repo
  excluded from submission and training.
- Author-reported Bellibolt Elo unverified; excluded from selection.
- Engine trajectories non-reproducible; analysis/splits reproducible from fixed captures.

## Recommended next contract
**c006** — train the distilled student on the frozen `dragapult` dataset per the
spec, evaluate against the frozen teacher/gauntlet, and decide Submission B.
