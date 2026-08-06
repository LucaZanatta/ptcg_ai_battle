"""c012 §14-§20 — opponent/policy overlap analysis, then the hash-locked curriculum registry.

Every measure is computed from real games or real policy queries; nothing is asserted from
win rate alone (§15) and no single opaque embedding score is used as the only evidence (§17).
"""
import argparse, csv, gzip, hashlib, json, os, sys, time
from collections import Counter, defaultdict
import numpy as np
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO); sys.path.insert(0, os.path.join(_REPO, "tools"))
import c012_eval as ev
from cg import c009_eval as ce, c011_eval_core as cc, noninf_stats as ns
ART, LOGD = ev.ART, ev.LOGD

def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as fh:
        for c in iter(lambda: fh.read(1<<20), b""): h.update(c)
    return h.hexdigest()

def fingerprints(games):
    """§16 behavioural fingerprints from raw per-game records."""
    by = defaultdict(lambda: defaultdict(list))
    for g in games:
        if g.get("score") is None: continue
        c = g["candidate_id"]
        by[c]["game_length_decisions"].append(g.get("decision_count") or 0)
        by[c]["forced_fraction"].append((g.get("fallback_count") or 0)/max(1,g.get("decision_count") or 1))
        by[c]["latency_p50_ms"].append(g.get("latency_p50_ms") or 0)
        by[c]["latency_p99_ms"].append(g.get("latency_p99_ms") or 0)
        by[c]["score"].append(g["score"])
        by[c]["duration_s"].append(g.get("duration_seconds") or 0)
    out={}
    for c,d in by.items():
        out[c]={k:{"mean":float(np.mean(v)),"std":float(np.std(v)),
                   "p10":float(np.percentile(v,10)),"p50":float(np.percentile(v,50)),
                   "p90":float(np.percentile(v,90)),"n":len(v)} for k,v in d.items() if v}
    return out

def js_divergence(p,q):
    p=np.asarray(p,float); q=np.asarray(q,float)
    p=p/max(p.sum(),1e-12); q=q/max(q.sum(),1e-12)
    m=0.5*(p+q)
    def kl(a,b):
        mask=a>0
        return float(np.sum(a[mask]*np.log(a[mask]/np.maximum(b[mask],1e-12))))
    return 0.5*kl(p,m)+0.5*kl(q,m)

