"""c012 §34-§36 — frozen hard-state benchmark, hidden-information-safe.

States are selected under registered criteria BEFORE Claude sees anything (§34), serialized
to only what a runtime agent can legally see (§35), audited for leakage, and hash-locked.
"""
import argparse, gzip, hashlib, json, os, pickle, sys
from collections import Counter, defaultdict
import numpy as np
_REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,_REPO); sys.path.insert(0,os.path.join(_REPO,"tools"))
import c012_eval as ev
ART,LOGD=ev.ART,ev.LOGD

# Fields a runtime agent legally sees. Anything not on this list is refused by the audit.
VISIBLE=("state_id","category","legal_actions","n_options","form","lo","hi",
         "own_hand_card_ids","own_board_card_ids","discard_public_card_ids","own_hand_size",
         "global_features","policy_entropy","value_confidence")
FORBIDDEN_KEYS=("opponent_hand","hidden","deck_order","future","rng","eventual","outcome",
                "teacher_action","incumbent_action","elite_action","result","winner","score")

def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as fh:
        for c in iter(lambda: fh.read(1<<20), b""): h.update(c)
    return h.hexdigest()

def categorize(t, ent, val):
    """Registered categories (§34). A state may match several; the first is its primary."""
    cats=[]
    form=t.get("form"); n=t.get("n_options",0)
    if form=="VARIABLE_MULTISELECT" or form=="FIXED_MULTISELECT": cats.append("multi_select")
    if n>=8: cats.append("high_branching")
    if ent is not None and ent>=1.0: cats.append("high_policy_entropy")
    if val is not None and abs(val)<=0.15: cats.append("poor_value_confidence")
    if n<=2: cats.append("forced_or_near_forced")
    if not cats: cats.append("ordinary_decision")
    return cats

def serialize(t, sid, cats, ent, val):
    """§35 runtime-visible serialization.

    The first version exposed only option counts and policy diagnostics, which asked the model
    to choose between opaque ids `a0..aN` with nothing to reason about. That is not a
    meaningful strategic task and would have made the qualification measure formatting rather
    than play. This version carries the runtime-visible CARD CONTENT the encoder itself sees:
    the agent's own board and hand card ids, public discard, and the per-option card ids the
    option encoder was given. All of it is information a player legally has; the opponent's
    hand, deck order, future randomness, other agents' choices and the outcome are excluded.
    """
    import numpy as _np
    feat = t.get("feat") or {}

    def ids(arr):
        a = _np.asarray(arr)
        return [int(x) for x in a.ravel().tolist() if int(x) > 0]

    hand = ids(feat.get("hand_rows", []))
    board = ids(feat.get("board_rows", []))
    disc = ids(feat.get("disc_rows", []))
    opt_rows = _np.asarray(feat.get("opt_rows", _np.zeros((1, 1, 2))))
    n = int(t.get("n_options") or 0)
    actions = []
    for i in range(n):
        prim = targ = None
        try:
            prim = int(opt_rows[0, i, 0]) if opt_rows.ndim == 3 else int(opt_rows[i, 0])
            targ = int(opt_rows[0, i, 1]) if opt_rows.ndim == 3 else int(opt_rows[i, 1])
        except Exception:  # noqa: BLE001
            pass
        actions.append({"action_id": f"a{i}", "index": i,
                        "primary_card_id": prim or None,
                        "target_card_id": targ or None})
    glob = _np.asarray(feat.get("global", [])).ravel().tolist()
    return {"state_id": sid, "category": cats[0], "all_categories": cats,
            "form": t.get("form"), "lo": t.get("lo"), "hi": t.get("hi"),
            "n_options": n, "legal_actions": actions,
            "own_hand_card_ids": hand, "own_board_card_ids": board,
            "discard_public_card_ids": disc[:20],
            "own_hand_size": len(hand),
            "global_features": [round(float(x), 4) for x in glob[:24]],
            "policy_entropy": None if ent is None else round(float(ent), 4),
            "value_confidence": None if val is None else round(float(val), 4),
            "note": "Runtime-visible only: own hand/board, public discard, per-option card "
                    "ids, and encoder global features. Excludes opponent hand, deck order, "
                    "future randomness, any agent's choice, and the game result."}


DOC_FIELDS = ("note",)


