"""c011 §19 — checkpoint nomination, applied prospectively in checkpoint order.

A checkpoint is nominated when ANY registered condition holds. The last condition (a late
checkpoint within 0.03 of the seed's best screen composite) exists specifically so a noisy
early screen peak cannot hide a stronger late checkpoint -- the failure mode c010's §7.1
repair had to clean up afterwards.
"""
import argparse, csv, json, os, sys
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO); sys.path.insert(0, os.path.join(_REPO, "tools"))
import c011_eval as ev
ART = ev.ART; LOGD = ev.LOGD
FIELDS = ["candidate_id","seed","training_games","registered_eval_point","teacher_score",
          "teacher_one_sided_lb95","strategic_field_score","promotion_composite",
          "composite_ci95_lo","composite_ci95_hi","games","defects","invalid",
          "nominated","nomination_reasons"]

def nominate(screen, best_conf, best_screen_comp, is_final, late):
    r = []
    t, f, c = (screen.get("teacher_score"), screen.get("strategic_field_score"),
               screen.get("promotion_composite"))
    if best_conf:
        if t is not None and best_conf.get("teacher_score") is not None and \
           t - best_conf["teacher_score"] >= 0.03 - 1e-9:
            r.append("teacher screen exceeds seed best confirmed by >=0.03")
        if f is not None and best_conf.get("strategic_field_score") is not None and \
           f - best_conf["strategic_field_score"] >= 0.04 - 1e-9:
            r.append("field screen exceeds seed best confirmed by >=0.04")
    if c is not None and (best_screen_comp is None or c > best_screen_comp):
        r.append("promotion composite exceeds seed current best screen")
    if is_final:
        r.append("seed's final registered checkpoint")
    if late and c is not None and best_screen_comp is not None and \
       c >= best_screen_comp - 0.03 - 1e-9:
        r.append("late checkpoint within 0.03 of seed best screen composite")
    return {"nominated": bool(r), "reasons": r}

def main(argv=None):
    p = argparse.ArgumentParser(); p.add_argument("--stage", required=True,
                                                  choices=["nominate","confirm"])
    a = p.parse_args(argv)
    reg = json.load(open(os.path.join(ART, "evaluation_candidate_registry.json")))
    screen = json.load(open(os.path.join(ART, "panel_screen_summaries.json")))
    if a.stage == "nominate":
        branches = {}
        for cid, m in reg.items():
            if m.get("arm") == "S" and cid in screen:
                branches.setdefault(m["seed"], []).append(cid)
        for k in branches:
            branches[k].sort(key=lambda c: reg[c]["training_games"])
        rows, noms = [], []
        for seed, cids in sorted(branches.items()):
            budget = max(reg[c]["training_games"] for c in cids)
            best_screen_comp, best_conf = None, None
            for i, cid in enumerate(cids):
                s = screen[cid]
                late = reg[cid]["training_games"] >= 0.75 * budget
                d = nominate(s, best_conf, best_screen_comp, i == len(cids) - 1, late)
                if d["nominated"]:
                    noms.append(cid)
                ci = s.get("composite_ci95") or [None, None]
                rows.append({"candidate_id": cid, "seed": seed,
                             "training_games": reg[cid]["training_games"],
                             "registered_eval_point": reg[cid].get("registered_eval_point"),
                             "teacher_score": s.get("teacher_score"),
                             "teacher_one_sided_lb95": s.get("teacher_one_sided_lb95"),
                             "strategic_field_score": s.get("strategic_field_score"),
                             "promotion_composite": s.get("promotion_composite"),
                             "composite_ci95_lo": ci[0], "composite_ci95_hi": ci[1],
                             "games": s["reliability"]["games"],
                             "defects": s["reliability"]["defects"],
                             "invalid": s["reliability"]["invalid"],
                             "nominated": d["nominated"],
                             "nomination_reasons": "; ".join(d["reasons"])})
                if s.get("promotion_composite") is not None and (
                        best_screen_comp is None or s["promotion_composite"] > best_screen_comp):
                    best_screen_comp = s["promotion_composite"]
        with open(os.path.join(ART, "checkpoint_screening.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader()
            for r in sorted(rows, key=lambda r: (r["seed"], r["training_games"])):
                w.writerow(r)
        json.dump({"rule": "§19", "nominated": noms, "n_nominated": len(noms),
                   "n_screened": len(rows),
                   "branches": {str(k): v for k, v in branches.items()}},
                  open(os.path.join(ART, "screening_nominations.json"), "w"), indent=2)
        print(json.dumps({"screened": len(rows), "nominated": noms}, indent=2))
    else:
        conf = json.load(open(os.path.join(ART, "panel_confirmation_summaries.json")))
        noms = json.load(open(os.path.join(ART, "screening_nominations.json")))["nominated"]
        out = {}
        for cid in noms:
            c = conf.get(cid); s = screen.get(cid, {})
            out[cid] = {"seed": reg[cid]["seed"], "training_games": reg[cid]["training_games"],
                        "trainer_state_id": reg[cid].get("trainer_state_id"),
                        "screen": {"teacher": s.get("teacher_score"),
                                   "field": s.get("strategic_field_score"),
                                   "composite": s.get("promotion_composite")},
                        "confirmation": ({"teacher": c.get("teacher_score"),
                                          "teacher_lb95": c.get("teacher_one_sided_lb95"),
                                          "field": c.get("strategic_field_score"),
                                          "composite": c.get("promotion_composite"),
                                          "composite_ci95": c.get("composite_ci95"),
                                          "games": c["reliability"]["games"]} if c else None),
                        "reliability": c["reliability"] if c else None}
        json.dump({"note": "Confirmation is a 500-game panel on every §19 nomination; "
                           "nominations that do not survive are retained as evidence.",
                   "n_nominated": len(noms),
                   "n_with_panel": sum(1 for v in out.values() if v["confirmation"]),
                   "candidates": out},
                  open(os.path.join(ART, "checkpoint_confirmation.json"), "w"), indent=2)
        print(json.dumps({"nominated": len(noms),
                          "with_panel": sum(1 for v in out.values() if v["confirmation"])},
                         indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