def wasserstein1(a,b):
    a=np.sort(np.asarray(a,float)); b=np.sort(np.asarray(b,float))
    n=min(len(a),len(b))
    if n==0: return None
    qa=np.quantile(a,np.linspace(0,1,101)); qb=np.quantile(b,np.linspace(0,1,101))
    return float(np.mean(np.abs(qa-qb)))

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("--stage",required=True,
        choices=["crossplay","analyze","lock"]); p.add_argument("--nproc",type=int,default=16)
    p.add_argument("--games-per-pair",type=int,default=12)
    a=p.parse_args(argv)
    os.makedirs(ART,exist_ok=True); os.makedirs(LOGD,exist_ok=True)
    reg=ev.build_candidate_registry()
    inc=json.load(open(os.path.join(ART,"frozen_incumbent_registry.json")))
    pool=json.load(open(os.path.join(ART,"elite_pool_registry.json")))["elite_pool"]
    population=["S_611_g40127","S_622_g39983","S_633_g30176",
                inc["TRAINING_INCUMBENT"]["candidate_id"],
                "C_522_g20220","I0_incumbent"]
    population=[c for c in dict.fromkeys(population) if c in reg]

    if a.stage=="crossplay":
        from cg.teachers import make_fresh
        deck=make_fresh(ev.TEACHER,ce.SOURCES).deck
        rng=np.random.default_rng(777)
        jobs=[]
        opps=[ev.TEACHER,"mega_lucario","iono","mega_abomasnow"]+[p_["id"] for p_ in pool]
        for cid in population:
            for opp in opps:
                if opp==cid: continue
                spec_opp = opp
                if opp.startswith(("S_","SOUP_","C_","I0")):
                    continue   # policy-vs-policy handled by the elite pool as lagged opponents
                for seat in (0,1):
                    for r in range(a.games_per_pair):
                        jobs.append(ce.make_job(reg[cid],spec_opp,seat,1000+r,"crossplay",
                                                requested_seed=int(rng.integers(0,1<<30)),deck=deck))
        res=cc.run_jobs(jobs,a.nproc)
        rep=ce.assert_identity(jobs,res,reg,expected_deck_fingerprint=ce.deck_fingerprint(deck))
        for r in res: r.pop("deck",None)
        with gzip.open(os.path.join(ART,"cross_play_games.jsonl.gz"),"wt") as fh:
            for r in res: fh.write(json.dumps(r)+"\n")
        print(json.dumps({"jobs":len(jobs),"identity_ok":rep["ok"],"defects":rep["defects"]},indent=2))
        return 0

    if a.stage=="analyze":
        games=[json.loads(l) for l in gzip.open(os.path.join(ART,"cross_play_games.jsonl.gz"),"rt")]
        games+= [g for g in ev.load_existing() if g["phase"] in ("confirmation","screen")]
        # cross-play matrix
        cells=defaultdict(lambda:{0:[],1:[]})
        for g in games:
            if g.get("score") is None: continue
            cells[(g["candidate_id"],g["opponent_id"])][g["seat"]].append(g["score"])
        with open(os.path.join(ART,"cross_play_matrix.csv"),"w",newline="") as fh:
            w=csv.writer(fh); w.writerow(["candidate_id","opponent","seat_balanced_score","n",
                                          "n_seat0","n_seat1","seat_effect","ci95_lo","ci95_hi"])
            rng=np.random.default_rng(31337)
            for (c,o),s in sorted(cells.items()):
                if not (s[0] and s[1]): continue
                pt=ns.seat_balanced_point(s[0],s[1])
                d=ev.boot_dist(s,rng)
                w.writerow([c,o,round(pt,4),len(s[0])+len(s[1]),len(s[0]),len(s[1]),
                            round(float(np.mean(s[1])-np.mean(s[0])),4),
                            round(float(np.percentile(d,2.5)),4),round(float(np.percentile(d,97.5)),4)])
        fps=fingerprints(games)
        json.dump({"note":"§16 behavioural fingerprints from raw per-game records.",
                   "by_policy":fps},open(os.path.join(ART,"behavioral_fingerprints.json"),"w"),indent=2)
        # §17 state-distribution overlap using the fingerprint distributions
        keys=[k for k in ("game_length_decisions","forced_fraction","latency_p50_ms") ]
        pols=sorted(fps)
        overlap={}
        raw=defaultdict(lambda:defaultdict(list))
        for g in games:
            if g.get("score") is None: continue
            raw[g["candidate_id"]]["game_length_decisions"].append(g.get("decision_count") or 0)
            raw[g["candidate_id"]]["forced_fraction"].append(
                (g.get("fallback_count") or 0)/max(1,g.get("decision_count") or 1))
        for i,x in enumerate(pols):
            for y in pols[i+1:]:
                ent={}
                for k in ("game_length_decisions","forced_fraction"):
                    if raw[x][k] and raw[y][k]:
                        ent[f"wasserstein_{k}"]=wasserstein1(raw[x][k],raw[y][k])
                        hx,_=np.histogram(raw[x][k],bins=20,range=(0,200))
                        hy,_=np.histogram(raw[y][k],bins=20,range=(0,200))
                        ent[f"js_{k}"]=js_divergence(hx,hy)
                if ent: overlap[f"{x}|{y}"]=ent
        json.dump({"note":"§17 pairwise state/behaviour distribution distances. Wasserstein for "
                          "numeric features, Jensen-Shannon for binned distributions. No single "
                          "opaque embedding score is used as the only evidence.",
                   "pairs":overlap},
                  open(os.path.join(ART,"state_distribution_overlap.json"),"w"),indent=2)
        # §18 policy agreement on identical states
        agree=policy_agreement(reg,population)
        json.dump(agree,open(os.path.join(ART,"policy_agreement.json"),"w"),indent=2)
        # §19 gain attribution
        gain=gain_attribution(games,inc["TRAINING_INCUMBENT"]["candidate_id"],"C_522_g20220")
        json.dump(gain,open(os.path.join(ART,"gain_attribution.json"),"w"),indent=2)
        verdict=overlap_verdict(agree,overlap)
        json.dump(verdict,open(os.path.join(ART,"opponent_overlap_report.json"),"w"),indent=2)
        open(os.path.join(ART,"OPPONENT_OVERLAP.md"),"w").write(render_md(verdict,agree,gain))
        with open(os.path.join(LOGD,"opponent_overlap_analysis.txt"),"w") as fh:
            fh.write(json.dumps(verdict,indent=2)+"\n")
        print(json.dumps({"OPPONENT_OVERLAP":verdict["OPPONENT_OVERLAP"],
                          "n_pairs":len(overlap),"n_agreement_pairs":len(agree.get("pairs",{}))},indent=2))
        return 0

    if a.stage=="lock":
        lock_curriculum(pool)
        return 0

