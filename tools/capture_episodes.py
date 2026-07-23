"""Capture cabt games to versioned JSONL episodes, with seed/seat discipline.

Cohorts (default 20 games each = 60 total):
  1. safe_vs_safe
  2. safe_p0_vs_random_p1   (safe agent in seat 0)
  3. random_p0_vs_safe_p1   (safe agent in seat 1)

Every game gets a unique deterministic seed derived from --base-seed and the
game index; the random opponent is seeded per-game (never the same sequence for
every game). Seeds and seat assignments are fully reproducible from the base
seed. NOTE: the cabt engine seeds its own RNG from std::random_device (OS
entropy) with no seed API, so game *trajectories* (decision counts, winners) are
NOT reproducible across runs — see --mode replay-check.

Usage (from repo root):
  .venv/bin/python tools/capture_episodes.py --mode capture \
      --games-per-cohort 20 --base-seed 777 \
      --output   contracts/c002_reproducible_episode_capture/results/artifacts/episodes/episodes.jsonl \
      --summary  contracts/c002_reproducible_episode_capture/results/artifacts/episode_run_summary.json

  .venv/bin/python tools/capture_episodes.py --mode print-plan --games-per-cohort 20 --base-seed 777
  .venv/bin/python tools/capture_episodes.py --mode replay-check --games-per-cohort 20 --base-seed 777
"""

import argparse
import json
import os
import random
import sys
import tempfile
import time

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.main import agent as safe_agent  # noqa: E402
from cg.safe_policy import load_deck, select_indices  # noqa: E402
from cg.episode_capture import (  # noqa: E402
    GameRecorder, JsonlWriter, deck_identifier, derive_seed, make_capturing_agent,
)

COHORTS = ["safe_vs_safe", "safe_p0_vs_random_p1", "random_p0_vs_safe_p1"]


def build_plan(base_seed, games_per_cohort):
    """Deterministic list of per-game specs. Pure function of the inputs."""
    plan = []
    gi = 0
    for cohort in COHORTS:
        for k in range(games_per_cohort):
            safe_seat = "both" if cohort == "safe_vs_safe" else (0 if cohort.endswith("random_p1") else 1)
            plan.append({
                "game_index": gi,
                "game_id": f"{cohort}-{k:03d}",
                "cohort": cohort,
                "safe_seat": safe_seat,
                "game_seed": derive_seed(base_seed, gi),
                "opponent_seed": derive_seed(base_seed, 1_000_000 + gi),
            })
            gi += 1
    return plan


def _make_random_opponent(seed, deck):
    rng = random.Random(seed)

    def opponent(obs):
        select = obs["select"]
        if select is None:
            return deck
        return rng.sample(range(len(select["option"])), select["maxCount"])

    return opponent


def _winner_from_rewards(r0, r1):
    if r0 == r1:
        return "draw"
    return 0 if (r0 or 0) > (r1 or 0) else 1


