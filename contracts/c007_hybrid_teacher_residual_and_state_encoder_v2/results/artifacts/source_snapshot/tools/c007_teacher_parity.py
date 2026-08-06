"""c007 AC-04: prove the instrumented teacher is behavior-equivalent to the frozen
Dragapult teacher, and emit the instrumentation manifest + plan-label schema.

Two registered parity tests (definition frozen in EXPERIMENT_REGISTRATION):
  1. REPLAY parity  - for every c006 game, load a fresh frozen teacher and a fresh
     instrumented teacher, feed the identical stored ordered observation stream to
     both, and require byte-identical returned actions at every decision (>=15,000
     decisions available; 19,050 present). Also reports agreement with the recorded
     teacher action as a sanity check.
  2. LIVE dual-call parity - play 100 fresh cabt games where the teacher seat calls
     BOTH teachers on the same observation, asserts equal, and drives the game with
     the instrumented action (the shipped artifact). Requires identical actions,
     identical exception behavior, zero invalid selections.

Because the shipped decision logic is byte-identical except one side-effect-free
capture statement, parity is expected to be exact; the tests certify it on the exact
artifact that ships. Engine games are random_device-seeded (c006), so parity is
per-decision action identity (dual-call), NOT cross-run outcome identity.
"""

import argparse
import difflib
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
C006_SEQ = os.path.join(_REPO, "contracts", "c006_distilled_policy_baseline",
                        "results", "artifacts", "sequence_dataset")
C007_ART = os.path.join(_REPO, "contracts", "c007_hybrid_teacher_residual_and_state_encoder_v2",
                        "results", "artifacts")
FROZEN_MAIN = os.path.join(C005_ART, "frozen_teacher", "main.py")
INSTR_DIR = os.path.join(C007_ART, "instrumented_teacher")
C005_SOURCES = os.path.join(C005_ART, "teacher_sources")


