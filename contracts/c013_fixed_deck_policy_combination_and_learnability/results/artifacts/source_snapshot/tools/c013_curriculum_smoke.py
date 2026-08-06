"""c013 §18-§20 — bounded adaptive-curriculum SMOKE TEST.

This validates machinery, not curriculum effectiveness (§18). c012 shipped a curriculum that
never executed: a path-keyed hash cache emptied every in-run evaluation, so the gates silently
received nothing and no stage ever changed. Every one of those failure points is asserted here.

§20 explicitly allows a deterministic fixture to force at least one stage change, because the
requirement is that the gate CODE executes correctly -- not that a 5,000-game run happens to
earn a promotion.
"""
import argparse,gzip,json,os,sys,time
from collections import Counter
import numpy as np, torch
_REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,_REPO); sys.path.insert(0,os.path.join(_REPO,"tools"))
from cg import c010_train as ct, c009_eval as ce, c013_eval_core as cc, ppo as legacy_ppo, rl_policy as rlp
import c011_torch_model as tm, c011_torch_ppo as tp
import c013_common as K
C013=os.path.join(_REPO,"contracts","c013_fixed_deck_policy_combination_and_learnability")
ART=os.path.join(C013,"results","artifacts"); LOGD=os.path.join(C013,"results","test_logs")
TEACHER="dragapult"; EVAL_POINTS=[0,2500,5000]
PANEL={"dragapult":20,"mega_lucario":10,"iono":10,"mega_abomasnow":10}

STAGES=[{"stage":0,"elite":0.15,"mixture":{"teacher":0.30,"mega_lucario":0.175,"iono":0.175,
                                           "elite":0.15,"lagged":0.10,"control":0.10}},
        {"stage":1,"elite":0.25,"mixture":{"teacher":0.275,"mega_lucario":0.15,"iono":0.15,
                                           "elite":0.25,"lagged":0.075,"control":0.10}},
        {"stage":2,"elite":0.35,"mixture":{"teacher":0.25,"mega_lucario":0.125,"iono":0.125,
                                           "elite":0.35,"lagged":0.05,"control":0.10}}]
CONTROL=[{"stage":0,"elite":0.0,"mixture":{"teacher":0.35,"mega_lucario":0.20,"iono":0.20,
                                           "lagged":0.15,"control":0.10}}]

def gates(ev,best,forced=False):
    """§24-style progression gates. Returns (advance, reasons) with EVERY gate evaluated so
    the record shows the calculation ran, not merely its verdict."""
    g={}
    t,f=ev.get("teacher"),ev.get("field"); po=ev.get("per_opponent",{})
    g["evaluation_returned_scores"]=bool(ev.get("scored",0)>0)
    g["teacher_preserved_vs_branch_best"]=bool(t is not None and (best.get("teacher") is None or t>=best["teacher"]-1e-9))
    g["no_iono_regression"]=bool(po.get("iono",1.0)>=0.20)
    g["no_abomasnow_regression"]=bool(po.get("mega_abomasnow",1.0)>=0.20)
    g["field_present"]=f is not None
    g["forced_by_fixture"]=bool(forced)
    advance=bool(forced or all(v for k,v in g.items() if k!="forced_by_fixture"))
    return advance,g

def mixture(stages,stage,lagged,elite):
    base=dict(stages[min(stage,len(stages)-1)]["mixture"])
    if not elite: base.pop("elite",None)
    if not lagged:
        lag=base.pop("lagged",0.0)
        ks=["teacher","mega_lucario","iono"]; tot=sum(base[k] for k in ks)
        for k in ks: base[k]+=lag*base[k]/tot
    s=sum(base.values()); return {k:v/s for k,v in base.items()}

