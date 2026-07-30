#!/usr/bin/env bash
# c022 — everything that may share the machine, launched together.
#
# The split is D18's, and it is a property of each job rather than a preference:
#
#   MAY SHARE                                        WHY
#   BR3 decisive arms                                bounded blocking FIFO: actors block when the
#                                                    queue is full, so the ratio is pinned near 1
#                                                    and lag is bounded by capacity, whatever the
#                                                    machine is doing
#   ctrl_BR2 / ctrl_BR3                              same
#   fid_* replay-fidelity runs                       replay deltas are arithmetic, not throughput
#   paired_k1_c96, stability, final panel            budgeted by SIMULATION COUNT: contention
#                                                    makes them slower, never weaker
#
#   MAY NOT SHARE (they run in c022_exclusive_block.sh, alone)
#   BR0 / BR1 / BR1.5                                unbounded queue: the reported quantity IS a
#                                                    throughput ratio
#   M11 unrestricted, M12 deploy                     searched to a wall clock: contention changes
#                                                    what the clock buys
#
# Order matters only in that the decisive arms are the long pole and start first. The fixed-deck
# arm is started before the end-to-end one because TRAINING_AND_EVALUATION §2 orders it first.
set -u
cd "$(dirname "$0")/.."
set -m
trap 'trap - TERM INT EXIT; kill -- -$$ 2>/dev/null; exit' TERM INT EXIT

S=${SCRATCH:-/tmp/claude-1000/-home-luca-kaggle-ptcg-ai-battle/3e28ed63-1041-4fe7-81fb-48ae9cc70346/scratchpad}
mkdir -p "$S"

# Stop the decisive arms at 23:50 so they write manifests and final checkpoints and get
# evaluated, instead of being killed with nothing to report. EXECUTION_BUDGET's cut procedure
# needs `produced_decisions` out of 3,607,599, and a killed process does not produce it.
export DECISIVE_DEADLINE_EPOCH=${DECISIVE_DEADLINE_EPOCH:-$(date -d "today 23:50" +%s)}
echo "=== $(date +%H:%M:%S)  launching the concurrent block"
echo "    decisive arms stop at $(date -d @$DECISIVE_DEADLINE_EPOCH +%H:%M) and self-report"

# 1. the decisive arms -- the long pole, and the only items whose scale a midnight cut touches
nohup bash tools/c022_byterl_campaign.sh decisive_fixed > "$S/br3_fixed.log" 2>&1 &
echo "    decisive_fixed  pid $!"
sleep 5
nohup bash tools/c022_byterl_campaign.sh decisive_e2e  > "$S/br3_e2e.log" 2>&1 &
echo "    decisive_e2e    pid $!"
sleep 5

# 2. the upper ladder -- bounded queue, so it costs the decisive arms wall clock and nothing else
nohup bash tools/c022_byterl_campaign.sh controlled_upper > "$S/ctrl_upper.log" 2>&1 &
echo "    controlled_upper pid $!"

# 3. the compute-matched MCGS control: the arm that decides whether the calibration gain is K
#    or is simply 8x the simulations
nohup bash tools/c022_paired_c96.sh > "$S/paired_c96.log" 2>&1 &
echo "    paired_k1_c96   pid $!"

echo "=== $(date +%H:%M:%S)  four jobs running; fidelity runs and the panel follow when the"
echo "                       ladder frees its actors"
wait
echo "=== $(date +%H:%M:%S)  concurrent block complete"
