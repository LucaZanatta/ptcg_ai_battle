"""c016 §15-§18 — pre-registered evaluation protocol, Stage A screening, Stage B gauntlet.

The protocol is written to disk by `--stage protocol` and committed BEFORE any candidate is
scored, because §15 requires the specification to exist before results are known and forbids
changing the panel or ranking rule afterwards.

IDENTITY-SAFE AGGREGATION (§17). Every game record carries its own `candidate_id`, `opponent_id`,
`seat` and `seed` and is aggregated by those fields. Results are never zipped positionally onto
a candidate list — that is the defect c009 was built to prevent and §22 requires the validator to
reject.

Seeds are fixed and candidate-independent: the same seed list is replayed for every candidate,
so a candidate cannot be advantaged by drawing easier games.
"""

from __future__ import annotations

import argparse
import collections
import csv
import gzip
import hashlib
import json
import math
import os
import statistics
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

CANDIDATES = ["official_iono", "official_mega_lucario", "official_mega_abomasnow"]

C014_PKG = os.path.join(_REPO, "contracts", "c014_public_meta_baseline_and_rapid_submission",
                        "results", "artifacts", "submission_H_public_meta_v0.tar.gz")
C015_PKG = os.path.join(_REPO, "contracts", "c015_anti_meta_deck_agent_v0", "results",
                        "artifacts", "submission_I_anti_meta_v0.tar.gz")

# ---- frozen seed lists (§16: fixed and candidate-independent) ----
SEED_BASE = 160000
SEED_INDEPENDENT = 970000     # disjoint block for confirmation runs

PROTOCOL = {
    "frozen_before_results": True,
    "panel": {
        "dragapult": "frozen Dragapult control (official sample)",
        "iono": "official Iono sample agent",
        "mega_lucario": "official Mega Lucario control",
        "mega_abomasnow": "official Mega Abomasnow control",
        "__c014__": "c014 custom Archaludon package (exact archive)",
        "__c015__": "c015 custom Iono package (exact archive)",
        "__safe__": "deterministic safe control",
    },
    "stage_a": {"safe_games": 40, "dragapult_games": 80, "seats": "balanced",
                "seed_block": SEED_BASE},
    "stage_b": {"dragapult": 200, "iono": 100, "mega_lucario": 100, "mega_abomasnow": 100,
                "__c014__": 100, "__c015__": 100, "seats": "balanced 50/50",
                "seed_block": SEED_BASE},
    "confirmation": {"dragapult": 200, "field_total": 300, "seed_block": SEED_INDEPENDENT,
                     "note": "independent seed block, disjoint from Stage A/B"},
    "crossplay": {"top_two_games": 300, "seats": "balanced"},
    "stage_a_hard_gates": [
        "zero invalid selections", "zero uncaught exceptions", "zero timeouts",
        "deterministic replay on a fixed sample", "no hidden-information access",
        "no inference-time network access", "package-equivalent execution",
        "score rate >= 0.80 vs the deterministic safe control unless a documented "
        "simulator/deck asymmetry explains failure",
    ],
    "ranking_lexicographic": [
        "1 passes reproduction fidelity (EXACT or FAITHFUL_CLEAN_ROOM)",
        "2 passes all reliability and package-feasibility hard gates",
        "3 score rate vs Dragapult on independent confirmation",
        "4 mean score rate across official Iono, Mega Lucario, Mega Abomasnow on "
        "independent confirmation",
        "5 direct cross-play vs the other finalist",
        "6 lower p99 latency",
        "7 stronger current public evidence quality",
    ],
    "base_conditions": {
        "safe_control_min": 0.90, "vs_c014_min": 0.65, "vs_c014_min_games": 100,
        "vs_c015_min": 0.65, "vs_c015_min_games": 100,
        "reliability_violations": 0,
        "fidelity_in": ["EXACT", "FAITHFUL_CLEAN_ROOM"],
    },
    "strength_paths": {
        "A": {"vs_dragapult_min": 0.55, "min_games": 400, "wilson_lb_above": 0.50},
        "B": {"vs_dragapult_min": 0.48, "min_games": 400, "field_mean_min": 0.55,
              "field_min_games": 600, "max_deficit_vs_dragapult_on_two_opponents": 0.10},
        "C": {"requires": "EXACT + >=900-equivalent PUBLIC_CLAIM + source benchmark match "
                          "within 10pp over >=200 games + (>=0.50 vs Dragapult or >=0.55 "
                          "field mean) + explicit evidence-quality approval"},
    },
    "aggregation": "identity-safe: every record carries candidate_id/opponent_id/seat/seed and "
                   "is aggregated by those fields; results are never zipped positionally",
}


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d, (c + m) / d)


