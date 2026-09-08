"""c012 §12/§13 — registered elite combinations, then freeze the three Phase-0 objects.

Weight soups are arithmetic averages of architecture-identical checkpoints, exported to the
runtime NPZ format so they evaluate through the established action stack like any other
policy. Logit ensembles are registered here and evaluated online.

Weights are frozen BEFORE results (§12 "No post-result weight tuning"): the registry is
written and hashed first, evaluation happens second.
"""

import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import c012_eval as ev  # noqa: E402
from cg import rl_policy as rlp, c009_eval as ce  # noqa: E402

ART = ev.ART
LOGD = ev.LOGD
COMPONENTS = ["S_611_g40127", "S_622_g39983", "S_633_g30176"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def make_soup(paths, out_path, seed=0):
    """Arithmetic average of architecture-identical RLPolicy checkpoints."""
    pols = [rlp.RLPolicy.load(p) for p in paths]
    cfgs = [tuple(sorted(p.trunk.cfg.items())) for p in pols]
    assert len(set(cfgs)) == 1, "soup requires architecture-identical checkpoints (§12)"
    sds = [p.state_dict() for p in pols]
    keys = set(sds[0])
    assert all(set(s) == keys for s in sds), "checkpoint key sets differ"
    avg = {k: np.mean([s[k] for s in sds], axis=0) for k in keys}
    base = pols[0]
    meta = np.array([base.trunk.cfg[k] for k in ("D", "Hs", "BV", "Hh", "HV", "Hd", "DV", "GH",
                                                 "CTX", "OH", "OH2", "SH")] + [seed],
                    dtype=np.int64)
    np.savez(out_path, __meta__=meta, **avg)
    return out_path


def validate_soup(path, deck):
    """§12 validation: finiteness, legal masking, latency, NPZ export, component hashes."""
    from cg import c010_train as ct
    pol = rlp.RLPolicy.load(path)
    sd = pol.state_dict()
    finite = all(np.all(np.isfinite(v)) for v in sd.values())
    job = {"policy_ckpt": path, "policy_version": 1, "policy_sha256": sha(path),
           "arm": "SOUPCHK", "seed": 0, "game_index": 0,
           "opponent": ("teacher", "mega_lucario"), "seat": 0, "rng_seed": 12345, "deck": deck}
    t0 = time.time()
    out = ct.play_training_game(job)
    dur = time.time() - t0
    m = out["meta"]
    return {"finite_weights": bool(finite), "n_tensors": len(sd),
            "smoke_game_terminal": bool(m["terminal"]),
            "invalid_actions": int(m["invalid_actions"]),
            "exceptions": int(m["exceptions"]),
            "legal_masking_ok": int(m["invalid_actions"]) == 0,
            "smoke_seconds": round(dur, 2), "npz_reloads": True}


def stage_register():
    os.makedirs(ART, exist_ok=True)
    reg = ev.build_candidate_registry()
    from cg.teachers import make_fresh
    deck = make_fresh(ev.TEACHER, ce.SOURCES).deck
    comps = {c: reg[c] for c in COMPONENTS if c in reg}
    assert len(comps) == 3, f"missing components: {set(COMPONENTS) - set(comps)}"

    ensembles = {}
    for combo in (("S_611_g40127", "S_622_g39983"), ("S_611_g40127", "S_633_g30176"),
                  ("S_622_g39983", "S_633_g30176"),
                  ("S_611_g40127", "S_622_g39983", "S_633_g30176")):
        cid = "ENSEMBLE_" + "+".join(c.split("_")[1] for c in combo)
        ensembles[cid] = {"components": list(combo), "weights": [1.0 / len(combo)] * len(combo),
                          "rule": "equal logit averaging (§12 first choice)",
                          "component_sha256": [reg[c]["checkpoint_sha256"] for c in combo]}

    soupdir = os.path.join(ART, "soups")
    os.makedirs(soupdir, exist_ok=True)
    soups = {}
    for combo in (("S_611_g40127", "S_622_g39983"), ("S_611_g40127", "S_633_g30176"),
                  ("S_622_g39983", "S_633_g30176"),
                  ("S_611_g40127", "S_622_g39983", "S_633_g30176")):
        cid = "SOUP_" + "+".join(c.split("_")[1] for c in combo)
        outp = os.path.join(soupdir, f"{cid}.npz")
        make_soup([os.path.join(_REPO, reg[c]["checkpoint_path"]) for c in combo], outp)
        soups[cid] = {"components": list(combo),
                      "weights": [1.0 / len(combo)] * len(combo),
                      "rule": "equal arithmetic weight average (§12)",
                      "component_sha256": [reg[c]["checkpoint_sha256"] for c in combo],
                      "checkpoint_path": os.path.relpath(outp, _REPO),
                      "sha256": sha(outp),
                      "validation": validate_soup(outp, deck)}
    doc = {"note": "Registered BEFORE any combination result is seen (§12). Equal weighting "
                   "only; no post-result tuning.",
           "components": {c: {"sha256": reg[c]["checkpoint_sha256"],
                              "checkpoint_path": reg[c]["checkpoint_path"]} for c in comps},
           "ensembles": ensembles, "soups": soups}
    json.dump(doc, open(os.path.join(ART, "elite_combination_registry.json"), "w"), indent=2)
    with open(os.path.join(LOGD, "elite_combination_eval.txt"), "w") as fh:
        fh.write("c012 §12 elite combination registry\n\n")
        for cid, m in soups.items():
            fh.write(f"  {cid:22s} {m['sha256'][:12]} validation={json.dumps(m['validation'])}\n")
        for cid, m in ensembles.items():
            fh.write(f"  {cid:22s} components={m['components']}\n")
    print(json.dumps({"ensembles": list(ensembles), "soups": list(soups),
                      "all_soups_valid": all(s["validation"]["finite_weights"]
                                             and s["validation"]["legal_masking_ok"]
                                             for s in soups.values())}, indent=2))


def stage_freeze():
    """§13 — TRAINING_INCUMBENT, EVALUATION_ELITE, ELITE_POOL."""
    reg = ev.build_candidate_registry()
    games = ev.load_existing()
    # pool c011 + c010 confirmation evidence (read-only) so every candidate is on 500 games
    import gzip
    for older in ("c011_fixed_deck_cuda_ppo_scale", "c010_fixed_deck_rl_loop_v2"):
        p = os.path.join(_REPO, "contracts", older, "results", "artifacts",
                         "evaluation_games.jsonl.gz")
        if os.path.exists(p):
            seen = {g["job_id"] for g in games}
            for l in gzip.open(p, "rt"):
                g = json.loads(l)
                if g["job_id"] not in seen:
                    games.append(g)
    rng = np.random.default_rng(20260726)
    cands = {}
    for cid in reg:
        if cid == "T_teacher":
            continue
        s, d = ev.summarize(games, cid, {"confirmation"}, rng)
        if s and s["promotion_composite"] is not None and s["reliability"]["games"] >= 500:
            cands[cid] = s
    assert cands, "no confirmed candidates"

    def key(cid):
        s = cands[cid]; po = s["per_opponent"]
        worst = min((po[o]["point"] for o in ev.ALL_OPPS if o in po), default=0.0)
        rel = s["reliability"]
        rel_ok = all(rel[k] == 0 for k in ("defects", "invalid", "exceptions", "timeouts"))
        return (s["teacher_score"], s["strategic_field_score"],
                po.get("mega_abomasnow", {}).get("point") or 0, worst, 1 if rel_ok else 0,
                -(s["latency_p99_max_ms"] or 0), -(reg[cid].get("training_games") or 0))

    ranked = sorted(cands, key=key, reverse=True)
    # TRAINING_INCUMBENT must be a single trainable checkpoint or a validated soup (§13)
    trainable = [c for c in ranked if reg[c]["kind"] == "rl_ckpt"]
    inc = trainable[0]
    elite_id = ranked[0]

    # ELITE_POOL: diverse strong policies. Diversity by seed/branch of origin, so the pool is
    # not three near-copies of one lineage (§23 "diverse frozen policies").
    pool, seen_lineage = [], set()
    for cid in ranked:
        if reg[cid]["kind"] != "rl_ckpt":
            continue
        lineage = (reg[cid].get("arm"), reg[cid].get("seed"))
        if lineage in seen_lineage:
            continue
        s = cands[cid]
        if s["promotion_composite"] < 0.25:
            continue
        seen_lineage.add(lineage)
        pool.append({"id": cid, "checkpoint_path": reg[cid]["checkpoint_path"],
                     "sha256": reg[cid]["checkpoint_sha256"],
                     "teacher": s["teacher_score"], "field": s["strategic_field_score"],
                     "composite": s["promotion_composite"],
                     "lineage": f"{lineage[0]}_{lineage[1]}"})
        if len(pool) >= 4:
            break

    def entry(cid):
        s = cands[cid]
        p = os.path.join(_REPO, reg[cid]["checkpoint_path"])
        return {"candidate_id": cid, "checkpoint_path": reg[cid]["checkpoint_path"],
                "checkpoint_sha256": sha(p), "kind": reg[cid]["kind"],
                "arm": reg[cid].get("arm"), "seed": reg[cid].get("seed"),
                "training_games": reg[cid].get("training_games"),
                "components": reg[cid].get("components"),
                "teacher_score": s["teacher_score"],
                "strategic_field_score": s["strategic_field_score"],
                "promotion_composite": s["promotion_composite"],
                "abomasnow": s["per_opponent"].get("mega_abomasnow", {}).get("point"),
                "confirmation_games": s["reliability"]["games"], "protected": True}

    doc = {"selection_rule": "§13 priority: teacher, strategic field, Abomasnow, worst-matchup "
                             "risk, latency, earlier training games. Confirmation evidence "
                             "only, so every candidate is judged on an equal 500-game footing.",
           "n_candidates_considered": len(cands),
           "TRAINING_INCUMBENT": entry(inc),
           "EVALUATION_ELITE": entry(elite_id),
           "evaluation_elite_note": ("An online logit ensemble may be EVALUATION_ELITE but may "
                                     "never be the trainable initialisation unless represented "
                                     "by a validated soup (§13)."),
           "ranking": ranked[:15],
           "scores": {c: {"teacher": cands[c]["teacher_score"],
                          "field": cands[c]["strategic_field_score"],
                          "composite": cands[c]["promotion_composite"]} for c in ranked[:15]}}
    json.dump(doc, open(os.path.join(ART, "frozen_incumbent_registry.json"), "w"), indent=2)
    json.dump({"note": "Diverse strong frozen policies used as fixed opponents (§23). "
                       "Diversity is enforced by lineage (arm, seed) so the pool is not "
                       "several near-copies of one branch.",
               "n": len(pool), "elite_pool": pool},
              open(os.path.join(ART, "elite_pool_registry.json"), "w"), indent=2)
    open(os.path.join(ART, "TRUE_INCUMBENT.md"), "w").write(
        f"# TRUE_INCUMBENT (AC-05)\n\n**TRAINING_INCUMBENT = {inc}**\n\n"
        f"- teacher {cands[inc]['teacher_score']:.4f}, field "
        f"{cands[inc]['strategic_field_score']:.4f}, composite "
        f"{cands[inc]['promotion_composite']:.4f} on 500 confirmation games\n"
        f"- sha256 `{doc['TRAINING_INCUMBENT']['checkpoint_sha256']}`\n\n"
        f"**EVALUATION_ELITE = {elite_id}**\n\n"
        f"**ELITE_POOL** ({len(pool)}): " + ", ".join(p["id"] for p in pool) + "\n\n"
        f"Selected from {len(cands)} correctly confirmed candidates by the §13 priority order. "
        f"Frozen and hashed before Phase 1.\n")
    with open(os.path.join(LOGD, "incumbent_freeze.txt"), "w") as fh:
        fh.write(f"TRAINING_INCUMBENT={inc}  EVALUATION_ELITE={elite_id}\n")
        fh.write(f"ELITE_POOL={[p['id'] for p in pool]}\n\n")
        for c in ranked[:15]:
            s = cands[c]
            fh.write(f"  {c:22s} t={s['teacher_score']:.4f} f={s['strategic_field_score']:.4f} "
                     f"comp={s['promotion_composite']:.4f} n={s['reliability']['games']}\n")
    print(json.dumps({"TRAINING_INCUMBENT": inc, "EVALUATION_ELITE": elite_id,
                      "elite_pool": [p["id"] for p in pool],
                      "considered": len(cands),
                      "incumbent_scores": {k: cands[inc][k] for k in
                                           ("teacher_score", "strategic_field_score",
                                            "promotion_composite")}}, indent=2))


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--stage", required=True, choices=["register", "freeze"])
    a = p.parse_args(argv)
    os.makedirs(LOGD, exist_ok=True)
    if a.stage == "register":
        stage_register()
    else:
        stage_freeze()
    return 0


if __name__ == "__main__":
    sys.exit(main())
