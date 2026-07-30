#!/usr/bin/env bash
# c022 A4 — the two causal K sweeps, run back to back on an otherwise idle machine.
#
# Both protocols are budgeted by SIMULATION COUNT, so worker contention makes an arm slower but
# never weaker. That is the whole reason c021's latency-bounded arms had to run alone and these
# do not: c021's own M16 measured sims_per_decision collapsing to 8% of its single-worker value
# at 24 workers, invisible in the field score. Here `budget_delivered` in each summary states
# whether the arm actually got its simulations.
#
# Arms differ in exactly one thing at a time. graph_reuse is OFF everywhere in the sweep (see
# results/mcgs/PREREGISTERED_AGGREGATION.json); the reuse-enabled K=1 identity arm for probe M04
# is run separately and is not part of either sweep.
set -u
cd "$(dirname "$0")/.."

GAMES=${GAMES:-60}
NPROC=${NPROC:-12}
SEED=${SEED:-90210}
FT_SIMS=${FT_SIMS:-256}      # fixed_total: TOTAL simulations per decision, constant across K
FPW_SIMS=${FPW_SIMS:-64}     # fixed_per_world: simulations PER WORLD, constant across K
OUT_FT="contracts/c022_mcgs_multideterminization_and_faithful_byterl_reproduction/results/mcgs/fixed_total_simulations"
OUT_FPW="contracts/c022_mcgs_multideterminization_and_faithful_byterl_reproduction/results/mcgs/fixed_simulations_per_world"

run () {  # tag k protocol sims out
  echo "=== $(date +%H:%M:%S)  $1  K=$2  $3  sims=$4"
  python3 tools/c022_mcgs_run.py \
    --tag "$1" --k "$2" --protocol "$3" --sims "$4" \
    --games "$GAMES" --nproc "$NPROC" --seed "$SEED" \
    --graph-reuse 0 --match-clock 0 --wall-ceiling 300 \
    --game-timeout 1200 --arm-timeout 10800 \
    --out "$5" 2>&1 | grep -viE '^\[kaggle_environments|INFO:'
}

for K in 1 2 4 8; do
  run "ft_k${K}" "$K" fixed_total "$FT_SIMS" "$OUT_FT"
done

for K in 1 2 4 8; do
  run "fpw_k${K}" "$K" fixed_per_world "$FPW_SIMS" "$OUT_FPW"
done

echo "=== $(date +%H:%M:%S)  sweeps complete"
