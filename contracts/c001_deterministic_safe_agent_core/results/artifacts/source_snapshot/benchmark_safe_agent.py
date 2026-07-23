"""Reproducible cabt integration benchmark and context-coverage for the safe agent.

Runs three cohorts (default 100 games each = 300 total):
  1. safe agent (player 0) vs random legal baseline (player 1)
  2. random legal baseline (player 0) vs safe agent (player 1)
  3. safe agent vs safe agent

For every safe-agent call it measures *only* the agent call latency (not engine
time), validates the returned selection against the observation, and records the
encountered ``SelectContext`` and ``(minCount, maxCount)`` pairs. The random
opponent is deliberately isolated from the safe-agent implementation and is the
only source of randomness in this script.

Usage:
  .venv/bin/python tools/benchmark_safe_agent.py \
      --games-per-cohort 100 \
      --output contracts/c001_deterministic_safe_agent_core/results/artifacts/safe_agent_benchmark.json

Writes the JSON report to ``--output`` and a sibling
``runtime_context_coverage.json``. Engine randomness (deck shuffles, coin flips)
means individual game trajectories are not bit-reproducible, but the aggregate
legality/latency guarantees are.
"""

import argparse
import json
import math
import os
import random
import sys
from time import perf_counter

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.main import agent as safe_agent  # noqa: E402
from cg.safe_policy import MalformedSelection, load_deck, validate_selection  # noqa: E402
from cg.api import SelectContext  # noqa: E402

TERMINAL_OK = "DONE"