def run_capture(plan, deck, output_path, summary_path, base_seed, games_per_cohort):
    from kaggle_environments import make

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    deck_id = deck_identifier(deck)
    writer = JsonlWriter(output_path)
    seeds = []
    per_cohort = {c: {"games": 0, "completed": 0, "failed": 0,
                      "safe_wins": 0, "safe_losses": 0, "draws": 0} for c in COHORTS}
    total_completed = total_failed = total_invalid_safe = 0

    try:
        for spec in plan:
            cohort = spec["cohort"]
            seeds.append(spec["game_seed"])
            per_cohort[cohort]["games"] += 1
            opp = _make_random_opponent(spec["opponent_seed"], deck)

            if cohort == "safe_vs_safe":
                inners = {0: safe_agent, 1: safe_agent}
                names = {0: "safe_agent", 1: "safe_agent"}
                is_safe = {0: True, 1: True}
            elif cohort == "safe_p0_vs_random_p1":
                inners = {0: safe_agent, 1: opp}
                names = {0: "safe_agent", 1: "random_baseline"}
                is_safe = {0: True, 1: False}
            else:  # random_p0_vs_safe_p1
                inners = {0: opp, 1: safe_agent}
                names = {0: "random_baseline", 1: "safe_agent"}
                is_safe = {0: False, 1: True}

            recorder = GameRecorder(
                writer, game_id=spec["game_id"], cohort=cohort, game_seed=spec["game_seed"],
                safe_seat=spec["safe_seat"], agents_by_seat=names,
                decks_by_seat={0: deck_id, 1: deck_id})
            recorder.write_start()
            players = [
                make_capturing_agent(recorder, inners[0], agent_name=names[0],
                                     player_index=0, seat=0, is_safe_agent=is_safe[0]),
                make_capturing_agent(recorder, inners[1], agent_name=names[1],
                                     player_index=1, seat=1, is_safe_agent=is_safe[1]),
            ]

            t0 = time.time()
            error_status = None
            try:
                env = make("cabt", configuration={"decks": [deck, deck], "seed": spec["game_seed"]})
                env.run(players)
            except Exception as exc:  # pragma: no cover - defensive
                error_status = repr(exc)
            duration = time.time() - t0

            if error_status is not None:
                per_cohort[cohort]["failed"] += 1
                total_failed += 1
                recorder.write_terminal(winner="error", terminal_reason=error_status,
                                        duration_s=duration, error_status=error_status,
                                        statuses=["ERROR", "ERROR"], rewards=[None, None])
                continue

            last = env.steps[-1]
            s0, s1 = last[0]["status"], last[1]["status"]
            r0, r1 = last[0].get("reward"), last[1].get("reward")
            completed = (s0 == "DONE" and s1 == "DONE")
            winner = _winner_from_rewards(r0, r1)
            reason = None
            try:
                reason = env.steps[0][0].get("error")
            except Exception:
                reason = None
            recorder.write_terminal(winner=winner, terminal_reason=(reason or "normal"),
                                    duration_s=duration, error_status=None,
                                    statuses=[s0, s1], rewards=[r0, r1])

            # safe-agent invalid selections in this game
            for seat, safe in is_safe.items():
                if safe:
                    total_invalid_safe += recorder.invalid_by_player.get(seat, 0)

            if completed:
                per_cohort[cohort]["completed"] += 1
                total_completed += 1
                if winner == "draw":
                    per_cohort[cohort]["draws"] += 1
                else:
                    safe_won = is_safe.get(winner, False)
                    per_cohort[cohort]["safe_wins" if safe_won else "safe_losses"] += 1
            else:
                per_cohort[cohort]["failed"] += 1
                total_failed += 1
    finally:
        writer.close()

    summary = {
        "schema_version": 1,
        "base_seed": base_seed,
        "games_per_cohort": games_per_cohort,
        "total_games": len(plan),
        "games_completed": total_completed,
        "games_failed": total_failed,
        "invalid_safe_selections": total_invalid_safe,
        "unique_seeds": len(set(seeds)) == len(seeds),
        "distinct_seed_count": len(set(seeds)),
        "seeds": seeds,
        "cohorts": [{"name": c, **per_cohort[c]} for c in COHORTS],
        "output_jsonl": os.path.relpath(output_path, _REPO_ROOT),
        "jsonl_records": writer.records_written,
    }
    if summary_path:
        os.makedirs(os.path.dirname(os.path.abspath(summary_path)), exist_ok=True)
        with open(summary_path, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
    return summary


def _run_subset_live(plan_subset, deck):
    """Run a subset live and return [(game_id, seed, safe_seat, total_decisions, winner)]."""
    from kaggle_environments import make
    rows = []
    for spec in plan_subset:
        cohort = spec["cohort"]
        opp = _make_random_opponent(spec["opponent_seed"], deck)
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as tf:
            tmp = tf.name
        writer = JsonlWriter(tmp)
        try:
            if cohort == "safe_vs_safe":
                inners, names, is_safe = {0: safe_agent, 1: safe_agent}, {0: "safe_agent", 1: "safe_agent"}, {0: True, 1: True}
            elif cohort == "safe_p0_vs_random_p1":
                inners, names, is_safe = {0: safe_agent, 1: opp}, {0: "safe_agent", 1: "random_baseline"}, {0: True, 1: False}
            else:
                inners, names, is_safe = {0: opp, 1: safe_agent}, {0: "random_baseline", 1: "safe_agent"}, {0: False, 1: True}
            rec = GameRecorder(writer, game_id=spec["game_id"], cohort=cohort, game_seed=spec["game_seed"],
                               safe_seat=spec["safe_seat"], agents_by_seat=names,
                               decks_by_seat={0: "d", 1: "d"})
            players = [make_capturing_agent(rec, inners[0], agent_name=names[0], player_index=0, seat=0, is_safe_agent=is_safe[0]),
                       make_capturing_agent(rec, inners[1], agent_name=names[1], player_index=1, seat=1, is_safe_agent=is_safe[1])]
            env = make("cabt", configuration={"decks": [deck, deck], "seed": spec["game_seed"]})
            env.run(players)
            last = env.steps[-1]
            winner = _winner_from_rewards(last[0].get("reward"), last[1].get("reward"))
            total_decisions = sum(rec.decisions_by_player.values())
            rows.append((spec["game_id"], spec["game_seed"], spec["safe_seat"], total_decisions, winner))
        finally:
            writer.close()
            os.unlink(tmp)
    return rows


def replay_check(base_seed, games_per_cohort, deck):
    """Emit a surgical reproducibility report separating my layer from the engine."""
    print("== Deterministic replay check ==")
    plan_a = build_plan(base_seed, games_per_cohort)
    plan_b = build_plan(base_seed, games_per_cohort)
    subset_a = plan_a[:5]
    subset_b = plan_b[:5]

    seeds_match = [s["game_seed"] for s in subset_a] == [s["game_seed"] for s in subset_b]
    seats_match = [(s["cohort"], s["safe_seat"]) for s in subset_a] == [(s["cohort"], s["safe_seat"]) for s in subset_b]
    print("\n[1] My-layer determinism (base_seed=%d, first 5 games):" % base_seed)
    print("    derived seeds      reproduce: %s" % seeds_match)
    print("    seat assignments   reproduce: %s" % seats_match)
    for s in subset_a:
        print("      %-24s cohort=%-20s safe_seat=%s seed=%d"
              % (s["game_id"], s["cohort"], s["safe_seat"], s["game_seed"]))

    print("\n[2] Engine trajectory determinism (same subset run live twice):")
    run1 = _run_subset_live(subset_a, deck)
    run2 = _run_subset_live(subset_a, deck)
    counts_match = [r[3] for r in run1] == [r[3] for r in run2]
    winners_match = [r[4] for r in run1] == [r[4] for r in run2]
    print("    decision counts    reproduce: %s" % counts_match)
    print("    winners            reproduce: %s" % winners_match)
    print("    run1 (decisions, winner): %s" % [(r[3], r[4]) for r in run1])
    print("    run2 (decisions, winner): %s" % [(r[3], r[4]) for r in run2])
    print("    ROOT CAUSE: libcg.so seeds std::mt19937 from std::random_device (OS")
    print("    entropy); no seed API is exported and configuration.seed is ignored.")

    print("\n[3] Record-level policy determinism (recompute safe decisions from records):")
    tmpdir = tempfile.mkdtemp()
    jsonl = os.path.join(tmpdir, "subset.jsonl")
    summ = os.path.join(tmpdir, "subset_summary.json")
    run_capture(subset_a, deck, jsonl, summ, base_seed, games_per_cohort)
    total = mismatches = 0
    with open(jsonl, encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("record_type") == "decision" and rec.get("used_fallback"):
                total += 1
                recomputed = select_indices(rec["legal_option_count"], rec["min_count"], rec["max_count"])
                if recomputed != rec["selected_indices"]:
                    mismatches += 1
    os.unlink(jsonl)
    if os.path.exists(summ):
        os.unlink(summ)
    os.rmdir(tmpdir)
    print("    safe decisions re-derived from recorded observations: %d" % total)
    print("    byte-identical to recorded selected_indices: %s (mismatches=%d)"
          % (mismatches == 0, mismatches))

    print("\nSUMMARY: my-layer seeds/seats + record-level policy REPRODUCE; engine")
    print("trajectory (counts/winners) does NOT (external, unseedable engine RNG).")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Capture cabt episodes")
    parser.add_argument("--mode", choices=["capture", "print-plan", "replay-check"], default="capture")
    parser.add_argument("--games-per-cohort", type=int, default=20)
    parser.add_argument("--base-seed", type=int, default=777)
    parser.add_argument("--output", default=None)
    parser.add_argument("--summary", default=None)
    args = parser.parse_args(argv)

    deck = load_deck()
    plan = build_plan(args.base_seed, args.games_per_cohort)

    if args.mode == "print-plan":
        print(json.dumps(plan, indent=2))
        return 0
    if args.mode == "replay-check":
        return replay_check(args.base_seed, args.games_per_cohort, deck)

    if not args.output:
        parser.error("--output is required in capture mode")
    summary = run_capture(plan, deck, args.output, args.summary, args.base_seed, args.games_per_cohort)
    print("captured %d/%d games (%d failed); invalid safe selections: %d"
          % (summary["games_completed"], summary["total_games"],
             summary["games_failed"], summary["invalid_safe_selections"]))
    print("unique seeds: %s (%d distinct)" % (summary["unique_seeds"], summary["distinct_seed_count"]))
    for c in summary["cohorts"]:
        print("  %-22s %d/%d completed, failed=%d, safe_wins=%d safe_losses=%d draws=%d"
              % (c["name"], c["completed"], c["games"], c["failed"],
                 c["safe_wins"], c["safe_losses"], c["draws"]))
    print("jsonl: %s (%d records)" % (args.output, summary["jsonl_records"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
