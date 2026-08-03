"""c023 — CANDIDATE_HISTORY.jsonl, one line per candidate, assembled from primary evidence.

The contract requires every challenger to record its parent, source commit, deck hash, agent
hash, protocol, seeds, opponents, seats, requested/completed games, runtime and errors. None of
that is typed by hand here: the identity fields come from the candidate manifest written when the
candidate was built, and every count comes from re-reading `games.jsonl`.

The seeds field is honest rather than empty. `libcg.so` seeds `std::mt19937` from
`std::random_device` and exposes no seeding API — c002 established this against the binary — so
there is no seed to record, and recording a fabricated one would imply a reproducibility this
engine does not offer.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

OUT = os.path.join(_REPO, "results", "c023_autonomous_meta_first_competition_sprint")

SEEDS_NOTE = ("NOT_SEEDABLE: libcg.so seeds std::mt19937 from std::random_device and exposes no "
              "seeding API (established in c002 against the binary). Games are therefore matched "
              "on opponents, seats and counts, never on the deal.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(OUT, "CANDIDATE_HISTORY.jsonl"))
    a = ap.parse_args()

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                            capture_output=True, text=True).stdout.strip()

    # every evaluation record, grouped by candidate then tag
    ev: Dict[str, Dict[str, Dict[str, Any]]] = collections.defaultdict(dict)
    raw = os.path.join(OUT, "raw_evaluations")
    tags = sorted(t for t in os.listdir(raw)
                  if os.path.isfile(os.path.join(raw, t, "games.jsonl"))) if os.path.isdir(raw) else []
    for t in tags:
        meta_p = os.path.join(raw, t, "summary.json")
        meta = json.load(open(meta_p)).get("meta", {}) if os.path.exists(meta_p) else {}
        rows = [json.loads(l) for l in open(os.path.join(raw, t, "games.jsonl"))]
        by_c: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
        for r in rows:
            by_c[r["candidate_id"]].append(r)
        for c, rs in by_c.items():
            opp = collections.Counter(r["opponent_id"] for r in rs)
            seats = collections.Counter(int(r["seat"]) for r in rs)
            done = [r for r in rs if r.get("completed")]
            per_opp = collections.defaultdict(list)
            for r in done:
                per_opp[r["opponent_id"]].append(r["score"])
            offs = {o: round(sum(x) / len(x), 4) for o, x in per_opp.items() if o != c}
            ev[c][t] = {
                "phase": rs[0].get("phase"),
                "opponents": dict(sorted(opp.items())),
                "seats": {"seat0": seats.get(0, 0), "seat1": seats.get(1, 0)},
                "requested_games": len(rs),
                "completed_games": len(done),
                "errors": len(rs) - len(done),
                "engine_process_deaths": sum(1 for r in rs if r.get("process_died")),
                "field_off_mirror": round(sum(offs.values()) / len(offs), 4) if offs else None,
                "per_opponent": {o: round(sum(x) / len(x), 4) for o, x in sorted(per_opp.items())},
                "runtime_seconds": round(sum(r.get("seconds") or 0.0 for r in rs), 1),
                "wall_clock_seconds": meta.get("elapsed_seconds"),
                "latency_p99_ms_max": max((r.get("latency_p99_ms") or 0.0) for r in rs),
                "latency_max_ms": max((r.get("latency_max_ms") or 0.0) for r in rs),
                "procs": meta.get("procs"),
                "utc": meta.get("utc"),
            }

    lines = []
    mdir = os.path.join(OUT, "candidate_manifests")
    manifests = {}
    if os.path.isdir(mdir):
        for f in sorted(os.listdir(mdir)):
            if f.endswith(".json"):
                m = json.load(open(os.path.join(mdir, f)))
                manifests[m["candidate_id"]] = m

    for cid in sorted(set(manifests) | set(ev)):
        m = manifests.get(cid, {})
        rec = {
            "candidate_id": cid,
            "parent": m.get("parent"),
            "base": m.get("base"),
            "kind": ("c023_candidate" if m else "external_player"),
            "rationale": m.get("rationale"),
            "source_commit": commit,
            "deck_sha256": m.get("deck_sha256"),
            "base_agent_sha256": m.get("base_agent_sha256"),
            "wrapper_sha256": m.get("wrapper_sha256"),
            "planner_sha256": m.get("planner_sha256"),
            "params_sha256": m.get("params_sha256"),
            "params": m.get("params"),
            "protocol": "c023_eval: fork-per-game, seat-balanced replicates, identity fields "
                        "carried job->result, score = 1/0.5/0 for win/draw/loss",
            "seeds": SEEDS_NOTE,
            "evaluations": ev.get(cid, {}),
        }
        lines.append(rec)

    with open(a.out, "w") as fh:
        for r in lines:
            fh.write(json.dumps(r) + "\n")
    print(f"{len(lines)} candidates -> {os.path.relpath(a.out, _REPO)}  "
          f"({sum(len(r['evaluations']) for r in lines)} evaluation records, {len(tags)} tags)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
