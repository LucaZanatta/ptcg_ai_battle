#!/usr/bin/env bash
# c022 — the arms that must run on a QUIET machine, in one block so nothing overlaps them.
#
# Three separate reasons an arm lands here, and they are not the same reason:
#
#   M11 probe   searches to a WALL deadline, so contention changes the simulations 15 s buys.
#               That IS the measurement.
#   deploy arm  imposes a cumulative match clock and a per-decision cap, so contention changes
#               how many decisions get searched before the clock runs out.
#   (ByteRL pre-b2 rungs run in the campaign, not here -- see D18.)
#
# `results/hardware/contention_tests.json` measured 52 ms/simulation unloaded against 71 under a
# 6-actor campaign at nproc 14. A latency-bounded arm run alongside anything is measuring the
# machine.
set -u
cd "$(dirname "$0")/.."
set -m
trap 'trap - TERM INT EXIT; kill -- -$$ 2>/dev/null; exit' TERM INT EXIT

R="contracts/c022_mcgs_multideterminization_and_faithful_byterl_reproduction/results/mcgs"

case "${1:-probe}" in

  # ---------------------------------------------------------------- M11 cost probe
  # EXECUTION_BUDGET's table says item 6 costs ~1 h; its own cut-order row says ~7 h for the
  # same item. That 7x contradiction is the largest single input to the midnight projection, and
  # it is cheaper to measure than to argue about. One game, one worker, the source's schedule.
  probe)
    # TWO measurements, because the 1 h / 7 h contradiction is a serial-vs-parallel question and
    # a serial number answers only half of it. The full arm would run at nproc 6; if per-worker
    # throughput degrades there, the 20-game arm is measuring the machine rather than the source.
    #
    #   serial    2 games, nproc 1   -> per-game cost, and the reference sims/decision
    #   parallel  6 games, nproc 6   -> the SAME quantity under the load the real arm would run at
    #
    # The ratio of the two `sims_per_decision` figures is the parallel-efficiency factor, and it
    # is what multiplies out to an hour or to seven. Contention was already measured at 52 ms vs
    # 71 ms per simulation with no formal oversubscription, so it cannot be assumed to be 1.
    for spec in "serial 2 1" "parallel 6 6"; do
      set -- $spec
      echo "=== $(date +%H:%M:%S)  M11 probe/$1: $2 games, nproc $3, K=1, source_time"
      python3 tools/c022_mcgs_run.py \
        --tag "m11_probe_$1" --k 1 --protocol source_time --sims 0 \
        --games "$2" --nproc "$3" --seed 90210 \
        --graph-reuse 0 --match-clock 0 --wall-ceiling 60 \
        --decision-budget 260 --game-timeout 3600 --arm-timeout 3600 \
        --out "$R/unrestricted_reference" 2>&1 | grep -viE '^\[kaggle_environments|INFO:'
    done
    python3 - <<'PYEOF'
import json, os, statistics
d = ("contracts/c022_mcgs_multideterminization_and_faithful_byterl_reproduction/"
     "results/mcgs/unrestricted_reference")


def dist(tag):
    """The MEDIAN, not the mean. D23: the mean of a timed arm is two collapsed decisions
    wearing the whole arm's name -- the serial probe's mean was 82,540 and its median 610,
    with the top three decisions holding 99.2% of every simulation. An efficiency ratio built
    from two such means measured nothing, reported 0.009, and confidently concluded that nproc
    6 was unusable. On medians the same two arms agree to 3%."""
    rows = [json.loads(l) for l in open(os.path.join(d, tag + "_calibration.jsonl"))]
    sims = sorted(int(r["simulations"]) for r in rows if r.get("simulations"))
    n = len(sims)
    summ = json.load(open(os.path.join(d, tag + "_summary.json")))
    q = lambda f: sims[int(f * (n - 1))]
    return {"tag": tag, "n_decisions": n, "median": q(0.5), "p25": q(0.25), "p75": q(0.75),
            "p90": q(0.9), "max": sims[-1], "mean": round(statistics.fmean(sims)),
            "top3_share": round(sum(sims[-3:]) / max(1, sum(sims)), 4),
            "games": summ["games"], "completed": summ["completed"],
            "wall_clock_s": summ["wall_clock_s"], "nproc": summ["nproc"]}


