"""c011 AC-08/09/10 — consolidate per-seed training output into the required artifact names.

Each seed trains in its own process, so output lands under training/seedNNN/. This copies it
to the contract's required names, re-counting rows from the consolidated file rather than
trusting the per-seed summary.
"""
import gzip, hashlib, json, os, shutil, sys
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C011 = os.path.join(_REPO, "contracts", "c011_fixed_deck_cuda_ppo_scale")
ART = os.path.join(C011, "results", "artifacts"); LOGD = os.path.join(C011, "results", "test_logs")

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""): h.update(c)
    return h.hexdigest()

def main():
    out = {}
    for sd in sorted(os.listdir(os.path.join(ART, "training"))):
        d = os.path.join(ART, "training", sd)
        s = json.load(open(os.path.join(d, "summary.json")))
        seed = s["seed"]
        gp = os.path.join(d, "training_games.jsonl.gz")
        up = os.path.join(d, "updates.jsonl.gz")
        cr = os.path.join(d, "checkpoint_registry.json")
        rows = sum(1 for _ in gzip.open(gp, "rt"))
        terminal = sum(1 for l in gzip.open(gp, "rt") if json.loads(l)["terminal"])
        trainable = sum(1 for l in gzip.open(gp, "rt")
                        if json.loads(l)["terminal"] and json.loads(l).get("trainable_decisions", 0) > 0)
        n_up = sum(1 for _ in gzip.open(up, "rt"))
        shutil.copyfile(gp, os.path.join(ART, f"seed_{seed}_training_games.jsonl.gz"))
        shutil.copyfile(up, os.path.join(ART, f"seed_{seed}_updates.jsonl.gz"))
        shutil.copyfile(cr, os.path.join(ART, f"seed_{seed}_checkpoint_registry.json"))
        summ = dict(s)
        summ.update({"raw_game_rows": rows, "terminal_games": terminal,
                     "terminal_with_transitions": trainable, "update_rows": n_up,
                     "consistency": {
                         "games_done_equals_trainable_games": s["games_done"] == trainable,
                         "update_rows_match_summary": n_up == s["updates"],
                         "zero_invalid_actions": s["reliability"]["invalid_actions"] == 0,
                         "every_checkpoint_has_trainer_state": all(
                             v.get("trainer_state_path") for v in s["checkpoints"].values()),
                         "note": "games_done counts TRAINABLE games; a terminal game with only "
                                 "forced decisions yields no transitions and is excluded."},
                     "files": {
                         "training_games_sha256": sha(gp), "updates_sha256": sha(up)}})
        json.dump(summ, open(os.path.join(ART, f"seed_{seed}_summary.json"), "w"), indent=2)
        shutil.copyfile(os.path.join(d, "train.log"),
                        os.path.join(LOGD, f"seed_{seed}_training.txt"))
        out[seed] = {"games": s["games_done"], "updates": s["updates"],
                     "consistency": summ["consistency"]}
    smk = os.path.join(ART, "smoke", "seed999")
    if os.path.exists(os.path.join(smk, "train.log")):
        shutil.copyfile(os.path.join(smk, "train.log"), os.path.join(LOGD, "cuda_smoke.txt"))
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    sys.exit(main() or 0)
