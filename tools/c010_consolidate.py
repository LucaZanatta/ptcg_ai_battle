"""c010 AC-07/08/09: consolidate the per-seed training outputs into the arm-level deliverables.

Each seed runs as its own process (spawn pools cannot be nested), so training writes under
training/arm_X/seedNNN/. This merges those into the arm-level artifact names the contract
requires, without re-deriving anything: every game row and update row is carried through
verbatim and re-counted, so the consolidated files can be independently checked against the
per-seed sources.
"""

import argparse
import gzip
import hashlib
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C010 = os.path.join(_REPO, "contracts", "c010_fixed_deck_rl_loop_v2")
ART = os.path.join(C010, "results", "artifacts")
LOGD = os.path.join(C010, "results", "test_logs")
TROOT = os.path.join(ART, "training")


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def eval_point_coverage(arm, per_seed, ckpt_registry):
    """Which registered §10/§11/§12 evaluation points each seed actually reached.

    Checkpoints fire on `games_done >= eval_point`, so a seed whose budget was trimmed can
    stop short of its last registered point. That produces a terminal checkpoint carrying
    `registered_eval_point: null`, and it must be reported as a point NOT reached rather than
    silently counted as coverage.
    """
    reg = json.load(open(os.path.join(ART, "experiment_registry.json")))
    points = [p for p in reg["arms"][arm]["evaluation_points"] if p]
    out = {"registered_points": points, "per_seed": {}}
    for sd, s in per_seed.items():
        reached, terminal_below = [], None
        for meta in s.get("checkpoints", {}).values():
            if meta.get("registered_eval_point"):
                reached.append(meta["registered_eval_point"])
            elif meta.get("terminal_below_registered_point"):
                terminal_below = {"training_games": meta["training_games"],
                                  "unreached_point": meta.get("unreached_registered_point"),
                                  "nearest_reached": meta.get("nearest_registered_point_reached")}
        out["per_seed"][sd] = {
            "reached": sorted(set(reached)),
            "missing": [p for p in points if p not in reached],
            "terminal_below_registered_point": terminal_below,
            "final_games": s["games_done"],
        }
    out["all_seeds_reached_every_registered_point"] = all(
        not v["missing"] for v in out["per_seed"].values())
    return out


def consolidate(arm):
    d = os.path.join(TROOT, f"arm_{arm}")
    if not os.path.isdir(d):
        return {"arm": arm, "status": "MISSING", "seeds": []}
    seeds = sorted(sd for sd in os.listdir(d)
                   if os.path.exists(os.path.join(d, sd, "summary.json")))
    if not seeds:
        return {"arm": arm, "status": "NO_COMPLETED_SEEDS", "seeds": []}

    per_seed, n_games, n_updates = {}, 0, 0
    ckpt_registry, games_out, updates_out, logs = {}, [], [], []
    for sd in seeds:
        sdir = os.path.join(d, sd)
        s = json.load(open(os.path.join(sdir, "summary.json")))
        per_seed[str(s["seed"])] = s

        gp = os.path.join(sdir, "training_games.jsonl.gz")
        with gzip.open(gp, "rt") as fh:
            rows = fh.readlines()
        games_out.extend(rows)
        n_games += len(rows)

        up = os.path.join(sdir, "updates.jsonl.gz")
        with gzip.open(up, "rt") as fh:
            urows = fh.readlines()
        updates_out.extend(urows)
        n_updates += len(urows)

        for games, meta in json.load(open(os.path.join(sdir, "checkpoint_registry.json"))).items():
            cid = f"{arm}_{meta['seed']}_g{games}"
            ckpt_registry[cid] = dict(meta, candidate_id=cid)

        lp = os.path.join(sdir, "train.log")
        if os.path.exists(lp):
            logs.append(f"===== arm {arm} seed {s['seed']} =====\n" + open(lp).read())

    gpath = os.path.join(ART, f"arm_{arm}_training_games.jsonl.gz")
    with gzip.open(gpath, "wt") as fh:
        fh.writelines(games_out)
    upath = os.path.join(ART, f"arm_{arm}_updates.jsonl.gz")
    with gzip.open(upath, "wt") as fh:
        fh.writelines(updates_out)
    json.dump(ckpt_registry, open(os.path.join(ART, f"arm_{arm}_checkpoint_registry.json"), "w"),
              indent=2)
    os.makedirs(LOGD, exist_ok=True)
    open(os.path.join(LOGD, f"arm_{arm}_training.txt"), "w").write("\n".join(logs))

    # re-count from the consolidated file rather than trusting the per-seed summaries
    recount = sum(1 for _ in gzip.open(gpath, "rt"))
    games_done = sum(s["games_done"] for s in per_seed.values())
    terminal = sum(1 for ln in games_out if json.loads(ln).get("terminal"))
    invalid = sum(json.loads(ln).get("invalid_actions", 0) for ln in games_out)
    exc = sum(json.loads(ln).get("exception_count", 0) for ln in games_out)

    summary = {
        "arm": arm,
        "seeds": sorted(int(k) for k in per_seed),
        "n_seeds": len(per_seed),
        "games_done_total": games_done,
        "training_game_rows": recount,
        "terminal_game_rows": terminal,
        "updates_total": n_updates,
        "trainable_decisions_total": sum(s["trainable_decisions"] for s in per_seed.values()),
        "reliability": {"invalid_actions": invalid, "exceptions": exc},
        "stop_reasons": {str(s["seed"]): s["stop_reason"] for s in per_seed.values()},
        "initializations": {str(s["seed"]): {"from": s["initialization"],
                                             "sha256": s["initialization_sha256"]}
                            for s in per_seed.values()},
        "registered_checkpoints": sorted(ckpt_registry),
        "evaluation_point_coverage": eval_point_coverage(arm, per_seed, ckpt_registry),
        "per_seed": per_seed,
        "files": {"training_games": os.path.relpath(gpath, _REPO),
                  "training_games_sha256": sha_file(gpath),
                  "updates": os.path.relpath(upath, _REPO),
                  "updates_sha256": sha_file(upath)},
        "consistency": {
            "row_count_matches_stream": recount == len(games_out),
            "terminal_rows_equal_games_done": terminal == games_done,
            "rows_at_least_terminal": recount >= terminal,
            "all_seeds_reached_budget": all(s["stop_reason"] == "budget_reached"
                                            for s in per_seed.values()),
            "single_initialization_source": len({s["initialization_sha256"]
                                                 for s in per_seed.values()}) == 1,
            "zero_invalid_actions": invalid == 0,
        },
    }
    json.dump(summary, open(os.path.join(ART, f"arm_{arm}_summary.json"), "w"), indent=2)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="A,B,C")
    a = ap.parse_args(argv)
    out = {}
    for arm in a.arms.split(","):
        s = consolidate(arm.strip())
        out[arm.strip()] = {k: s.get(k) for k in
                            ("status", "seeds", "games_done_total", "updates_total",
                             "trainable_decisions_total", "consistency")}
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