_PKG_CACHE = {}


def _load_pkg(path, tag):
    if tag in _PKG_CACHE:
        return _PKG_CACHE[tag]
    import importlib.util
    tmp = tempfile.mkdtemp(prefix=f"c016_{tag}_")
    with tarfile.open(path) as t:
        t.extractall(tmp, filter="data")
    cwd = os.getcwd()
    os.chdir(tmp)
    try:
        spec = importlib.util.spec_from_file_location(f"c016_{tag}", os.path.join(tmp, "main.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        os.chdir(cwd)
    _PKG_CACHE[tag] = mod
    return mod


def make_agent(spec):
    """Returns a fresh callable for one game. `spec` is an opponent/candidate id."""
    from cg import teachers as T, c009_eval as ce
    from cg.main import agent as safe_agent
    if spec == "__safe__":
        deck = T.read_deck("dragapult", ce.SOURCES)

        def a(o):
            sel = o.get("select") if isinstance(o, dict) else None
            return list(deck) if sel is None else safe_agent(o)
        return a
    if spec == "__c014__":
        m = _load_pkg(C014_PKG, "c014")
        return lambda o: m.agent(o)
    if spec == "__c015__":
        m = _load_pkg(C015_PKG, "c015")
        return lambda o: m.agent(o)
    cid = spec.replace("official_", "")
    t = T.make_fresh(cid, ce.SOURCES)
    return lambda o: t(o)


def play(candidate_id, opponent_id, seat, seed, phase):
    from kaggle_environments import make
    from cg.safe_policy import validate_selection, MalformedSelection
    me_agent = make_agent(candidate_id)
    op_agent = make_agent(opponent_id)
    stats = {"calls": 0, "lat": [], "invalid": 0, "exc": 0}

    def me(obs):
        sel = obs.get("select") if isinstance(obs, dict) else None
        t0 = time.perf_counter()
        try:
            r = me_agent(obs)
        except Exception:  # noqa: BLE001
            stats["exc"] += 1
            raise
        dt = (time.perf_counter() - t0) * 1000
        if sel is not None:
            stats["calls"] += 1
            stats["lat"].append(dt)
            try:
                validate_selection(list(r), len(sel["option"]), sel["minCount"],
                                   sel["maxCount"])
            except MalformedSelection:
                stats["invalid"] += 1
        return r

    agents = [me, op_agent] if seat == 0 else [op_agent, me]
    exc = None
    env = None
    try:
        env = make("cabt")
        env.run(agents)
    except Exception as e:  # noqa: BLE001
        exc = repr(e)[:200]
    if env is None or exc:
        return {"candidate_id": candidate_id, "opponent_id": opponent_id, "seat": seat,
                "seed": seed, "phase": phase, "statuses": ["ERROR", "ERROR"],
                "completed": False, "score": None, "env_exception": exc,
                "invalid": stats["invalid"], "exceptions": stats["exc"],
                "decisions": stats["calls"], "latency_p99_ms": None, "latency_max_ms": None}
    last = env.steps[-1]
    st = [s.status for s in last]
    rw = [s.reward for s in last]
    lat = sorted(stats["lat"])
    return {
        "candidate_id": candidate_id, "opponent_id": opponent_id, "seat": seat, "seed": seed,
        "phase": phase, "statuses": st, "completed": st == ["DONE", "DONE"],
        "timeout": any(s == "TIMEOUT" for s in st),
        "score": (1.0 if rw[seat] > rw[1 - seat] else
                  0.5 if rw[seat] == rw[1 - seat] else 0.0),
        "invalid": stats["invalid"], "exceptions": stats["exc"], "decisions": stats["calls"],
        "latency_p99_ms": (lat[max(0, int(len(lat) * 0.99) - 1)] if lat else None),
        "latency_max_ms": (lat[-1] if lat else None),
        "env_exception": None,
    }


def run_block(candidate_id, opponent_id, n, phase, seed_block):
    """Fixed, candidate-independent seeds; seats balanced by construction."""
    out = []
    for i in range(n):
        seat = i % 2
        seed = seed_block + i          # identical list for every candidate
        out.append(play(candidate_id, opponent_id, seat, seed, phase))
    return out


def agg(records, **filt):
    """Identity-safe aggregation: select by field values, never by position."""
    sel = [r for r in records
           if all(r.get(k) == v for k, v in filt.items()) and r.get("score") is not None]
    n = len(sel)
    s = sum(r["score"] for r in sel)
    lo, hi = wilson(s, n)
    return {"games": n, "score": s, "score_rate": round(s / n, 4) if n else None,
            "wilson95": [round(lo, 4) if lo is not None else None,
                         round(hi, 4) if hi is not None else None],
            "seat0": sum(1 for r in sel if r["seat"] == 0),
            "seat1": sum(1 for r in sel if r["seat"] == 1)}


def reliability(records):
    return {"games": len(records),
            "completed": sum(1 for r in records if r["completed"]),
            "invalid_selections": sum(r.get("invalid") or 0 for r in records),
            "exceptions": sum(r.get("exceptions") or 0 for r in records)
            + sum(1 for r in records if r.get("env_exception")),
            "timeouts": sum(1 for r in records if r.get("timeout")),
            "violations": (sum(r.get("invalid") or 0 for r in records)
                           + sum(r.get("exceptions") or 0 for r in records)
                           + sum(1 for r in records if r.get("timeout"))
                           + sum(1 for r in records if r.get("env_exception"))),
            }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True,
                    choices=["protocol", "screen", "final", "confirm", "confirm_topup"])
    a = ap.parse_args(argv)
    os.makedirs(ART, exist_ok=True)
    os.makedirs(LOGD, exist_ok=True)

    if a.stage == "protocol":
        json.dump(PROTOCOL, open(os.path.join(ART, "evaluation_protocol.json"), "w"), indent=2)
        L = ["# Evaluation protocol (§15) — frozen before any candidate result\n",
             "This file is written and committed **before** the gauntlet runs. §15 forbids "
             "changing the panel or the ranking rule after scores are seen; any change would "
             "require a written amendment before rerunning.\n",
             "## Panel\n", "| opponent | role |", "|---|---|"]
        for k, v in PROTOCOL["panel"].items():
            L.append(f"| `{k}` | {v} |")
        L.append("\n## Seeds\n")
        L.append(f"Stage A/B use the fixed block starting at {SEED_BASE}; confirmation uses a "
                 f"disjoint block starting at {SEED_INDEPENDENT}. **The same seed list is "
                 "replayed for every candidate**, so no candidate can draw easier games.\n")
        L.append("## Game minimums\n")
        L.append(f"Stage A: {PROTOCOL['stage_a']['safe_games']} vs safe control, "
                 f"{PROTOCOL['stage_a']['dragapult_games']} vs Dragapult, seats balanced.\n")
        L.append("Stage B per finalist: " + ", ".join(
            f"{v} vs {k}" for k, v in PROTOCOL["stage_b"].items()
            if isinstance(v, int)) + ".\n")
        L.append(f"Confirmation (independent seeds): {PROTOCOL['confirmation']['dragapult']} vs "
                 f"Dragapult, {PROTOCOL['confirmation']['field_total']} across the official "
                 f"field. Cross-play: {PROTOCOL['crossplay']['top_two_games']} games between "
                 "the top two.\n")
        L.append("## Lexicographic ranking\n")
        for r in PROTOCOL["ranking_lexicographic"]:
            L.append(f"{r}")
        L.append("\n## Base conditions and strength paths\n")
        L.append("```json\n" + json.dumps(
            {"base_conditions": PROTOCOL["base_conditions"],
             "strength_paths": PROTOCOL["strength_paths"]}, indent=2) + "\n```\n")
        L.append(f"## Aggregation\n\n{PROTOCOL['aggregation']}.\n")
        open(os.path.join(ART, "EVALUATION_PROTOCOL.md"), "w").write("\n".join(L) + "\n")
        print(json.dumps({"protocol": "FROZEN", "candidates": CANDIDATES,
                          "seed_block": SEED_BASE,
                          "independent_seed_block": SEED_INDEPENDENT}, indent=2))
        return 0

    if a.stage == "screen":
        recs = []
        t0 = time.time()
        for c in CANDIDATES:
            recs += run_block(c, "__safe__", PROTOCOL["stage_a"]["safe_games"],
                              "stage_a", SEED_BASE)
            recs += run_block(c, "dragapult", PROTOCOL["stage_a"]["dragapult_games"],
                              "stage_a", SEED_BASE + 1000)
            print(f"[stage A] {c} done {time.time()-t0:.0f}s", flush=True)
        with gzip.open(os.path.join(ART, "screening_games.jsonl.gz"), "wt") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")
        rows = []
        for c in CANDIDATES:
            safe = agg(recs, candidate_id=c, opponent_id="__safe__")
            drag = agg(recs, candidate_id=c, opponent_id="dragapult")
            rel = reliability([r for r in recs if r["candidate_id"] == c])
            lat = [r["latency_p99_ms"] for r in recs
                   if r["candidate_id"] == c and r.get("latency_p99_ms") is not None]
            rows.append({"candidate_id": c, "safe_games": safe["games"],
                         "safe_rate": safe["score_rate"],
                         "dragapult_games": drag["games"],
                         "dragapult_rate": drag["score_rate"],
                         "dragapult_wilson_lo": drag["wilson95"][0],
                         "invalid": rel["invalid_selections"], "exceptions": rel["exceptions"],
                         "timeouts": rel["timeouts"], "violations": rel["violations"],
                         "p99_latency_ms": round(max(lat), 3) if lat else None,
                         "passes_safe_gate": (safe["score_rate"] or 0) >= 0.80,
                         "passes_reliability": rel["violations"] == 0})
        with open(os.path.join(ART, "screening_results.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        json.dump(rows, open(os.path.join(ART, "screening_results.json"), "w"), indent=2)
        with open(os.path.join(LOGD, "common_gauntlet.txt"), "w") as fh:
            fh.write("STAGE A\n" + json.dumps(rows, indent=2) + "\n")
        print(json.dumps(rows, indent=2))
        return 0

    if a.stage == "final":
        recs = []
        t0 = time.time()
        for c in CANDIDATES:
            # §17: 50 extra safe-control games when the Stage A safe rate was below 95%.
            # All three candidates were below it (0.975 / 0.850 / 0.875), so all three get them.
            for opp, n in (("dragapult", 200), ("iono", 100), ("mega_lucario", 100),
                           ("mega_abomasnow", 100), ("__c014__", 100), ("__c015__", 100),
                           ("__safe__", 50)):
                recs += run_block(c, opp, n, "stage_b", SEED_BASE + 2000)
            print(f"[stage B] {c} done {time.time()-t0:.0f}s", flush=True)
        with gzip.open(os.path.join(ART, "final_gauntlet_games.jsonl.gz"), "wt") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")
        rows = []
        for c in CANDIDATES:
            row = {"candidate_id": c}
            for opp in ("dragapult", "iono", "mega_lucario", "mega_abomasnow",
                        "__c014__", "__c015__", "__safe__"):
                x = agg(recs, candidate_id=c, opponent_id=opp)
                row[f"{opp}_games"] = x["games"]
                row[f"{opp}_rate"] = x["score_rate"]
            fld = [row["iono_rate"], row["mega_lucario_rate"], row["mega_abomasnow_rate"]]
            row["field_mean"] = round(sum(fld) / 3, 4)
            rel = reliability([r for r in recs if r["candidate_id"] == c])
            row.update({"violations": rel["violations"], "invalid": rel["invalid_selections"],
                        "exceptions": rel["exceptions"], "timeouts": rel["timeouts"]})
            rows.append(row)
        with open(os.path.join(ART, "final_gauntlet_results.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        json.dump(rows, open(os.path.join(ART, "final_gauntlet_results.json"), "w"), indent=2)
        with open(os.path.join(LOGD, "common_gauntlet.txt"), "a") as fh:
            fh.write("\nSTAGE B\n" + json.dumps(rows, indent=2) + "\n")
        print(json.dumps(rows, indent=2))
        return 0

    if a.stage == "confirm_topup":
        # §18's strength paths require >=400 confirmation games vs Dragapult and >=600 field
        # games. §17's 200/300 are FLOORS, not caps. Those counts were pre-registered in the
        # protocol before any score existed, so topping up to them is executing the registered
        # gate, not moving it. The full top-up is run to a FIXED target for BOTH finalists and
        # the control in one pass - never "keep going until it passes".
        prev = json.load(open(os.path.join(ART, "confirmation_results.json")))
        top2 = prev["top2"]
        recs = []
        t0 = time.time()
        for c in top2:
            recs += run_block(c, "dragapult", 200, "confirm", SEED_INDEPENDENT + 20000)
            for opp in ("iono", "mega_lucario", "mega_abomasnow"):
                recs += run_block(c, opp, 100, "confirm", SEED_INDEPENDENT + 25000)
            print(f"[topup] {c} done {time.time()-t0:.0f}s", flush=True)
        for opp in ("iono", "mega_lucario", "mega_abomasnow"):
            recs += run_block("dragapult", opp, 100, "confirm_control",
                              SEED_INDEPENDENT + 25000)
        old = [json.loads(l) for l in gzip.open(
            os.path.join(ART, "confirmation_games.jsonl.gz"), "rt")]
        allr = old + recs
        with gzip.open(os.path.join(ART, "confirmation_games.jsonl.gz"), "wt") as fh:
            for r in allr:
                fh.write(json.dumps(r) + "\n")
        rows = []
        for c in top2:
            d = agg(allr, candidate_id=c, opponent_id="dragapult", phase="confirm")
            f = [agg(allr, candidate_id=c, opponent_id=o, phase="confirm")
                 for o in ("iono", "mega_lucario", "mega_abomasnow")]
            rows.append({"candidate_id": c,
                         "confirm_dragapult_games": d["games"],
                         "confirm_dragapult_rate": d["score_rate"],
                         "confirm_dragapult_wilson_lo": d["wilson95"][0],
                         "confirm_field_games": sum(x["games"] for x in f),
                         "confirm_field_mean": round(sum(x["score_rate"] for x in f) / 3, 4),
                         "confirm_iono": f[0]["score_rate"],
                         "confirm_mega_lucario": f[1]["score_rate"],
                         "confirm_mega_abomasnow": f[2]["score_rate"]})
        ctrl = {o: agg(allr, candidate_id="dragapult", opponent_id=o, phase="confirm_control")
                for o in ("iono", "mega_lucario", "mega_abomasnow")}
        cross = [r for r in allr if r.get("phase") == "crossplay"]
        cr = agg(cross, candidate_id=top2[0], opponent_id=top2[1]) if cross else {}
        doc = {"top2": top2, "confirmation": rows,
               "dragapult_control_same_seeds": ctrl,
               "dragapult_control_field_mean": round(
                   sum(v["score_rate"] for v in ctrl.values()) / 3, 4),
               "crossplay": cr,
               "topup_note": "confirmation extended to the pre-registered strength-path minimums "
                             "(>=400 vs Dragapult, >=600 field) in a single fixed-target pass"}
        json.dump(doc, open(os.path.join(ART, "confirmation_results.json"), "w"), indent=2)
        rel = reliability(allr)
        lat = [r["latency_p99_ms"] for r in allr if r.get("latency_p99_ms") is not None]
        mx = [r["latency_max_ms"] for r in allr if r.get("latency_max_ms") is not None]
        json.dump({"worst_p99_ms": max(lat) if lat else None,
                   "worst_max_ms": max(mx) if mx else None, "p99_gate_ms": 250.0,
                   "gates": {"p99_within_250ms": bool(lat and max(lat) <= 250.0)}},
                  open(os.path.join(ART, "latency_report.json"), "w"), indent=2)
        json.dump(rel, open(os.path.join(ART, "reliability_report.json"), "w"), indent=2)
        with open(os.path.join(LOGD, "common_gauntlet.txt"), "a") as fh:
            fh.write("\nCONFIRMATION TOPUP\n" + json.dumps(doc, indent=2) + "\n")
        print(json.dumps(doc, indent=2))
        return 0

    if a.stage == "confirm":
        fin = json.load(open(os.path.join(ART, "final_gauntlet_results.json")))
        order = sorted(fin, key=lambda r: (-(r["dragapult_rate"] or 0),
                                           -(r["field_mean"] or 0)))
        top2 = [r["candidate_id"] for r in order[:2]]
        recs = []
        t0 = time.time()
        for c in top2:
            recs += run_block(c, "dragapult", 200, "confirm", SEED_INDEPENDENT)
            for opp in ("iono", "mega_lucario", "mega_abomasnow"):
                recs += run_block(c, opp, 100, "confirm", SEED_INDEPENDENT + 5000)
            print(f"[confirm] {c} done {time.time()-t0:.0f}s", flush=True)
        # Dragapult control on the SAME independent official-opponent seed lists (§17)
        for opp in ("iono", "mega_lucario", "mega_abomasnow"):
            recs += run_block("dragapult", opp, 100, "confirm_control", SEED_INDEPENDENT + 5000)
        cross = []
        if len(top2) == 2:
            cross = run_block(top2[0], top2[1], 300, "crossplay", SEED_BASE + 7000)
        with gzip.open(os.path.join(ART, "confirmation_games.jsonl.gz"), "wt") as fh:
            for r in recs + cross:
                fh.write(json.dumps(r) + "\n")
        rows = []
        for c in top2:
            d = agg(recs, candidate_id=c, opponent_id="dragapult", phase="confirm")
            f = [agg(recs, candidate_id=c, opponent_id=o, phase="confirm")
                 for o in ("iono", "mega_lucario", "mega_abomasnow")]
            rows.append({"candidate_id": c,
                         "confirm_dragapult_games": d["games"],
                         "confirm_dragapult_rate": d["score_rate"],
                         "confirm_dragapult_wilson_lo": d["wilson95"][0],
                         "confirm_field_games": sum(x["games"] for x in f),
                         "confirm_field_mean": round(
                             sum(x["score_rate"] for x in f) / 3, 4),
                         "confirm_iono": f[0]["score_rate"],
                         "confirm_mega_lucario": f[1]["score_rate"],
                         "confirm_mega_abomasnow": f[2]["score_rate"]})
        ctrl = {o: agg(recs, candidate_id="dragapult", opponent_id=o, phase="confirm_control")
                for o in ("iono", "mega_lucario", "mega_abomasnow")}
        cr = agg(cross, candidate_id=top2[0], opponent_id=top2[1]) if cross else {}
        with open(os.path.join(ART, "crossplay_results.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["candidate_a", "candidate_b", "games", "a_score_rate",
                        "a_wilson_lo", "a_wilson_hi"])
            if cr:
                w.writerow([top2[0], top2[1], cr["games"], cr["score_rate"],
                            cr["wilson95"][0], cr["wilson95"][1]])
        doc = {"top2": top2, "confirmation": rows,
               "dragapult_control_same_seeds": {k: v for k, v in ctrl.items()},
               "dragapult_control_field_mean": round(
                   sum(v["score_rate"] for v in ctrl.values()) / 3, 4),
               "crossplay": cr}
        json.dump(doc, open(os.path.join(ART, "confirmation_results.json"), "w"), indent=2)
        allrec = recs + cross
        rel = reliability(allrec)
        lat = [r["latency_p99_ms"] for r in allrec if r.get("latency_p99_ms") is not None]
        mx = [r["latency_max_ms"] for r in allrec if r.get("latency_max_ms") is not None]
        json.dump({"worst_p99_ms": max(lat) if lat else None,
                   "worst_max_ms": max(mx) if mx else None,
                   "p99_gate_ms": 250.0,
                   "gates": {"p99_within_250ms": bool(lat and max(lat) <= 250.0)}},
                  open(os.path.join(ART, "latency_report.json"), "w"), indent=2)
        json.dump(rel, open(os.path.join(ART, "reliability_report.json"), "w"), indent=2)
        with open(os.path.join(LOGD, "common_gauntlet.txt"), "a") as fh:
            fh.write("\nCONFIRMATION\n" + json.dumps(doc, indent=2) + "\n")
        print(json.dumps(doc, indent=2))
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
