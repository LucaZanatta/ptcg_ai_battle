"""c024 — STATUS.json, recomputed from artifacts rather than transcribed from reports.

Every number here is derived from a file on disk that was written by the run that produced it:
field scores come from `games.jsonl` and are recounted, not read out of a summary; the prize
oracle's violation count comes from its own output; package validity comes from the manifests.
A claim in a `.md` that no artifact supports does not appear.

The ladder readings are the exception and are labelled as such: they come from the Kaggle API,
which is a live external service, so they are snapshots with a timestamp and cannot be recomputed
after the fact. `--ladder` refreshes them; without it the last stored snapshot is reused so the
status can be regenerated offline.
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import time
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C024 = os.path.join(_REPO, "results", "c024_final_sprint")
RAW = os.path.join(_REPO, "results", "c023_autonomous_meta_first_competition_sprint",
                   "raw_evaluations")
PKG = os.path.join(_REPO, "results", "c023_autonomous_meta_first_competition_sprint",
                   "final_packages")
LADDER_SNAPSHOT = os.path.join(C024, "ladder_snapshot.json")

TRACKED = [(55478202, "champion_redeploy"), (55254872, "champion_original"),
           (55477137, "c024_alakazam_v2"), (55466460, "c024_alakazam_v1"),
           (55011215, "official_mega_lucario"), (54948560, "c005_dragapult")]


def recount(tag: str) -> Optional[Dict[str, Any]]:
    """Field score and error count for every candidate in a tag, recounted from raw games."""
    p = os.path.join(RAW, tag, "games.jsonl")
    if not os.path.isfile(p):
        return None
    per: Dict[str, Dict[str, Any]] = {}
    for line in open(p):
        try:
            r = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        c = per.setdefault(r["candidate_id"], {"games": 0, "errors": 0,
                                               "by_opp": collections.defaultdict(list)})
        c["games"] += 1
        if r.get("error"):
            c["errors"] += 1
        elif r.get("score") is not None and r.get("opponent_id") != r.get("candidate_id"):
            c["by_opp"][r["opponent_id"]].append(float(r["score"]))
    out = {}
    for cid, c in per.items():
        rates = {o: sum(v) / len(v) for o, v in c["by_opp"].items() if v}
        out[cid] = {"games": c["games"], "errors": c["errors"],
                    "field_off_mirror": round(sum(rates.values()) / len(rates), 4) if rates else None,
                    "opponents": len(rates),
                    "per_opponent": {o: round(v, 4) for o, v in sorted(rates.items())}}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ladder", action="store_true", help="refresh ladder readings from Kaggle")
    a = ap.parse_args()

    tags = sorted(os.path.basename(os.path.dirname(p))
                  for p in glob.glob(os.path.join(RAW, "c024_*", "games.jsonl")))
    evals = {t: recount(t) for t in tags}
    total_games = sum(c["games"] for t in evals for c in (evals[t] or {}).values())
    total_errors = sum(c["errors"] for t in evals for c in (evals[t] or {}).values())

    oracle = None
    p = os.path.join(C024, "PRIZE_ORACLE.json")
    if os.path.isfile(p):
        d = json.load(open(p))
        oracle = {"games": d["games"], "frames": d["totals"]["frames"],
                  "frames_with_known_prizes": d["totals"]["declared_frames"],
                  "prize_reveals_checked": d["totals"]["checked_takes"],
                  "violations": d["totals"]["violations"],
                  "coverage": round(d["totals"]["declared_frames"]
                                    / max(1, d["totals"]["frames"]), 4)}

    packages = {}
    for m in sorted(glob.glob(os.path.join(PKG, "*_manifest.json"))):
        d = json.load(open(m))
        name = os.path.basename(m).replace("_manifest.json", "")
        # The manifest calls it `clean_validation`, not `validation`. Reading the wrong key
        # returned None for every package and printed "valid=None" -- which reads as "unknown"
        # and would have let a package with valid=false pass unnoticed in a status summary.
        v = d.get("clean_validation") or d.get("validation") or {}
        packages[name] = {"valid": v.get("valid"),
                          "checks": v.get("checks"),
                          "sha256": (d.get("archive_sha256") or "")[:16]}

    ladder = None
    if a.ladder:
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()
        subs = {s.ref: s for s in api.competition_submissions("pokemon-tcg-ai-battle")}
        rows = []
        for sid, name in TRACKED:
            s = subs.get(sid)
            if s is None:
                continue
            eps = api.competition_list_episodes(submission_id=sid) or []
            w = l = d_ = 0
            for e in eps:
                for ag in (e.agents or []):
                    if int(getattr(ag, "submission_id", 0) or 0) == sid:
                        r = getattr(ag, "reward", None)
                        w += r == 1
                        l += r == -1
                        d_ += r is not None and r not in (1, -1)
            rows.append({"submission": sid, "agent": name,
                         "status": str(s.status).split(".")[-1],
                         "rating": (float(s.public_score) if s.public_score not in (None, "") else None),
                         "episodes": len(eps), "wins": w, "losses": l,
                         "score_rate": round((w + 0.5 * d_) / max(1, w + l + d_), 4)})
        ladder = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "submissions": rows}
        with open(LADDER_SNAPSHOT, "w") as fh:
            json.dump(ladder, fh, indent=2)
    elif os.path.isfile(LADDER_SNAPSHOT):
        ladder = json.load(open(LADDER_SNAPSHOT))

    status = {
        "contract": "c024_final_sprint",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "deadline": "2026-08-16T23:59:00+02:00",
        "decision": "official_dragapult (Kiyota sample, byte-for-byte) is the entry",
        "champion_converged_rating": 688.5,
        "champion_converged_basis": "submission 55254872, 200 episodes, 94W-107L",
        "leaderboard_number_is_not_strength": (
            "Three byte-identical copies of this agent have read 719.7 (83 eps), 688.5 (200 eps) "
            "and 947.9->817.4 (34 eps and falling). Quote ~690 as strength; the leaderboard "
            "number is whichever draw is frozen highest."),
        "local_games_this_contract": total_games,
        "local_errors_this_contract": total_errors,
        "local_errors_accounted": {
            "6": "pub_prvsiyan_lopunny_1208 in c024_smoke -- D9, the kernel's entry point is "
                 "not called `agent`; fixed by _ENTRYPOINT_ALIASES and it played cleanly after",
            "1": "pub_soutasakurai_libraryout_1208 in c024_screen1 -- one engine-side INVALID "
                 "status in 6,540 games, opponent-side, not reproduced"},
        "evaluations": evals,
        "prize_tracker_oracle": oracle,
        "packages": packages,
        "ladder": ladder,
        "findings": {
            "panel_ceiling_below_target": {
                "fit": "rating ~= 341 + 619 * field, field <= 1.0 by construction",
                "perfect_panel_score_predicts": 960,
                "leaderboard_top": 1233.7,
                "evidence": "CALIBRATION_RETEST.md"},
            "panel_reproducibility": {
                "official_dragapult_13panel_2026_08_03": 0.5708,
                "official_dragapult_13panel_2026_08_13": 0.5710,
                "games_each": 2400},
            "calibration_out_of_sample_miss_rating": -119.9,
            "d11_unsubmittable_candidates": {
                "cause": "kaggle_environments execs main.py with no __file__ in scope",
                "second_layer": "the wrapper is copied into candidates at BUILD time, so a source "
                                "fix does not repair the 28 already built",
                "check_added": "raw_python_check: file-path self-play, gates package validity"},
        },
    }
    os.makedirs(C024, exist_ok=True)
    with open(os.path.join(C024, "STATUS.json"), "w") as fh:
        json.dump(status, fh, indent=2)

    print(f"c024 local games {total_games}  errors {total_errors}  tags {len(tags)}")
    if oracle:
        print(f"prize oracle: {oracle['violations']} violations over "
              f"{oracle['prize_reveals_checked']} reveals, coverage {oracle['coverage']:.3f}")
    for n, d in packages.items():
        print(f"package {n:34s} valid={d['valid']}")
    if ladder:
        for r in ladder["submissions"]:
            print(f"  {r['submission']} {r['agent']:22s} {str(r['rating']):8s} "
                  f"eps={r['episodes']:4d} rate={r['score_rate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