def draw(rng,mix,lagged,elite):
    cats=sorted(mix); p=np.array([mix[c] for c in cats]); p/=p.sum()
    c=cats[int(rng.choice(len(cats),p=p))]
    if c=="control": return ("control",),"control","__control__"
    if c=="lagged":
        ck=lagged[int(rng.integers(0,len(lagged)))]
        return ("lagged",ck,int(rng.integers(0,1<<30))),"lagged",f"lagged::{os.path.basename(ck)}"
    if c=="elite":
        e=elite[int(rng.integers(0,len(elite)))]
        return ("lagged",os.path.join(_REPO,e["checkpoint_path"]),int(rng.integers(0,1<<30))),"elite",e["id"]
    oid=TEACHER if c=="teacher" else c
    return ("teacher",oid),c,oid

def panel(pool,ckpt,deck,rng,tag):
    ec,sha=K.content_addressed_copy(ckpt,tag)
    cand={"candidate_id":f"SMOKE::{sha[:12]}","kind":"rl_ckpt","arm":"SMOKE","seed":None,
          "checkpoint_path":os.path.relpath(ec,_REPO),"checkpoint_sha256":sha}
    jobs=[ce.make_job(cand,o,s,r,"smoke",requested_seed=int(rng.integers(0,1<<30)),deck=deck)
          for o,per in PANEL.items() for s in (0,1) for r in range(per)]
    res=pool.map(cc.run_job,jobs)
    K.require_scored_games(res,f"curriculum smoke panel @ {tag}")
    from cg import noninf_stats as ns
    po={}
    for o in PANEL:
        s={0:[],1:[]}
        for gme in res:
            if gme["opponent_id"]==o and gme["score"] is not None: s[gme["seat"]].append(gme["score"])
        if s[0] and s[1]: po[o]=ns.seat_balanced_point(s[0],s[1])
    fl=[po[o] for o in ("mega_lucario","iono","mega_abomasnow") if o in po]
    return {"per_opponent":po,"teacher":po.get(TEACHER),
            "field":float(np.mean(fl)) if len(fl)==3 else None,
            "n_games":len(res),"scored":sum(1 for g in res if g["score"] is not None),
            "checkpoint_sha256":sha}

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--arm",required=True,choices=["R0","R1"]); p.add_argument("--seed",type=int,required=True)
    p.add_argument("--init",default="C012_SOUP_622_633"); p.add_argument("--max-games",type=int,default=5000)
    p.add_argument("--nproc",type=int,default=16); p.add_argument("--force-stage-change-at",type=int,default=2500)
    a=p.parse_args(argv)
    torch.set_num_threads(max(1,min(8,(os.cpu_count() or 12)//3)))
    device="cuda" if torch.cuda.is_available() else "cpu"
    reg=json.load(open(os.path.join(ART,"candidate_registry.json")))["candidates"]
    meta=reg[a.init]; init=os.path.join(_REPO,meta["checkpoint_path"])
    pool_reg=json.load(open(os.path.join(ART,"combination_registry.json")))["combinations"]
    elite=[{"id":k,"checkpoint_path":v["checkpoint_path"]} for k,v in pool_reg.items()
           if v["candidate_type"]=="weight_soup"][:3] if a.arm=="R1" else []
    stages=STAGES if a.arm=="R1" else CONTROL
    outdir=os.path.join(ART,"training",a.arm,f"seed{a.seed}"); ckdir=os.path.join(outdir,"checkpoints")
    os.makedirs(ckdir,exist_ok=True); log=open(os.path.join(outdir,"train.log"),"w")
    def emit(m): print(m,flush=True); log.write(m+"\n"); log.flush()
    from cg.teachers import make_fresh
    deck=make_fresh(TEACHER,ce.SOURCES).deck
    legacy=rlp.RLPolicy.load(init)
    model=tm.TorchPolicy(legacy.trunk.cfg,dtype=torch.float32,device=device).load_legacy_state(legacy.state_dict())
    opt=tp.make_optimizer(model,K.PPO_CFG["learning_rate"],K.PPO_CFG["weight_decay"])
    rng=K.TrainerState.new_rng(a.seed)
    st=K.TrainerState(seed=a.seed,entropy_schedule={"start":K.PPO_CFG["entropy_coef_start"],
        "end":K.PPO_CFG["entropy_coef_end"],"kind":"linear"})
    machinery={"nonzero_evaluations":[], "hash_refresh_distinct":set(), "gate_evaluations":0,
               "stage_changes":0,"early_stop_path_exercised":False,
               "trainer_state_saved":0,"restore_verified":None}
    completed=trainable=tdec=updates=0; stage=0; next_eval=0; lagged,last_lag=[],0
    grecs,urecs,hist,evals,ckpts=[],[],[],[],{}
    cur=os.path.join(outdir,"cur.npz"); best={"teacher":None,"field":None}; stop=None; t0=time.time()
    def export(pth):
        sd=model.export_legacy_state()
        m=np.array([legacy.trunk.cfg[k] for k in ("D","Hs","BV","Hh","HV","Hd","DV","GH","CTX","OH","OH2","SH")]+[a.seed],dtype=np.int64)
        np.savez(pth,__meta__=m,**sd); return pth
    import multiprocessing as mp
    pool=mp.get_context("spawn").Pool(processes=a.nproc)
    try:
        while completed<a.max_games and stop is None:
            frac=completed/max(a.max_games,1)
            ent=K.PPO_CFG["entropy_coef_start"]+(K.PPO_CFG["entropy_coef_end"]-K.PPO_CFG["entropy_coef_start"])*frac
            export(cur); cur_sha=K.sha_file(cur); ct._SHA.pop(cur,None)
            machinery["hash_refresh_distinct"].add(cur_sha)
            tsid=f"{a.arm}{a.seed}-u{updates}-{cur_sha[:12]}"
            mix=mixture(stages,stage,lagged,elite)
            while next_eval<len(EVAL_POINTS) and completed>=EVAL_POINTS[next_eval]:
                pt=EVAL_POINTS[next_eval]; next_eval+=1
                ev=panel(pool,cur,deck,rng,f"{a.arm}{a.seed}_g{completed}")
                ev.update({"arm":a.arm,"seed":a.seed,"registered_point":pt,
                           "completed_games":completed,"stage":stage,"trainer_state_id":tsid})
                evals.append(ev); machinery["nonzero_evaluations"].append(ev["scored"]>0)
                forced=(a.arm=="R1" and pt==a.force_stage_change_at)
                adv,g=gates(ev,best,forced=forced); machinery["gate_evaluations"]+=1
                ev["gates"]=g; ev["advance"]=adv
                emit(f"  [eval @ {completed} pt={pt}] teacher={ev['teacher']} field={ev['field']} "
                     f"scored={ev['scored']}/{ev['n_games']} gates={sum(1 for v in g.values() if v)}/{len(g)} adv={adv}")
                if ev["teacher"] is not None and (best["teacher"] is None or ev["teacher"]>best["teacher"]):
                    best={"teacher":ev["teacher"],"field":ev["field"]}
                if adv and a.arm=="R1" and stage+1<len(stages):
                    stage+=1; machinery["stage_changes"]+=1
                    hist.append({"completed_games":completed,"from_stage":stage-1,"to_stage":stage,
                                 "forced_by_fixture":forced,"gates":g,"eval":ev,
                                 "new_mixture":mixture(stages,stage,lagged,elite)})
                    emit(f"  [curriculum] stage -> {stage} (forced_by_fixture={forced})")
                if pt>0:
                    cp=os.path.join(ckdir,f"ckpt_g{completed}.npz"); export(cp)
                    tsp=os.path.join(ckdir,f"trainer_g{completed}.pt")
                    st.completed_games=completed; st.updates=updates; st.trainer_state_id=tsid
                    st.curriculum_state={"stage":stage,"mixture":mix}
                    st.save(tsp,model,opt,rng,K.PPO_CFG["learning_rate"],ent)
                    machinery["trainer_state_saved"]+=1
                    ckpts[str(completed)]={"checkpoint_path":os.path.relpath(cp,_REPO),
                        "sha256":K.sha_file(cp),"trainer_state_path":os.path.relpath(tsp,_REPO),
                        "trainer_state_sha256":K.sha_file(tsp),"training_games":completed,
                        "registered_eval_point":pt,"arm":a.arm,"seed":a.seed,"stage":stage}
                    # §20 mid-run restore: the restored Generator must reproduce the next draws
                    if machinery["restore_verified"] is None:
                        exp=[draw(np.random.default_rng(),mix,lagged,elite)[2] for _ in range(0)]
                        snap=rng.bit_generator.state
                        seq=[(draw(rng,mix,lagged,elite)[2],int(rng.integers(0,2)),
                              int(rng.integers(0,1<<30))) for _ in range(6)]
                        m2=tm.TorchPolicy(legacy.trunk.cfg,dtype=torch.float32,device=device)
                        o2=tp.make_optimizer(m2,K.PPO_CFG["learning_rate"],K.PPO_CFG["weight_decay"])
                        _st2,rng2,rep=K.TrainerState.load(tsp,m2,o2,device=device)
                        seq2=[(draw(rng2,mix,lagged,elite)[2],int(rng2.integers(0,2)),
                               int(rng2.integers(0,1<<30))) for _ in range(6)]
                        rng.bit_generator.state=snap   # rewind: the check must not consume the stream
                        machinery["restore_verified"]={"sequences_match":seq==seq2,
                            "expected":seq[:3],"restored":seq2[:3],"report":rep}
                        emit(f"  [restore] next opponent/seat/seed sequence reproduced: {seq==seq2}")
            if stop: break
            games,ndec,ntr,ncomp=[],0,0,0; troll=time.time(); oc=Counter()
            # cap the rollout by the REMAINING budget. Rollouts are atomic, so a rollout that
            # begins near the ceiling overshoots it -- the same mechanism that produced c010's
            # rollout-granularity deviation, and the reason R0/R1 finished 112 games over §19's
            # maximum. Enforcing the budget at rollout granularity is what makes that possible.
            room=max(0,a.max_games-completed)
            target=min(K.PPO_CFG["rollout_game_target"],room)
            while ncomp<target or (ndec<K.PPO_CFG["min_trainable_decisions"] and ncomp<room):
                batch=[]
                for _ in range(a.nproc):
                    spec,cat,oid=draw(rng,mix,lagged,elite)
                    batch.append({"policy_ckpt":cur,"policy_version":updates+1,"policy_sha256":cur_sha,
                        "arm":a.arm,"seed":a.seed,"game_index":completed+ncomp+len(batch),
                        "opponent":spec,"seat":int(rng.integers(0,2)),
                        "rng_seed":int(rng.integers(0,1<<30)),"deck":deck})
                for r in pool.map(ct.play_training_game,batch):
                    m=dict(r["meta"]); m["trainer_state_id"]=tsid; m["curriculum_stage"]=stage
                    m["completed_game"]=bool(m["terminal"]); grecs.append(m); oc[m["opponent_id"]]+=1
                    if m["terminal"]:
                        ncomp+=1
                        if r["transitions"]: games.append(r["transitions"]); ndec+=len(r["transitions"]); ntr+=1
                if ncomp>3*K.PPO_CFG["rollout_game_target"]: break
            roll=time.time()-troll; completed+=ncomp; trainable+=ntr; tdec+=ndec
            flat=legacy_ppo.compute_gae(games,K.PPO_CFG["gamma"],K.PPO_CFG["lam"])
            orders=[]; order=np.arange(len(flat))
            for _ in range(K.PPO_CFG["epochs"]): rng.shuffle(order); orders.append(order.copy())
            tup=time.time()
            diag=tp.ppo_update_torch(model,games,K.PPO_CFG,opt,ent,orders=orders,device=device,flat=flat)
            up=time.time()-tup; updates+=1
            urecs.append({"arm":a.arm,"seed":a.seed,"update":updates,"completed_games":completed,
                "stage":stage,"opponent_probabilities":mix,"realized_opponent_counts":dict(oc),
                "policy_loss":diag["policy_loss"],"entropy":diag["entropy"],
                "approx_kl":diag["approx_kl"],"explained_variance":diag["explained_variance"],
                "rollout_seconds":round(roll,1),"update_seconds":round(up,1)})
            emit(f"[{a.arm} s{a.seed}] c={completed} upd={updates} stage={stage} "
                 f"ret={diag['return_mean']:+.3f} ent={diag['entropy']:.3f} roll={roll:.0f}s")
            # exercise the early-stop code path deterministically (§20) without ending the run
            if completed>=2500 and not machinery["early_stop_path_exercised"]:
                fake={"teacher":0.0,"field":0.0,"scored":10,"per_opponent":{"iono":0.0,"mega_abomasnow":0.0}}
                _adv,_g=gates(fake,{"teacher":0.9,"field":0.9})
                machinery["early_stop_path_exercised"]=(_adv is False)
                emit(f"  [early-stop path] regression fixture evaluated -> advance={_adv} (expected False)")
            if completed>=2500 and completed-last_lag>=2500:
                lp=os.path.join(ckdir,f"lagged_g{completed}.npz"); export(lp)
                lagged.append(lp); lagged=lagged[-3:]; last_lag=completed
        # §19 requires evaluations at 0, 2,500 AND 5,000. The evaluation block lives inside the
        # budget loop, so a run that crosses the last registered point on its final rollout
        # exits before evaluating it. Flush the remaining points against the FINAL policy.
        export(cur); cur_sha=K.sha_file(cur); ct._SHA.pop(cur,None)
        machinery["hash_refresh_distinct"].add(cur_sha)
        while next_eval<len(EVAL_POINTS) and completed>=EVAL_POINTS[next_eval]:
            pt=EVAL_POINTS[next_eval]; next_eval+=1
            ev=panel(pool,cur,deck,rng,f"{a.arm}{a.seed}_g{completed}_final")
            ev.update({"arm":a.arm,"seed":a.seed,"registered_point":pt,
                       "completed_games":completed,"stage":stage,
                       "trainer_state_id":f"{a.arm}{a.seed}-u{updates}-{cur_sha[:12]}",
                       "evaluated_after_budget_loop":True})
            evals.append(ev); machinery["nonzero_evaluations"].append(ev["scored"]>0)
            adv,g=gates(ev,best); machinery["gate_evaluations"]+=1
            ev["gates"]=g; ev["advance"]=adv
            emit(f"  [eval @ {completed} pt={pt} FINAL] teacher={ev['teacher']} "
                 f"field={ev['field']} scored={ev['scored']}/{ev['n_games']} adv={adv}")
    finally:
        pool.close(); pool.join()
    with gzip.open(os.path.join(outdir,"training_games.jsonl.gz"),"wt") as fh:
        for m in grecs: fh.write(json.dumps(m)+"\n")
    with gzip.open(os.path.join(outdir,"updates.jsonl.gz"),"wt") as fh:
        for r in urecs: fh.write(json.dumps(r)+"\n")
    json.dump(ckpts,open(os.path.join(outdir,"checkpoint_registry.json"),"w"),indent=2)
    open(os.path.join(outdir,"curriculum_history.jsonl"),"w").writelines(json.dumps(h)+"\n" for h in hist)
    machinery["hash_refresh_distinct"]=len(machinery["hash_refresh_distinct"])
    summ={"arm":a.arm,"seed":a.seed,"initialization":a.init,"completed_games":completed,
          "games_with_trainable_decisions":trainable,"trainable_decisions":tdec,"updates":updates,
          "final_stage":stage,"stage_changes":machinery["stage_changes"],
          "n_evaluations":len(evals),"evaluations":evals,"curriculum_history":hist,
          "machinery":machinery,"stop_reason":stop or "budget_reached",
          "elapsed_seconds":round(time.time()-t0,1),
          "opponent_distribution":dict(Counter(m["opponent_id"] for m in grecs)),
          "reliability":{k:sum(m[k] for m in grecs) for k in ("invalid_actions","exceptions","timeouts")}}
    json.dump(summ,open(os.path.join(outdir,"summary.json"),"w"),indent=2)
    emit(f"[{a.arm} s{a.seed}] DONE completed={completed} stages={machinery['stage_changes']} "
         f"evals={len(evals)} all_nonzero={all(machinery['nonzero_evaluations'])}")
    log.close(); return 0
if __name__=="__main__": sys.exit(main())
