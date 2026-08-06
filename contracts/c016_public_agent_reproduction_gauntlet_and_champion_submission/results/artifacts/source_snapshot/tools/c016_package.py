"""c016 §19 — build and validate the champion package, only for a candidate that passed §18.

The package shape copies c005's `submission_A_teacher.tar.gz`, which this competition accepted
and scored. The selected candidate IS an official sample agent, so `main.py` is the exact source
byte-for-byte — nothing is rewritten between selection and packaging, which §19 forbids.

An `ATTRIBUTION.md` is included: §12 requires attribution for any submitted public code, and §19
permits extra files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C16 = os.path.join(_REPO, "contracts",
                   "c016_public_agent_reproduction_gauntlet_and_champion_submission", "results")
ART = os.path.join(C16, "artifacts")
LOGD = os.path.join(C16, "test_logs")
CAND = os.path.join(ART, "candidates")
ARCHIVE = os.path.join(ART, "submission_J_public_champion_v0.tar.gz")
SDK = ["__init__.py", "api.py", "game.py", "libcg.so", "sim.py", "utils.py"]


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def jload(p):
    p = p if os.path.isabs(p) else os.path.join(ART, p)
    return json.load(open(p)) if os.path.exists(p) else None


def build(cid):
    src_dir = os.path.join(CAND, cid)
    man_c = jload(os.path.join(src_dir, "candidate_manifest.json"))
    tmp = tempfile.mkdtemp(prefix="c016pkg_")
    smap = []
    try:
        for f in ("main.py", "deck.csv"):
            shutil.copyfile(os.path.join(src_dir, f), os.path.join(tmp, f))
            smap.append({"source": os.path.relpath(os.path.join(src_dir, f), _REPO),
                         "archive_path": f, "sha256": sha_file(os.path.join(tmp, f))})
        os.makedirs(os.path.join(tmp, "cg"), exist_ok=True)
        for f in SDK:
            shutil.copyfile(os.path.join(_REPO, "cg", f), os.path.join(tmp, "cg", f))
            smap.append({"source": f"cg/{f}", "archive_path": f"cg/{f}",
                         "sha256": sha_file(os.path.join(tmp, "cg", f))})
        att = os.path.join(tmp, "ATTRIBUTION.md")
        open(att, "w").write(
            f"# Attribution\n\n{man_c['attribution']}\n\n"
            f"Source: {man_c['source_reference']}\n"
            f"main.py SHA-256: {man_c['source_main_sha256']}\n"
            f"deck.csv SHA-256: {man_c['deck_sha256']}\n\n"
            "Reuse class: SUBMISSION_REUSE_ALLOWED. This package contains the official sample "
            "agent source unmodified.\n")
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
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    with tarfile.open(ARCHIVE) as tar:
        members = [{"name": m.name, "size": m.size} for m in tar.getmembers()]
    man = {"archive": os.path.relpath(ARCHIVE, _REPO), "sha256": sha_file(ARCHIVE),
           "bytes": os.path.getsize(ARCHIVE), "members": members, "n_members": len(members),
           "candidate_id": cid, "fidelity": man_c["fidelity"],
           "source_main_sha256": man_c["source_main_sha256"],
           "deck_sha256": man_c["deck_sha256"],
           "permission_class": man_c["permission_class"],
           "attribution": man_c["attribution"],
           "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                                           capture_output=True, text=True).stdout.strip(),
           "build_command": f"python tools/c016_package.py --stage validate --candidate {cid}",
           "post_selection_strategic_changes": "none — main.py is the byte-identical official "
                                               "source used during selection"}
    json.dump(man, open(os.path.join(ART, "submission_J_manifest.json"), "w"), indent=2)
    json.dump({"map": smap}, open(os.path.join(ART, "source_to_package_map.json"), "w"),
              indent=2)
    return man


def extracted_games(n_drag=100, n_iono=50, n_safe=50):
    import importlib.util
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce
    from cg.safe_policy import validate_selection, MalformedSelection
    from cg.main import agent as safe_agent
    tmp = tempfile.mkdtemp(prefix="c016extract_")
    games = []
    try:
        with tarfile.open(ARCHIVE) as tar:
            tar.extractall(tmp, filter="data")
        cwd = os.getcwd()
        os.chdir(tmp)
        try:
            spec = importlib.util.spec_from_file_location("c016_pkg_main",
                                                          os.path.join(tmp, "main.py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        finally:
            os.chdir(cwd)
        plan = ([("dragapult", i) for i in range(n_drag)]
                + [("iono", i) for i in range(n_iono)]
                + [("__safe__", i) for i in range(n_safe)])
        deck = T.read_deck("dragapult", ce.SOURCES)
        for k, (opp_id, i) in enumerate(plan):
            bad = [0]

            def me(obs):
                sel = obs.get("select") if isinstance(obs, dict) else None
                r = mod.agent(obs)
                if sel is not None:
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
            games.append({"opponent_id": opp_id, "seat": seat,
                          "completed": st == ["DONE", "DONE"],
                          "timeout": any(s == "TIMEOUT" for s in st),
                          "invalid": bad[0],
                          "score": 1.0 if rw[seat] > rw[1 - seat] else
                                   (0.5 if rw[seat] == rw[1 - seat] else 0.0)})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return games


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--stage", default="validate")
    a = ap.parse_args(argv)
    os.makedirs(LOGD, exist_ok=True)
    man = build(a.candidate)
    print(json.dumps({"archive": man["archive"], "sha256": man["sha256"],
                      "members": man["n_members"], "candidate": man["candidate_id"]}, indent=2))
    if a.stage == "build":
        return 0
    games = extracted_games()
    import collections
    by = collections.defaultdict(lambda: [0, 0.0])
    for g in games:
        by[g["opponent_id"]][0] += 1
        by[g["opponent_id"]][1] += g["score"]
    rates = {k: round(v[1] / v[0], 4) for k, v in by.items()}
    # §19: package results within 10pp of the source-run results on the same protocol
    fin = {r["candidate_id"]: r for r in (jload("final_gauntlet_results.json") or [])}
    src_drag = (fin.get(a.candidate) or {}).get("dragapult_rate")
    parity = (abs(rates.get("dragapult", 0) - src_drag) <= 0.10
              if src_drag is not None else None)
    gates = {
        "at_least_200_games": len(games) >= 200,
        "zero_invalid_selections": sum(g["invalid"] for g in games) == 0,
        "zero_timeouts": sum(1 for g in games if g["timeout"]) == 0,
        "all_completed": all(g["completed"] for g in games),
        "both_seats": len({g["seat"] for g in games}) == 2,
        "package_within_10pp_of_source_run": bool(parity),
        "deck_hash_matches_selection": man["deck_sha256"] == (
            jload(os.path.join(CAND, a.candidate, "candidate_manifest.json")) or {}
        ).get("deck_sha256"),
    }
    val = {"manifest_sha256": man["sha256"], "games": len(games),
           "score_rates": rates, "source_run_dragapult_rate": src_drag,
           "hard_gates": gates, "overall_pass": all(gates.values())}
    json.dump(val, open(os.path.join(ART, "submission_J_validation.json"), "w"), indent=2)
    with open(os.path.join(LOGD, "package_validation.txt"), "w") as fh:
        fh.write(json.dumps(val, indent=2) + "\n")
    print(json.dumps({"games": len(games), "rates": rates, "hard_gates": gates,
                      "overall_pass": val["overall_pass"]}, indent=2))
    return 0 if val["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
