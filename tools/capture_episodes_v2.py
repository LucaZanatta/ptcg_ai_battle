"""Schema-v2 cabt episode capture with full lineage and a canonical deck registry.

Runs three cohorts (default 10 games each = 30 total), varying runner/opponent
seeds per game, and writes a self-describing schema-v2 dataset:
  - episodes_v2.jsonl and episodes_v2.jsonl.gz (byte-identical record streams)
  - run_metadata.json (run/git/capture/environment/engine/agent/deck lineage)
  - deck_registry.json (canonical multiset deck records)

Engine RNG is NOT claimed controlled (see the seed block / engine_rng_note).

Usage (from repo root):
  .venv/bin/python tools/capture_episodes_v2.py --games-per-cohort 10 --base-seed 4242 \
      --output-dir contracts/c003_episode_lineage_and_semantic_replay/results/artifacts/validation_run \
      --require-clean
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.agents import random_baseline_definition, safe_agent_definition
from cg.episode_capture import derive_seed  # reuse the v1 deterministic seed derivation
from cg.episode_capture_v2 import GameRecorderV2, RunWriter, make_capturing_agent
from cg.episode_schema import (
    canonical_deck, collect_engine_info, collect_environment, collect_git_info,
    implementation_sha256, seed_metadata, sha256_bytes, source_files_lineage,
)
from cg.safe_policy import load_deck

COHORTS = ["safe_p0_vs_random_p1", "random_p0_vs_safe_p1", "safe_vs_safe"]
_IMPL_FILES = [
    "starter_kit/main.py", "starter_kit/safe_policy.py", "starter_kit/agents.py",
    "starter_kit/episode_schema.py", "starter_kit/episode_capture.py",
    "starter_kit/episode_capture_v2.py", "tools/capture_episodes_v2.py",
]


def build_plan(base_seed, games_per_cohort):
    plan, gi = [], 0
    for cohort in COHORTS:
        for k in range(games_per_cohort):
            safe_seat = "both" if cohort == "safe_vs_safe" else (0 if cohort.endswith("random_p1") else 1)
            plan.append({
                "game_index": gi, "game_id": f"{cohort}-{k:03d}", "cohort": cohort,
                "safe_seat": safe_seat,
                "runner_seed": derive_seed(base_seed, gi),
                "opponent_policy_seed": derive_seed(base_seed, 1_000_000 + gi),
            })
            gi += 1
    return plan


def build_run_metadata(repo_root, base_seed, command, deck_record, safe_lineage, random_lineage):
    git = collect_git_info(repo_root)
    env = collect_environment()
    engine = collect_engine_info(os.path.join(repo_root, "starter_kit", "libcg.so"), repo_root)
    created = datetime.now(timezone.utc).isoformat()
    run_id = "run_" + sha256_bytes(f"{git['commit']}|{created}|{base_seed}".encode("utf-8"))[:16]
    return {
        "schema_version": 2,
        "record_type": "run_metadata",
        "run_id": run_id,
        "created_at_utc": created,
        "git": git,
        "capture": {
            "implementation_sha256": implementation_sha256(_IMPL_FILES, repo_root),
            "implementation_source_files": source_files_lineage(_IMPL_FILES, repo_root),
            "command": command,
            "compression": "none+gzip",
        },
        "environment": env,
        "engine": engine,
        "agents": {"safe_agent": safe_lineage, "random_baseline": random_lineage},
        "base_seed": base_seed,
        "decks": {deck_record["deck_id"]: deck_record},
        "seed_policy_note": (
            "requested_engine_seed is passed to make('cabt', configuration={'seed':...}) "
            "but does NOT control the engine trajectory (engine_rng_controlled=false)."),
    }


def run(args):
    repo_root = _REPO_ROOT
    deck = load_deck()
    deck_path = os.path.join(repo_root, "starter_kit", "deck.csv")
    deck_record = canonical_deck(deck, source_path=deck_path, repo_root=repo_root)
    deck_id = deck_record["deck_id"]

    git = collect_git_info(repo_root)
    if args.require_clean and git.get("dirty"):
        print("REFUSING: worktree has uncommitted tracked changes (dirty). "
              "Commit source before capturing the acceptance dataset.", file=sys.stderr)
        return 2

    safe_def = safe_agent_definition(repo_root)
    # Random-baseline lineage template: identity/source are stable; the RNG seed
    # varies per game (see each game_start.seed.opponent_policy_seed).
    random_lineage = random_baseline_definition(repo_root, seed=args.base_seed, deck=deck).lineage()
    random_lineage["configuration"] = {
        "opponent_policy_seed": "per_game: see game_start.seed.opponent_policy_seed"}
    command = (f".venv/bin/python tools/capture_episodes_v2.py "
               f"--games-per-cohort {args.games_per_cohort} --base-seed {args.base_seed} "
               f"--output-dir {os.path.relpath(args.output_dir, repo_root)}")
    run_meta = build_run_metadata(repo_root, args.base_seed, command, deck_record,
                                  safe_def.lineage(), random_lineage)
    run_id = run_meta["run_id"]

    os.makedirs(args.output_dir, exist_ok=True)
    jsonl_path = os.path.join(args.output_dir, "episodes_v2.jsonl")
    gz_path = os.path.join(args.output_dir, "episodes_v2.jsonl.gz")
    with open(os.path.join(args.output_dir, "run_metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(run_meta, fh, indent=2)
    with open(os.path.join(args.output_dir, "deck_registry.json"), "w", encoding="utf-8") as fh:
        json.dump({"decks": [deck_record], "by_id": {deck_id: deck_record}}, fh, indent=2)

    from kaggle_environments import make
    plan = build_plan(args.base_seed, args.games_per_cohort)
    seq = [0]
    writer = RunWriter(jsonl_path, gz_path, flush_interval=args.flush_interval)
    writer.write(run_meta)  # run_metadata is the first record in the stream

    per_cohort = {c: {"games": 0, "completed": 0, "failed": 0} for c in COHORTS}
    total_completed = total_failed = total_invalid = 0
    try:
        for spec in plan:
            cohort = spec["cohort"]
            per_cohort[cohort]["games"] += 1
            opp_def = random_baseline_definition(repo_root, seed=spec["opponent_policy_seed"], deck=deck)
            if cohort == "safe_vs_safe":
                seat_def = {0: safe_def, 1: safe_def}
            elif cohort == "safe_p0_vs_random_p1":
                seat_def = {0: safe_def, 1: opp_def}
            else:
                seat_def = {0: opp_def, 1: safe_def}

            smeta = seed_metadata(runner_seed=spec["runner_seed"],
                                  opponent_policy_seed=spec["opponent_policy_seed"],
                                  requested_engine_seed=spec["runner_seed"])
            recorder = GameRecorderV2(
                writer, run_id=run_id, game_id=spec["game_id"], cohort=cohort,
                seat_agent_ids={0: seat_def[0].agent_id, 1: seat_def[1].agent_id},
                seat_deck_ids={0: deck_id, 1: deck_id}, seed_meta=smeta, seq=seq)
            recorder.write_game_start()
            players = [
                make_capturing_agent(recorder, seat_def[0], player_index=0, seat=0),
                make_capturing_agent(recorder, seat_def[1], player_index=1, seat=1),
            ]
            t0 = time.time()
            exception = None
            try:
                env = make("cabt", configuration={"decks": [deck, deck], "seed": spec["runner_seed"]})
                env.run(players)
            except Exception as exc:  # pragma: no cover
                exception = repr(exc)
            duration = time.time() - t0

            if exception is not None:
                per_cohort[cohort]["failed"] += 1
                total_failed += 1
                recorder.write_terminal(statuses=["ERROR", "ERROR"], rewards=[None, None],
                                        error=None, exception=exception, duration_s=duration)
                continue
            last = env.steps[-1]
            statuses = [last[0]["status"], last[1]["status"]]
            rewards = [last[0].get("reward"), last[1].get("reward")]
            try:
                err = env.steps[0][0].get("error")
            except Exception:
                err = None
            term = recorder.write_terminal(statuses=statuses, rewards=rewards, error=err,
                                           exception=None, duration_s=duration)
            total_invalid += sum(recorder.invalid_by_player.values())
            if statuses == ["DONE", "DONE"]:
                per_cohort[cohort]["completed"] += 1
                total_completed += 1
            else:
                per_cohort[cohort]["failed"] += 1
                total_failed += 1
    finally:
        writer.close()

    summary = {
        "run_id": run_id, "base_seed": args.base_seed,
        "games_total": len(plan), "games_completed": total_completed,
        "games_failed": total_failed, "invalid_selections": total_invalid,
        "records_written": writer.records_written,
        "cohorts": [{"name": c, **per_cohort[c]} for c in COHORTS],
        "jsonl": os.path.relpath(jsonl_path, repo_root),
        "gzip": os.path.relpath(gz_path, repo_root),
    }
    print(json.dumps(summary, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Schema-v2 episode capture")
    parser.add_argument("--games-per-cohort", type=int, default=10)
    parser.add_argument("--base-seed", type=int, default=4242)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--flush-interval", type=int, default=50)
    parser.add_argument("--require-clean", action="store_true")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
