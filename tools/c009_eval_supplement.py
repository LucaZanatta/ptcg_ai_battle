"""c009 supplementary identity-safe evaluation batch.

Adds Phase C strategic games for additional candidates under the IDENTICAL registered
protocol (50 games per seat per opponent) and appends them to the corrected raw-game
evidence. Used when two within-arm candidates are statistically tied on the teacher score,
so §11.1's tie-break (strategic field, then held-out) can be applied on real evidence
instead of a sample-size artifact.

All nine identity assertions run; job-id collisions with existing evidence are rejected.
"""

import argparse
import gzip
import json
import os
import sys
import time
from collections import Counter

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c009_eval as ce  # noqa: E402

C009 = os.path.join(_REPO, "contracts", "c009_amendment_c008")
ART = os.path.join(C009, "results", "artifacts")
LOGD = os.path.join(C009, "results", "test_logs")
TEACHER = "dragapult"
FIELD = ["mega_lucario", "iono", "mega_abomasnow", TEACHER]


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--candidates", required=True, help="comma-separated candidate_ids")
    p.add_argument("--per-seat", type=int, default=50)
    p.add_argument("--phase", default="C")
    p.add_argument("--replicate-offset", type=int, default=20000)
    p.add_argument("--nproc", type=int, default=16)
    p.add_argument("--reason", required=True)
    a = p.parse_args(argv)

    registry = json.load(open(os.path.join(ART, "candidate_checkpoint_registry.json")))
    raw_path = os.path.join(ART, "corrected_games.jsonl.gz")
    existing = [json.loads(l) for l in gzip.open(raw_path, "rt")]
    existing_ids = {g["job_id"] for g in existing}

    from cg.teachers import make_fresh
    deck = make_fresh(TEACHER, ce.SOURCES).deck
    deck_fp = ce.deck_fingerprint(deck)
    manifest = json.load(open(os.path.join(ART, "corrected_game_manifest.json")))
    assert manifest["deck_fingerprint"] == deck_fp, "deck fingerprint drift vs existing evidence"

    cands = [c.strip() for c in a.candidates.split(",") if c.strip()]
    for c in cands:
        assert c in registry, f"unknown candidate {c}"

    import numpy as np
    rng = np.random.default_rng(717171)
    jobs = []
    for cid in cands:
        for opp in FIELD:
            for seat in (0, 1):
                for r in range(a.per_seat):
                    j = ce.make_job(registry[cid], opp, seat, a.replicate_offset + r, a.phase,
                                    requested_seed=int(rng.integers(0, 1 << 30)), deck=deck)
                    assert j["job_id"] not in existing_ids, f"job_id collision: {j['job_id']}"
                    jobs.append(j)
    ids = [j["job_id"] for j in jobs]
    assert len(ids) == len(set(ids)), "duplicate job_id within supplement batch"

    t0 = time.time()
    results = ce.run_jobs(jobs, a.nproc)
    rep = ce.assert_identity(jobs, results, registry, expected_deck_fingerprint=deck_fp)
    dt = time.time() - t0
    for r in results:
        r.pop("deck", None)

    merged = existing + results
    with gzip.open(raw_path, "wt") as fh:
        for g in sorted(merged, key=lambda r: r["job_id"]):
            fh.write(json.dumps(g) + "\n")

    cells = Counter((g["candidate_id"], g["opponent_id"], g["seat"]) for g in merged)
    manifest["total_games"] = len(merged)
    manifest["phases"] = dict(Counter(g["phase"] for g in merged))
    manifest["per_candidate"] = dict(Counter(g["candidate_id"] for g in merged))
    manifest["per_candidate_opponent_seat"] = {f"{c}|{o}|{s}": n for (c, o, s), n in sorted(cells.items())}
    manifest["seat_balance_ok"] = all(cells[(c, o, 0)] == cells[(c, o, 1)] for (c, o, s) in cells if s == 0)
    manifest["terminal"] = sum(1 for g in merged if g["terminal"])
    manifest["defects"] = sum(1 for g in merged if g.get("defect"))
    rep.update({"phase": a.phase, "candidates": cands, "opponents": FIELD,
                "per_seat": a.per_seat, "wall_seconds": round(dt, 1), "supplement_reason": a.reason})
    manifest.setdefault("identity_reports", []).append(rep)
    manifest.setdefault("supplements", []).append(
        {"candidates": cands, "phase": a.phase, "games": len(results), "reason": a.reason})
    manifest["raw_sha256"] = ce.sha256_file(raw_path)
    json.dump(manifest, open(os.path.join(ART, "corrected_game_manifest.json"), "w"), indent=2)

    with open(os.path.join(LOGD, "corrected_evaluation_execution.txt"), "a") as fh:
        fh.write(f"[SUPPLEMENT {a.phase}] {len(results)} games for {cands} in {dt:.0f}s | "
                 f"identity OK (terminal {rep['terminal']}, defects {rep['defects']})\n"
                 f"  reason: {a.reason}\n")
    print(json.dumps({"added_games": len(results), "total_games": len(merged),
                      "identity_ok": rep["ok"], "defects": rep["defects"],
                      "wall_seconds": round(dt, 1)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