def _percentile(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    k = (len(sorted_vals) - 1) * (p / 100.0)
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return float(sorted_vals[int(k)])
    return float(sorted_vals[lo] * (hi - k) + sorted_vals[hi] * (k - lo))


def _context_name(value):
    try:
        return SelectContext(value).name
    except ValueError:
        return f"UNKNOWN_{value}"


class Instrument:
    """Collects safe-agent latency, context, count-pair and validity stats."""

    def __init__(self):
        self.latencies_ms = []
        self.calls = 0
        self.deck_calls = 0
        self.invalid = 0
        self.context_counts = {}          # context value -> count
        self.count_pairs = {}             # (minCount, maxCount) -> count
        self.invalid_details = []

    def wrap(self, cohort):
        def wrapped(obs):
            select = obs["select"]
            t0 = perf_counter()
            result = safe_agent(obs)               # measure ONLY the agent call
            dt_ms = (perf_counter() - t0) * 1000.0
            self.calls += 1
            self.latencies_ms.append(dt_ms)
            if select is None:
                self.deck_calls += 1
                return result                       # deck payload, not indices
            ctx = select.get("context")
            lo = select.get("minCount")
            hi = select.get("maxCount")
            n = len(select.get("option", []))
            self.context_counts[ctx] = self.context_counts.get(ctx, 0) + 1
            self.count_pairs[(lo, hi)] = self.count_pairs.get((lo, hi), 0) + 1
            try:
                validate_selection(result, n, lo, hi)
            except MalformedSelection as exc:
                self.invalid += 1
                if len(self.invalid_details) < 50:
                    self.invalid_details.append({
                        "cohort": cohort, "context": ctx, "minCount": lo,
                        "maxCount": hi, "num_options": n, "result": list(result),
                        "error": str(exc),
                    })
            return result
        return wrapped


def make_random_opponent(seed, deck):
    """A legal random opponent, isolated from the safe agent (only RNG here)."""
    rng = random.Random(seed)

    def opponent(obs):
        select = obs["select"]
        if select is None:
            return deck
        return rng.sample(range(len(select["option"])), select["maxCount"])

    return opponent


def run_cohort(name, make_players, n_games, deck, failures):
    from kaggle_environments import make

    completed = failed = 0
    p0_wins = p1_wins = draws = 0
    for g in range(n_games):
        players = make_players()
        try:
            env = make("cabt", configuration={"decks": [deck, deck]})
            env.run(players)
        except Exception as exc:  # pragma: no cover - defensive
            failed += 1
            failures.append({"cohort": name, "game": g, "exception": repr(exc)})
            continue
        last = env.steps[-1]
        s0, s1 = last[0]["status"], last[1]["status"]
        r0, r1 = last[0].get("reward"), last[1].get("reward")
        if s0 == TERMINAL_OK and s1 == TERMINAL_OK:
            completed += 1
            if r0 == r1:
                draws += 1
            elif (r0 or 0) > (r1 or 0):
                p0_wins += 1
            else:
                p1_wins += 1
        else:
            failed += 1
            err = None
            try:
                err = env.steps[0][0].get("error")
            except Exception:
                err = None
            failures.append({
                "cohort": name, "game": g, "status": [s0, s1],
                "reward": [r0, r1], "engine_error": err,
            })
    return {
        "name": name, "games": n_games, "games_completed": completed,
        "games_failed": failed, "p0_wins": p0_wins, "p1_wins": p1_wins, "draws": draws,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Safe-agent cabt benchmark")
    parser.add_argument("--games-per-cohort", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20240101)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    deck = load_deck()
    inst = Instrument()
    failures = []
    g = args.games_per_cohort

    cohorts = [
        run_cohort(
            "safe_p0_vs_random_p1",
            lambda: [inst.wrap("safe_p0_vs_random_p1"),
                     make_random_opponent(args.seed, deck)],
            g, deck, failures),
        run_cohort(
            "random_p0_vs_safe_p1",
            lambda: [make_random_opponent(args.seed + 1, deck),
                     inst.wrap("random_p0_vs_safe_p1")],
            g, deck, failures),
        run_cohort(
            "safe_vs_safe",
            lambda: [inst.wrap("safe_vs_safe"), inst.wrap("safe_vs_safe")],
            g, deck, failures),
    ]

    total_completed = sum(c["games_completed"] for c in cohorts)
    total_failed = sum(c["games_failed"] for c in cohorts)
    lat = sorted(inst.latencies_ms)
    latency = {
        "min": (lat[0] if lat else 0.0),
        "mean": (sum(lat) / len(lat) if lat else 0.0),
        "p50": _percentile(lat, 50),
        "p95": _percentile(lat, 95),
        "p99": _percentile(lat, 99),
        "max": (lat[-1] if lat else 0.0),
    }

    enum_total = len(list(SelectContext))
    observed_values = sorted(inst.context_counts)
    observed = [{"name": _context_name(v), "value": v, "count": inst.context_counts[v]}
                for v in observed_values]
    observed_names = {o["name"] for o in observed}
    not_observed = [{"name": c.name, "value": int(c)}
                    for c in SelectContext if c.name not in observed_names]

    report = {
        "games_required": 3 * g,
        "games_completed": total_completed,
        "games_failed": total_failed,
        "invalid_safe_selections": inst.invalid,
        "safe_agent_calls": inst.calls,
        "safe_agent_deck_calls": inst.deck_calls,
        "latency_ms": latency,
        "cohorts": cohorts,
        "context_counts": {_context_name(v): inst.context_counts[v] for v in observed_values},
        "count_pairs": [{"minCount": lo, "maxCount": hi, "count": n}
                        for (lo, hi), n in sorted(inst.count_pairs.items(),
                                                  key=lambda kv: (kv[0][0], kv[0][1]))],
        "runtime_contexts_observed": len(observed),
        "enum_contexts_total": enum_total,
        "seed": args.seed,
        "games_per_cohort": g,
        "invalid_selection_details": inst.invalid_details,
        "failures": failures,
    }

    coverage = {
        "description": "Runtime-observed SelectContext coverage during the "
        "benchmark games (distinct from enum-level selector coverage). Not every "
        "enum context is expected to occur in the sampled games.",
        "enum_contexts_total": enum_total,
        "runtime_contexts_observed": len(observed),
        "observed": observed,
        "not_observed": not_observed,
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as fh:
        json.dump(report, fh, indent=2)
    coverage_path = os.path.join(os.path.dirname(os.path.abspath(args.output)),
                                 "runtime_context_coverage.json")
    with open(coverage_path, "w") as fh:
        json.dump(coverage, fh, indent=2)

    # Human-readable summary (captured to the benchmark log).
    print(f"games: {total_completed}/{3 * g} completed, {total_failed} failed")
    print(f"invalid safe selections: {inst.invalid}")
    print(f"safe-agent calls: {inst.calls} (deck calls: {inst.deck_calls})")
    print("latency ms: " + ", ".join(f"{k}={v:.4f}" for k, v in latency.items()))
    print(f"runtime contexts observed: {len(observed)}/{enum_total}")
    for c in cohorts:
        print(f"  cohort {c['name']}: {c['games_completed']}/{c['games']} completed, "
              f"failed={c['games_failed']}, p0w={c['p0_wins']} p1w={c['p1_wins']} draws={c['draws']}")
    print("observed contexts: " + ", ".join(f"{o['name']}={o['count']}" for o in observed))
    print(f"output: {args.output}")
    print(f"coverage: {coverage_path}")

    ok = (total_completed == 3 * g and inst.invalid == 0 and latency["p99"] < 10.0)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
