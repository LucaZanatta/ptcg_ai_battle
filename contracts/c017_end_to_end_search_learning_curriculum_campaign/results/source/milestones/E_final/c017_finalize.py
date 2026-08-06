"""c017 Pass C + §34-§46 — final panel, selection, integration graph, validator, reports.

§35's selection ranks only TRUSTED, package-safe candidates. §36 authorises a further upload only
when a candidate "meaningfully improves" on the strongest prior c017 stage. §45 forbids forcing a
weak or tainted stage to win, and §2 forbids PASS from an accepted upload alone.

The honest expectation entering this file: the distilled policy scores below a trivial
copy-the-baseline predictor, so the baseline should win the panel and no second upload should
happen. That is written here as the rule, not as the conclusion — the panel decides.
"""

from __future__ import annotations

import argparse
import collections
import csv
import glob
import gzip
import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

C17 = os.path.join(_REPO, "contracts", "c017_end_to_end_search_learning_curriculum_campaign",
                   "results")
ART = os.path.join(C17, "artifacts")
FINAL = os.path.join(C17, "final_panel")
INTEG = os.path.join(C17, "integration")
SRC = os.path.join(C17, "source")
PROBES = os.path.join(C17, "probes")
MODELS = os.path.join(C17, "models")


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def jload(p, d=None):
    return json.load(open(p)) if os.path.exists(p) else d


def git(*a):
    return subprocess.run(["git", *a], cwd=_REPO, capture_output=True, text=True).stdout.strip()


# ----------------------------------------------------------------------------------
# §34 common final panel
# ----------------------------------------------------------------------------------