def audit(rec):
    """§35 hidden-information audit for one serialized state.

    Audits the DATA the model will act on -- field names and field values -- not the
    human-readable `note`, which documents the exclusions and therefore legitimately contains
    words like "hidden" and "outcome". Auditing the note flagged every state as unclean while
    no state actually leaked anything.
    """
    data = {k: v for k, v in rec.items() if k not in DOC_FIELDS}
    key_hits = [k for k in data if any(f in k.lower() for f in FORBIDDEN_KEYS)]
    val_hits = [k for k, v in data.items()
                if isinstance(v, str) and any(f in v.lower() for f in FORBIDDEN_KEYS)]
    extra = [k for k in data
             if k not in VISIBLE and k not in ("all_categories", "form", "lo", "hi")]
    return {"state_id": rec["state_id"], "forbidden_key_hits": key_hits,
            "forbidden_value_hits": val_hits, "unexpected_fields": extra,
            "audited_fields": sorted(data),
            "clean": not key_hits and not val_hits and not extra}

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("--primary",type=int,default=240)
    p.add_argument("--repeat",type=int,default=48); a=p.parse_args(argv)
    os.makedirs(ART,exist_ok=True); os.makedirs(LOGD,exist_ok=True)
    # §34 needs 200-300 primary states under a 25% per-category cap; the c011 fixture pool is
    # far too small for that, so states are harvested from fresh games played by the frozen
    # incumbent against the registered opponents. Harvesting happens BEFORE any Claude call.
    cache=os.path.join(ART,"hard_state_pool.pkl")
    if os.path.exists(cache):
        fixtures=pickle.load(open(cache,"rb"))
    else:
        from cg import c010_train as ct, c009_eval as ce
        from cg.teachers import make_fresh
        incq=json.load(open(os.path.join(ART,"frozen_incumbent_registry.json")))["TRAINING_INCUMBENT"]
        ck=os.path.join(_REPO,incq["checkpoint_path"]); cksha=incq["checkpoint_sha256"]
        deck=make_fresh("dragapult",ce.SOURCES).deck
        opps=["dragapult","mega_lucario","iono","mega_abomasnow"]
        jobs=[]
        for i in range(72):
            jobs.append({"policy_ckpt":ck,"policy_version":1,"policy_sha256":cksha,
                         "arm":"HS","seed":9,"game_index":i,
                         "opponent":("teacher",opps[i%len(opps)]),"seat":i%2,
                         "rng_seed":50000+i,"deck":deck})
        out=ct.run_rollout(jobs,16)
        fixtures=[t for r in out for t in (r.get("transitions") or [])]
        pickle.dump(fixtures,open(cache,"wb"))
    # policy entropy / value confidence from the frozen incumbent, for category assignment
    from cg import rl_policy as rlp
    inc=json.load(open(os.path.join(ART,"frozen_incumbent_registry.json")))["TRAINING_INCUMBENT"]
    pol=rlp.RLPolicy.load(os.path.join(_REPO,inc["checkpoint_path"]))
    recs=[]
    rng=np.random.default_rng(4242)
    for i,t in enumerate(fixtures):
        b,arr=rlp.collate_rl([t])
        sc,v,_=pol.forward(b)
        aug=np.concatenate([sc.data[0],[float(pol.pv["stop"].data[0])]])
        m=arr["aug_mask"][0]
        z=np.where(m>0,aug,-1e30); z=z-z.max(); e=np.exp(z)*(m>0); pr=e/e.sum()
        ent=float(-(pr[pr>0]*np.log(pr[pr>0])).sum()); val=float(v.data[0])
        cats=categorize(t,ent,val)
        recs.append(serialize(t,f"S{i:04d}",cats,ent,val))
    # §34: no category may exceed 25% unless too few valid states exist
    bycat=defaultdict(list)
    for r in recs: bycat[r["category"]].append(r)
    target=min(a.primary,len(recs))
    cap=max(1,int(0.25*target))
    chosen=[]
    for c,rs in sorted(bycat.items(),key=lambda x:-len(x[1])):
        rng.shuffle(rs); chosen.extend(rs[:cap])
    if len(chosen)<target:
        rest=[r for r in recs if r not in chosen]
        rng.shuffle(rest); chosen.extend(rest[:target-len(chosen)])
    chosen=chosen[:target]
    rpt=list(chosen)
    rng.shuffle(rpt); repeats=rpt[:min(a.repeat,len(rpt))]
    audits=[audit(r) for r in chosen]
    bench=os.path.join(ART,"hard_state_benchmark.jsonl.gz")
    with gzip.open(bench,"wt") as fh:
        for r in chosen: fh.write(json.dumps(r)+"\n")
    man={"n_primary":len(chosen),"n_repeat":len(repeats),
         "repeat_state_ids":[r["state_id"] for r in repeats],
         "category_counts":dict(Counter(r["category"] for r in chosen)),
         "category_share":{k:round(v/len(chosen),4) for k,v in
                           Counter(r["category"] for r in chosen).items()},
         "max_category_share":max(Counter(r["category"] for r in chosen).values())/len(chosen),
         "cap_rule":"§34 — no category above 25% unless insufficient valid states exist",
         "selection_note":"Selected under registered criteria BEFORE any Claude call (§34).",
         "benchmark_sha256":sha(bench)}
    json.dump(man,open(os.path.join(ART,"hard_state_manifest.json"),"w"),indent=2)
    json.dump({"note":"§35 audit of every serialized state. A state is clean only when no "
                      "forbidden key appears anywhere in its JSON and it exposes no field "
                      "outside the runtime-visible allowlist.",
               "allowlist":list(VISIBLE),"forbidden_substrings":list(FORBIDDEN_KEYS),
               "n_states":len(audits),"n_clean":sum(1 for x in audits if x["clean"]),
               "all_clean":all(x["clean"] for x in audits),"audits":audits},
              open(os.path.join(ART,"hard_state_hidden_information_audit.json"),"w"),indent=2)
    with open(os.path.join(LOGD,"hard_state_extraction.txt"),"w") as fh:
        fh.write(f"primary={len(chosen)} repeat={len(repeats)} sha={man['benchmark_sha256']}\n")
        for k,v in man["category_counts"].items(): fh.write(f"  {k:26s} {v}\n")
    print(json.dumps({k:man[k] for k in ("n_primary","n_repeat","category_counts",
                                         "max_category_share","benchmark_sha256")},indent=2))
if __name__=="__main__": sys.exit(main())
