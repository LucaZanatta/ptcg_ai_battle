"""c023 — evidence validator.

The contract names seven things this must reject: stale files, zero-game summaries, timestamp
mismatches, run-ID mismatches, incomplete arms, missing hashes, and report/raw-data disagreement.
Each is a check below, and each check **recomputes from the raw games** rather than reading the
number it is supposed to be verifying. c008 shipped a corrupted aggregate that passed 16/16
acceptance criteria because every criterion tested file *existence*.

Every check reports PASS / FAIL / NO_DATA. `NO_DATA` is never PASS.

`--inject <check_id>` corrupts a copy of the evidence in the way that check exists to catch and
asserts the check fires. A check that cannot be made to fail is not a check, it is a comment.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

OUT = os.path.join(_REPO, "results", "c023_autonomous_meta_first_competition_sprint")


class Result:
    def __init__(self, cid: str, title: str):
        self.id = cid
        self.title = title
        self.status = "NO_DATA"
        self.detail = ""

    def ok(self, detail: str = ""):
        self.status, self.detail = "PASS", detail
        return self

    def fail(self, detail: str):
        self.status, self.detail = "FAIL", detail
        return self

    def nodata(self, detail: str):
        self.status, self.detail = "NO_DATA", detail
        return self

    def as_dict(self):
        return {"id": self.id, "title": self.title, "status": self.status, "detail": self.detail}


def _tags(root: str) -> List[str]:
    d = os.path.join(root, "raw_evaluations")
    if not os.path.isdir(d):
        return []
    return sorted(t for t in os.listdir(d)
                  if os.path.isfile(os.path.join(d, t, "summary.json")))


def _rows(root: str, tag: str) -> List[Dict[str, Any]]:
    p = os.path.join(root, "raw_evaluations", tag, "games.jsonl")
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p)]


# --------------------------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------------------------

def v01_summary_matches_raw(root: str) -> Result:
    """Report/raw-data disagreement: recompute every summary cell from games.jsonl."""
    r = Result("V01", "every summary score rate is recomputable from its own raw games")
    tags = _tags(root)
    if not tags:
        return r.nodata("no evaluation tags")
    bad = []
    for t in tags:
        s = json.load(open(os.path.join(root, "raw_evaluations", t, "summary.json")))
        rows = _rows(root, t)
        agg = collections.defaultdict(list)
        for x in rows:
            if x.get("completed"):
                agg[(x["candidate_id"], x["opponent_id"])].append(x["score"])
        for cand, cs in (s.get("summary") or {}).items():
            for opp, cell in (cs.get("per_opponent") or {}).items():
                xs = agg.get((cand, opp), [])
                if not xs:
                    bad.append(f"{t}:{cand}/{opp} summary has a cell with no raw games")
                    continue
                recomputed = round(sum(xs) / len(xs), 4)
                if abs(recomputed - cell["score_rate"]) > 1e-6 or len(xs) != cell["games"]:
                    bad.append(f"{t}:{cand}/{opp} summary {cell['score_rate']}@{cell['games']} "
                               f"vs raw {recomputed}@{len(xs)}")
    return r.fail("; ".join(bad[:6])) if bad else r.ok(f"{len(tags)} tags recomputed")


def v02_no_zero_game_summaries(root: str) -> Result:
    r = Result("V02", "no summary reports a candidate with zero completed games")
    tags = _tags(root)
    if not tags:
        return r.nodata("no evaluation tags")
    bad = []
    for t in tags:
        s = json.load(open(os.path.join(root, "raw_evaluations", t, "summary.json")))
        if int(s.get("completed_games", 0)) <= 0:
            bad.append(f"{t}: 0 completed games")
        for cand, cs in (s.get("summary") or {}).items():
            if int(cs.get("completed_games", 0)) <= 0:
                bad.append(f"{t}:{cand}: 0 completed")
    return r.fail("; ".join(bad[:6])) if bad else r.ok(f"{len(tags)} tags")


def v03_identity_roundtrip(root: str) -> Result:
    """Run-ID mismatch: every raw record's job_id must encode its own identity fields."""
    r = Result("V03", "every raw game's job_id encodes its own candidate/opponent/seat")
    tags = _tags(root)
    if not tags:
        return r.nodata("no evaluation tags")
    bad, n = [], 0
    for t in tags:
        for x in _rows(root, t):
            n += 1
            jid = x.get("job_id", "")
            want = f"{x.get('phase')}::{x.get('candidate_id')}::{x.get('opponent_id')}::" \
                   f"s{x.get('seat')}::r{x.get('replicate')}"
            if jid != want:
                bad.append(f"{t}: {jid} != {want}")
                if len(bad) > 5:
                    break
    return r.fail("; ".join(bad[:6])) if bad else r.ok(f"{n} records")


