"""c005 Phase E: generate the strategic-teacher distillation dataset.

Runs the frozen primary teacher (fresh instance per game) against the required
opponents (backup, the other of Dragapult/Lucario, another strategic archetype,
an engineering control, and the teacher mirror), both seats. Captures every
teacher decision with a mutation-safe FULL observation snapshot + legal options +
selected action + lineage + per-decision latency, stamped with the game's terminal
outcome. Filters quality, splits by whole game (70/15/15, stratified, test frozen),
and writes compressed model-ready JSONL with deterministic example IDs + reports.

Usage: .venv/bin/python tools/generate_teacher_dataset.py --primary <id> --backup <id> \
    --sources <src> --out-dir <dataset_dir> --base-seed 424242
"""

import argparse
import gzip
import hashlib
import json
import os
import random
import sys
from datetime import datetime, timezone

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.api import SelectContext
from cg.candidates import make_agent as make_control
from cg.episode_capture import context_name, normalize_observation
from cg.safe_policy import MalformedSelection, validate_selection
from cg.teachers import TEACHERS, canonical_deck_record, make_fresh

_HIGH = {"MAIN", "ATTACK", "SWITCH", "EVOLVE", "TO_ACTIVE", "TO_BENCH", "TO_HAND", "DISCARD", "ACTIVATE"}
_MIN_GAMES, _TARGET_DECISIONS, _MAX_GAMES, _MIN_PER_OPP = 240, 8000, 400, 30
_load = [0]


def _teacher(cid, sources):
    return make_fresh(cid, sources)


def _control():
    _load[0] += 1
    return make_control("det_starter", _REPO_ROOT)  # engineering control (c004)


def _example_id(teacher_id, game_id, didx):
    return hashlib.sha256(f"{teacher_id}|{game_id}|{didx}".encode()).hexdigest()[:24]


def capture_game(make, sources, primary, opponent_id, teacher_seat, game_id):
    """Play one game; return (game_record, list_of_teacher_decision_records)."""
    teacher = _teacher(primary, sources)
    if opponent_id == "__control__":
        opp = _control()
    elif opponent_id == primary:  # mirror -> fresh separate instance
        opp = _teacher(primary, sources)
    else:
        opp = _teacher(opponent_id, sources)
    decisions = []
    invalid = [0]
    didx = [0]

    def wrap(agent, is_teacher, seat):
        def w(obs):
            sel = obs["select"]
            if is_teacher:
                snap = normalize_observation(obs)[0]  # deep copy BEFORE the call
            import time
            t0 = time.perf_counter_ns()
            res = agent(obs)
            dt = time.perf_counter_ns() - t0
            if is_teacher and sel is not None:
                n = len(sel.get("option", []))
                ok = "valid"
                try:
                    validate_selection(list(res), n, sel.get("minCount"), sel.get("maxCount"))
                except MalformedSelection as e:
                    ok = f"invalid: {e}"; invalid[0] += 1
                cv = sel.get("context")
                decisions.append({
                    "decision_index": didx[0], "seat": seat, "select_context": context_name(cv),
                    "select_context_value": cv, "observation": snap, "legal_options": sel.get("option"),
                    "legal_option_count": n, "min_count": sel.get("minCount"), "max_count": sel.get("maxCount"),
                    "teacher_action_indices": list(res), "decision_source": "rule",
                    "decision_latency_ms": round(dt / 1e6, 6), "validation_status": ok,
                    "importance_class": "high" if context_name(cv) in _HIGH else "normal"})
                didx[0] += 1
            return res
        return w

    players = ([wrap(teacher, True, 0), wrap(opp, False, 1)] if teacher_seat == 0
               else [wrap(opp, False, 0), wrap(teacher, True, 1)])
    exc = None; env = None
    try:
        env = make("cabt"); env.run(players)
    except Exception as e:  # pragma: no cover
        exc = repr(e)
    if env is None:
        return ({"game_id": game_id, "opponent": opponent_id, "teacher_seat": teacher_seat,
                 "terminal_present": False, "error": exc, "invalid_teacher_actions": invalid[0],
                 "outcome": None, "decision_count": len(decisions)}, decisions)
    last = env.steps[-1]
    st = [last[0]["status"], last[1]["status"]]
    rw = [last[0].get("reward"), last[1].get("reward")]
    terminal = st == ["DONE", "DONE"]
    tr = rw[teacher_seat]
    outcome = None if not terminal else (0.5 if rw[0] == rw[1] else (1.0 if tr == 1 else 0.0))
    return ({"game_id": game_id, "opponent": opponent_id, "teacher_seat": teacher_seat,
             "terminal_present": terminal, "statuses": st, "error": None,
             "invalid_teacher_actions": invalid[0], "outcome": outcome,
             "decision_count": len(decisions), "game_length_steps": len(env.steps)}, decisions)


