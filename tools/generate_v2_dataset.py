"""c007 AC-05: generate the expanded ordered v2 dataset.

The INSTRUMENTED teacher (behavior-equivalent, AC-04) plays both seats against the
strategic field (Mega Lucario / Mega Abomasnow / Iono / Dragapult mirror); the
engineering control is captured SEPARATELY (§9). Per teacher decision we store the
mutation-safe raw observation snapshot, exact legal options, actual history (previous
context + selected indices), the privileged plan labels, the terminal outcome, latency,
and lineage. State Encoder v2 is derived offline from the stored obs (so a single
encoder bug never forces a 600-game regeneration). Whole-game 70/15/15 split, frozen
test, no leakage. Parallelised with spawn (fresh libcg.so per worker).

Targets: >= 600 strategic games AND >= 50,000 ordered strategic decisions.
"""

import argparse
import gzip
import hashlib
import json
import multiprocessing as mp
import os
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C005_ART = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset",
                        "results", "artifacts")
C005_SOURCES = os.path.join(C005_ART, "teacher_sources")
C007_ART = os.path.join(_REPO, "contracts", "c007_hybrid_teacher_residual_and_state_encoder_v2",
                        "results", "artifacts")
INSTR_DIR = os.path.join(C007_ART, "instrumented_teacher")

STRATEGIC = ["mega_lucario", "mega_abomasnow", "iono", "dragapult"]  # last = mirror
TEACHER = "dragapult"


def _eid(tid, gid, didx):
    return hashlib.sha256(f"{tid}|{gid}|{didx}".encode()).hexdigest()[:24]


def _deck_id():
    from cg.teachers import canonical_deck_record
    return canonical_deck_record(TEACHER, C005_SOURCES, _REPO)["deck_id"]


def capture_game(job):
    from kaggle_environments import make
    from cg.instrumented_teacher import make_fresh as instr_fresh
    from cg.teachers import make_fresh as teacher_fresh
    from cg.control_agent import DetControl
    from cg.episode_capture import context_name, normalize_observation
    from cg.safe_policy import MalformedSelection, validate_selection

    opp_id = job["opponent"]; seat = job["teacher_seat"]; gid = job["game_id"]
    teacher = instr_fresh(INSTR_DIR)
    if opp_id == "__control__":
        opp = DetControl(teacher.deck)
    elif opp_id == TEACHER:
        opp = teacher_fresh(TEACHER, C005_SOURCES)  # mirror = fresh separate instance
    else:
        opp = teacher_fresh(opp_id, C005_SOURCES)

    decisions = []
    invalid = [0]
    didx = [0]
    prev_ctx = [None]
    prev_act = [[]]

    def make_teacher_wrap():
        def w(obs):
            sel = obs["select"] if isinstance(obs, dict) else getattr(obs, "select", None)
            snap = normalize_observation(obs)[0] if sel is not None else None
            t0 = time.perf_counter_ns()
            res = teacher(obs)
            dt = time.perf_counter_ns() - t0
            if sel is not None:
                n = len(sel.get("option", []))
                try:
                    validate_selection(list(res), n, sel.get("minCount"), sel.get("maxCount"))
                except MalformedSelection:
                    invalid[0] += 1
                cv = sel.get("context")
                cap = teacher.captures[-1] if teacher.captures else {}
                decisions.append({
                    "decision_index": didx[0],
                    "turn_index": (snap.get("current") or {}).get("turn"),
                    "step_index": snap.get("step"),
                    "teacher_seat": seat, "teacher_id": TEACHER, "opponent_id": opp_id,
                    "select_context": context_name(cv), "select_context_value": cv,
                    "min_count": sel.get("minCount"), "max_count": sel.get("maxCount"),
                    "legal_option_count": n,
                    "previous_context": prev_ctx[0],
                    "previous_teacher_action_indices": list(prev_act[0]),
                    "observation": snap, "legal_options": sel.get("option"),
                    "teacher_action_indices": list(res),
                    "decision_latency_ms": round(dt / 1e6, 6),
                    "plan_labels": cap,
                })
                prev_ctx[0] = context_name(cv); prev_act[0] = list(res)
                didx[0] += 1
            return res
        return w

    def make_opp_wrap():
        def w(obs):
            return opp(obs)
        return w

    players = ([make_teacher_wrap(), make_opp_wrap()] if seat == 0
               else [make_opp_wrap(), make_teacher_wrap()])
    exc = None; env = None
    try:
        env = make("cabt"); env.run(players)
    except Exception as e:  # noqa: BLE001
        exc = repr(e)
    if env is None:
        return {"game_id": gid, "opponent": opp_id, "teacher_seat": seat, "terminal": False,
                "error": exc, "invalid": invalid[0], "outcome": None, "decisions": []}
    last = env.steps[-1]
    st = [last[0]["status"], last[1]["status"]]
    rw = [last[0].get("reward"), last[1].get("reward")]
    terminal = st == ["DONE", "DONE"]
    tr = rw[seat]
    outcome = None if not terminal else (0.5 if rw[0] == rw[1] else (1.0 if tr == 1 else 0.0))
    return {"game_id": gid, "opponent": opp_id, "teacher_seat": seat, "terminal": terminal,
            "statuses": st, "error": None, "invalid": invalid[0], "outcome": outcome,
            "game_length_steps": len(env.steps), "decisions": decisions}