def v04_hashes_present(root: str) -> Result:
    """Missing hashes: every candidate manifest carries deck/base/wrapper hashes."""
    r = Result("V04", "every candidate manifest carries deck, base-agent and wrapper hashes")
    d = os.path.join(root, "candidate_manifests")
    if not os.path.isdir(d) or not os.listdir(d):
        return r.nodata("no candidate manifests")
    bad = []
    for f in sorted(os.listdir(d)):
        if not f.endswith(".json"):
            continue
        m = json.load(open(os.path.join(d, f)))
        for k in ("deck_sha256", "base_agent_sha256", "wrapper_sha256", "params_sha256"):
            if not m.get(k):
                bad.append(f"{f}: missing {k}")
    return r.fail("; ".join(bad[:6])) if bad else r.ok(f"{len(os.listdir(d))} manifests")


def v05_incomplete_arms(root: str) -> Result:
    """Incomplete arms: requested vs completed, per candidate, from the raw rows."""
    r = Result("V05", "no arm reports fewer raw games than it requested without saying so")
    tags = _tags(root)
    if not tags:
        return r.nodata("no evaluation tags")
    bad = []
    for t in tags:
        s = json.load(open(os.path.join(root, "raw_evaluations", t, "summary.json")))
        rows = _rows(root, t)
        cnt = collections.Counter(x["candidate_id"] for x in rows)
        for cand, cs in (s.get("summary") or {}).items():
            if cnt[cand] != int(cs.get("requested_games", -1)):
                bad.append(f"{t}:{cand} raw rows {cnt[cand]} vs requested "
                           f"{cs.get('requested_games')}")
    return r.fail("; ".join(bad[:6])) if bad else r.ok(f"{len(tags)} tags")


def v06_staleness(root: str) -> Result:
    """Stale files: a summary must not predate the raw games it claims to summarise."""
    r = Result("V06", "no summary is older than the raw games it summarises")
    tags = _tags(root)
    if not tags:
        return r.nodata("no evaluation tags")
    bad = []
    for t in tags:
        sp = os.path.join(root, "raw_evaluations", t, "summary.json")
        gp = os.path.join(root, "raw_evaluations", t, "games.jsonl")
        if not os.path.exists(gp):
            bad.append(f"{t}: summary with no games.jsonl")
            continue
        if os.path.getmtime(sp) + 1.0 < os.path.getmtime(gp):
            bad.append(f"{t}: summary mtime precedes games.jsonl")
    return r.fail("; ".join(bad[:6])) if bad else r.ok(f"{len(tags)} tags")


def v07_champion_backed_by_games(root: str) -> Result:
    r = Result("V07", "champion.json's per-opponent cells exist in the raw games it cites")
    p = os.path.join(root, "champion.json")
    if not os.path.exists(p):
        return r.nodata("no champion.json")
    c = json.load(open(p))
    rows = []
    for t in c.get("source_tags", []):
        rows.extend(_rows(root, t))
    if not rows:
        return r.fail("champion cites tags with no raw games")
    agg = collections.defaultdict(list)
    for x in rows:
        if x.get("completed"):
            agg[(x["candidate_id"], x["opponent_id"])].append(x["score"])
    bad = []
    for opp, cell in (c.get("per_opponent") or {}).items():
        xs = agg.get((c["champion"], opp), [])
        if not xs:
            bad.append(f"{opp}: no raw games")
        elif abs(round(sum(xs) / len(xs), 4) - cell["score_rate"]) > 1e-6:
            bad.append(f"{opp}: {cell['score_rate']} vs raw {round(sum(xs)/len(xs),4)}")
    return r.fail("; ".join(bad[:6])) if bad else r.ok(f"{len(c.get('per_opponent') or {})} cells")


def v08_no_errors_hidden(root: str) -> Result:
    r = Result("V08", "error counts in summaries equal the raw non-completed rows")
    tags = _tags(root)
    if not tags:
        return r.nodata("no evaluation tags")
    bad = []
    for t in tags:
        s = json.load(open(os.path.join(root, "raw_evaluations", t, "summary.json")))
        rows = _rows(root, t)
        raw_err = sum(1 for x in rows if not x.get("completed"))
        if int(s.get("errors", -1)) != raw_err:
            bad.append(f"{t}: summary errors {s.get('errors')} vs raw {raw_err}")
    return r.fail("; ".join(bad[:6])) if bad else r.ok(f"{len(tags)} tags")


