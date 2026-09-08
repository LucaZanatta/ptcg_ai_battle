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

# Kill the whole process group on exit, not just this script. Twice now, `pkill -f c022_sweep.sh`
# killed the driver while the arm it had already spawned survived as an orphan, ran to
# completion, and wrote a full set of result files into the live results directory using
# PRE-FIX code -- once corrupting the relaunched sweep's log through its inherited file
# descriptor. Both orphaned arms had to be quarantined in results/failures/superseded/.
#
# `set -m` puts this script in its own process group so the trap can take the children with it.
set -m
trap 'trap - TERM INT EXIT; kill -- -$$ 2>/dev/null; exit' TERM INT EXIT

GAMES=${GAMES:-32}
NPROC=${NPROC:-12}
SEED=${SEED:-90210}
FT_SIMS=${FT_SIMS:-96}       # fixed_total: TOTAL simulations per decision, constant across K
FPW_SIMS=${FPW_SIMS:-12}     # fixed_per_world: simulations PER WORLD, constant across K
# An arm's WALL TIME is set by its LONGEST game, not its average: once games outnumber workers,
# the arm cannot finish until its slowest game does. ft_k1 at a 3760 s guard took 3912 s while
# its games averaged 33 searched decisions -- three games ran to the guard and 29 waited on them.
#
# So the guard sets arm duration, and lowering the guard raises abandonment. The DECISION BUDGET
# lowers both, and it is the only one of the two applied identically across K, so shortening
# arms this way cannot reintroduce the D08/D14 confound.
DECISION_BUDGET=${DECISION_BUDGET:-50}
# Measured UNDER LOAD (results/hardware/contention_tests.json): 71 ms per simulation per worker
# at nproc 14 alongside a 6-actor ByteRL campaign, against 52 ms unloaded. The per-game wall
# guard is derived from this, because deriving it from the unloaded figure is what doubled
# abandonment -- and abandoned games leave the field score, so the surviving population changes.
# Derived from the games that actually ran to the guard: 120 decisions x 128 simulations in
# 3760 s. That is ~2x the figure taken from whole-arm wall clock, which is inflated by the
# straggler tail -- and taking it from whole-arm wall clock was the error in the previous
# calibration.
SEC_PER_SIM=${SEC_PER_SIM:-0.245}
K_OVERHEAD=${K_OVERHEAD:-0.34}
# Per-game guard at K=1, from MEASURED completed-game duration rather than search cost. ft_k1
# completed 29 games at a mean of 148.7 s and a maximum of 275 s, while its three abandoned
# games each ran to exactly 1881.9 s -- the guard, to a tenth of a second. Those are not slow
# games, they are games that do not terminate, and they consume whatever guard they are given.
#
# So abandonment measures the STALEMATE RATE, a property of the game rather than of K, and the
# guard IS the arm's wall time because an arm cannot finish until its stalemates time out.
# 700 s is 2.5x the slowest completed game and cuts nothing real.
GAME_TIMEOUT_BASE=${GAME_TIMEOUT_BASE:-700}
R="contracts/c022_mcgs_multideterminization_and_faithful_byterl_reproduction/results/mcgs"

run () {  # tag k protocol sims out reuse
  echo "=== $(date +%H:%M:%S)  $1  K=$2  $3  sims=$4  reuse=${6:-0}"
  python3 tools/c022_mcgs_run.py \
    --tag "$1" --k "$2" --protocol "$3" --sims "$4" \
    --games "$GAMES" --nproc "$NPROC" --seed "$SEED" \
    --graph-reuse "${6:-0}" --match-clock 0 --wall-ceiling 300 \
    --decision-budget "$DECISION_BUDGET" --arm-timeout 21600 \
    --seconds-per-simulation "$SEC_PER_SIM" --k-overhead "$K_OVERHEAD" \
    --game-timeout-base "$GAME_TIMEOUT_BASE" \
    --out "$5" 2>&1 | grep -viE '^\[kaggle_environments|INFO:'
}

# ---- M04: does the c022 search reproduce the c021 search? Everything else is compared to a
# K=1 control, so this runs first. Budget matches the frozen control's MEASURED 176.6
# sims/decision; see PREREGISTERED_M04_IDENTITY.json for what is and is not asserted.
# RUN_M04=0 skips it: the arm has already run and passed 9/9, and re-running it costs 30
# minutes of the sweep's exclusive window for a probe whose result is committed.
if [ "${RUN_M04:-1}" = "1" ]; then
  run "m04_k1_reuse" 1 fixed_total 177 "$R/k1_control" 1
else
  echo "=== $(date +%H:%M:%S)  m04_k1_reuse SKIPPED (RUN_M04=0); result already committed"
fi

for K in 1 2 4 8; do
  run "ft_k${K}" "$K" fixed_total "$FT_SIMS" "$R/fixed_total_simulations"
done

for K in 1 2 4 8; do
  run "fpw_k${K}" "$K" fixed_per_world "$FPW_SIMS" "$R/fixed_simulations_per_world"
done

echo "=== $(date +%H:%M:%S)  sweeps complete"