try:
    s_ = dist("m11_probe_serial")
    p_ = dist("m11_probe_parallel")
except FileNotFoundError as e:
    raise SystemExit(f"probe summary missing: {e}")

eff = p_["median"] / max(1, s_["median"])
per_game_parallel = p_["wall_clock_s"] / max(1, p_["games"] / p_["nproc"]) / p_["nproc"]
print(json.dumps({
    "serial": s_, "parallel": p_,
    "parallel_efficiency_on_median": round(eff, 3),
    "parallel_efficiency_on_mean_DO_NOT_USE": round(
        p_["mean"] / max(1, s_["mean"]), 4),
    "why_median": ("the mean is dominated by decisions whose search collapsed onto an "
                   "already-decided line, where rollouts cost ~128us instead of ~29ms. Two of "
                   "279 decisions across both probes did this. See D23."),
    "serial_seconds_per_game": round(s_["wall_clock_s"] / max(1, s_["completed"]), 1),
    "projected_20_game_arm_at_nproc_6_seconds": round(
        p_["wall_clock_s"] * (20.0 / max(1, p_["games"])), 0),
    "verdict": ("nproc 6 is safe -- the schedule binds and the median is within 10%"
                if eff > 0.9 else
                "nproc 6 degrades the schedule; M11 must run at lower nproc or be blocked"),
}, indent=2))
PYEOF
    ;;

  # ---------------------------------------------------------------- M11 full arm
  unrestricted)
    G=${GAMES:-20}; N=${NPROC:-6}
    echo "=== $(date +%H:%M:%S)  M11 unrestricted: $G games, K=1, source_time, nproc $N"
    python3 tools/c022_mcgs_run.py \
      --tag m11_unrestricted --k 1 --protocol source_time --sims 0 \
      --games "$G" --nproc "$N" --seed 90210 \
      --graph-reuse 0 --match-clock 0 --wall-ceiling 60 \
      --decision-budget 260 --game-timeout 3600 --arm-timeout 28800 \
      --out "$R/unrestricted_reference" 2>&1 | grep -viE '^\[kaggle_environments|INFO:'
    ;;

  # ---------------------------------------------------------------- M12 Kaggle deploy arm
  # `FIDELITY_RULES §2` forbids judging SOURCE TRANSFER by this arm -- it is a deployment
  # measurement and a separately named branch. It is what the SUBMISSION decision rests on, and
  # nothing else, which is why it runs before the decisive training arms rather than after.
  # EVERY parameter here is read off the frozen C021_MCGS_K1_CONTROL config, not chosen:
  #
  #     "match_clock_seconds": 90.0        the Kaggle cumulative budget c021 played under
  #     "first_move_seconds": 0.9          the source's 15 s, scaled to fit it
  #     "continuing_move_seconds": 0.7     the source's 10 s, same scaling
  #
  # That is what makes this arm a DEPLOYMENT measurement rather than an invented one, and it is
  # why it uses `source_time`: c021's deploy agent was time-budgeted, so a count-budgeted arm
  # would not be the same question. `FIDELITY_RULES §2` forbids judging source transfer by it.
  #
  # Both K are run. The paired arms do not license K=8 as the deploy configuration -- the
  # compute-matched control has not landed -- and under a 90 s clock the K comparison is a
  # different question anyway: K=8 divides the same clock eight ways.
  deploy)
    G=${GAMES:-40}; N=${NPROC:-6}
    for KK in ${KS:-1 8}; do
      echo "=== $(date +%H:%M:%S)  M12 deploy K=$KK: $G games, nproc $N, clock 90s, 0.9/0.7"
      python3 tools/c022_mcgs_run.py \
        --tag "deploy_k${KK}" --branch MCGS_2019_PTCG_MULTI_DET_KAGGLE_DEPLOY \
        --k "$KK" --protocol source_time --sims 0 \
        --games "$G" --nproc "$N" --seed 90210 \
        --graph-reuse 0 --match-clock 90 \
        --first-move-seconds 0.9 --continuing-move-seconds 0.7 \
        --wall-ceiling 10 --decision-budget 260 \
        --game-timeout 900 --arm-timeout 7200 \
        --out "$R/kaggle_deploy" 2>&1 | grep -viE '^\[kaggle_environments|INFO:'
    done
    ;;
esac
echo "=== $(date +%H:%M:%S)  done"