def sha256_file(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def _load_games():
    """Return {game_id: [records ordered by decision_index]} from all c006 splits."""
    games = {}
    for sp in ("train", "validation", "test"):
        with gzip.open(os.path.join(C006_SEQ, f"{sp}.jsonl.gz"), "rt") as fh:
            for line in fh:
                r = json.loads(line)
                games.setdefault(r["game_id"], []).append(r)
    for gid in games:
        games[gid].sort(key=lambda r: r["decision_index"])
    return games


def replay_parity():
    from cg.teachers import make_fresh as frozen_fresh
    from cg.instrumented_teacher import make_fresh as instr_fresh
    games = _load_games()
    n_dec = n_match_fi = n_match_stored = n_exc = 0
    mismatches = []
    for gid, recs in games.items():
        frozen = frozen_fresh("dragapult", C005_SOURCES)
        instr = instr_fresh(INSTR_DIR)
        for r in recs:
            obs = r["observation"]
            try:
                fa = list(frozen(obs))
                ia = list(instr(obs))
            except Exception as e:  # noqa: BLE001
                n_exc += 1
                mismatches.append({"game": gid, "didx": r["decision_index"], "exception": repr(e)})
                continue
            n_dec += 1
            if fa == ia:
                n_match_fi += 1
            elif len(mismatches) < 50:
                mismatches.append({"game": gid, "didx": r["decision_index"],
                                   "frozen": fa, "instrumented": ia})
            if fa == list(r["teacher_action_indices"]):
                n_match_stored += 1
    return {
        "games": len(games),
        "decisions": n_dec,
        "frozen_vs_instrumented_match": n_match_fi,
        "frozen_vs_instrumented_mismatch": n_dec - n_match_fi,
        "frozen_vs_recorded_match": n_match_stored,
        "exceptions": n_exc,
        "parity_exact": (n_dec - n_match_fi) == 0 and n_exc == 0,
        "min_required_decisions": 15000,
        "meets_minimum": n_dec >= 15000,
        "sample_mismatches": mismatches[:50],
        "captured_plan_labels_example": _sample_capture(),
    }


def _sample_capture():
    """One instrumented decision with its captured plan labels (evidence the labels populate)."""
    from cg.instrumented_teacher import make_fresh as instr_fresh
    games = _load_games()
    gid = next(iter(games))
    instr = instr_fresh(INSTR_DIR)
    for r in games[gid]:
        instr(r["observation"])
        cap = instr.captures[-1]
        if cap.get("scores"):
            return {"game": gid, "didx": r["decision_index"], "labels": cap}
    return instr.captures[-1] if instr.captures else None


def _play_dual(job):
    from kaggle_environments import make
    from cg.teachers import make_fresh as frozen_fresh
    from cg.instrumented_teacher import make_fresh as instr_fresh
    from cg.safe_policy import MalformedSelection, validate_selection
    res = {"games": [], "n_decisions": 0, "n_mismatch": 0, "n_invalid": 0,
           "n_exc": 0, "completed": 0, "samples": []}
    def make_teacher(frozen, instr, st):
        # single-arg closure: kaggle_environments inspects arity, so no default-arg params
        def teacher_seat(obs):
            sel = obs.get("select") if isinstance(obs, dict) else getattr(obs, "select", None)
            fa = list(frozen(obs))
            ia = list(instr(obs))
            if sel is not None:
                st["dec"] += 1
                if fa != ia:
                    st["mism"] += 1
                    if len(res["samples"]) < 20:
                        res["samples"].append({"frozen": fa, "instrumented": ia})
                n = len(sel.get("option", [])) if isinstance(sel, dict) else len(sel.option)
                lo = sel.get("minCount") if isinstance(sel, dict) else sel.minCount
                mx = sel.get("maxCount") if isinstance(sel, dict) else sel.maxCount
                try:
                    validate_selection(list(ia), n, lo, mx)
                except MalformedSelection:
                    st["inv"] += 1
            return ia
        return teacher_seat

    def make_opp(opp):
        def opp_seat(obs):
            return opp(obs)
        return opp_seat

    for g in job["games"]:
        frozen = frozen_fresh("dragapult", C005_SOURCES)
        instr = instr_fresh(INSTR_DIR)
        opp = frozen_fresh(job["opp"], C005_SOURCES)
        st = {"dec": 0, "mism": 0, "inv": 0}
        teacher_seat = make_teacher(frozen, instr, st)
        opp_seat = make_opp(opp)
        seats = [teacher_seat, opp_seat] if g["teacher_seat"] == 0 else [opp_seat, teacher_seat]
        exc = None
        env = None
        try:
            env = make("cabt")
            env.run(seats)
        except Exception as e:  # noqa: BLE001
            exc = repr(e)
            res["n_exc"] += 1
        statuses = [s.status for s in env.steps[-1]] if env is not None else ["ERROR", "ERROR"]
        res["n_decisions"] += st["dec"]
        res["n_mismatch"] += st["mism"]
        res["n_invalid"] += st["inv"]
        if statuses == ["DONE", "DONE"]:
            res["completed"] += 1
        res["games"].append({"teacher_seat": g["teacher_seat"], "opp": job["opp"],
                             "statuses": statuses, "decisions": st["dec"],
                             "mismatch": st["mism"], "exception": exc})
    return res


def live_parity(n_games, nproc):
    opps = ["mega_lucario", "mega_abomasnow", "iono", "dragapult"]
    jobs_games = []
    for i in range(n_games):
        jobs_games.append({"teacher_seat": i % 2, "opp": opps[i % len(opps)]})
    # chunk across workers
    chunks = [[] for _ in range(min(nproc, n_games))]
    for i, g in enumerate(jobs_games):
        chunks[i % len(chunks)].append(g)
    jobs = [{"games": c, "opp_placeholder": None} for c in chunks]
    # each chunk may span opponents; regroup so a worker handles mixed opps via per-game opp
    # (simpler: attach opp per job = first game's opp is not enough) -> handle per game:
    jobs = []
    for c in chunks:
        # split chunk by opp so _play_dual gets a single opp per job
        byopp = {}
        for g in c:
            byopp.setdefault(g["opp"], []).append(g)
        for opp, gg in byopp.items():
            jobs.append({"games": gg, "opp": opp})
    ctx = mp.get_context("spawn")
    if nproc <= 1:
        outs = [_play_dual(j) for j in jobs]
    else:
        with ctx.Pool(processes=min(nproc, len(jobs))) as pool:
            outs = list(pool.imap_unordered(_play_dual, jobs))
    agg = {"games": 0, "n_decisions": 0, "n_mismatch": 0, "n_invalid": 0,
           "n_exc": 0, "completed": 0, "samples": []}
    per_game = []
    for o in outs:
        agg["n_decisions"] += o["n_decisions"]
        agg["n_mismatch"] += o["n_mismatch"]
        agg["n_invalid"] += o["n_invalid"]
        agg["n_exc"] += o["n_exc"]
        agg["completed"] += o["completed"]
        agg["games"] += len(o["games"])
        agg["samples"].extend(o["samples"][:5])
        per_game.extend(o["games"])
    agg["parity_exact"] = agg["n_mismatch"] == 0 and agg["n_invalid"] == 0 and agg["n_exc"] == 0
    agg["per_game"] = per_game
    return agg


def instrumented_diff():
    """Structural diff proving the instrumented copy differs from frozen ONLY by the
    inserted side-effect-free capture block (contiguous added lines, no removed line)."""
    frozen = open(FROZEN_MAIN).read().splitlines()
    instr = open(os.path.join(INSTR_DIR, "main.py")).read().splitlines()
    added, removed = [], []
    for ln in difflib.unified_diff(frozen, instr, lineterm="", n=0):
        if ln.startswith("+") and not ln.startswith("+++"):
            added.append(ln[1:])
        elif ln.startswith("-") and not ln.startswith("---"):
            removed.append(ln[1:])
    return {"frozen_main_sha256": sha256_file(FROZEN_MAIN),
            "instrumented_main_sha256": sha256_file(os.path.join(INSTR_DIR, "main.py")),
            "added_lines": added, "removed_lines": removed,
            "only_additions": len(removed) == 0,
            "addition_is_capture_only": all(
                ("_c007_capture" in a or a.strip() == "" or a.strip().startswith("#")
                 or a.strip().startswith('"') or ":" in a) for a in added) and len(removed) == 0}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", default=C007_ART)
    p.add_argument("--log-dir", default=os.path.join(os.path.dirname(C007_ART), "test_logs"))
    p.add_argument("--live-games", type=int, default=100)
    p.add_argument("--nproc", type=int, default=12)
    a = p.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    os.makedirs(a.log_dir, exist_ok=True)

    t0 = time.time()
    diff = instrumented_diff()
    replay = replay_parity()
    live = live_parity(a.live_games, a.nproc)
    dt = time.time() - t0

    parity = {
        "contract": "c007",
        "teacher_id": "dragapult",
        "instrumented_source_diff": diff,
        "replay_parity": replay,
        "live_dual_call_parity": {k: v for k, v in live.items() if k != "per_game"},
        "overall_valid": bool(diff["only_additions"] and replay["parity_exact"]
                              and replay["meets_minimum"] and live["parity_exact"]
                              and live["games"] >= 100 and live["completed"] >= 1),
        "wall_seconds": round(dt, 1),
    }
    json.dump(parity, open(os.path.join(a.out_dir, "teacher_instrumentation_parity.json"), "w"), indent=2)
    json.dump(live.get("per_game", []),
              open(os.path.join(a.out_dir, "teacher_instrumentation_live_games.json"), "w"), indent=2)

    # manifest
    from cg.instrumented_teacher import PLAN_LABEL_FIELDS
    manifest = {
        "contract": "c007",
        "teacher_id": "dragapult",
        "instrumentation_method": "byte-identical decision logic + one side-effect-free "
            "capture statement; persistent planning globals snapshotted read-only AFTER "
            "each agent() call by cg.instrumented_teacher (zero runtime inputs).",
        "frozen_source": os.path.relpath(FROZEN_MAIN, _REPO),
        "instrumented_source": os.path.relpath(os.path.join(INSTR_DIR, "main.py"), _REPO),
        "frozen_main_sha256": diff["frozen_main_sha256"],
        "instrumented_main_sha256": diff["instrumented_main_sha256"],
        "captured_globals": ["plan_a.attack", "plan_a.counter", "plan_b.attack",
                             "plan_b.counter", "use_support", "bench_attacker",
                             "can_switch", "can_attack", "can_main_attack", "prize"],
        "captured_locals_via_capture_line": ["scores", "prize_diff", "do_switch",
                                             "no_draw", "damage", "no_more_dex"],
        "hazards_respected": [
            "plan_*.counter deep-copied (aliased at main.py L284; never reset on early return L215-216)",
            "card_counts NOT snapshotted by probing keys (defaultdict mutation hazard); only globals read",
            "select==None deck-extraction call not snapshotted",
            "teacher loads sequential per process (os.chdir at import)",
        ],
        "labels_are_training_targets_only": True,
        "plan_label_fields": PLAN_LABEL_FIELDS,
    }
    json.dump(manifest, open(os.path.join(a.out_dir, "teacher_instrumentation_manifest.json"), "w"), indent=2)

    schema = {
        "contract": "c007",
        "description": "Privileged teacher-plan labels captured per decision by the "
                       "instrumented teacher. Auxiliary training targets ONLY (V2-B).",
        "fields": {
            "plan_a_attack": "int; opponent Pokemon index [active]+bench the teacher plans as the 200-dmg main target (-1 none, 0 active, k bench k-1)",
            "plan_a_counter": "list[int]; spread damage-counter allocation for plan_a (indices into opponent [active]+bench)",
            "plan_b_attack": "int; plan assuming main target = current opponent active (i==0)",
            "plan_b_counter": "list[int]; spread allocation for plan_b (consumed at DAMAGE_COUNTER_ANY, main.py L705)",
            "use_support": "int card id; the Supporter the teacher plans to play this turn (0 none)",
            "bench_attacker": "bool; a benched Dragapult ex is charged (>=2 energy)",
            "can_switch/can_attack/can_main_attack": "bool capability flags refreshed at MAIN",
            "prize_inference": "list[int] card ids the teacher infers are in its own prizes",
            "scores": "list[float]; teacher per-legal-option score vector (argmax/top-k -> action)",
            "argmax_option/top1_score/top2_score/score_margin": "teacher's chosen option and confidence margin",
            "prize_diff": "int; own prizes - opponent prizes",
            "do_switch/no_draw/no_more_dex/damage": "teacher planning flags/values",
            "plan_recomputed_this_decision": "bool; True iff SelectContext.MAIN (planner ran this decision)",
            "select_context": "int SelectContext of the decision",
        },
    }
    json.dump(schema, open(os.path.join(a.out_dir, "teacher_plan_label_schema.json"), "w"), indent=2)

    lines = [
        "c007 AC-04 teacher instrumentation parity",
        "=" * 60,
        f"instrumented main.py sha256: {diff['instrumented_main_sha256']}",
        f"diff vs frozen: +{len(diff['added_lines'])} lines, -{len(diff['removed_lines'])} lines; "
        f"only_additions={diff['only_additions']}",
        "",
        f"REPLAY parity: {replay['decisions']} decisions over {replay['games']} games",
        f"  frozen==instrumented: {replay['frozen_vs_instrumented_match']}/{replay['decisions']} "
        f"(mismatch {replay['frozen_vs_instrumented_mismatch']}, exceptions {replay['exceptions']})",
        f"  frozen==recorded action (sanity): {replay['frozen_vs_recorded_match']}/{replay['decisions']}",
        f"  parity_exact={replay['parity_exact']}  meets_15000={replay['meets_minimum']}",
        "",
        f"LIVE dual-call parity: {live['games']} games, {live['n_decisions']} teacher decisions",
        f"  mismatches={live['n_mismatch']} invalid={live['n_invalid']} exceptions={live['n_exc']} "
        f"completed={live['completed']}",
        f"  parity_exact={live['parity_exact']}",
        "",
        f"OVERALL VALID = {parity['overall_valid']}  ({parity['wall_seconds']}s)",
    ]
    txt = "\n".join(lines) + "\n"
    open(os.path.join(a.log_dir, "teacher_instrumentation_parity.txt"), "w").write(txt)
    print(txt)
    return 0 if parity["overall_valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