def run(args):
    from kaggle_environments import make
    os.makedirs(args.out_dir, exist_ok=True)
    primary, backup = args.primary, args.backup
    others = [c for c in TEACHERS if c not in (primary, backup)]
    third = next((c for c in others if c in ("dragapult", "mega_lucario")), others[0]) if others else backup
    fourth = next((c for c in others if c != third), (others[0] if others else backup))
    opponents = [backup, third, fourth, "__control__", primary]  # backup, other official, 3rd archetype, control, mirror
    opponents = list(dict.fromkeys(opponents))  # dedupe preserve order
    deck_id = canonical_deck_record(primary, args.sources, _REPO_ROOT)["deck_id"]

    # capture: round-robin over opponents+seats until minimums met
    all_games = []; all_decisions = {}; games = 0; teacher_decisions = 0
    rng = random.Random(args.base_seed)
    per_opp = {o: 0 for o in opponents}
    log = []
    schedule = []
    # ensure >= _MIN_PER_OPP per opponent, both seats; then round-robin to reach targets
    for o in opponents:
        for seat in (0, 1):
            for _ in range((_MIN_PER_OPP + 1) // 2):
                schedule.append((o, seat))
    ri = 0
    while True:
        if ri < len(schedule):
            opp, seat = schedule[ri]; ri += 1
        else:
            opp = opponents[games % len(opponents)]; seat = games % 2
        gid = f"{primary}-vs-{opp}-s{seat}-{games:05d}"
        grec, decs = capture_game(make, args.sources, primary, opp, seat, gid)
        all_games.append(grec); all_decisions[gid] = decs
        games += 1; per_opp[opp] += 1
        if grec["terminal_present"] and grec["invalid_teacher_actions"] == 0:
            teacher_decisions += grec["decision_count"]
        if games % 40 == 0:
            log.append(f"{games} games, {teacher_decisions} valid teacher decisions")
        enough = (games >= _MIN_GAMES and teacher_decisions >= _TARGET_DECISIONS
                  and all(per_opp[o] >= _MIN_PER_OPP for o in opponents))
        if enough or games >= _MAX_GAMES:
            break
    stopping = ("targets_met" if teacher_decisions >= _TARGET_DECISIONS and games >= _MIN_GAMES
                else "max_400_games_cap")

    # quality: valid vs excluded
    valid = [g for g in all_games if g["terminal_present"] and g["invalid_teacher_actions"] == 0]
    excluded = [g for g in all_games if g not in valid]

    # whole-game stratified split (70/15/15), test frozen
    srng = random.Random(args.base_seed ^ 0xABCDEF)
    strata = {}
    for g in valid:
        key = (g["opponent"], g["teacher_seat"], "win" if g["outcome"] == 1.0 else ("loss" if g["outcome"] == 0.0 else "draw"))
        strata.setdefault(key, []).append(g["game_id"])
    split_of = {}
    for key, gids in strata.items():
        srng.shuffle(gids)
        n = len(gids); ntr = int(round(0.70 * n)); nval = int(round(0.15 * n))
        for i, gid in enumerate(gids):
            split_of[gid] = "train" if i < ntr else ("validation" if i < ntr + nval else "test")

    # write model-ready records per split
    counts = {"train": 0, "validation": 0, "test": 0}
    game_counts = {"train": 0, "validation": 0, "test": 0}
    ctx_counts = {}
    fhs = {s: gzip.open(os.path.join(args.out_dir, f"{s}.jsonl.gz"), "wt", encoding="utf-8")
           for s in ("train", "validation", "test")}
    seen_ids = set(); dup = 0
    for g in valid:
        gid = g["game_id"]; split = split_of[gid]; game_counts[split] += 1
        for d in all_decisions[gid]:
            eid = _example_id(primary, gid, d["decision_index"])
            if eid in seen_ids:
                dup += 1
            seen_ids.add(eid)
            rec = {"example_id": eid, "game_id": gid, "split": split, "teacher_id": primary,
                   "teacher_deck_id": deck_id, "opponent_id": g["opponent"], "seat": d["seat"],
                   "select_context": d["select_context"], "observation": d["observation"],
                   "legal_options": d["legal_options"], "legal_option_count": d["legal_option_count"],
                   "min_count": d["min_count"], "max_count": d["max_count"],
                   "teacher_action_indices": d["teacher_action_indices"], "decision_source": d["decision_source"],
                   "terminal_outcome": g["outcome"], "decision_latency_ms": d["decision_latency_ms"],
                   "importance_class": d["importance_class"]}
            fhs[split].write(json.dumps(rec) + "\n")
            counts[split] += 1
            ctx_counts[d["select_context"]] = ctx_counts.get(d["select_context"], 0) + 1
    for fh in fhs.values():
        fh.close()

    # reports
    total_valid_decisions = sum(counts.values())
    splits = {"seed": args.base_seed, "split_by": "whole_game", "target_ratio": [0.70, 0.15, 0.15],
              "stratify_by": ["opponent", "teacher_seat", "outcome"],
              "games": game_counts, "decisions": counts, "test_frozen": True,
              "no_game_in_multiple_splits": True}
    json.dump(splits, open(os.path.join(args.out_dir, "splits.json"), "w"), indent=2)
    # leakage check
    leak = _leak_check(args.out_dir)
    split_report = {"strata": {str(k): len(v) for k, v in strata.items()}, **splits,
                    "leakage_detected": leak, "high_impact_contexts_present": sorted(set(ctx_counts) & _HIGH)}
    json.dump(split_report, open(os.path.join(args.out_dir, "split_report.json"), "w"), indent=2)

    quality = {"total_games": games, "valid_games": len(valid), "excluded_games": len(excluded),
               "excluded_reasons": {"non_terminal": sum(1 for g in excluded if not g["terminal_present"]),
                                    "invalid_teacher_action": sum(1 for g in excluded if g["invalid_teacher_actions"])},
               "teacher_decisions_valid": total_valid_decisions, "duplicate_example_ids": dup,
               "teacher_losses_kept": sum(1 for g in valid if g["outcome"] == 0.0),
               "outcome_balance": {"win": sum(1 for g in valid if g["outcome"] == 1.0),
                                   "loss": sum(1 for g in valid if g["outcome"] == 0.0),
                                   "draw": sum(1 for g in valid if g["outcome"] == 0.5)},
               "per_opponent_games": per_opp, "both_seats": {"seat0": sum(1 for g in valid if g["teacher_seat"] == 0),
                                                             "seat1": sum(1 for g in valid if g["teacher_seat"] == 1)},
               "stopping_reason": stopping}
    json.dump(quality, open(os.path.join(args.out_dir, "quality_report.json"), "w"), indent=2)
    with open(os.path.join(args.out_dir, "context_report.csv"), "w") as fh:
        fh.write("context,count,high_impact\n")
        for k, v in sorted(ctx_counts.items(), key=lambda x: -x[1]):
            fh.write(f"{k},{v},{k in _HIGH}\n")
    json.dump(_schema(), open(os.path.join(args.out_dir, "schema.json"), "w"), indent=2)

    manifest = {"teacher_id": primary, "teacher_deck_id": deck_id, "backup": backup,
                "opponents": opponents, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "total_games": games, "valid_games": len(valid),
                "teacher_decisions": total_valid_decisions, "stopping_reason": stopping,
                "splits": {"train": counts["train"], "validation": counts["validation"], "test": counts["test"]},
                "split_games": game_counts, "min_games": _MIN_GAMES, "target_decisions": _TARGET_DECISIONS,
                "high_impact_contexts": sorted(set(ctx_counts) & _HIGH)}
    json.dump(manifest, open(os.path.join(os.path.dirname(args.out_dir), "teacher_dataset_manifest.json"), "w"), indent=2)
    print(json.dumps({"games": games, "valid_games": len(valid), "teacher_decisions": total_valid_decisions,
                      "splits_decisions": counts, "split_games": game_counts, "stopping": stopping,
                      "high_impact": sorted(set(ctx_counts) & _HIGH), "duplicates": dup, "leakage": leak}, indent=2))
    print("\n".join(log))
    return 0


def _leak_check(out_dir):
    seen = {}
    for s in ("train", "validation", "test"):
        p = os.path.join(out_dir, f"{s}.jsonl.gz")
        for line in gzip.open(p, "rt", encoding="utf-8"):
            gid = json.loads(line)["game_id"]
            if gid in seen and seen[gid] != s:
                return True
            seen[gid] = s
    return False


def _schema():
    return {"record_fields": {
        "example_id": "deterministic sha256[:24] of teacher_id|game_id|decision_index",
        "game_id": "string", "split": "train|validation|test", "teacher_id": "string",
        "teacher_deck_id": "sha256:...", "opponent_id": "string", "seat": "0|1",
        "select_context": "SelectContext name", "observation": "full schema-v2 normalized observation snapshot",
        "legal_options": "list of cabt option dicts", "legal_option_count": "int",
        "min_count": "int", "max_count": "int", "teacher_action_indices": "list[int] (label)",
        "terminal_outcome": "1.0 win / 0.5 draw / 0.0 loss (teacher seat)",
        "decision_latency_ms": "float", "importance_class": "high|normal"},
        "contexts_enum": [c.name for c in SelectContext]}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--primary", required=True)
    p.add_argument("--backup", required=True)
    p.add_argument("--sources", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--base-seed", type=int, default=424242)
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