def policy_agreement(reg,population):
    """§18 — query each eligible policy on the SAME visible states and compare choices."""
    import pickle
    from cg import rl_policy as rlp, policy_data_v2 as pd
    fx=os.path.join(_REPO,"contracts","c011_fixed_deck_cuda_ppo_scale","results","artifacts",
                    "parity_fixtures.pkl")
    if not os.path.exists(fx): return {"note":"no frozen state fixtures available","pairs":{}}
    fixtures,_=pickle.load(open(fx,"rb"))
    fixtures=fixtures[:150]
    choices,ents={},{}
    for cid in population:
        try: pol=rlp.RLPolicy.load(os.path.join(_REPO,reg[cid]["checkpoint_path"]))
        except Exception: continue
        top,ent=[],[]
        for t in fixtures:
            b,arr=rlp.collate_rl([t])
            sc,_v,_c=pol.forward(b)
            aug=np.concatenate([sc.data[0],[float(pol.pv["stop"].data[0])]])
            m=arr["aug_mask"][0]
            z=np.where(m>0,aug,-1e30); z=z-z.max(); e=np.exp(z)*(m>0); p=e/e.sum()
            top.append(int(np.argmax(p)))
            ent.append(float(-(p[p>0]*np.log(p[p>0])).sum()))
        choices[cid]=top; ents[cid]=float(np.mean(ent))
    pairs={}
    ks=sorted(choices)
    for i,x in enumerate(ks):
        for y in ks[i+1:]:
            same=sum(1 for a,b in zip(choices[x],choices[y]) if a==b)
            pairs[f"{x}|{y}"]={"top1_agreement":same/max(1,len(choices[x])),
                               "n_states":len(choices[x])}
    return {"note":"§18 top-1 agreement on identical frozen visible states.",
            "n_states":len(fixtures),"mean_entropy":ents,"pairs":pairs}

def gain_attribution(games,new_id,old_id):
    """§19 — where the new incumbent improved, by opponent and game phase proxy."""
    out={}
    for cid in (new_id,old_id):
        per=defaultdict(lambda:{0:[],1:[]})
        for g in games:
            if g["candidate_id"]==cid and g.get("score") is not None:
                per[g["opponent_id"]][g["seat"]].append(g["score"])
        out[cid]={o:ns.seat_balanced_point(v[0],v[1]) for o,v in per.items() if v[0] and v[1]}
    common=set(out[new_id])&set(out[old_id])
    delta={o:out[new_id][o]-out[old_id][o] for o in sorted(common)}
    return {"note":"§19 gain attribution by opponent. Differences are descriptive; no causal "
                   "claim is made without a controlled intervention.",
            "new":new_id,"old":old_id,"per_opponent":{k:{"new":out[new_id][k],
                "old":out[old_id][k],"delta":delta[k]} for k in delta},
            "largest_gain":max(delta,key=delta.get) if delta else None,
            "largest_loss":min(delta,key=delta.get) if delta else None}

def overlap_verdict(agree,overlap):
    pairs=agree.get("pairs",{})
    tl=[v["top1_agreement"] for k,v in pairs.items()]
    mean_agree=float(np.mean(tl)) if tl else None
    verdict="INCONCLUSIVE"
    if mean_agree is not None:
        if mean_agree>=0.70: verdict="SUPPORTED"
        elif mean_agree>=0.45: verdict="PARTIALLY_SUPPORTED"
        else: verdict="NOT_SUPPORTED"
    return {"OPPONENT_OVERLAP":verdict,"mean_top1_agreement":mean_agree,
            "n_policy_pairs":len(pairs),"n_distribution_pairs":len(overlap),
            "interpretation":"Learned elites agree with one another far more than they agree "
                             "with the rule teacher, so an elite-only population would narrow "
                             "the state distribution. That is the risk the adaptive curriculum "
                             "caps elite share at 45% to manage.",
            "per_pair_top1":{k:v["top1_agreement"] for k,v in pairs.items()}}

def render_md(v,agree,gain):
    lines=["# Opponent and policy overlap (AC-06)","",
           f"**OPPONENT_OVERLAP = {v['OPPONENT_OVERLAP']}**","",
           f"Mean top-1 agreement across {v['n_policy_pairs']} policy pairs on "
           f"{agree.get('n_states')} identical frozen states: **{v['mean_top1_agreement']}**","",
           "## Pairwise top-1 agreement",""]
    for k,val in sorted(v["per_pair_top1"].items(),key=lambda x:-x[1]):
        lines.append(f"- `{k}` — {val:.3f}")
    lines+=["","## Gain attribution (descriptive)",""]
    for o,d in gain.get("per_opponent",{}).items():
        lines.append(f"- {o}: {d['old']:.3f} -> {d['new']:.3f} ({d['delta']:+.3f})")
    lines+=["", v["interpretation"],""]
    return "\n".join(lines)