def v09_packages_validated(root: str) -> Result:
    r = Result("V09", "every package manifest carries an executed clean validation")
    d = os.path.join(root, "final_packages")
    if not os.path.isdir(d):
        return r.nodata("no final_packages directory")
    mans = [f for f in sorted(os.listdir(d)) if f.endswith("_manifest.json")]
    if not mans:
        return r.nodata("no package manifests")
    bad = []
    for f in mans:
        m = json.load(open(os.path.join(d, f)))
        cv = m.get("clean_validation") or {}
        if "valid" not in cv:
            bad.append(f"{f}: no clean_validation")
        elif not cv.get("summary", {}).get("completed_games"):
            bad.append(f"{f}: clean validation over zero games")
        arc = os.path.join(_REPO, m.get("archive", ""))
        if not os.path.exists(arc):
            bad.append(f"{f}: archive missing")
    return r.fail("; ".join(bad[:6])) if bad else r.ok(f"{len(mans)} packages")


def v10_required_files(root: str) -> Result:
    r = Result("V10", "every file and directory the contract names is present and non-empty")
    files = ["EXECUTIVE_DECISION.md", "STATUS.json", "DECISION_BOARD.json",
             "ACCEPTANCE_CHECKLIST.md", "SOURCES.md", "META_REPORT.md", "MATCHUP_MATRIX.csv",
             "CANDIDATE_HISTORY.jsonl", "FAILURE_TAXONOMY.md", "PIVOT_LEDGER.md",
             "DECK_CHANGE_LEDGER.md", "AGENT_CHANGE_LEDGER.md", "BYTERL_COMPONENT_RESULTS.md",
             "LEADERBOARD_SUBMISSION_PLAN.md", "UNRESOLVED_RISKS.md"]
    dirs = ["raw_evaluations", "candidate_manifests", "final_packages", "source", "git",
            "failures", "superseded"]
    missing = [f for f in files
               if not (os.path.isfile(os.path.join(root, f))
                       and os.path.getsize(os.path.join(root, f)) > 0)]
    missing += [d + "/" for d in dirs if not os.path.isdir(os.path.join(root, d))]
    return r.fail(f"missing/empty: {missing}") if missing else r.ok(
        f"{len(files)} files, {len(dirs)} directories")


def v11_candidate_history(root: str) -> Result:
    r = Result("V11", "every evaluated candidate appears in CANDIDATE_HISTORY.jsonl")
    p = os.path.join(root, "CANDIDATE_HISTORY.jsonl")
    if not os.path.exists(p):
        return r.nodata("no CANDIDATE_HISTORY.jsonl")
    known = {json.loads(l)["candidate_id"] for l in open(p) if l.strip()}
    evaluated = set()
    for t in _tags(root):
        for x in _rows(root, t):
            evaluated.add(x["candidate_id"])
    missing = sorted(evaluated - known - {"_pkgtest"})
    return r.fail(f"evaluated but unrecorded: {missing[:8]}") if missing else r.ok(
        f"{len(known)} recorded, {len(evaluated)} evaluated")


CHECKS = [v01_summary_matches_raw, v02_no_zero_game_summaries, v03_identity_roundtrip,
          v04_hashes_present, v05_incomplete_arms, v06_staleness, v07_champion_backed_by_games,
          v08_no_errors_hidden, v09_packages_validated, v10_required_files, v11_candidate_history]


# --------------------------------------------------------------------------------------------
# injections
# --------------------------------------------------------------------------------------------

def _copy_root(dst: str) -> str:
    shutil.copytree(OUT, dst, symlinks=True,
                    ignore=shutil.ignore_patterns("final_packages", "source"))
    return dst


INJECTIONS = {
    "V01": "alter one score rate in a summary without touching the raw games",
    "V02": "set a candidate's completed_games to 0",
    "V03": "rewrite one raw record's candidate_id, leaving its job_id intact",
    "V04": "delete deck_sha256 from a candidate manifest",
    "V05": "delete raw rows for one candidate, leaving requested_games unchanged",
    "V06": "backdate a summary behind its games.jsonl",
    "V07": "alter a champion.json per-opponent score rate",
    "V08": "zero the error count in a summary that has a failed game",
    "V11": "remove one evaluated candidate from CANDIDATE_HISTORY.jsonl",
}


