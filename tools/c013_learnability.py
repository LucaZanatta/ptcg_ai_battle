"""c013 §12-§17 — soup learnability: Q0 direct continuation, Q1 value-head recalibration,
Q2 component continuation. Built on the c011 CUDA PPO backend with c013's repaired state.

The question is why PPO cannot improve the strongest weight soup. Three registered hypotheses:
  Q0  nothing is wrong beyond noise -- direct continuation under repaired infrastructure works;
  Q1  the AVERAGED value head is miscalibrated and poisons the advantage signal, so refitting
      it on ACTUAL terminal outcomes before resuming PPO should unlock learning;
  Q2  averaging destroyed something lineage-specific, so continuing S622/S633 separately and
      recombining afterwards beats optimising the soup directly.

No method "works" from training reward alone (§17): every Q candidate is judged on identity-safe
panels against the frozen Phase 2 start.
"""
import argparse,gzip,json,os,shutil,subprocess,sys,time
from collections import Counter
import numpy as np, torch
_REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,_REPO); sys.path.insert(0,os.path.join(_REPO,"tools"))
from cg import c010_train as ct, c009_eval as ce, c013_eval_core as cc, ppo as legacy_ppo, rl_policy as rlp
import c011_torch_model as tm, c011_torch_ppo as tp
import c013_common as K
C013=os.path.join(_REPO,"contracts","c013_fixed_deck_policy_combination_and_learnability")
ART=os.path.join(C013,"results","artifacts")
TEACHER="dragapult"
EVAL_POINTS=[0,5000,10000,12000]
PANEL={"dragapult":20,"mega_lucario":10,"iono":10,"mega_abomasnow":10}

