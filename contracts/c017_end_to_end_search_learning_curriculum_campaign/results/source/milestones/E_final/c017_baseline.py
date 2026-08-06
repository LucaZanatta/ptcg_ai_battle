"""c017 §9 — reverify, package, validate and automatically submit the c016 baseline.

The baseline is the exact c016 `official_mega_lucario` candidate. §8 fixes its hashes in advance,
so this module re-derives them from the files on disk rather than reading c016's manifest: a
manifest can be wrong, the bytes cannot.

Nothing about the agent is modified before submission (§8). The package is the official sample
source verbatim plus its deck, the SDK, and the attribution §12-of-c016 requires.

c016 measured this agent at 0.520 against Dragapult over 400 independent-seed games and 0.614
across the official field — better than the Dragapult control on all three official opponents. It
was not submitted there because it failed two *base conditions* (safe-control 0.833 < 0.90,
vs-c014 0.625 < 0.65). c017 §8 fixes it as the campaign baseline and §9 requires submitting it,
so those conditions are not re-litigated here; they are recorded as known limitations.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from zoneinfo import ZoneInfo

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C17 = os.path.join(_REPO, "contracts", "c017_end_to_end_search_learning_curriculum_campaign",
                   "results")
PKG_DIR = os.path.join(C17, "packages", "baseline")
PROBE = os.path.join(C17, "probes", "P00_baseline_submission")
SUBS = os.path.join(C17, "submissions")
ARCHIVE = os.path.join(C17, "packages",
                       "submission_J_official_mega_lucario_baseline.tar.gz")

C016_CAND = os.path.join(_REPO, "contracts",
                         "c016_public_agent_reproduction_gauntlet_and_champion_submission",
                         "results", "artifacts", "candidates", "official_mega_lucario")
EXPECT_MAIN = "ab8563b67b88b3666c2ff9c308505085a84fdac676c194c5b484d8544478c3b2"
EXPECT_DECK = "406e2e9bd6ae82b8008b16ee64ffcbb58e4a50cd6bc36e33ae655456c6b9afee"
SDK = ["__init__.py", "api.py", "game.py", "libcg.so", "sim.py", "utils.py"]
COMPETITION = "pokemon-tcg-ai-battle"
KAGGLE = os.path.join(_REPO, ".venv/bin/kaggle")
POLL_MAX, POLL_S = 20, 30


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def reverify() -> dict:
    """§8: locate from c016 raw artifacts and reverify all hashes from the bytes."""
    main_p = os.path.join(C016_CAND, "main.py")
    deck_p = os.path.join(C016_CAND, "deck.csv")
    man = json.load(open(os.path.join(C016_CAND, "candidate_manifest.json")))
    got_main, got_deck = sha_file(main_p), sha_file(deck_p)
    checks = {
        "main_hash_matches_contract_expected": got_main == EXPECT_MAIN,
        "deck_hash_matches_contract_expected": got_deck == EXPECT_DECK,
        "main_hash_matches_c016_manifest": got_main == man["source_main_sha256"],
        "deck_hash_matches_c016_manifest": got_deck == man["deck_sha256"],
        "fidelity_is_exact": man["fidelity"] == "EXACT",
        "permission_allows_submission":
            man["permission_class"] == "SUBMISSION_REUSE_ALLOWED",
        "deck_is_60_cards": sum(1 for l in open(deck_p) if l.strip()) == 60,
    }
    return {"checks": checks, "all_pass": all(checks.values()),
            "main_sha256": got_main, "deck_sha256": got_deck,
            "attribution": man["attribution"],
            "source_reference": man["source_reference"],
            "c016_measured": {"vs_dragapult_confirm": 0.520, "field_mean_confirm": 0.614,
                              "note": "c016 independent-seed confirmation, 400/600 games"}}


def build(rv) -> dict:
    os.makedirs(os.path.dirname(ARCHIVE), exist_ok=True)
    os.makedirs(PKG_DIR, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="c017base_")
    smap = []
    try:
        for f in ("main.py", "deck.csv"):
            shutil.copyfile(os.path.join(C016_CAND, f), os.path.join(tmp, f))
            smap.append({"source": os.path.relpath(os.path.join(C016_CAND, f), _REPO),
                         "archive_path": f, "sha256": sha_file(os.path.join(tmp, f))})
        os.makedirs(os.path.join(tmp, "cg"), exist_ok=True)
        for f in SDK:
            shutil.copyfile(os.path.join(_REPO, "cg", f), os.path.join(tmp, "cg", f))
            smap.append({"source": f"cg/{f}", "archive_path": f"cg/{f}",
                         "sha256": sha_file(os.path.join(tmp, "cg", f))})
        att = os.path.join(tmp, "ATTRIBUTION.md")
        open(att, "w").write(
            f"# Attribution\n\n{rv['attribution']}\n\nSource: {rv['source_reference']}\n"
            f"main.py SHA-256: {rv['main_sha256']}\ndeck.csv SHA-256: {rv['deck_sha256']}\n\n"
            "Reuse class: SUBMISSION_REUSE_ALLOWED (recorded by c016). This package contains "
            "the official sample agent source unmodified.\n")
        smap.append({"source": "generated", "archive_path": "ATTRIBUTION.md",
                     "sha256": sha_file(att)})
        if os.path.exists(ARCHIVE):
            os.remove(ARCHIVE)
        with tarfile.open(ARCHIVE, "w:gz") as tar:
            tar.add(os.path.join(tmp, "main.py"), arcname="main.py")
            tar.add(os.path.join(tmp, "deck.csv"), arcname="deck.csv")
            tar.add(att, arcname="ATTRIBUTION.md")
            tar.add(os.path.join(tmp, "cg"), arcname="cg", recursive=False)
            for f in SDK:
                tar.add(os.path.join(tmp, "cg", f), arcname=f"cg/{f}")
        for f in ("main.py", "deck.csv"):
            shutil.copyfile(os.path.join(tmp, f), os.path.join(PKG_DIR, f))
        shutil.copyfile(att, os.path.join(PKG_DIR, "ATTRIBUTION.md"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    with tarfile.open(ARCHIVE) as tar:
        members = [{"name": m.name, "size": m.size} for m in tar.getmembers()]
    man = {"archive": os.path.relpath(ARCHIVE, _REPO), "sha256": sha_file(ARCHIVE),
           "bytes": os.path.getsize(ARCHIVE), "members": members, "n_members": len(members),
           "candidate_id": "official_mega_lucario", "fidelity": "EXACT",
           "source_main_sha256": rv["main_sha256"], "deck_sha256": rv["deck_sha256"],
           "permission_class": "SUBMISSION_REUSE_ALLOWED",
           "attribution": rv["attribution"],
           "source_to_package_map": smap,
           "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                                           capture_output=True, text=True).stdout.strip(),
           "strategically_modified_before_submission": False}
    json.dump(man, open(os.path.join(PKG_DIR, "baseline_manifest.json"), "w"), indent=2)
    return man


def clean_validate(n_drag=30, n_safe=25) -> dict:
    """§9: >=50 both-seat games vs Dragapult and safe control combined, from clean extraction."""
    import importlib.util
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce
    from cg.safe_policy import validate_selection, MalformedSelection
    from cg.main import agent as safe_agent
    tmp = tempfile.mkdtemp(prefix="c017extract_")
    games = []
    try:
        with tarfile.open(ARCHIVE) as tar:
            tar.extractall(tmp, filter="data")
        cwd = os.getcwd()
        os.chdir(tmp)
        try:
            spec = importlib.util.spec_from_file_location("c017_base_main",
                                                          os.path.join(tmp, "main.py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        finally:
            os.chdir(cwd)
        deck = T.read_deck("dragapult", ce.SOURCES)
        plan = [("dragapult", i) for i in range(n_drag)] + [("__safe__", i)
                                                            for i in range(n_safe)]
        for opp_id, i in plan:
            bad = [0]
            lat = []

            def me(obs):
                sel = obs.get("select") if isinstance(obs, dict) else None
                t0 = time.perf_counter()
                r = mod.agent(obs)
                if sel is not None:
                    lat.append((time.perf_counter() - t0) * 1000)
                    try:
                        validate_selection(list(r), len(sel["option"]), sel["minCount"],
                                           sel["maxCount"])
                    except MalformedSelection:
                        bad[0] += 1
                return r
            if opp_id == "__safe__":
                def other(o):
                    sel = o.get("select") if isinstance(o, dict) else None
                    return list(deck) if sel is None else safe_agent(o)
            else:
                opp = T.make_fresh(opp_id, ce.SOURCES)
                other = lambda o: opp(o)  # noqa: E731
            seat = i % 2
            ag = [me, other] if seat == 0 else [other, me]
            env = make("cabt")
            env.run(ag)
            last = env.steps[-1]
            st = [s.status for s in last]
            rw = [s.reward for s in last]
            lat.sort()
            games.append({"opponent_id": opp_id, "seat": seat, "statuses": st,
                          "completed": st == ["DONE", "DONE"],
                          "timeout": any(s == "TIMEOUT" for s in st),
                          "invalid": bad[0],
                          "latency_p99_ms": lat[max(0, int(len(lat) * .99) - 1)] if lat else None,
                          "score": 1.0 if rw[seat] > rw[1 - seat] else
                                   (0.5 if rw[seat] == rw[1 - seat] else 0.0)})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    import collections
    by = collections.defaultdict(lambda: [0, 0.0])
    for g in games:
        by[g["opponent_id"]][0] += 1
        by[g["opponent_id"]][1] += g["score"]
    lats = [g["latency_p99_ms"] for g in games if g["latency_p99_ms"] is not None]
    gates = {
        "at_least_50_games": len(games) >= 50,
        "zero_invalid_actions": sum(g["invalid"] for g in games) == 0,
        "zero_exceptions": all(g["completed"] or g["timeout"] for g in games),
        "zero_timeouts": sum(1 for g in games if g["timeout"]) == 0,
        "all_completed": all(g["completed"] for g in games),
        "both_seats": len({g["seat"] for g in games}) == 2,
        "entrypoint_and_deck_verified": True,
    }
    return {"games": len(games), "score_rates": {k: round(v[1] / v[0], 4)
                                                 for k, v in by.items()},
            "worst_p99_ms": max(lats) if lats else None,
            "hard_gates": gates, "all_gates_pass": all(gates.values()),
            "raw": games}


def kag(*a, timeout=300):
    try:
        r = subprocess.run([KAGGLE, *a], capture_output=True, text=True, timeout=timeout)
        return r
    except Exception as e:  # noqa: BLE001
        class R:
            returncode, stdout, stderr = -1, "", repr(e)[:300]
        return R()


def submit(man, val) -> dict:
    r = kag("competitions", "submissions", COMPETITION, "-v")
    before = list(csv.DictReader(io.StringIO(r.stdout))) if r.returncode == 0 else []
    before_refs = {x.get("ref") for x in before}
    short = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=_REPO,
                           capture_output=True, text=True).stdout.strip()
    desc = f"c017 baseline official_mega_lucario EXACT {short}"
    if any((x.get("description") or "").strip() == desc for x in before):
        return {"kaggle_upload": "BLOCKED_DUPLICATE", "description": desc,
                "submission_ref": None}
    cmd = [KAGGLE, "competitions", "submit", COMPETITION,
           "-f", os.path.relpath(ARCHIVE, _REPO), "-m", desc]
    t0 = datetime.datetime.now(datetime.timezone.utc)
    sub = kag(*cmd[1:], timeout=900)
    snaps = []
    ref = row = status = score = None
    for attempt in range(1, POLL_MAX + 1):
        rr = kag("competitions", "submissions", COMPETITION, "-v")
        rows = list(csv.DictReader(io.StringIO(rr.stdout))) if rr.returncode == 0 else []
        new = [x for x in rows if x.get("ref") not in before_refs]
        cand = [x for x in new if (x.get("description") or "").strip() == desc] or new
        if cand:
            row = cand[0]
            ref = row.get("ref")
            status = (row.get("status") or "").replace("SubmissionStatus.", "")
            score = row.get("publicScore") or None
        snaps.append({"attempt": attempt,
                      "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      "ref": ref, "status": status, "publicScore": score})
        if ref and status in ("COMPLETE", "ERROR", "CANCELLED"):
            break
        if attempt < POLL_MAX:
            time.sleep(POLL_S)
    with open(os.path.join(SUBS, "status_snapshots.jsonl"), "a") as fh:
        for s in snaps:
            fh.write(json.dumps({"stage": "baseline", **s}) + "\n")
    doc = {"stage": "baseline", "kaggle_upload": "SUBMITTED" if (sub.returncode == 0 and ref)
           else "FAILED", "competition": COMPETITION, "description": desc,
           "archive": os.path.relpath(ARCHIVE, _REPO), "archive_sha256": man["sha256"],
           "submitted_utc": t0.isoformat(),
           "submitted_europe_rome": t0.astimezone(ZoneInfo("Europe/Rome")).isoformat(),
           "submission_ref": ref, "submission_row": row,
           "status": status or ("PENDING" if ref else None),
           "public_score": score,
           "public_score_note": "the public score is a LIVE ladder rating; this is a "
                                "timestamped reading, not a final result",
           "polls": len(snaps), "submit_returncode": sub.returncode,
           "stdout": sub.stdout[:1500], "stderr": sub.stderr[:1500],
           "permission_class": man["permission_class"], "attribution": man["attribution"]}
    json.dump(doc, open(os.path.join(SUBS, "baseline_submission.json"), "w"), indent=2)
    return doc


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args(argv)
    for d in (PKG_DIR, PROBE, SUBS):
        os.makedirs(d, exist_ok=True)

    rv = reverify()
    man = build(rv)
    val = clean_validate()
    probe = {"probe_id": "P00_baseline_submission",
             "status": "PASS" if (rv["all_pass"] and val["all_gates_pass"]) else "FAIL_TAINTED",
             "reverification": rv, "package": {k: man[k] for k in
                                               ("sha256", "bytes", "n_members")},
             "clean_extraction_validation": {k: val[k] for k in
                                             ("games", "score_rates", "worst_p99_ms",
                                              "hard_gates", "all_gates_pass")},
             "trust_status": "TRUSTED" if (rv["all_pass"] and val["all_gates_pass"])
             else "NON_SUBMITTABLE",
             "tainted_by": []}
    json.dump(probe, open(os.path.join(PROBE, "probe.json"), "w"), indent=2, default=str)
    json.dump(val["raw"], open(os.path.join(PROBE, "clean_extraction_games.json"), "w"),
              indent=2)
    print(json.dumps({"reverify_all_pass": rv["all_pass"],
                      "package_sha256": man["sha256"][:16],
                      "validation_gates": val["hard_gates"],
                      "score_rates": val["score_rates"],
                      "probe": probe["status"]}, indent=2))
    if not a.execute:
        return 0
    if not (rv["all_pass"] and val["all_gates_pass"]):
        print("BLOCKED: reverification or validation gate failed; not uploading")
        return 1
    doc = submit(man, val)
    print(json.dumps({k: doc[k] for k in ("kaggle_upload", "submission_ref", "status",
                                          "public_score", "polls")}, indent=2))
    return 0 if doc["submission_ref"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
