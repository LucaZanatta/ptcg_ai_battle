# Clean Checkout & Run — c006

Reproduce c006 from a clean checkout of branch
`contract/c006_distilled_policy_baseline` (final HEAD
`08ebac88385444a69d0615b7976dea9dbddeb79a`). Run from repo root with `.venv/bin/python`
and `OMP_NUM_THREADS=1`.

## 1. Runtime assets (as in c002–c005) + Kaggle CLI
Git-tracked: all c001–c006 `starter_kit/*.py` and `tools/*.py`. Provide externally
(gitignored / pre-existing untracked): the starter-kit SDK
(`api/sim/game/utils/__init__/deck.csv`), `libcg.so`, the `cg`/`starter_kit/cg`
symlinks, `kaggle-environments==1.30.1`, `numpy`, `scipy`. The `kaggle` CLI reads the
public competition and (for the teacher-baseline refresh) the user's own submissions;
**no student upload is performed** (gate DO_NOT_SUBMIT).

Also required from **c005 results** (not committed; produced by c005 or re-acquired):
`teacher_sources/` (the 4 official teachers), `frozen_teacher/` (main.py, deck.csv, cg/),
and `teacher_dataset/{train,validation,test}.jsonl.gz` (+ splits.json / manifest).

## 2. Run (see `../COMMANDS_RUN.md` for the full ordered list)
Data → vocab → taxonomy/decoders → tests → registration → training → offline eval →
smoke → non-inferiority → gauntlet+analysis → package → decisions.

## 3. Reproducibility scope
- **Deterministic & bit-reproducible**: sequence-dataset rebuild, ambiguity analysis,
  card vocabulary, taxonomy/decoders, model training (seed + `OMP_NUM_THREADS=1` →
  byte-identical checkpoints, verified on S1 seed 101), offline evaluation, and all
  decision artifacts.
- **Not bit-reproducible (engine `std::random_device`)**: the gameplay *games*. The
  statistical conclusions (both students clearly inferior to the teacher; students beat
  control; MEMORY_NOT_JUSTIFIED) are stable across the large game samples and the fixed
  bootstrap seeds used for the intervals.

## 4. Results policy
The `results/` package (reports, dataset, checkpoints, game captures, diagnostic
archive, Kaggle evidence, decisions) is review evidence and is **not committed**; only
c006 source is on the branch. No file under `contracts/c005_.../` is modified.
