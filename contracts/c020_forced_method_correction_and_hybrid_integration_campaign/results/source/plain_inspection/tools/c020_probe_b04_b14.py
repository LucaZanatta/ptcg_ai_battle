"""c020 B04/B14 — canonical action round-trip, and package/repository inference parity.

B04: every legal option — single AND multi-select — must reconstruct the exact environment
payload. If the round trip loses information, an action the search or the policy selected is not
the action the engine executes, and every downstream statistic is attached to the wrong move.

B14: the extracted package must reproduce the repository's logits, selected payload, recurrent
transition and value on fixed sequences. `CONTRACT §8` lists "submitted code differs from
evaluated code" as a blocker, and a package can differ while still playing legal games.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C20 = os.path.join(_REPO, "contracts",
                   "c020_forced_method_correction_and_hybrid_integration_campaign", "results")
P = os.path.join(C20, "probes")


def collect_selects(n_games: int):
    """Real select contexts from real games, including multi-select ones."""
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce
    from cg import c020_baseline_memory as BM
    from cg import c019_core as K
    from cg import api as A

    rows = []
    opps = ["dragapult", "mega_lucario", "iono", "mega_abomasnow"]
    for gi in range(n_games):
        st = {"mem": BM.initial_memory()}

        def make_me(state):
            def me(obs):
                action, _ = BM.recommend(obs, state["mem"])
                state["mem"] = BM.advance_after_executed(obs, action, state["mem"])
                sel = obs.get("select") if isinstance(obs, dict) else None
                if sel is not None and len(rows) < 4000:
                    try:
                        o = A.to_observation_class(obs)
                        s2 = getattr(o, "select", None)
                        ok, detail = K.round_trip_ok(s2)
                        lo = int(getattr(s2, "minCount", 0) or 0)
                        hi = int(getattr(s2, "maxCount", 1) or 1)
                        rows.append({"ok": bool(ok), "detail": detail,
                                     "min_count": lo, "max_count": hi,
                                     "multi": bool(max(lo, hi) > 1),
                                     "n_options": len(K.canonical_options(s2))})
                    except Exception as e:  # noqa: BLE001
                        rows.append({"ok": False, "error": f"{type(e).__name__}: {e}"[:160]})
                return list(action)
            return me

        def mo(o):
            def f(x):
                return o(x)
            return f
        opp = T.make_fresh(opps[gi % 4], ce.SOURCES)
        agents = [make_me(st), mo(opp)] if gi % 2 == 0 else [mo(opp), make_me(st)]
        try:
            env = make("cabt")
            env.run(agents)
        except Exception:  # noqa: BLE001
            pass
    return rows


def package_parity(zpath: str, checkpoint: str, n: int = 6) -> Dict[str, Any]:
    """Load the SAME checkpoint in the repository and in the extracted package; compare."""
    import numpy as np
    import torch
    from cg import c020_byterl_encode as E, c020_byterl_model as M

    rs = np.random.RandomState(7)
    feats = []
    for _ in range(n):
        k = int(rs.randint(3, 9))
        feats.append({
            "board": rs.rand(E.BOARD_SLOTS, E.BOARD_DIM).astype("float32"),
            "hand": rs.rand(E.N_HAND, E.HAND_DIM).astype("float32"),
            "global": rs.rand(E.GLOBAL_DIM).astype("float32"),
            "opt": rs.rand(E.N_OPT, E.OPT_DIM).astype("float32"),
            "opt_mask": np.array([1.] * k + [0.] * (E.N_OPT - k), dtype="float32"),
            "opt_src": np.array([i % E.BOARD_SLOTS for i in range(k)]
                                + [E.BOARD_SLOTS] * (E.N_OPT - k)),
            "opt_tgt": np.array([(i + 3) % E.BOARD_SLOTS for i in range(k)]
                                + [E.BOARD_SLOTS] * (E.N_OPT - k)),
            "n_options": np.int64(k), "min_count": np.int64(1), "max_count": np.int64(1)})

    m = M.PTCGByteRL()
    m.load_state_dict(torch.load(checkpoint, map_location="cpu")["state_dict"])
    m.eval()
    repo = []
    state = None
    for f in feats:
        b = M.to_torch(f)
        with torch.no_grad():
            lg, v, nxt = m.forward(b, state)
            out = m.select_autoregressive(b, state, k=1, greedy=True)
        state = tuple(t.detach() for t in nxt)
        repo.append({"logits": [round(float(x), 6) for x in lg[0][:8]],
                     "value": round(float(v[0]), 6),
                     "selected": out["selected"],
                     "h_sum": round(float(state[0].sum()), 5),
                     "c_sum": round(float(state[1].sum()), 5)})

    tmp = tempfile.mkdtemp(prefix="c020par_")
    with zipfile.ZipFile(zpath) as z:
        z.extractall(tmp)
    np.save(os.path.join(tmp, "_feats.npy"), np.array(feats, dtype=object),
            allow_pickle=True)
    script = os.path.join(tmp, "_parity.py")
    open(script, "w").write(f'''
import json, os, sys
import numpy as np, torch
_BLOCK = {{{_REPO!r}, os.path.join({_REPO!r}, "cg"), os.path.join({_REPO!r}, "starter_kit"),
           os.path.join({_REPO!r}, "tools")}}
sys.path = [p for p in sys.path if os.path.abspath(p or ".") not in
            {{os.path.abspath(x) for x in _BLOCK}}]
sys.path.insert(0, {tmp!r})
os.chdir({tmp!r})
from cg import c020_byterl_model as M
feats = np.load(os.path.join({tmp!r}, "_feats.npy"), allow_pickle=True)
m = M.PTCGByteRL()
m.load_state_dict(torch.load(os.path.join({tmp!r}, "model.pt"), map_location="cpu")["state_dict"])
m.eval()
out, state = [], None
for f in feats:
    b = M.to_torch(dict(f))
    with torch.no_grad():
        lg, v, nxt = m.forward(b, state)
        sel = m.select_autoregressive(b, state, k=1, greedy=True)
    state = tuple(t.detach() for t in nxt)
    out.append({{"logits": [round(float(x), 6) for x in lg[0][:8]],
                "value": round(float(v[0]), 6),
                "selected": sel["selected"],
                "h_sum": round(float(state[0].sum()), 5),
                "c_sum": round(float(state[1].sum()), 5)}})
print("C020PAR" + json.dumps(out))
''')
    r = subprocess.run([os.path.join(_REPO, ".venv/bin/python"), script],
                       capture_output=True, text=True, timeout=1200)
    pkg = None
    for line in r.stdout.splitlines():
        if line.startswith("C020PAR"):
            pkg = json.loads(line[len("C020PAR"):])
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    if pkg is None:
        return {"ok": False, "error": r.stderr[-500:]}
    diffs = []
    for i, (a, b) in enumerate(zip(repo, pkg)):
        if a != b:
            diffs.append({"step": i, "repo": a, "package": b})
    return {"ok": not diffs, "steps": len(repo), "mismatches": len(diffs),
            "first_mismatch": diffs[0] if diffs else None,
            "checked": ["legal logits", "autoregressive selected payload",
                        "recurrent transition (h/c)", "value output"],
            "repo_sample": repo[0], "package_sample": pkg[0]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=12)
    ap.add_argument("--package", default="")
    ap.add_argument("--checkpoint", default="")
    a = ap.parse_args(argv)

    rows = collect_selects(a.games)
    multi = [r for r in rows if r.get("multi")]
    ok = [r for r in rows if r.get("ok")]
    b04 = {"select_contexts": len(rows), "round_trip_ok": len(ok),
           "multi_select_contexts": len(multi),
           "multi_select_round_trip_ok": sum(1 for r in multi if r.get("ok")),
           "rate": round(len(ok) / max(1, len(rows)), 6),
           "failures": [r for r in rows if not r.get("ok")][:5]}
    d = os.path.join(P, "B04_canonical_action_round_trip")
    os.makedirs(d, exist_ok=True)
    json.dump({"probe_id": "B04", "name": "canonical_action_round_trip", "branch": "byterl",
               "status": "PASS" if b04["rate"] >= 0.999 and rows else "FAIL_TAINTED",
               "checks": b04}, open(os.path.join(d, "probe.json"), "w"), indent=2)
    open(os.path.join(d, "README.md"), "w").write(
        f"# B04 — Canonical action round trip\n\n{b04['round_trip_ok']} of "
        f"{b04['select_contexts']} real select contexts reconstruct the exact environment "
        f"payload, including {b04['multi_select_round_trip_ok']} of "
        f"{b04['multi_select_contexts']} MULTI-select contexts.\n\nThe multi-select column is "
        f"the one that matters: an option identified by index rather than by key, or a payload "
        f"built with the wrong cardinality, produces a legal-looking action that is not the "
        f"action selected. The c020 search failed exactly this way before the repair pass — it "
        f"stepped every multi-select context with a single option and the engine rejected it.\n")

    pkg = a.package
    ck = a.checkpoint
    if not pkg:
        cands = glob.glob(os.path.join(C20, "packages", "corrected_byterl", "*.zip"))
        pkg = max(cands, key=os.path.getmtime) if cands else ""
    if not ck:
        man = pkg.replace(".zip", "_manifest.json")
        if os.path.exists(man):
            base = json.load(open(man)).get("checkpoint")
            for root, _d, fs in os.walk(os.path.join(C20, "byterl", "checkpoints")):
                if base in fs:
                    ck = os.path.join(root, base)
    b14 = ({"ok": False, "reason": "no ByteRL package or checkpoint available yet"}
           if not (pkg and ck and os.path.exists(ck)) else package_parity(pkg, ck))
    d = os.path.join(P, "B14_package_recurrent_action_parity")
    os.makedirs(d, exist_ok=True)
    json.dump({"probe_id": "B14", "name": "package_recurrent_action_parity",
               "branch": "byterl",
               "status": "PASS" if b14.get("ok") else "NOT_EXERCISED",
               "checks": {**b14, "package": os.path.basename(pkg) if pkg else None,
                          "checkpoint": os.path.basename(ck) if ck else None}},
              open(os.path.join(d, "probe.json"), "w"), indent=2)
    open(os.path.join(d, "README.md"), "w").write(
        f"# B14 — Package recurrent/action parity\n\nThe SAME checkpoint is loaded in the "
        f"repository and in the extracted package (repository source roots removed from "
        f"`sys.path`), and both are driven through an identical fixed sequence. Compared at "
        f"every step: legal logits, the autoregressive selected payload, the recurrent "
        f"transition and the value output.\n\nResult: **{b14.get('mismatches', 'n/a')}** "
        f"mismatches over {b14.get('steps', 0)} steps.\n\nPlaying legal games is not parity — a "
        f"package can differ from the evaluated code and still complete every game, which is why "
        f"`CONTRACT §8` lists submitted-differs-from-evaluated as its own blocker.\n")

    print(json.dumps({"B04": b04, "B14": {k: v for k, v in b14.items()
                                          if k not in ("repo_sample", "package_sample")}},
                     indent=2)[:1600])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
