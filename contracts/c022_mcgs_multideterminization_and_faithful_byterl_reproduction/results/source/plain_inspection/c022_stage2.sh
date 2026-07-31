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

# Wait for ctrl_BR3, but fall back to ctrl_BR2 rather than probing a tag that does not exist.
# B06/B07 (versions, stored recurrent starts) work against any run; B08/B09/B10 need a run with
# the BOUNDED BLOCKING FIFO, and BR2 is the rung that INTRODUCES it -- so BR2 is a correct
# fallback for every probe here rather than a degraded one.
#
# The original wait was a fixed 100 minutes and would have expired at ~23:15, after which the
# probes would have run against a tag with no manifest and reported nothing useful. Under
# four-way contention the upper rungs run at ~15% of clean throughput, so a fixed wait sized
# from clean throughput is exactly the wrong shape.
WAIT_UNTIL=${STAGE2_WAIT_UNTIL:-$(date -d "today 23:55" +%s)}
echo "=== $(date +%H:%M:%S)  waiting for ctrl_BR3 (until $(date -d @"$WAIT_UNTIL" +%H:%M))"
while [ "$(date +%s)" -lt "$WAIT_UNTIL" ]; do
  [ -f "$BY/stages/ctrl_BR3_manifest.json" ] && break
  sleep 10
done

PROBE_TAG=ctrl_BR3
if [ -f "$BY/stages/ctrl_BR3_manifest.json" ]; then
  echo "=== $(date +%H:%M:%S)  ctrl_BR3 present"
elif [ -f "$BY/stages/ctrl_BR2_manifest.json" ]; then
  PROBE_TAG=ctrl_BR2
  echo "=== $(date +%H:%M:%S)  ctrl_BR3 absent; probing ctrl_BR2 (also a bounded-FIFO rung)"
else
  PROBE_TAG=""
  echo "=== $(date +%H:%M:%S)  neither upper rung present; queue probes report NO_DATA"
fi

# 1. B06/B07 (versions, stored recurrent starts) and B08/B09/B10 (queue, production/consumption)
#    against a rung that has the published b2 behaviour.
echo "=== $(date +%H:%M:%S)  probes against ${PROBE_TAG:-<none>}"
if [ -n "$PROBE_TAG" ]; then
  python3 tools/c022_byterl_probes.py --tag "$PROBE_TAG" 2>&1 \
    | grep -viE '^\[kaggle_environments|INFO:'
fi

# 2. The architecture, action-trace and construction analyses CONTRACT §6 names. Run against a
#    TRAINED checkpoint, because deck diversity from random weights measures the prior, not the
#    policy -- and DECISION_RULES §3 makes diversity the PASS/PARTIAL line for the E2E arm.
echo "=== $(date +%H:%M:%S)  ByteRL analyses"
CK="$BY/checkpoints/${PROBE_TAG:-ctrl_BR3}_final.pt"
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