def gpu():
    try:
        r=subprocess.run(["nvidia-smi","--query-gpu=utilization.gpu,memory.used,temperature.gpu",
            "--format=csv,noheader,nounits"],capture_output=True,text=True,timeout=20)
        u,m,t=[x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
        return {"gpu_util_pct":float(u),"vram_used_mib":float(m),"gpu_temp_c":float(t)}
    except Exception: return {}

def population(rng,lagged):
    """Identical opponent population to c011/c012 (§12)."""
    if lagged:
        d=[(("teacher",TEACHER),0.35),(("teacher","mega_lucario"),0.20),
           (("teacher","iono"),0.20),("__lagged__",0.15),(("control",),0.10)]
    else:
        d=[(("teacher",TEACHER),0.35+0.15*0.35/0.75),(("teacher","mega_lucario"),0.20+0.15*0.20/0.75),
           (("teacher","iono"),0.20+0.15*0.20/0.75),(("control",),0.10)]
    specs=[x[0] for x in d]; p=np.array([x[1] for x in d]); p/=p.sum()
    c=specs[int(rng.choice(len(specs),p=p))]
    if c=="__lagged__":
        ck=lagged[int(rng.integers(0,len(lagged)))]
        return ("lagged",ck,int(rng.integers(0,1<<30))),"lagged"
    return c,("control" if c[0]=="control" else c[1])

def inrun_panel(pool,ckpt,deck,rng,tag):
    """Registered in-run evaluation. Content-addressed path + hard failure on zero scores."""
    ec,sha=K.content_addressed_copy(ckpt,tag)
    cand={"candidate_id":f"INRUN::{sha[:12]}","kind":"rl_ckpt","arm":"INRUN","seed":None,
          "checkpoint_path":os.path.relpath(ec,_REPO),"checkpoint_sha256":sha}
    jobs=[]
    for opp,per in PANEL.items():
        for seat in (0,1):
            for r in range(per):
                jobs.append(ce.make_job(cand,opp,seat,r,"inrun",
                            requested_seed=int(rng.integers(0,1<<30)),deck=deck))
    res=pool.map(cc.run_job,jobs)
    K.require_scored_games(res,f"in-run panel @ {tag}")
    from cg import noninf_stats as ns
    per_opp={}
    for opp in PANEL:
        s={0:[],1:[]}
        for g in res:
            if g["opponent_id"]==opp and g["score"] is not None: s[g["seat"]].append(g["score"])
        if s[0] and s[1]: per_opp[opp]=ns.seat_balanced_point(s[0],s[1])
    fld=[per_opp[o] for o in ("mega_lucario","iono","mega_abomasnow") if o in per_opp]
    return {"per_opponent":per_opp,"teacher":per_opp.get(TEACHER),
            "field":float(np.mean(fld)) if len(fld)==3 else None,
            "n_games":len(res),"scored":sum(1 for g in res if g["score"] is not None),
            "checkpoint_sha256":sha}

def value_refit(model,opt,pool,ckpt,deck,rng,seed,outdir,n_games=1200):
    """§14 — reinitialise the value head on a deterministic seed and fit it to ACTUAL terminal
    outcomes / Monte-Carlo returns, never GAE lambda-returns alone."""
    g=torch.Generator().manual_seed(seed)
    with torch.no_grad():
        for mod in (model.vW1,model.vW2):
            w=torch.empty_like(mod.weight); torch.nn.init.kaiming_uniform_(w,a=5**0.5,generator=g)
            mod.weight.copy_(w); mod.bias.zero_()
    sha=K.sha_file(ckpt)
    jobs=[{"policy_ckpt":ckpt,"policy_version":1,"policy_sha256":sha,"arm":"Q1REFIT","seed":seed,
           "game_index":i,"opponent":population(rng,[])[0],"seat":int(rng.integers(0,2)),
           "rng_seed":int(rng.integers(0,1<<30)),"deck":deck} for i in range(n_games)]
    out=pool.map(ct.play_training_game,jobs)
    games=[r["transitions"] for r in out if r["meta"]["terminal"] and r["transitions"]]
    # Monte-Carlo target = the realised terminal outcome for every state in the game
    X,Y,PH=[],[],[]
    for tr in games:
        outcome=float(tr[-1].get("reward",0.0))
        n=len(tr)
        for i,t in enumerate(tr):
            X.append(t); Y.append(outcome); PH.append(min(int((i+1)/n*5),4))
    if not X: raise K.ZeroScoredGamesError("value refit collected no transitions")
    y=torch.tensor(Y,dtype=torch.float32,device=model.dev)
    vopt=torch.optim.AdamW(list(model.vW1.parameters())+list(model.vW2.parameters()),lr=1e-3)
    idx=np.arange(len(X)); hist=[]
    for ep in range(4):
        rng.shuffle(idx)
        tot=0.0
        for s in range(0,len(idx),256):
            sub=[X[i] for i in idx[s:s+256]]
            b,_=rlp.collate_rl(sub)
            tb=tm.to_torch_batch(b,model.dt,model.dev)
            _,v,_=model(tb)
            loss=torch.mean((v-y[idx[s:s+256]])**2)
            vopt.zero_grad(set_to_none=True); loss.backward(); vopt.step()
            tot+=float(loss)*len(sub)
        hist.append(tot/len(idx))
    # calibration by phase against actual outcomes
    with torch.no_grad():
        preds=[]
        for s in range(0,len(X),512):
            b,_=rlp.collate_rl(X[s:s+512])
            tb=tm.to_torch_batch(b,model.dt,model.dev)
            _,v,_=model(tb); preds.append(v.double().cpu().numpy())
        p=np.concatenate(preds)
    diag=_calibration(p,np.array(Y),np.array(PH))
    diag["mse_by_epoch"]=hist; diag["n_transitions"]=len(X); diag["n_games"]=len(games)
    diag["refit_seed"]=seed
    diag["target"]="actual terminal outcome (Monte-Carlo return to game end), not GAE lambda-return"
    json.dump(diag,open(os.path.join(ART,"value_refit_diagnostics.json"),"w"),indent=2)
    return diag,len([r for r in out if r["meta"]["terminal"]])

def _calibration(pred,y,phase):
    pr=np.clip(0.5*(pred+1),0,1); yy=0.5*(y+1)
    out={"overall":_cal_one(pr,yy),"by_phase":{}}
    for i,name in enumerate(["0-20","20-40","40-60","60-80","80-100"]):
        m=phase==i
        if m.sum()>10: out["by_phase"][name]=_cal_one(pr[m],yy[m])
    return out
def _cal_one(pr,yy):
    brier=float(np.mean((pr-yy)**2)); dec=yy!=0.5; auc=None; acc=None
    if dec.sum()>0:
        yb=(yy[dec]>0.5).astype(float); pb=pr[dec]
        acc=float(np.mean((pb>0.5)==yb))
        if 0<yb.sum()<len(yb):
            o=np.argsort(pb); r=np.empty(len(pb)); r[o]=np.arange(1,len(pb)+1)
            n1=yb.sum(); n0=len(yb)-n1
            auc=float((r[yb==1].sum()-n1*(n1+1)/2)/(n1*n0))
    var=float(np.var(yy))
    return {"brier":brier,"calibration_error":float(np.mean(pr)-np.mean(yy)),
            "outcome_accuracy":acc,"auc":auc,
            "monte_carlo_return_error":float(np.mean(np.abs(pr-yy))),
            "explained_variance_vs_outcome":float(1-np.var(yy-pr)/var) if var>1e-12 else None,
            "n":int(len(pr))}

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--arm",required=True,choices=["Q0","Q1","Q2A","Q2B"])
    p.add_argument("--seed",type=int,required=True)
    p.add_argument("--init",required=True,help="candidate id from the frozen registry")
    p.add_argument("--resume-trainer",default=None,help="c011 trainer state for Q2 (§15)")
    p.add_argument("--max-games",type=int,default=12000)
    p.add_argument("--nproc",type=int,default=16)
    p.add_argument("--device",default="cuda")
    a=p.parse_args(argv)
    torch.set_num_threads(max(1,min(8,(os.cpu_count() or 12)//3)))
    device=a.device if (a.device=="cpu" or torch.cuda.is_available()) else "cpu"
    reg=json.load(open(os.path.join(ART,"candidate_registry.json")))["candidates"]
    comb=json.load(open(os.path.join(ART,"combination_registry.json")))["combinations"]
    meta=reg.get(a.init) or comb.get(a.init)
    assert meta, f"unknown init {a.init}"
    init=os.path.join(_REPO,meta["checkpoint_path"])
    assert K.sha_file(init)==meta["checkpoint_sha256"], "init hash drift"
    outdir=os.path.join(ART,"training",a.arm,f"seed{a.seed}")
    ckdir=os.path.join(outdir,"checkpoints"); os.makedirs(ckdir,exist_ok=True)
    log=open(os.path.join(outdir,"train.log"),"w")
    def emit(m): print(m,flush=True); log.write(m+"\n"); log.flush()

    from cg.teachers import make_fresh
    deck=make_fresh(TEACHER,ce.SOURCES).deck
    legacy=rlp.RLPolicy.load(init)
    model=tm.TorchPolicy(legacy.trunk.cfg,dtype=torch.float32,device=device).load_legacy_state(legacy.state_dict())
    opt=tp.make_optimizer(model,K.PPO_CFG["learning_rate"],K.PPO_CFG["weight_decay"])
    rng=K.TrainerState.new_rng(a.seed)
    st=K.TrainerState(seed=a.seed,entropy_schedule={"start":K.PPO_CFG["entropy_coef_start"],
        "end":K.PPO_CFG["entropy_coef_end"],"kind":"linear_in_completed_games"})
    resume_report=None
    if a.resume_trainer:
        rp=os.path.join(_REPO,a.resume_trainer)
        st,rng,resume_report=K.TrainerState.load(rp,model,opt,device=device)
        st.seed=a.seed
        emit(f"[{a.arm}] resumed {os.path.basename(rp)} -> {resume_report['continuation_kind']} "
             f"(restored {len(resume_report['restored'])} fields, absent {resume_report['absent']})")
    emit(f"[{a.arm} s{a.seed}] init {a.init} ({meta['checkpoint_sha256'][:12]}) on {device}")

    refit=None; refit_games=0
    import multiprocessing as mp
    pool=mp.get_context("spawn").Pool(processes=a.nproc)
    completed=trainable_g=trainable_d=updates=0
    lagged,last_lag=[],0; next_eval=0
    grecs,urecs,evals,ckpts=[],[],[],{}
    cur=os.path.join(outdir,"cur.npz"); stop=None; t0=time.time()
    def export(path):
        sd=model.export_legacy_state()
        m=np.array([legacy.trunk.cfg[k] for k in ("D","Hs","BV","Hh","HV","Hd","DV","GH","CTX","OH","OH2","SH")]+[a.seed],dtype=np.int64)
        np.savez(path,__meta__=m,**sd); return path
    try:
        if a.arm=="Q1":
            export(cur)
            emit(f"[{a.arm}] value-head reinit (seed {a.seed}) + refit on actual outcomes")
            refit,refit_games=value_refit(model,opt,pool,cur,deck,rng,a.seed,outdir)
            ov=refit["overall"]
            emit(f"[{a.arm}] refit: brier={ov['brier']:.4f} auc={ov['auc']:.3f} "
                 f"EVvsOutcome={ov['explained_variance_vs_outcome']:.3f} on {refit['n_transitions']} states")
            opt=tp.make_optimizer(model,K.PPO_CFG["learning_rate"],K.PPO_CFG["weight_decay"])
        while completed<a.max_games and stop is None:
            frac=completed/max(a.max_games,1)
            ent=K.PPO_CFG["entropy_coef_start"]+(K.PPO_CFG["entropy_coef_end"]-K.PPO_CFG["entropy_coef_start"])*frac
            st.entropy_schedule["fraction"]=frac
            export(cur); cur_sha=K.sha_file(cur); ct._SHA.pop(cur,None)
            tsid=f"{a.arm}{a.seed}-u{updates}-{cur_sha[:12]}"
            while next_eval<len(EVAL_POINTS) and completed>=EVAL_POINTS[next_eval]:
                pt=EVAL_POINTS[next_eval]; next_eval+=1
                ev=inrun_panel(pool,cur,deck,rng,f"{a.arm}{a.seed}_g{completed}")
                ev.update({"arm":a.arm,"seed":a.seed,"registered_point":pt,
                           "completed_games":completed,"updates":updates,"trainer_state_id":tsid})
                evals.append(ev)
                emit(f"  [eval @ {completed} pt={pt}] teacher={ev['teacher']} field={ev['field']} "
                     f"scored={ev['scored']}/{ev['n_games']}")
                if pt>0:
                    cp=os.path.join(ckdir,f"ckpt_g{completed}.npz"); export(cp)
                    tsp=os.path.join(ckdir,f"trainer_g{completed}.pt")
                    st.completed_games=completed; st.games_with_trainable_decisions=trainable_g
                    st.trainable_decisions=trainable_d; st.updates=updates; st.trainer_state_id=tsid
                    st.lagged=[{"path":os.path.relpath(x,_REPO),"sha256":K.sha_file(x)} for x in lagged]
                    st.save(tsp,model,opt,rng,K.PPO_CFG["learning_rate"],ent)
                    ckpts[str(completed)]={"checkpoint_path":os.path.relpath(cp,_REPO),
                        "sha256":K.sha_file(cp),"trainer_state_path":os.path.relpath(tsp,_REPO),
                        "trainer_state_sha256":K.sha_file(tsp),"trainer_state_id":tsid,
                        "training_games":completed,"registered_eval_point":pt,"arm":a.arm,
                        "seed":a.seed,"updates":updates,
                        "inrun_eval":{"teacher":ev["teacher"],"field":ev["field"]}}
            if stop: break
            games,ndec,ntr,ncomp=[],0,0,0
            troll=time.time(); oc=Counter()
            while ncomp<K.PPO_CFG["rollout_game_target"] or ndec<K.PPO_CFG["min_trainable_decisions"]:
                batch=[]
                for _ in range(a.nproc):
                    spec,oid=population(rng,lagged)
                    batch.append({"policy_ckpt":cur,"policy_version":updates+1,"policy_sha256":cur_sha,
                        "arm":a.arm,"seed":a.seed,"game_index":completed+ncomp+len(batch),
                        "opponent":spec,"seat":int(rng.integers(0,2)),
                        "rng_seed":int(rng.integers(0,1<<30)),"deck":deck})
                for r in pool.map(ct.play_training_game,batch):
                    m=dict(r["meta"]); m["trainer_state_id"]=tsid
                    m["completed_game"]=bool(m["terminal"]); grecs.append(m)
                    oc[m["opponent_id"]]+=1
                    if m["terminal"]:
                        ncomp+=1
                        if r["transitions"]:
                            games.append(r["transitions"]); ndec+=len(r["transitions"]); ntr+=1
                if ncomp>3*K.PPO_CFG["rollout_game_target"]: break
            roll=time.time()-troll
            completed+=ncomp; trainable_g+=ntr; trainable_d+=ndec
            tup=time.time()
            if device.startswith("cuda"): torch.cuda.synchronize()
            flat=legacy_ppo.compute_gae(games,K.PPO_CFG["gamma"],K.PPO_CFG["lam"])
            orders=[]; order=np.arange(len(flat))
            for _ in range(K.PPO_CFG["epochs"]):
                rng.shuffle(order); orders.append(order.copy())
            diag=tp.ppo_update_torch(model,games,K.PPO_CFG,opt,ent,orders=orders,device=device,flat=flat)
            if device.startswith("cuda"): torch.cuda.synchronize()
            up=time.time()-tup; updates+=1
            g=gpu()
            rec={"arm":a.arm,"seed":a.seed,"update":updates,"completed_games":completed,
                 "games_with_trainable_decisions":trainable_g,"trainable_decisions":trainable_d,
                 "decisions":diag["n_decisions"],"policy_loss":diag["policy_loss"],
                 "value_loss":diag["value_loss"],"entropy":diag["entropy"],
                 "approx_kl":diag["approx_kl"],"clip_fraction":diag["clip_frac"],
                 "explained_variance":diag["explained_variance"],"grad_norm":diag["grad_norm"],
                 "learning_rate":K.PPO_CFG["learning_rate"],"entropy_coef":ent,
                 "return_mean":diag["return_mean"],"realized_opponent_counts":dict(oc),
                 "rollout_seconds":round(roll,1),"update_seconds":round(up,1),
                 "trainer_state_id":tsid,"device":device,**g,
                 "elapsed_seconds":round(time.time()-t0,1)}
            urecs.append(rec)
            open(os.path.join(outdir,"updates.partial.jsonl"),"a").write(json.dumps(rec)+"\n")
            emit(f"[{a.arm} s{a.seed}] c={completed} upd={updates} ret={diag['return_mean']:+.3f} "
                 f"ev={diag['explained_variance']:.2f} ent={diag['entropy']:.3f} "
                 f"kl={diag['approx_kl']:.4f} roll={roll:.0f}s up={up:.1f}s")
            if not np.isfinite(diag["policy_loss"]): stop="nonfinite_loss"
            if sum(x["invalid_actions"] for x in grecs[-(ncomp+a.nproc*4):])>0:
                stop=stop or "reliability_failure"
            if completed>=5000 and completed-last_lag>=5000:
                lp=os.path.join(ckdir,f"lagged_g{completed}.npz"); export(lp)
                lagged.append(lp); lagged=lagged[-3:]; last_lag=completed
    finally:
        pool.close(); pool.join()
    stop=stop or "budget_reached"
    with gzip.open(os.path.join(outdir,"training_games.jsonl.gz"),"wt") as fh:
        for m in grecs: fh.write(json.dumps(m)+"\n")
    with gzip.open(os.path.join(outdir,"updates.jsonl.gz"),"wt") as fh:
        for r in urecs: fh.write(json.dumps(r)+"\n")
    json.dump(ckpts,open(os.path.join(outdir,"checkpoint_registry.json"),"w"),indent=2)
    open(os.path.join(outdir,"inrun_evaluations.jsonl"),"w").writelines(
        json.dumps(e)+"\n" for e in evals)
    el=time.time()-t0
    summ={"arm":a.arm,"seed":a.seed,"initialization":a.init,
          "initialization_sha256":meta["checkpoint_sha256"],
          "resume_report":resume_report,
          "continuation_kind":(resume_report or {}).get("continuation_kind","fresh_optimizer"),
          "completed_games":completed,"games_with_trainable_decisions":trainable_g,
          "trainable_decisions":trainable_d,"updates":updates,"stop_reason":stop,
          "value_refit":refit,"value_refit_games":refit_games,
          "elapsed_seconds":round(el,1),
          "completed_games_per_hour":round(3600*completed/el,1) if el>0 else None,
          "checkpoints":ckpts,"n_inrun_evaluations":len(evals),
          "inrun_evaluations":evals,
          "opponent_distribution":dict(Counter(m["opponent_id"] for m in grecs)),
          "seat_distribution":dict(Counter(m["seat"] for m in grecs)),
          "reliability":{k:sum(m[k] for m in grecs) for k in
                         ("invalid_actions","exceptions","timeouts","fallbacks")}}
    json.dump(summ,open(os.path.join(outdir,"summary.json"),"w"),indent=2)
    emit(f"[{a.arm} s{a.seed}] DONE completed={completed} upd={updates} stop={stop} "
         f"{summ['completed_games_per_hour']} g/h")
    log.close(); return 0
if __name__=="__main__": sys.exit(main())
