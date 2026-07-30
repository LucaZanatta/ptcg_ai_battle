#!/usr/bin/env bash
# c022 A4 — the M04 identity arm, then the two causal K sweeps, on an otherwise idle machine.
#
# Every arm is budgeted by SIMULATION COUNT, so worker contention makes an arm slower but never
# weaker; `budget_delivered` in each summary states whether the simulations were actually run.
#
# Two properties keep the sweeps causal, and both are equalities across K rather than defaults:
#
#   * a per-game DECISION BUDGET, identical for every K. A per-game wall clock would cut a K=8
#     fixed_per_world arm eight times earlier in decision space than K=1, and since abandoned
#     games are excluded from the field score, the K=8 survivors would be systematically shorter
#     games -- "K=8 is worse" would be indistinguishable from "K=8 dropped its long games".
#   * a wall-clock guard DERIVED from the arm's own per-decision cost, so it is a backstop rather
#     than the thing doing the cutting. The runner prints the derived value per arm.
#
# graph_reuse is OFF in every sweep arm so that K is the only difference. The reuse-enabled K=1
# identity arm runs first and is NOT part of either sweep.
set -u
cd "$(dirname "$0")/.."

GAMES=${GAMES:-60}
NPROC=${NPROC:-12}
SEED=${SEED:-90210}
FT_SIMS=${FT_SIMS:-256}      # fixed_total: TOTAL simulations per decision, constant across K
FPW_SIMS=${FPW_SIMS:-64}     # fixed_per_world: simulations PER WORLD, constant across K
DECISION_BUDGET=${DECISION_BUDGET:-260}
R="contracts/c022_mcgs_multideterminization_and_faithful_byterl_reproduction/results/mcgs"

run () {  # tag k protocol sims out reuse
  echo "=== $(date +%H:%M:%S)  $1  K=$2  $3  sims=$4  reuse=${6:-0}"
  python3 tools/c022_mcgs_run.py \
    --tag "$1" --k "$2" --protocol "$3" --sims "$4" \
    --games "$GAMES" --nproc "$NPROC" --seed "$SEED" \
    --graph-reuse "${6:-0}" --match-clock 0 --wall-ceiling 300 \
    --decision-budget "$DECISION_BUDGET" --arm-timeout 14400 \
    --out "$5" 2>&1 | grep -viE '^\[kaggle_environments|INFO:'
}

# ---- M04: does the c022 search reproduce the c021 search? Everything else is compared to a
# K=1 control, so this runs first. Budget matches the frozen control's MEASURED 176.6
# sims/decision; see PREREGISTERED_M04_IDENTITY.json for what is and is not asserted.
run "m04_k1_reuse" 1 fixed_total 177 "$R/k1_control" 1

for K in 1 2 4 8; do
  run "ft_k${K}" "$K" fixed_total "$FT_SIMS" "$R/fixed_total_simulations"
done

for K in 1 2 4 8; do
  run "fpw_k${K}" "$K" fixed_per_world "$FPW_SIMS" "$R/fixed_simulations_per_world"
done

echo "=== $(date +%H:%M:%S)  sweeps complete"
