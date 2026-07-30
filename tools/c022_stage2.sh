#!/usr/bin/env bash
# c022 — the analyses that need a completed training run, plus the panel.
#
# Waits for the controlled ladder's upper half to finish, because B08-B10 (queue) and B06-B07
# (recurrence) read a specific run's queue log and recurrent traces, and `ctrl_BR3` is the run
# they should read: it is the only rung with both the bounded blocking FIFO and the b3 objective.
#
# Everything here is decision-budgeted, count-budgeted or offline, so it may share the machine
# with the decisive arms (D18). Nothing here is latency-bounded.
set -u
cd "$(dirname "$0")/.."
set -m
trap 'trap - TERM INT EXIT; kill -- -$$ 2>/dev/null; exit' TERM INT EXIT

BY="contracts/c022_mcgs_multideterminization_and_faithful_byterl_reproduction/results/byterl"

echo "=== $(date +%H:%M:%S)  waiting for ctrl_BR3 to land"
for i in $(seq 1 1200); do
  [ -f "$BY/stages/ctrl_BR3_manifest.json" ] && break
  sleep 5
done
[ -f "$BY/stages/ctrl_BR3_manifest.json" ] \
  && echo "=== $(date +%H:%M:%S)  ctrl_BR3 present" \
  || echo "=== $(date +%H:%M:%S)  TIMED OUT; running what can be run"

# 1. B06/B07 (versions, stored recurrent starts) and B08/B09/B10 (queue, production/consumption)
#    against the rung that has the published b2 and b3 behaviour.
echo "=== $(date +%H:%M:%S)  probes against ctrl_BR3"
python3 tools/c022_byterl_probes.py --tag ctrl_BR3 2>&1 \
  | grep -viE '^\[kaggle_environments|INFO:'

# 2. The architecture, action-trace and construction analyses CONTRACT §6 names. Run against a
#    TRAINED checkpoint, because deck diversity from random weights measures the prior, not the
#    policy -- and DECISION_RULES §3 makes diversity the PASS/PARTIAL line for the E2E arm.
echo "=== $(date +%H:%M:%S)  ByteRL analyses"
CK="$BY/checkpoints/ctrl_BR3_final.pt"
if [ -f "$CK" ]; then
  python3 tools/c022_byterl_analysis.py --checkpoint "$CK" 2>&1 \
    | grep -viE '^\[kaggle_environments|INFO:'
else
  python3 tools/c022_byterl_analysis.py 2>&1 | grep -viE '^\[kaggle_environments|INFO:'
fi

# 3. B06 at high coverage, per stage. D20: the rungs verify ~10% of their opportunities because
#    a pre-b2 rung's lag exceeds any blob history that fits alongside two decisive arms.
echo "=== $(date +%H:%M:%S)  dedicated fidelity runs"
FID_ACTORS=3 bash tools/c022_byterl_campaign.sh fidelity 2>&1 \
  | grep -viE '^\[kaggle_environments|INFO:'

# 4. The rung ladder, now that all five exist from one commit.
echo "=== $(date +%H:%M:%S)  rung ladder analysis"
python3 tools/c022_byterl_ladder.py

# 5. The final panel: candidates and the frozen bar over ONE panel. Count-budgeted, so it shares.
echo "=== $(date +%H:%M:%S)  final panel"
python3 tools/c022_final_panel.py --games "${PANEL_GAMES:-60}" --nproc "${PANEL_NPROC:-6}" 2>&1 \
  | grep -viE '^\[kaggle_environments|INFO:'

# 6. Re-run every validator and recompute the statuses from whatever now exists.
echo "=== $(date +%H:%M:%S)  validators and statuses"
python3 tools/c022_byterl_fixtures.py
python3 tools/c022_mcgs_paired.py
python3 tools/c022_validate.py
python3 tools/c022_status.py
echo "=== $(date +%H:%M:%S)  stage 2 complete"