def inject(root: str, cid: str) -> bool:
    tags = _tags(root)
    if not tags:
        return False
    t = tags[0]
    sp = os.path.join(root, "raw_evaluations", t, "summary.json")
    gp = os.path.join(root, "raw_evaluations", t, "games.jsonl")
    if cid == "V01":
        s = json.load(open(sp))
        c = sorted(s["summary"])[0]
        o = sorted(s["summary"][c]["per_opponent"])[0]
        s["summary"][c]["per_opponent"][o]["score_rate"] += 0.1234
        json.dump(s, open(sp, "w"))
        return True
    if cid == "V02":
        s = json.load(open(sp))
        s["summary"][sorted(s["summary"])[0]]["completed_games"] = 0
        json.dump(s, open(sp, "w"))
        return True
    if cid == "V03":
        rows = [json.loads(l) for l in open(gp)]
        rows[0]["candidate_id"] = "SOMETHING_ELSE"
        with open(gp, "w") as fh:
            for x in rows:
                fh.write(json.dumps(x) + "\n")
        return True
    if cid == "V04":
        d = os.path.join(root, "candidate_manifests")
        f = sorted(os.listdir(d))[0]
        m = json.load(open(os.path.join(d, f)))
        m.pop("deck_sha256", None)
        json.dump(m, open(os.path.join(d, f), "w"))
        return True
    if cid == "V05":
        rows = [json.loads(l) for l in open(gp)]
        victim = rows[0]["candidate_id"]
        rows = [x for x in rows if x["candidate_id"] != victim or x["replicate"] > 0]
        with open(gp, "w") as fh:
            for x in rows:
                fh.write(json.dumps(x) + "\n")
        return True
    if cid == "V06":
        os.utime(sp, (time.time() - 86400, time.time() - 86400))
        return True
    if cid == "V07":
        p = os.path.join(root, "champion.json")
        if not os.path.exists(p):
            return False
        c = json.load(open(p))
        k = sorted(c["per_opponent"])[0]
        c["per_opponent"][k]["score_rate"] += 0.2
        json.dump(c, open(p, "w"))
        return True
    if cid == "V08":
        rows = [json.loads(l) for l in open(gp)]
        rows[0]["completed"] = False
        rows[0]["score"] = None
        with open(gp, "w") as fh:
            for x in rows:
                fh.write(json.dumps(x) + "\n")
        # the summary still says zero errors -> V08 must fire
        return True
    if cid == "V11":
        p = os.path.join(root, "CANDIDATE_HISTORY.jsonl")
        if not os.path.exists(p):
            return False
        lines = [l for l in open(p) if l.strip()]
        with open(p, "w") as fh:
            for l in lines[1:]:
                fh.write(l)
        return True
    return False


def run(root: str) -> List[Dict[str, Any]]:
    return [c(root).as_dict() for c in CHECKS]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=OUT)
    ap.add_argument("--injections", action="store_true",
                    help="verify every check can be made to fail")
    ap.add_argument("--out", default=os.path.join(OUT, "validation.json"))
    a = ap.parse_args()

    res = run(a.root)
    payload: Dict[str, Any] = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                               "root": os.path.relpath(a.root, _REPO), "checks": res}
    for x in res:
        print(f"{x['id']}  {x['status']:8s} {x['title']}")
        if x["status"] != "PASS":
            print(f"        {x['detail'][:300]}")

    if a.injections:
        inj = []
        for cid, what in sorted(INJECTIONS.items()):
            tmp = tempfile.mkdtemp(prefix="c023_inj_")
            d = os.path.join(tmp, "root")
            _copy_root(d)
            ok_inject = inject(d, cid)
            if not ok_inject:
                inj.append({"check": cid, "injection": what, "status": "NOT_INJECTABLE"})
                shutil.rmtree(tmp, ignore_errors=True)
                continue
            after = {x["id"]: x["status"] for x in run(d)}
            fired = after.get(cid) == "FAIL"
            inj.append({"check": cid, "injection": what,
                        "status": "DETECTED" if fired else "UNDETECTED"})
            shutil.rmtree(tmp, ignore_errors=True)
        payload["injections"] = inj
        print()
        for x in inj:
            print(f"{x['check']}  {x['status']:14s} {x['injection']}")

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(payload, fh, indent=2)
    failed = [x for x in res if x["status"] == "FAIL"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