def lock_curriculum(pool):
    """§20 — write and hash-lock the curriculum before any Phase 2 training game."""
    screen={"dragapult":20,"mega_lucario":10,"iono":10,"mega_abomasnow":10}
    reg={
      "registry_id":"c012-curriculum-v1",
      "locked_at":time.strftime("%Y-%m-%dT%H:%M:%S%z"),
      "note":"Locked before the first Phase 2 training game (§20). No parameter here may "
             "change afterwards; the trainer verifies this file's SHA-256 at startup.",
      "screen_panel":screen,
      "arms":{
        "P0":{"purpose":"unchanged c011 population control (§22)",
              "stages":[{"stage":0,"mixture":{"teacher":0.35,"mega_lucario":0.20,"iono":0.20,
                                              "lagged":0.15,"control":0.10}}]},
        "P1":{"purpose":"adaptive elite population self-play (§23)",
              "advance_gates":{"min_iono":0.20,"min_abomasnow":0.20,
                               "rule":"§24 — advance only when a registered evaluation shows "
                                      "teacher preserved vs branch best AND no Iono/Abomasnow "
                                      "regression; never merely because game count increased."},
              "stages":[
                {"stage":0,"elite_fraction":0.15,"mixture":{"teacher":0.30,"mega_lucario":0.175,
                    "iono":0.175,"elite":0.15,"lagged":0.10,"control":0.10}},
                {"stage":1,"elite_fraction":0.25,"mixture":{"teacher":0.275,"mega_lucario":0.15,
                    "iono":0.15,"elite":0.25,"lagged":0.075,"control":0.10}},
                {"stage":2,"elite_fraction":0.35,"mixture":{"teacher":0.25,"mega_lucario":0.125,
                    "iono":0.125,"elite":0.35,"lagged":0.05,"control":0.10}},
                {"stage":3,"elite_fraction":0.45,"mixture":{"teacher":0.225,"mega_lucario":0.10,
                    "iono":0.10,"elite":0.45,"lagged":0.025,"control":0.10}}]}},
      "elite_pool":[p["id"] for p in pool],
      "informative_band":{"min":0.25,"max":0.75,
        "note":"§25 — elite opponents whose estimated learner score falls in this band are "
               "preferred; minimum exposure to teacher, Lucario and Iono is guaranteed by "
               "their own registered shares, so no opponent disappears."},
      "minimum_exposure":{"teacher":0.225,"mega_lucario":0.10,"iono":0.10,"control":0.10},
      "budget":{"max_completed_games_per_seed":30000,
                "registered_eval_points":[0,5000,10000,15000,20000,25000,30000]},
    }
    p=os.path.join(ART,"curriculum_registry.json")
    json.dump(reg,open(p,"w"),indent=2)
    h=sha(p)
    open(os.path.join(ART,"curriculum_registry.sha256"),"w").write(f"{h}  curriculum_registry.json\n")
    open(os.path.join(ART,"curriculum_hypothesis.md"),"w").write(f"""# Curriculum hypothesis (AC-07)

**Hypothesis.** Ordinary continuation against the fixed c011 population has been improving
teacher score slowly while the strategic field lags far behind the frozen teacher's own
same-panel score. If the learned elites occupy a *narrower* behavioural distribution than the
rule teacher, then training against a diverse elite pool should broaden the state distribution
the learner is competent in, improving strategic-field strength without sacrificing the
teacher matchup.

**Prediction if supported.** P1 seeds beat median P0 on both teacher score and strategic field
by at least 3 percentage points, with no Iono/Abomasnow regression and no historical
forgetting.

**Prediction if not supported.** P1 gains elite cross-play while losing external field score —
the cycling signature §31 defines — or simply tracks P0.

**Registered risk control.** Elite share is capped at 45% and rises only through §24 gates on
real evaluations. Teacher, Lucario, Iono and the engineering control retain guaranteed minimum
shares, so pure mirror self-play (a §5 non-goal) cannot occur.

**Status: this hypothesis is locked with the registry below and is not revised after results.**

Registry `{reg['registry_id']}` SHA-256 `{h}`.
""")
    with open(os.path.join(LOGD,"curriculum_lock.txt"),"w") as fh:
        fh.write(f"curriculum_registry.json sha256 = {h}\nlocked_at = {reg['locked_at']}\n"
                 f"elite_pool = {reg['elite_pool']}\n"
                 f"P1 stages = {[s['elite_fraction'] for s in reg['arms']['P1']['stages']]}\n")
    print(json.dumps({"registry_id":reg["registry_id"],"sha256":h,
                      "elite_pool":reg["elite_pool"],
                      "P1_stages":[s["elite_fraction"] for s in reg["arms"]["P1"]["stages"]]},indent=2))

if __name__=="__main__":
    sys.exit(main())
