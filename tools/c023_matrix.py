"""c023 — turn round-robin games into the matchup matrix and a champion decision.

The champion is decided here, from measurement, and not inherited as a label. c016 named
`official_mega_lucario` its best candidate on a six-opponent panel that never ran
`official_dragapult` as a candidate at all, while the Kaggle ladder scored dragapult 719.7 against
mega_lucario's 593.3. Those two rankings disagree, and building forty hours of challenger work on
the wrong one is the most expensive mistake available in this contract.

Everything is recomputed from `games.jsonl` rather than read out of a summary, so a stale or
partially-written summary cannot reach a report. Several tags may be merged — they are produced
by the same harness under the same protocol — and the merge is by (candidate, opponent) identity,
never by position.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import os
import sys
from typing import Any, Dict, List, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

OUT = os.path.join(_REPO, "results", "c023_autonomous_meta_first_competition_sprint")

# Archetype usage on the public ladder, 1000+ bands, from META_REPORT §2. Used only to weight a
# secondary field score; the primary number stays unweighted.
LADDER_WEIGHT = {
    "pub_tetsutani_grimmsnarl": 0.60,        # Marnie Grimmsnarl: ~59-61% of the top two bands
    "pub_jazivxt_codex_alakazam": 0.05,      # Alakazam: 9.5% at 1000-1099, split over 3 agents
    "pub_jazivxt_rising_tide_v21": 0.05,
    "pub_raunakdey_heuristic": 0.05,
    "pub_makthanithin_lucario_1084": 0.10,   # a strong non-meta implementation
    "pub_prvsiyan_lucario_v12": 0.05,
    "official_dragapult": 0.04,              # Dragapult: 4.2% at 1000-1099
    "official_mega_lucario": 0.02,
    "official_iono": 0.02,
    "official_mega_abomasnow": 0.02,
}


def wilson(k: float, n: int, z: float = 1.96):
    if n <= 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(max(0.0, p * (1 - p) / n + z * z / (4 * n * n))) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def load(tags: List[str]) -> List[Dict[str, Any]]:
    rows = []
    seen = set()
    for t in tags:
        p = os.path.join(OUT, "raw_evaluations", t, "games.jsonl")
        if not os.path.exists(p):
            raise FileNotFoundError(p)
        for line in open(p):
            r = json.loads(line)
            key = (t, r["job_id"])
            if key in seen:
                raise ValueError(f"duplicate job_id {r['job_id']} in {t}")
            seen.add(key)
            r["_tag"] = t
            rows.append(r)
    return rows


def cells(rows: List[Dict[str, Any]]):
    d: Dict[Tuple[str, str], List[float]] = collections.defaultdict(list)
    err: Dict[str, int] = collections.defaultdict(int)
    lat: Dict[str, float] = collections.defaultdict(float)
    seats: Dict[Tuple[str, int], List[float]] = collections.defaultdict(list)
    for r in rows:
        c, o = r["candidate_id"], r["opponent_id"]
        lat[c] = max(lat[c], r.get("latency_p99_ms") or 0.0)
        if not r.get("completed"):
            err[c] += 1
            continue
        d[(c, o)].append(r["score"])
        seats[(c, int(r["seat"]))].append(r["score"])
    return d, err, lat, seats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", required=True, help="comma-separated evaluation tags to merge")
    ap.add_argument("--out-csv", default=os.path.join(OUT, "MATCHUP_MATRIX.csv"))
    ap.add_argument("--champion-out", default=os.path.join(OUT, "champion.json"))
    ap.add_argument("--eligible", help="comma-separated players eligible to BE the champion "
                                       "(submission-eligible bases). Others are panel members only.")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    tags = [t for t in a.tags.split(",") if t]
    rows = load(tags)
    d, err, lat, seats = cells(rows)
    players = sorted({c for c, _ in d} | {o for _, o in d})

    table = []
    for c in players:
        rec: Dict[str, Any] = {"candidate": c}
        offs = []
        for o in players:
            xs = d.get((c, o))
            rec[o] = "" if not xs else f"{sum(xs)/len(xs):.4f}"
            if xs and o != c:
                offs.append((o, sum(xs) / len(xs), len(xs)))
        rec["_offs"] = offs
        rec["field_off_mirror"] = (round(sum(v for _, v, _ in offs) / len(offs), 4)
                                   if offs else 0.0)
        wsum = sum(LADDER_WEIGHT.get(o, 0.0) for o, _, _ in offs)
        rec["field_ladder_weighted"] = (round(sum(LADDER_WEIGHT.get(o, 0.0) * v
                                                  for o, v, _ in offs) / wsum, 4)
                                        if wsum > 0 else 0.0)
        rec["completed"] = sum(n for _, _, n in offs) + len(d.get((c, c), []))
        rec["errors"] = err.get(c, 0)
        rec["p99_ms"] = round(lat.get(c, 0.0), 2)
        s0, s1 = seats.get((c, 0), []), seats.get((c, 1), [])
        rec["seat0"] = round(sum(s0) / len(s0), 4) if s0 else ""
        rec["seat1"] = round(sum(s1) / len(s1), 4) if s1 else ""
        table.append(rec)
    table.sort(key=lambda r: -r["field_off_mirror"])

    os.makedirs(os.path.dirname(a.out_csv), exist_ok=True)
    fields = (["candidate"] + players +
              ["field_off_mirror", "field_ladder_weighted", "seat0", "seat1",
               "completed", "errors", "p99_ms"])
    with open(a.out_csv, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(table)

    # The strongest player on the panel and the strongest *frozen champion* are different
    # questions, and conflating them would put an unpackageable base under forty hours of work.
    # SOURCES.md classifies every community kernel LOCAL_BENCHMARK_ONLY, so only an official
    # sample (or a candidate built on one) can be the champion.
    eligible = [x for x in a.eligible.split(",") if x] if a.eligible else None
    panel_leader = table[0]["candidate"]
    best = table[0]
    if eligible:
        cands = [r for r in table if r["candidate"] in eligible]
        if cands:
            best = cands[0]
    n_off = sum(n for _, _, n in best["_offs"])
    k_off = sum(v * n for _, v, n in best["_offs"])
    ci = wilson(k_off, n_off)
    pool = [r for r in table if (not eligible or r["candidate"] in eligible)]
    contenders = [r["candidate"] for r in pool
                  if r["candidate"] != best["candidate"] and r["field_off_mirror"] >= (ci[0] or 0.0)]

    champ = {
        "champion": best["candidate"],
        "decided_by": "highest off-mirror field score on the c023 round-robin AMONG "
                      "SUBMISSION-ELIGIBLE bases -- every player measured on one panel, with one "
                      "harness, in one protocol",
        "eligibility_filter": eligible,
        "panel_leader": panel_leader,
        "panel_leader_note": ("the strongest player on the panel is not necessarily the champion: "
                              "SOURCES.md classifies every community kernel LOCAL_BENCHMARK_ONLY, "
                              "so it can be an opponent and never a base"),
        "panel_leader_field_off_mirror": table[0]["field_off_mirror"],
        "field_off_mirror": best["field_off_mirror"],
        "field_ladder_weighted": best["field_ladder_weighted"],
        "off_mirror_games": n_off,
        "off_mirror_wilson95": ci,
        "statistical_contenders": contenders,
        "seat0": best["seat0"], "seat1": best["seat1"],
        "per_opponent": {o: {"score_rate": round(v, 4), "games": n, "wilson95": wilson(v * n, n)}
                         for o, v, n in best["_offs"]},
        "ranking": [{"player": r["candidate"], "field_off_mirror": r["field_off_mirror"],
                     "field_ladder_weighted": r["field_ladder_weighted"],
                     "errors": r["errors"], "p99_ms": r["p99_ms"]} for r in table],
        "source_tags": tags,
        "total_games": len(rows),
    }
    with open(a.champion_out, "w") as fh:
        json.dump(champ, fh, indent=2)

    if not a.quiet:
        w = max(len(x) for x in players) + 1
        hdr = "  ".join(f"{o.replace('official_','o_').replace('pub_','p_')[:13]:>13s}" for o in players)
        print(f"{'player':{w}s} {'field':>7s} {'wtd':>7s}  {hdr}")
        for r in table:
            print(f"{r['candidate']:{w}s} {r['field_off_mirror']:>7.4f} {r['field_ladder_weighted']:>7.4f}  " +
                  "  ".join(f"{(r[o] or '-'):>13s}" for o in players))
        print(f"\npanel leader (may be ineligible) = {panel_leader} {table[0]['field_off_mirror']:.4f}")
        print(f"CHAMPION = {best['candidate']}  off-mirror {best['field_off_mirror']:.4f} "
              f"n={n_off} CI={ci}  ladder-weighted {best['field_ladder_weighted']:.4f}")
        if contenders:
            print(f"statistical contenders inside the interval: {contenders}")
        print(f"total games {len(rows)}  errors {sum(err.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