def _schedule(games_per_combo, control_games, base):
    jobs = []
    n = 0
    for opp in STRATEGIC:
        for seat in (0, 1):
            for _ in range(games_per_combo):
                jobs.append({"opponent": opp, "teacher_seat": seat,
                             "game_id": f"{TEACHER}-vs-{opp}-s{seat}-{n:05d}"})
                n += 1
    for seat in (0, 1):
        for _ in range(control_games // 2):
            jobs.append({"opponent": "__control__", "teacher_seat": seat,
                         "game_id": f"{TEACHER}-vs-__control__-s{seat}-{n:05d}"})
            n += 1
    return jobs


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", default=os.path.join(C007_ART, "v2_dataset"))
    p.add_argument("--log-dir", default=os.path.join(os.path.dirname(C007_ART), "test_logs"))
    p.add_argument("--games-per-combo", type=int, default=90)  # 8 combos -> 720 strategic
    p.add_argument("--control-games", type=int, default=48)
    p.add_argument("--nproc", type=int, default=14)
    p.add_argument("--split-seed", type=int, default=70157)
    a = p.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    os.makedirs(a.log_dir, exist_ok=True)
    genlog = open(os.path.join(a.log_dir, "v2_dataset_generation.txt"), "w")
    t0 = time.time()
    deck_id = _deck_id()
    jobs = _schedule(a.games_per_combo, a.control_games, 0)
    genlog.write(f"scheduled {len(jobs)} games ({a.games_per_combo}/combo x8 strategic + "
                 f"{a.control_games} control); nproc {a.nproc}\n"); genlog.flush()

    ctx = mp.get_context("spawn")
    results = []
    done = 0
    with ctx.Pool(processes=a.nproc) as pool:
        for r in pool.imap_unordered(capture_game, jobs, chunksize=1):
            results.append(r)
            done += 1
            if done % 40 == 0:
                genlog.write(f"  {done}/{len(jobs)} games done ({time.time()-t0:.0f}s)\n")
                genlog.flush()

    # split strategic valid games; control kept separate
    strat = [r for r in results if r["opponent"] != "__control__"]
    ctrl = [r for r in results if r["opponent"] == "__control__"]
    valid = [r for r in strat if r["terminal"] and r["invalid"] == 0]
    ctrl_valid = [r for r in ctrl if r["terminal"] and r["invalid"] == 0]

    import random
    srng = random.Random(a.split_seed)
    strata = {}
    for g in valid:
        key = (g["opponent"], g["teacher_seat"])
        strata.setdefault(key, []).append(g["game_id"])
    split_of = {}
    for key, gids in strata.items():
        gids = sorted(gids)
        srng.shuffle(gids)
        n = len(gids); ntr = int(round(0.70 * n)); nval = int(round(0.15 * n))
        for i, gid in enumerate(gids):
            split_of[gid] = "train" if i < ntr else ("validation" if i < ntr + nval else "test")

    gmap = {g["game_id"]: g for g in valid}
    counts = {"train": {"games": 0, "decisions": 0}, "validation": {"games": 0, "decisions": 0},
              "test": {"games": 0, "decisions": 0}}
    fhs = {s: gzip.open(os.path.join(a.out_dir, f"{s}.jsonl.gz"), "wt", encoding="utf-8")
           for s in ("train", "validation", "test")}
    sem_counts = {}
    for gid, g in gmap.items():
        sp = split_of[gid]
        counts[sp]["games"] += 1
        for d in g["decisions"]:
            d["example_id"] = _eid(TEACHER, gid, d["decision_index"])
            d["game_id"] = gid; d["split"] = sp
            d["teacher_deck_id"] = deck_id; d["terminal_outcome"] = g["outcome"]
            fhs[sp].write(json.dumps(d) + "\n")
            counts[sp]["decisions"] += 1
            sem_counts[d["select_context"]] = sem_counts.get(d["select_context"], 0) + 1
    for fh in fhs.values():
        fh.close()

    # control set (separate)
    cfh = gzip.open(os.path.join(a.out_dir, "control.jsonl.gz"), "wt", encoding="utf-8")
    cdec = 0
    for g in ctrl_valid:
        for d in g["decisions"]:
            d["example_id"] = _eid(TEACHER, g["game_id"], d["decision_index"])
            d["game_id"] = g["game_id"]; d["split"] = "control"
            d["teacher_deck_id"] = deck_id; d["terminal_outcome"] = g["outcome"]
            cfh.write(json.dumps(d) + "\n"); cdec += 1
    cfh.close()

    tot_games = sum(counts[s]["games"] for s in counts)
    tot_dec = sum(counts[s]["decisions"] for s in counts)
    file_sha = {s: hashlib.sha256(open(os.path.join(a.out_dir, f"{s}.jsonl.gz"), "rb").read()).hexdigest()
                for s in ("train", "validation", "test")}
    manifest = {
        "contract": "c007", "teacher_id": TEACHER, "teacher_deck_id": deck_id,
        "generated_by": "instrumented teacher (behavior-equivalent, AC-04)",
        "opponents_strategic": STRATEGIC, "engineering_control": "__control__ (separate)",
        "games_scheduled": len(jobs), "games_strategic_played": len(strat),
        "games_strategic_valid": len(valid), "games_control_valid": len(ctrl_valid),
        "split_counts": counts, "total_strategic_games": tot_games, "total_strategic_decisions": tot_dec,
        "control_decisions": cdec, "control_games": len(ctrl_valid),
        "split_seed": a.split_seed, "split_scheme": "whole-game 70/15/15 stratified by (opponent,seat)",
        "file_sha256": file_sha,
        "meets_min_600_games": tot_games >= 600,
        "meets_min_50000_decisions": tot_dec >= 50000,
        "semantic_context_counts": dict(sorted(sem_counts.items(), key=lambda kv: -kv[1])),
        "wall_seconds": round(time.time() - t0, 1),
    }
    json.dump(manifest, open(os.path.join(C007_ART, "v2_dataset_manifest.json"), "w"), indent=2)

    # leakage + split report
    game_split = {}
    for gid, sp in split_of.items():
        game_split.setdefault(gid, set()).add(sp)
    leak = {g: sorted(s) for g, s in game_split.items() if len(s) > 1}
    split_report = {"counts": counts, "no_leakage": len(leak) == 0, "leaking": leak,
                    "excluded_invalid_or_nonterminal": len(strat) - len(valid),
                    "control_valid": len(ctrl_valid)}
    json.dump(split_report, open(os.path.join(C007_ART, "v2_dataset_split_report.json"), "w"), indent=2)

    genlog.write(f"\nDONE {tot_games} strategic games / {tot_dec} decisions "
                 f"(min600={manifest['meets_min_600_games']} min50k={manifest['meets_min_50000_decisions']}); "
                 f"control {len(ctrl_valid)} games / {cdec} decisions; {manifest['wall_seconds']}s\n")
    genlog.close()
    print(json.dumps({k: manifest[k] for k in ("total_strategic_games", "total_strategic_decisions",
                      "meets_min_600_games", "meets_min_50000_decisions", "control_games",
                      "wall_seconds")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
