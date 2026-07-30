"""c022 — field scores when the excluded games are not spread evenly over the panel.

`deploy_k1` abandoned 5 of its 40 games. All five were `mega_lucario` games — the one matchup
the agent wins 40% of the time — so its reported field score of 0.0857 is a panel average over a
panel that is missing half of one opponent, and it is biased DOWNWARD by roughly 4 points.

The pooled rate `wins / scored` assumes exclusions are independent of the opponent. `D15`
established that abandonment here IS the stalemate rate, and stalemates are a property of the
matchup, so that assumption is exactly the one this environment breaks.

Two statistics fix it, and both are reported for every arm rather than only where the problem is
visible — a diagnostic that only runs where you already suspect trouble finds nothing new:

* **opponent-balanced field score** — the mean of the per-opponent rates, each computed on that
  opponent's own surviving games. Games are assigned round-robin, so equal weight per opponent
  is what the pooled rate was already trying to be. This is robust to exclusions concentrated in
  one matchup.
* **exclusion concentration** — the largest fraction of any single opponent's games that were
  excluded, and the share of ALL exclusions falling on one opponent. A concentration of 1.0
  means every excluded game came from the same matchup.

Neither replaces the pooled rate. Both are printed beside it, and where they disagree the
disagreement is the finding.
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import math
import os
import statistics
import sys
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C22 = os.path.join(_REPO, "contracts",
                   "c022_mcgs_multideterminization_and_faithful_byterl_reproduction", "results")


def wilson(k: float, n: int, z: float = 1.96):
    if n <= 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def analyse(games_path: str) -> Dict[str, Any]:
    rows = []
    with open(games_path) as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                try:
                    rows.append(json.loads(ln))
                except Exception:  # noqa: BLE001
                    pass
    if not rows:
        return {}
    # The tag must carry its DIRECTORY. Six files are named `ft_k1_games.jsonl` in this tree --
    # one live arm and five quarantined ones -- and a basename-only tag reported all six as `ft_k1`
    # with different numbers, which is unreadable and, worse, put superseded arms in an evidence
    # table. That is D12 (a stale arm surviving as evidence) reintroduced by a reporting tool.
    rel = os.path.relpath(games_path, C22)
    tag = os.path.basename(games_path).replace("_games.jsonl", "")
    parent = os.path.basename(os.path.dirname(games_path))
    tag = f"{parent}/{tag}"

    played = collections.Counter()
    scored = collections.Counter()
    wins = collections.defaultdict(float)
    for r in rows:
        o = r.get("opponent")
        played[o] += 1
        if r.get("score") is not None:
            scored[o] += 1
            wins[o] += float(r["score"])

    total_scored = sum(scored.values())
    total_wins = sum(wins.values())
    pooled = (total_wins / total_scored) if total_scored else None

    per_opp = {}
    rates = []
    for o in sorted(played):
        n, s = played[o], scored[o]
        rate = (wins[o] / s) if s else None
        per_opp[o] = {"played": n, "scored": s, "excluded": n - s,
                      "excluded_fraction": round((n - s) / n, 4) if n else None,
                      "rate": round(rate, 4) if rate is not None else None,
                      "wilson95": wilson(wins[o], s)}
        if rate is not None:
            rates.append(rate)

    excluded_total = sum(played.values()) - total_scored
    worst = max((v["excluded_fraction"] or 0.0) for v in per_opp.values()) if per_opp else 0.0
    biggest = max(((k, played[k] - scored[k]) for k in played), key=lambda kv: kv[1],
                  default=(None, 0))
    concentration = (biggest[1] / excluded_total) if excluded_total else None

    balanced = statistics.fmean(rates) if rates else None
    return {
        "tag": tag,
        "games": sum(played.values()),
        "scored": total_scored,
        "excluded": excluded_total,
        "field_score_pooled": round(pooled, 4) if pooled is not None else None,
        "field_score_opponent_balanced": round(balanced, 4) if balanced is not None else None,
        "difference_pp": (round(100 * (balanced - pooled), 2)
                          if (balanced is not None and pooled is not None) else None),
        "exclusion": {
            "total": excluded_total,
            "worst_opponent_excluded_fraction": round(worst, 4),
            "share_of_exclusions_on_one_opponent": (round(concentration, 4)
                                                    if concentration is not None else None),
            "most_excluded_opponent": biggest[0] if biggest[1] else None,
        },
        "per_opponent": per_opp,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(C22, "mcgs", "FIELD_BALANCE.md"))
    ap.add_argument("--out-json", default=os.path.join(C22, "mcgs", "field_balance.json"))
    a = ap.parse_args(argv)

    paths = sorted(glob.glob(os.path.join(C22, "**", "*_games.jsonl"), recursive=True))
    # Quarantined arms are quarantined. `results/failures/superseded/` holds runs that were
    # discarded for a recorded reason, and an evidence table that silently includes them is the
    # defect the quarantine exists to prevent.
    dropped = [p for p in paths if os.sep + "superseded" + os.sep in p
               or os.sep + "failures" + os.sep in p]
    paths = [p for p in paths if p not in dropped]
    arms = [x for x in (analyse(p) for p in paths) if x and x["games"]]
    arms.sort(key=lambda x: x["tag"])
    print(f"[balance] {len(arms)} live arms; {len(dropped)} quarantined files skipped")

    L = ["# Field scores, and where the excluded games went", "",
         "The pooled rate `wins / scored` assumes exclusions are independent of the opponent. "
         "`D15` established that abandonment in this environment IS the stalemate rate, and a "
         "stalemate is a property of the MATCHUP — so that assumption is precisely the one this "
         "environment breaks.", "",
         "| arm | games | scored | excluded | pooled | opponent-balanced | Δ | worst opponent "
         "excluded | exclusions on one opponent |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    _ = dropped
    for x in arms:
        e = x["exclusion"]
        L.append(
            f"| `{x['tag']}` | {x['games']} | {x['scored']} | {x['excluded']} | "
            f"{x['field_score_pooled']} | {x['field_score_opponent_balanced']} | "
            f"{x['difference_pp']} pp | {e['worst_opponent_excluded_fraction']} | "
            f"{e['share_of_exclusions_on_one_opponent'] if e['total'] else '—'} |")
    L += ["", "A `Δ` near zero means the exclusions were spread evenly and the pooled rate is "
              "safe. A large `Δ` with exclusions concentrated on one opponent means the pooled "
              "rate is an average over a panel that is missing part of itself.", ""]

    flagged = [x for x in arms
               if (x["exclusion"]["worst_opponent_excluded_fraction"] or 0) >= 0.2
               and x["excluded"] >= 3]
    if flagged:
        L += ["## Arms where the panel is unbalanced by exclusion", ""]
        for x in flagged:
            e = x["exclusion"]
            L.append(f"### `{x['tag']}`")
            L.append("")
            L.append(f"{x['excluded']} of {x['games']} games excluded, "
                     f"{e['share_of_exclusions_on_one_opponent']:.0%} of them against "
                     f"`{e['most_excluded_opponent']}`, which lost "
                     f"{e['worst_opponent_excluded_fraction']:.0%} of its games.")
            L.append("")
            L.append("| opponent | played | scored | excluded | rate |")
            L.append("|---|---:|---:|---:|---:|")
            for o, v in x["per_opponent"].items():
                L.append(f"| {o} | {v['played']} | {v['scored']} | {v['excluded']} | "
                         f"{v['rate']} |")
            L.append("")
            L.append(f"Pooled **{x['field_score_pooled']}**, opponent-balanced "
                     f"**{x['field_score_opponent_balanced']}** "
                     f"({x['difference_pp']} pp). The balanced figure is the one to read.")
            L.append("")
    else:
        L += ["No arm has exclusions concentrated enough to move its field score.", ""]

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out_json, "w") as fh:
        json.dump({"arms": arms}, fh, indent=2)
    with open(a.out, "w") as fh:
        fh.write("\n".join(L) + "\n")

    for x in arms:
        e = x["exclusion"]
        flag = " <-- UNBALANCED" if x in flagged else ""
        print(f"{x['tag']:22s} pooled={x['field_score_pooled']} "
              f"balanced={x['field_score_opponent_balanced']} "
              f"delta={x['difference_pp']}pp excl={x['excluded']}/{x['games']} "
              f"worst_opp={e['worst_opponent_excluded_fraction']}{flag}")
    print(f"wrote {a.out}\nwrote {a.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
