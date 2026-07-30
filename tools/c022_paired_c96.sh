#!/usr/bin/env bash
# c022 — the compute-matched K=1 control for the 200-game paired comparison.
#
# `paired_k8` runs fixed_per_world at 12 simulations per world, which is 96 simulations per
# decision. `paired_k1` runs 12. So the paired pair confounds K with an 8x search budget, and no
# part of its result is attributable to the ensemble until a K=1 arm at the SAME simulation count
# exists. This is that arm.
#
# It is worth more than a control. `fixed_per_world` 12/world at K=8 is arithmetically identical
# to `fixed_total` 96 at K=8 -- the crossing point identified in
# NOISE_FLOOR_ACCIDENTAL_REPLICATION.md -- so adding a K=1 arm at fixed_total 96 turns these into
# the compute-controlled `fixed_total` comparison at 200 games, the sample size at which the
# 32-game sweep resolved nothing.
#
# WHY THE GUARD IS 2366 s AND NOT 700 s. The guard is a backstop against games that do not
# terminate, and such games consume whatever guard they are given (D15). It must therefore be
# sized to the arm's real per-game duration. This arm does 96 simulations per decision -- the
# same as `paired_k8`, eight times `paired_k1` -- so it takes `paired_k8`'s guard, not
# `paired_k1`'s. Giving it 700 s would abandon ordinary games, and abandoned games leave the
# field score, so the surviving population would no longer be comparable.
set -u
cd "$(dirname "$0")/.."
set -m
trap 'trap - TERM INT EXIT; kill -- -$$ 2>/dev/null; exit' TERM INT EXIT

R="contracts/c022_mcgs_multideterminization_and_faithful_byterl_reproduction/results/mcgs"
NPROC=${NPROC:-10}

echo "=== $(date +%H:%M:%S)  paired_k1_c96  K=1 fixed_total sims=96 games=200 nproc=$NPROC"
python3 tools/c022_mcgs_run.py \
  --tag paired_k1_c96 --k 1 --protocol fixed_total --sims 96 \
  --games 200 --nproc "$NPROC" --seed 90210 \
  --graph-reuse 0 --match-clock 0 --wall-ceiling 300 \
  --decision-budget 50 --arm-timeout 21600 \
  --seconds-per-simulation 0.245 --k-overhead 0.34 \
  --game-timeout-base 2366 \
  --out "$R/paired" 2>&1 | grep -viE '^\[kaggle_environments|INFO:'

echo "=== $(date +%H:%M:%S)  analysing"
python3 tools/c022_mcgs_paired.py
echo "=== $(date +%H:%M:%S)  done"