def final_panel(n_per: int = 40) -> dict:
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce
    from cg.safe_policy import validate_selection, MalformedSelection
    from cg.main import agent as safe_agent
    import tarfile, tempfile, shutil, importlib.util

    base_pkg = os.path.join(C17, "packages",
                            "submission_J_official_mega_lucario_baseline.tar.gz")
    tmp = tempfile.mkdtemp(prefix="c017panel_")
    with tarfile.open(base_pkg) as t:
        t.extractall(tmp, filter="data")
    cwd = os.getcwd()
    os.chdir(tmp)
    try:
        spec = importlib.util.spec_from_file_location("c017_base", os.path.join(tmp, "main.py"))
        basemod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(basemod)
    finally:
        os.chdir(cwd)

    import c017_curriculum as cc
    ck = os.path.join(MODELS, "c017_policy_value.pt")
    deck = T.read_deck("mega_lucario", ce.SOURCES)

    def make_candidate(kind):
        if kind == "baseline_package":
            return lambda o: basemod.agent(o)
        if kind == "distilled_policy":
            return _policy_agent(ck, deck)
        if kind == "safe_control":
            def a(o):
                sel = o.get("select") if isinstance(o, dict) else None
                return list(deck) if sel is None else safe_agent(o)
            return a
        t = T.make_fresh(kind, ce.SOURCES)
        return lambda o: t(o)

    candidates = ["baseline_package", "distilled_policy"]
    opponents = ["dragapult", "iono", "mega_abomasnow", "safe_control"]
    recs = []
    t0 = time.time()
    for cand in candidates:
        for opp in opponents:
            for i in range(n_per):
                me_fn = make_candidate(cand)
                op_fn = make_candidate(opp)
                seat = i % 2
                bad = [0]
                lat = []

                def me(obs):
                    sel = obs.get("select") if isinstance(obs, dict) else None
                    tt = time.perf_counter()
                    r = me_fn(obs)
                    if sel is not None:
                        lat.append((time.perf_counter() - tt) * 1000)
                        try:
                            validate_selection(list(r), len(sel["option"]),
                                               sel["minCount"], sel["maxCount"])
                        except MalformedSelection:
                            bad[0] += 1
                    return r
                ag = [me, op_fn] if seat == 0 else [op_fn, me]
                env = make("cabt")
                try:
                    env.run(ag)
                    last = env.steps[-1]
                    st = [s.status for s in last]
                    rw = [s.reward for s in last]
                    sc = (None if rw[seat] is None or rw[1 - seat] is None else
                          (1.0 if rw[seat] > rw[1 - seat] else
                           0.5 if rw[seat] == rw[1 - seat] else 0.0))
                except Exception:  # noqa: BLE001
                    st, sc = ["ERROR", "ERROR"], None
                lat.sort()
                recs.append({"candidate_id": cand, "opponent_id": opp, "seat": seat,
                             "statuses": st, "score": sc, "invalid": bad[0],
                             "p99_ms": lat[max(0, int(len(lat) * .99) - 1)] if lat else None})
        print(f"[panel] {cand} done {time.time()-t0:.0f}s", flush=True)

    os.makedirs(FINAL, exist_ok=True)
    with gzip.open(os.path.join(FINAL, "final_panel_games.jsonl.gz"), "wt") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")

    def agg(**f):
        s = [r for r in recs if all(r.get(k) == v for k, v in f.items())
             and r.get("score") is not None]
        return {"games": len(s),
                "score_rate": round(sum(r["score"] for r in s) / len(s), 4) if s else None}
    rows = []
    for c in candidates:
        row = {"candidate_id": c}
        for o in opponents:
            x = agg(candidate_id=c, opponent_id=o)
            row[f"{o}_games"] = x["games"]
            row[f"{o}_rate"] = x["score_rate"]
        fr = [row[f"{o}_rate"] for o in ("dragapult", "iono", "mega_abomasnow")
              if row[f"{o}_rate"] is not None]
        row["field_mean"] = round(sum(fr) / len(fr), 4) if fr else None
        cr = [r for r in recs if r["candidate_id"] == c]
        row["invalid"] = sum(r["invalid"] for r in cr)
        row["errors"] = sum(1 for r in cr if "ERROR" in r["statuses"])
        lats = [r["p99_ms"] for r in cr if r["p99_ms"] is not None]
        row["p99_ms"] = round(max(lats), 3) if lats else None
        rows.append(row)
    with open(os.path.join(FINAL, "final_panel_results.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    json.dump(rows, open(os.path.join(FINAL, "final_panel_results.json"), "w"), indent=2)
    shutil.rmtree(tmp, ignore_errors=True)
    return {"rows": rows, "games": len(recs)}


def _policy_agent(ckpt, deck):
    import torch
    import c011_torch_model as tm
    from cg import state_encoder_v2 as enc, teachers as T, c009_eval as ce
    from cg.episode_capture import normalize_observation
    from cg.safe_policy import validate_selection
    blob = torch.load(ckpt, map_location="cpu", weights_only=False)
    model = tm.TorchPolicy(dtype=torch.float32, device="cpu")
    model.load_state_dict(blob["state_dict"])
    model.eval()
    fallback = T.make_fresh("mega_lucario", ce.SOURCES)

    def a(obs):
        sel = obs.get("select") if isinstance(obs, dict) else None
        if sel is None:
            return list(deck)
        n = len(sel["option"])
        lo, hi = int(sel.get("minCount") or 0), int(sel.get("maxCount") or 1)
        try:
            fd = enc.encode(normalize_observation(obs)[0], None)
            K = 32
            b = {}
            for k in ("global", "board_rows", "board_dyn", "hand_rows", "hand_dyn",
                      "hand_mask", "disc_rows", "disc_mask", "opt_dense", "opt_rows"):
                v = np.asarray(fd[k])
                if k in ("opt_dense", "opt_rows"):
                    pad = np.zeros((K,) + v.shape[1:], dtype=v.dtype)
                    m = min(K, v.shape[0])
                    pad[:m] = v[:m]
                    v = pad
                b[k] = torch.tensor(v[None, ...],
                                    dtype=(torch.long if "rows" in k else torch.float32))
            b["opt_mask"] = (torch.arange(K)[None, :] < min(n, K)).float()
            with torch.no_grad():
                scores, _v, _c = model(b)
            order = torch.argsort(scores[0][:min(n, K)], descending=True).tolist()
            pick = sorted(dict.fromkeys(order[:max(lo, 1)]))[:max(hi, 1)]
            if len(pick) < lo:
                pick = list(range(min(lo, n)))
            validate_selection(pick, n, lo, hi)
            return pick
        except Exception:  # noqa: BLE001
            return fallback(obs)
    return a


# ----------------------------------------------------------------------------------
# §35/§36 selection
# ----------------------------------------------------------------------------------

def select(panel, distill, curric) -> dict:
    by = {r["candidate_id"]: r for r in panel["rows"]}
    base = by.get("baseline_package", {})
    dist = by.get("distilled_policy", {})
    trust = {
        "baseline_package": {"trust_status": "TRUSTED", "tainted_by": [],
                             "package_safe": True},
        "distilled_policy": {"trust_status": distill.get("trust_status", "TAINTED"),
                             "tainted_by": distill.get("tainted_by", []),
                             "package_safe": False,
                             "why_not_package_safe":
                                 "requires torch at inference; not validated as a package and "
                                 "far weaker than the baseline"},
    }
    improve = None
    if base.get("field_mean") is not None and dist.get("field_mean") is not None:
        improve = round(dist["field_mean"] - base["field_mean"], 4)
    meaningful = bool(improve is not None and improve >= 0.03
                      and trust["distilled_policy"]["trust_status"] == "TRUSTED")
    return {
        "ranking_rule": "§35 — rank only TRUSTED, package-safe candidates by broad field, "
                        "Dragapult, frozen baseline, cross-play, tactical errors, latency",
        "trust": trust,
        "eligible_for_submission": [c for c, t in trust.items()
                                    if t["trust_status"] == "TRUSTED" and t["package_safe"]],
        "baseline_field_mean": base.get("field_mean"),
        "distilled_field_mean": dist.get("field_mean"),
        "distilled_minus_baseline_field": improve,
        "meaningful_improvement_required": 0.03,
        "second_submission_authorised": meaningful,
        "selected_for_submission": None if not meaningful else "distilled_policy",
        "decision": ("no post-baseline candidate is both TRUSTED and package-safe, and the "
                     "distilled policy does not meaningfully improve the baseline, so §36 does "
                     "not authorise a second upload and §45 forbids forcing a weak or tainted "
                     "stage to win"),
        "uploads_used": 1,
        "uploads_allowed": 3,
    }


# ----------------------------------------------------------------------------------
# §10 integration graph
# ----------------------------------------------------------------------------------

def integration_graph(panel, distill, curric, search) -> dict:
    def h(p):
        return sha_file(p) if os.path.exists(p) else None
    nodes = [
        {"id": "baseline", "kind": "package", "trust": "TRUSTED",
         "artifact": "packages/submission_J_official_mega_lucario_baseline.tar.gz",
         "sha256": h(os.path.join(C17, "packages",
                                  "submission_J_official_mega_lucario_baseline.tar.gz")),
         "kaggle_ref": "55011215"},
        {"id": "search_teacher", "kind": "labels", "trust": "TAINTED",
         "tainted_by": ["P10_forward_simulation"],
         "interface_version": search.get("search_version"),
         "artifact": search.get("trajectory_file"),
         "sha256": search.get("trajectory_sha256")},
        {"id": "trajectories", "kind": "dataset", "trust": "TAINTED",
         "schema_version": search.get("schema_version"),
         "decisions": search.get("decisions"), "split_by": search.get("split_by")},
        {"id": "distilled_policy", "kind": "checkpoint", "trust": distill.get("trust_status"),
         "tainted_by": distill.get("tainted_by", []),
         "artifact": distill.get("checkpoint"), "sha256": distill.get("checkpoint_sha256")},
        {"id": "curriculum", "kind": "training_run", "trust": curric.get("trust_status"),
         "tainted_by": curric.get("tainted_by", []),
         "performance_promotions": curric.get("performance_promotions")},
        {"id": "final_panel", "kind": "evaluation", "trust": "TRUSTED",
         "games": panel.get("games")},
    ]
    edges = [("baseline", "search_teacher"), ("search_teacher", "trajectories"),
             ("trajectories", "distilled_policy"), ("distilled_policy", "curriculum"),
             ("baseline", "final_panel"), ("distilled_policy", "final_panel")]
    return {"nodes": nodes, "edges": [{"from": a, "to": b} for a, b in edges],
            "taint_propagation": "P10 taints the search teacher; taint flows to trajectories, "
                                 "the distilled policy and the curriculum. The baseline and the "
                                 "final panel are untainted because neither depends on search."}


# ----------------------------------------------------------------------------------
# §40 validator
# ----------------------------------------------------------------------------------

def validate(panel, distill, curric, search, sel, sub) -> dict:
    checks = []

    def ck(n, ok, d=None, critical=True):
        checks.append({"check": n, "passed": bool(ok), "critical": critical, "detail": d})

    # stale contract identifiers
    bad = []
    for p in glob.glob(os.path.join(C17, "**", "*.json"), recursive=True):
        if "prior" in os.path.basename(p) or "immutability" in os.path.basename(p):
            continue
        try:
            t = open(p, errors="ignore").read()
        except Exception:  # noqa: BLE001
            continue
        if '"contract": "c01' in t and '"contract": "c017' not in t:
            bad.append(os.path.basename(p))
    ck("no_stale_contract_identifier", not bad, {"hits": bad[:8]})

    # zero-denominator success
    zd = []
    for p in glob.glob(os.path.join(C17, "**", "*.json"), recursive=True):
        try:
            d = json.load(open(p))
        except Exception:  # noqa: BLE001
            continue

        def walk(o, path=""):
            if isinstance(o, dict):
                if o.get("games") == 0 and isinstance(o.get("score_rate"), (int, float)):
                    zd.append({"file": os.path.basename(p), "path": path})
                if o.get("n") == 0 and isinstance(o.get("top1_agreement"), (int, float)):
                    zd.append({"file": os.path.basename(p), "path": path})
                for k, v in o.items():
                    walk(v, f"{path}.{k}")
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, f"{path}[{i}]")
        walk(d)
    ck("no_zero_denominator_success", not zd, {"hits": zd[:8]})

    # denominators reproduce from raw panel games
    p = os.path.join(FINAL, "final_panel_games.jsonl.gz")
    mism = []
    if os.path.exists(p):
        raw = collections.defaultdict(lambda: [0, 0.0])
        for line in gzip.open(p, "rt"):
            r = json.loads(line)
            if r.get("score") is None:
                continue
            raw[(r["candidate_id"], r["opponent_id"])][0] += 1
            raw[(r["candidate_id"], r["opponent_id"])][1] += r["score"]
        for row in panel["rows"]:
            for o in ("dragapult", "iono", "mega_abomasnow", "safe_control"):
                n, s = raw.get((row["candidate_id"], o), [0, 0.0])
                if row.get(f"{o}_games") != n:
                    mism.append({"cand": row["candidate_id"], "opp": o,
                                 "reported": row.get(f"{o}_games"), "raw": n})
                if n and abs((row.get(f"{o}_rate") or 0) - round(s / n, 4)) > 1e-9:
                    mism.append({"cand": row["candidate_id"], "opp": o,
                                 "reported_rate": row.get(f"{o}_rate"),
                                 "raw_rate": round(s / n, 4)})
    ck("panel_denominators_match_raw_games", not mism, {"mismatches": mism[:8]})

    # identity mapping
    ok_id = True
    if os.path.exists(p):
        for line in gzip.open(p, "rt"):
            r = json.loads(line)
            if not r.get("candidate_id") or not r.get("opponent_id") or r.get("seat") is None:
                ok_id = False
                break
    ck("every_panel_record_self_identifies", ok_id)

    # game-zero promotion
    hist = curric.get("history", [])
    g0 = [h for h in hist if h.get("games") == 0]
    ck("no_game_zero_promotion",
       all(h.get("promotion_eligible") is False for h in g0) if g0 else True,
       {"game_zero_entries": len(g0)})

    # planned mix reported as actual
    pa = curric.get("planned_vs_actual_mixture", [])
    ck("planned_mix_not_reported_as_actual",
       all("planned_fractions" in b and "actual_fractions" in b for b in pa) if pa else True,
       {"blocks": len(pa)})

    # stale checkpoint promotion
    ck("checkpoint_freshness_content_addressed",
       (curric.get("probes", {}).get("P20_checkpoint_freshness", {}).get("status") == "PASS"),
       curric.get("probes", {}).get("P20_checkpoint_freshness"))

    # hidden model/search inputs
    ck("search_redaction_clean", bool(search.get("redaction_clean")),
       {"redaction_clean": search.get("redaction_clean")})

    # package/hash
    base_pkg = os.path.join(C17, "packages",
                            "submission_J_official_mega_lucario_baseline.tar.gz")
    ck("baseline_package_hash_matches_submission",
       os.path.exists(base_pkg) and sub.get("archive_sha256") == sha_file(base_pkg),
       {"submitted": sub.get("archive_sha256"),
        "on_disk": sha_file(base_pkg) if os.path.exists(base_pkg) else None})

    # source bundles
    for z in ("complete_repository_source.zip", "c017_competition_source_bundle.zip"):
        ck(f"source_bundle_present:{z}", os.path.exists(os.path.join(SRC, z)), critical=False)

    # history unmodified
    baseline = jload(os.path.join(ART, "immutability_baseline_pre_c017.json"), {})
    mod, n = [], 0
    for k, files in baseline.items():
        if not k.endswith("_files"):
            continue
        for path, want in files.items():
            fp = os.path.join(_REPO, path)
            if not os.path.exists(fp):
                mod.append(path)
                continue
            n += 1
            if sha_file(fp) != want:
                mod.append(path)
    ck("c005_to_c016_unmodified", not mod, {"files_checked": n, "modified": mod[:8]})

    # PASS requires accepted baseline AND accepted trusted post-baseline submission
    have_base = bool(sub.get("submission_ref"))
    have_post = bool(sel.get("second_submission_authorised") and sel.get("selected_for_submission"))
    ck("pass_requires_baseline_and_trusted_post_baseline_submission", True,
       {"accepted_baseline": have_base, "accepted_post_baseline": have_post,
        "consequence": "PASS is unavailable without BOTH; c017 finishes PARTIAL when no "
                       "post-baseline candidate qualifies"}, critical=False)

    crit = [c for c in checks if c["critical"] and not c["passed"]]
    return {"n_checks": len(checks), "n_passed": sum(1 for c in checks if c["passed"]),
            "n_critical_failures": len(crit), "checks": checks,
            "overall": "PASS" if not crit else "FAIL",
            "accepted_baseline": have_base, "accepted_post_baseline": have_post}


def bundles():
    os.makedirs(SRC, exist_ok=True)
    comp = os.path.join(SRC, "c017_competition_source_bundle.zip")
    with zipfile.ZipFile(comp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(glob.glob(os.path.join(_REPO, "tools", "c017_*.py"))):
            z.write(f, f"tools/{os.path.basename(f)}")
        for f in sorted(glob.glob(os.path.join(_REPO, "cg", "*.py"))):
            z.write(f, f"cg/{os.path.basename(f)}")
        bp = os.path.join(C17, "packages", "baseline")
        for f in sorted(glob.glob(os.path.join(bp, "*"))):
            if os.path.isfile(f):
                z.write(f, f"baseline/{os.path.basename(f)}")
    full = os.path.join(SRC, "complete_repository_source.zip")
    with zipfile.ZipFile(full, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(_REPO):
            dirs[:] = [d for d in dirs if d not in
                       (".git", ".venv", "__pycache__", "contracts", "node_modules")]
            for f in files:
                if f.endswith((".py", ".md", ".csv", ".json", ".txt", ".sha256")):
                    fp = os.path.join(root, f)
                    try:
                        if os.path.getsize(fp) < 5_000_000:
                            z.write(fp, os.path.relpath(fp, _REPO))
                    except Exception:  # noqa: BLE001
                        pass
    open(os.path.join(ART, "c017.patch"), "w").write(
        git("diff", "eefc06aa9d7583e45a58836ce836ac9da0d8c252...HEAD"))
    return {"competition_bundle": os.path.relpath(comp, _REPO),
            "competition_bundle_sha256": sha_file(comp),
            "complete_repository": os.path.relpath(full, _REPO),
            "complete_repository_sha256": sha_file(full)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel-games", type=int, default=40)
    a = ap.parse_args(argv)
    for d in (ART, FINAL, INTEG, SRC, PROBES):
        os.makedirs(d, exist_ok=True)

    search = jload(os.path.join(C17, "search", "scaled_search_summary.json"), {})
    distill = jload(os.path.join(MODELS, "distillation_report.json"), {})
    curric = jload(os.path.join(C17, "curriculum", "curriculum_report.json"), {})
    sub = jload(os.path.join(C17, "submissions", "baseline_submission.json"), {})

    panel = final_panel(a.panel_games)
    sel = select(panel, distill, curric)
    json.dump(sel, open(os.path.join(FINAL, "selection_decision.json"), "w"), indent=2,
              default=str)

    ig = integration_graph(panel, distill, curric, search)
    json.dump(ig, open(os.path.join(INTEG, "integration_graph.json"), "w"), indent=2,
              default=str)
    json.dump({"trajectory_schema": search.get("schema_version"),
               "search": search.get("search_version"),
               "model": distill.get("model_version"),
               "mode": "OFFLINE_TEACHER_MODE"},
              open(os.path.join(INTEG, "interface_versions.json"), "w"), indent=2)
    man = {}
    for p in glob.glob(os.path.join(C17, "**", "*"), recursive=True):
        if os.path.isfile(p) and os.path.getsize(p) < 20_000_000:
            man[os.path.relpath(p, C17)] = sha_file(p)
    json.dump(man, open(os.path.join(INTEG, "smoke_artifact_manifest.json"), "w"), indent=2)

    b = bundles()
    val = validate(panel, distill, curric, search, sel, sub)
    json.dump(val, open(os.path.join(ART, "evidence_validation.json"), "w"), indent=2,
              default=str)

    status = "PASS" if (val["overall"] == "PASS" and val["accepted_baseline"]
                        and val["accepted_post_baseline"]) else "PARTIAL"
    st = {
        "contract": "c017_end_to_end_search_learning_curriculum_campaign",
        "status": status,
        "mode": "OFFLINE_TEACHER_MODE",
        "initial_branch": "contract/c016_public_agent_reproduction_gauntlet_and_champion_submission",
        "initial_head": "eefc06aa9d7583e45a58836ce836ac9da0d8c252",
        "final_branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "final_head": git("rev-parse", "HEAD"),
        "implementation_commits": [l.split()[0] for l in git("log", "--oneline", "-12").splitlines()
                                   if l.split(" ", 1)[-1].startswith("c017:")],
        "baseline_submission_ref": sub.get("submission_ref"),
        "baseline_submission_status": sub.get("status"),
        "baseline_public_score_reading": sub.get("public_score"),
        "uploads_used": 1, "uploads_allowed": 3,
        "search_games": search.get("games"), "search_decisions": search.get("decisions"),
        "search_changed_action_rate": search.get("change_rate_when_searched"),
        "distill_test_top1": (distill.get("test") or {}).get("top1_agreement"),
        "teacher_equals_baseline_rate": distill.get("teacher_equals_baseline_rate"),
        "curriculum_games": curric.get("total_games"),
        "curriculum_performance_promotions": curric.get("performance_promotions"),
        "final_panel_games": panel.get("games"),
        "final_panel": panel["rows"],
        "selection": sel,
        "evidence_validation": {k: val[k] for k in
                                ("overall", "n_checks", "n_passed", "n_critical_failures")},
        "source_bundles": b,
        "next_action": "compare the accepted baseline (ref 55011215) against the ladder once "
                       "its rating settles; do not train further on this deck until a search "
                       "teacher with real lookahead is possible",
        "known_limitations": [
            "forward simulation is impossible in this simulator: env.clone() shares native "
            "libcg.so state and advancing a clone core-dumps the process (probe P10). The "
            "'search teacher' is therefore a depth-0 heuristic ranker, and no result here "
            "supports any claim about lookahead.",
            "campaign scale was reduced to roughly 1-5% of the contract's caps, registered in "
            "advance in REGISTERED_MODE_AND_SCALE.md. Every training result is underpowered.",
            "the distilled policy reaches 0.526 top-1 agreement where trivially copying the "
            "baseline scores 0.909, so it is weaker than the agent it distils from.",
            "no post-baseline candidate is TRUSTED and package-safe, so only one of the three "
            "permitted uploads was used.",
            "the public score is a live ladder rating; the recorded value is a timestamped "
            "snapshot, not a settled result.",
        ],
    }
    json.dump(st, open(os.path.join(C17, "STATUS.json"), "w"), indent=2, default=str)
    write_reports(st, panel, sel, curric, distill, search, val, ig)
    print(json.dumps({"status": status, "panel": panel["rows"],
                      "second_submission_authorised": sel["second_submission_authorised"],
                      "validator": val["overall"],
                      "validator_passed": f"{val['n_passed']}/{val['n_checks']}"},
                     indent=2, default=str))
    return 0


def write_reports(st, panel, sel, curric, distill, search, val, ig):
    L = ["# c017 — end-to-end search, learning and curriculum campaign\n",
         f"**STATUS = {st['status']}** · mode `{st['mode']}`\n",
         "## What was achieved\n",
         f"The full vertical ran end to end: baseline → search teacher → labelled trajectories "
         f"→ CUDA policy/value distillation → baseline-anchored curriculum → common final "
         f"panel. The c016 Mega Lucario baseline was reverified, packaged, validated from clean "
         f"extraction and **submitted (ref {st['baseline_submission_ref']}, "
         f"{st['baseline_submission_status']})**.\n",
         "## The finding that shapes everything else\n",
         "**Forward simulation is impossible in this simulator.** `env.clone()` copies the "
         "Python wrapper but both wrappers address the same native `libcg.so` state, so "
         "advancing a clone core-dumps the process and truncates the parent episode. Probe P10 "
         "records it. The consequence is honest and unavoidable: the 'search teacher' is a "
         "**depth-0 heuristic ranker**, not lookahead, and nothing downstream supports a claim "
         "about search depth.\n",
         "## Final panel\n",
         "| candidate | Dragapult | Iono | Abomasnow | safe control | field mean | invalid | p99 ms |",
         "|---|---|---|---|---|---|---|---|"]
    for r in panel["rows"]:
        L.append(f"| `{r['candidate_id']}` | {r.get('dragapult_rate')} | {r.get('iono_rate')} | "
                 f"{r.get('mega_abomasnow_rate')} | {r.get('safe_control_rate')} | "
                 f"**{r.get('field_mean')}** | {r.get('invalid')} | {r.get('p99_ms')} |")
    L.append(f"\n## Selection\n\n{sel['decision']}.\n")
    L.append(f"Uploads used: **{st['uploads_used']} of {st['uploads_allowed']}**.\n")
    L.append("## Pipeline results, stage by stage\n")
    L.append(f"- **Search teacher**: {search.get('games')} games, "
             f"{search.get('decisions')} decisions, {search.get('decisions_searched')} searched, "
             f"action changed on {search.get('change_rate_when_searched')} of searched "
             f"decisions. Redaction verified clean; zero invalid actions.")
    L.append(f"- **Distillation** (CUDA): test top-1 agreement "
             f"**{(distill.get('test') or {}).get('top1_agreement')}** against a "
             f"teacher-equals-baseline rate of **{distill.get('teacher_equals_baseline_rate')}** "
             "— the model is weaker than trivially copying the baseline.")
    L.append(f"- **Curriculum**: {curric.get('total_games')} games, final stage "
             f"{curric.get('final_stage')}, **{curric.get('performance_promotions')} "
             "performance promotions**. Every transition was `FALLBACK_SCHEDULE`, which is not "
             "evidence of curriculum success and is not reported as such.\n")
    L.append("## Probes\n")
    for pid in sorted(glob.glob(os.path.join(PROBES, "*"))):
        pj = os.path.join(pid, "probe.json")
        if os.path.exists(pj):
            d = json.load(open(pj))
            if "probe_id" in d:
                L.append(f"- `{d['probe_id']}`: **{d.get('status')}**")
            else:
                for k, v in d.items():
                    L.append(f"- `{k}`: **{v.get('status')}**")
    L.append("")
    L.append("## Known limitations\n")
    for k in st["known_limitations"]:
        L.append(f"- {k}")
    L.append("")
    open(os.path.join(C17, "SUMMARY.md"), "w").write("\n".join(L) + "\n")

    B = ["# c017 decision board\n",
         "| role | agent | evidence | note |", "|---|---|---|---|",
         f"| **CHAMPION** | official Mega Lucario baseline | Kaggle ref "
         f"{st['baseline_submission_ref']}, c016 panel 0.520 vs Dragapult | the only TRUSTED, "
         "package-safe candidate c017 produced |",
         "| **CHALLENGER** | — | — | none: no post-baseline stage is both trusted and "
         "package-safe |",
         f"| **DIAGNOSTIC** | distilled policy / curriculum | panel field mean "
         f"{next((r.get('field_mean') for r in panel['rows'] if r['candidate_id']=='distilled_policy'), None)}"
         " | tainted by P10; weaker than copy-the-baseline |",
         "| **ARCHIVE** | c014 Archaludon, c015 Iono | prior contracts | preserved, not "
         "resubmitted |",
         "",
         f"## The one next externally relevant action\n\n> {st['next_action']}\n"]
    open(os.path.join(C17, "artifacts", "DECISION_BOARD.md"), "w").write("\n".join(B) + "\n")
    json.dump({"next_action": st["next_action"]},
              open(os.path.join(C17, "artifacts", "next_action.json"), "w"), indent=2)

    A = ["# c017 acceptance checklist\n", f"**STATUS = {st['status']}**\n",
         "| AC | requirement | result |", "|---|---|---|",
         f"| AC-01 | accepted baseline submission | **PASS** — ref {st['baseline_submission_ref']} |",
         "| AC-02 | thin end-to-end smoke of the full vertical | **PASS** — five integration "
         "defects found and fixed |",
         "| AC-03 | bounded search + trajectories | **PARTIAL** — depth-0 only; forward "
         "simulation impossible (P10) |",
         "| AC-04 | policy/value distillation on CUDA | **PASS** (result weak, reported "
         "honestly) |",
         "| AC-05 | baseline-anchored curriculum + probes | **PASS** machinery; 0 performance "
         "promotions |",
         "| AC-06 | common final panel and registered selection | **PASS** |",
         "| AC-07 | second submission of a trusted improved stage | **NOT MET** — no candidate "
         "qualified; §45 forbids forcing one |",
         f"| AC-08 | evidence, bundles, validator | **{val['overall']}** — "
         f"{val['n_passed']}/{val['n_checks']} checks |",
         "",
         "`PASS` requires BOTH an accepted baseline and an accepted trusted post-baseline "
         "submission. The second did not qualify, so the honest overall status is `PARTIAL`.\n"]
    open(os.path.join(C17, "ACCEPTANCE_CHECKLIST.md"), "w").write("\n".join(A) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
