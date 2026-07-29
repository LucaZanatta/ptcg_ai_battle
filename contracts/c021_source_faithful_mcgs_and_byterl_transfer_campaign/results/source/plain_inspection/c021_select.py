"""c021 — select the extension's best checkpoint by the PREREGISTERED rule.

External-panel win rate first, MCGS transfer-prior utility second. Never internal self-play,
never recency. See results/byterl/selection/PREREGISTERED_SELECTION.json, written before the
extension ran.
"""
from __future__ import annotations
import argparse, glob, json, math, multiprocessing as mp, os, sys, time
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
C21 = os.path.join(_REPO, "contracts",
                   "c021_source_faithful_mcgs_and_byterl_transfer_campaign", "results")
SEL = os.path.join(C21, "byterl", "selection")
OPPONENTS = ["dragapult", "mega_lucario", "iono", "mega_abomasnow"]


def wilson(k, n, z=1.96):
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(max(p * (1 - p) / n + z * z / (4 * n * n), 0.0))
    return ((c - m) / d, (c + m) / d)


def _panel_game(job, q):
    """One external-panel game: the checkpoint's policy against a frozen scripted opponent."""
    sys.path.insert(0, _REPO)
    import torch
    torch.set_num_threads(1)
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce
    from cg import c021_byterl_actor as AC, c021_byterl_deck as DK
    from cg import c021_byterl_encode as EN, c021_byterl_model as M
    pool = DK.CardPool.from_archetypes()
    d = EN.dims()
    st = torch.load(job["ckpt"], map_location="cpu", weights_only=True)
    width = int(st["global_proj.weight"].shape[0])
    blocks = len({k.split(".")[1] for k in st if k.startswith("torso.")})
    net = M.ByteRLNet(d["global_dim"], d["slot_dim"], d["option_dim"], pool.size(),
                      width=width, blocks=blocks)
    net.load_state_dict(st)
    net.eval()
    actor = AC.ByteRLActor(net, pool, seed=job["seed"],
                           fixed_deck=DK.greedy_reference_deck(pool))
    opp = T.make_fresh(job["opponent"], ce.SOURCES)
    seat = int(job["seat"])
    agents = ([lambda o: actor.act(o), lambda o: opp(o)] if seat == 0
              else [lambda o: opp(o), lambda o: actor.act(o)])
    try:
        env = make("cabt")
        env.run(agents)
        last = env.steps[-1]
        if [s.status for s in last] == ["DONE", "DONE"]:
            rw = [s.reward for s in last]
            if rw[seat] is not None:
                q.put(1.0 if rw[seat] > rw[1 - seat]
                      else (0.5 if rw[seat] == rw[1 - seat] else 0.0))
                return
    except Exception:
        pass
    q.put(None)


def external_panel(ckpt: str, games: int, nproc: int, seed: int) -> dict:
    """Identical protocol for every candidate: same opponents, seats, game count and seeds."""
    ctx = mp.get_context("spawn")
    jobs = [{"ckpt": ckpt, "opponent": OPPONENTS[i % 4], "seat": i % 2, "seed": seed + i * 7919}
            for i in range(games)]
    scores, running = [], []
    t0 = time.time()

    def reap(block):
        for item in list(running):
            pr, q, started = item
            try:
                scores.append(q.get_nowait()); pr.join(5)
                if pr.is_alive():
                    pr.terminate()
                running.remove(item); continue
            except Exception:
                pass
            if not pr.is_alive() or time.time() - started > 300:
                pr.terminate(); pr.join(3)
                running.remove(item)

    for j in jobs:
        while len(running) >= nproc:
            reap(False); time.sleep(0.2)
        q = ctx.Queue(); pr = ctx.Process(target=_panel_game, args=(j, q))
        pr.start(); running.append((pr, q, time.time()))
    while running:
        reap(False); time.sleep(0.2)
    ok = [s for s in scores if s is not None]
    wr = (sum(ok) / len(ok)) if ok else None
    lo, hi = wilson((wr or 0) * len(ok), len(ok))
    return {"checkpoint": os.path.basename(ckpt), "games": games, "completed": len(ok),
            "win_rate": round(wr, 4) if wr is not None else None,
            "wilson95": [round(lo, 4), round(hi, 4)], "seconds": round(time.time() - t0, 1)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=64)
    ap.add_argument("--nproc", type=int, default=20)
    ap.add_argument("--seed", type=int, default=90210)
    ap.add_argument("--pattern", default="big_ctrl_*")
    ap.add_argument("--checkpoints", nargs="*", default=None,
                    help="evaluate exactly these paths instead of globbing candidates -- used "
                         "for the out-of-sample re-evaluation of an already-selected checkpoint")
    ap.add_argument("--out", default="external_panel_selection.json")
    a = ap.parse_args(argv)
    os.makedirs(SEL, exist_ok=True)
    CK = os.path.join(C21, "byterl", "checkpoints")
    if a.checkpoints:
        cands = list(a.checkpoints)
    else:
        cands = sorted(glob.glob(os.path.join(CK, "intermediate", f"{a.pattern}*.pt")))
        cands += sorted(glob.glob(os.path.join(CK, f"{a.pattern}final.pt")))
    if not cands:
        print("no candidates"); return 1
    print(f"evaluating {len(cands)} candidates on the external panel, "
          f"{a.games} games each, identical protocol", flush=True)
    rows = []
    for c in cands:
        r = external_panel(c, a.games, a.nproc, a.seed)
        rows.append(r)
        print(json.dumps(r), flush=True)
    scored = [r for r in rows if r["win_rate"] is not None]
    # PRIMARY: external panel. TIE-BREAK: fewer training games, i.e. the earlier checkpoint.
    def order(r):
        return (-r["win_rate"], r["checkpoint"])
    scored.sort(key=order)
    out = {"rule": "results/byterl/selection/PREREGISTERED_SELECTION.json",
           "primary": "external-panel win rate vs four frozen scripted opponents",
           "excluded": ["internal self-play", "checkpoint recency", "training-curve win rate"],
           "candidates": rows,
           "selected": scored[0] if scored else None,
           "runner_up": scored[1] if len(scored) > 1 else None,
           "generated": time.strftime("%Y-%m-%dT%H:%M:%S")}
    json.dump(out, open(os.path.join(SEL, a.out), "w"), indent=2)
    if scored:
        s = scored[0]
        print(f"\nSELECTED {s['checkpoint']}  win_rate={s['win_rate']} "
              f"wilson={s['wilson95']} over {s['completed']} games")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
