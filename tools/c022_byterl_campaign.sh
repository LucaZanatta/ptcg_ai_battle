#!/usr/bin/env bash
# c022 — the ByteRL campaign, in the order TRAINING_AND_EVALUATION §2 fixes.
#
#   1. conformance    every stage BR0->BR3 runs, with its intended delta, stable losses,
#                     verified recurrence, legal actions and legal decks
#   2. controlled     adjacent-stage comparison at an EQUAL preregistered smaller budget --
#                     "do not give one rung more samples and attribute the difference to the
#                     algorithmic change"
#   3. decisive       BR3_FIXED_DECK to the matched c021 budget, then BR3_END_TO_END
#
# Every run is budgeted in DECISIONS, not wall clock or iterations, because the matched budget
# is a decision count (results/byterl/budget/c021_matched_budget.json: 3,607,599).
#
# The recurrence check runs in STRICT mode throughout: TRAINING_AND_EVALUATION §4 says to stop
# immediately for a "recurrent replay mismatch", so a mismatch aborts the run rather than being
# logged and continued past.
set -u
cd "$(dirname "$0")/.."
set -m
trap 'trap - TERM INT EXIT; kill -- -$$ 2>/dev/null; exit' TERM INT EXIT

ACTORS=${ACTORS:-6}
QUEUE=${QUEUE:-48}
BATCH=${BATCH:-8}
UNROLL=${UNROLL:-32}
CONFORMANCE_DECISIONS=${CONFORMANCE_DECISIONS:-40000}
CONTROLLED_DECISIONS=${CONTROLLED_DECISIONS:-120000}
MATCHED_DECISIONS=${MATCHED_DECISIONS:-3607599}
EVAL_GAMES=${EVAL_GAMES:-128}
EVAL_NPROC=${EVAL_NPROC:-6}
SEED=${SEED:-4242}
BY="contracts/c022_mcgs_multideterminization_and_faithful_byterl_reproduction/results/byterl"

train () {  # tag stage learn_construction target_decisions [extra...]
  local tag=$1 stage=$2 lc=$3 dec=$4; shift 4
  echo "=== $(date +%H:%M:%S)  TRAIN $tag  stage=$stage  learn_construction=$lc  decisions=$dec"
  python3 tools/c022_byterl_train.py \
    --tag "$tag" --stage "$stage" --learn-construction "$lc" \
    --actors "$ACTORS" --queue-size "$QUEUE" --batch-unrolls "$BATCH" \
    --unroll-length "$UNROLL" --target-decisions "$dec" \
    --seed "$SEED" --recurrence-check-every 20 --recurrence-strict 1 \
    --log-every 50 --checkpoint-every 400 "$@" 2>&1 \
    | grep -viE '^\[kaggle_environments|INFO:'
}

evaluate () {  # tag checkpoint learn_construction
  local tag=$1 ck=$2 lc=$3
  echo "=== $(date +%H:%M:%S)  EVAL $tag"
  python3 tools/c022_byterl_eval.py \
    --tag "$tag" --checkpoint "$ck" --learn-construction "$lc" \
    --games "$EVAL_GAMES" --nproc "$EVAL_NPROC" --seed 777001 2>&1 \
    | grep -viE '^\[kaggle_environments|INFO:'
}

case "${1:-all}" in
  floor)
    # The floor EVERY learning claim is measured against: fresh random weights on the same
    # external panel. DECISION_RULES §3 requires a credible improvement over it, so it must be
    # measured on the panel rather than inferred from a training curve.
    echo "=== $(date +%H:%M:%S)  EVAL random floor (fixed deck)"
    python3 tools/c022_byterl_eval.py --tag floor_fixed_deck --learn-construction 0 \
      --games "$EVAL_GAMES" --nproc "$EVAL_NPROC" --seed 777001 2>&1 \
      | grep -viE '^\[kaggle_environments|INFO:'
    echo "=== $(date +%H:%M:%S)  EVAL random floor (end to end)"
    python3 tools/c022_byterl_eval.py --tag floor_end_to_end --learn-construction 1 \
      --games "$EVAL_GAMES" --nproc "$EVAL_NPROC" --seed 777001 2>&1 \
      | grep -viE '^\[kaggle_environments|INFO:'
    ;;

  conformance)
    for S in BR0 BR1 BR1_5 BR2 BR3; do
      train "conf_${S}" "$S" 1 "$CONFORMANCE_DECISIONS"
    done
    ;;

  controlled)
    # EQUAL budget for every rung -- this is the whole point of the controlled comparison.
    for S in BR0 BR1 BR1_5 BR2 BR3; do
      train "ctrl_${S}" "$S" 1 "$CONTROLLED_DECISIONS"
      evaluate "ctrl_${S}" "$BY/checkpoints/ctrl_${S}_final.pt" 1
    done
    ;;

  decisive_fixed)
    train "br3_fixed_deck" BR3 0 "$MATCHED_DECISIONS"
    evaluate "br3_fixed_deck" "$BY/checkpoints/br3_fixed_deck_final.pt" 0
    ;;

  decisive_e2e)
    train "br3_end_to_end" BR3 1 "$MATCHED_DECISIONS"
    evaluate "br3_end_to_end" "$BY/checkpoints/br3_end_to_end_final.pt" 1
    ;;

  all)
    bash "$0" floor
    bash "$0" conformance
    bash "$0" controlled
    bash "$0" decisive_fixed
    bash "$0" decisive_e2e
    ;;
esac

echo "=== $(date +%H:%M:%S)  byterl campaign step '${1:-all}' complete"
