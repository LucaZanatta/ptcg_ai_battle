"""c011 §11 — worker calibration and backend benchmark.

Two independent measurements:

  §11.1  Simulator-worker calibration at 12 / 16 / 20 workers. The rollout is the CPU-bound
         half of the loop, so this decides the worker count; it is measured, not assumed
         (§11.1 "Do not assume 24 workers is optimal").

  §11.2  The same FROZEN rollout batch pushed through four update backends: legacy
         NumPy/micrograd, PyTorch CPU, PyTorch FP32 CUDA and (conditionally) BF16 CUDA.
         Using one frozen batch means the comparison measures the backend and nothing else.

The end-to-end figure is what decides CUDA_SPEEDUP, because a faster update only helps in
proportion to its share of the cycle. Forcing the GPU when it is not faster is explicitly
prohibited (§11.2), so NUMPY_FALLBACK is a legitimate outcome.

Calibration games count against the 124,000 hard maximum, so the game cost is computed and
logged BEFORE the run rather than discovered afterwards.
"""

import argparse
import json
import os
import pickle
import subprocess
import sys
import time

import numpy as np
import torch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

from cg import ppo as legacy_ppo, rl_policy as rlp, c010_train as ct, c009_eval as ce  # noqa: E402
import c011_torch_model as tm  # noqa: E402
import c011_torch_ppo as tp  # noqa: E402

C011 = os.path.join(_REPO, "contracts", "c011_fixed_deck_cuda_ppo_scale")
ART = os.path.join(C011, "results", "artifacts")
LOGD = os.path.join(C011, "results", "test_logs")
BATCH = os.path.join(ART, "ppo_parity_batch.pkl")

CFG = {"gamma": 0.997, "lam": 0.95, "clip": 0.20, "vf_coef": 0.50, "max_grad_norm": 0.50,
       "epochs": 4, "minibatch": 256}
LR, WD, ENT = 3e-5, 1e-5, 0.004
WORKER_CANDIDATES = [12, 16, 20]


def gpu_stats():
    try:
        r = subprocess.run(["nvidia-smi",
                            "--query-gpu=utilization.gpu,memory.used,memory.free,temperature.gpu",
                            "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=20)
        u, used, free, temp = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
        return {"gpu_util_pct": float(u), "vram_used_mib": float(used),
                "vram_free_mib": float(free), "gpu_temp_c": float(temp)}
    except Exception:  # noqa: BLE001
        return {}


def ram_available_gib():
    try:
        for ln in open("/proc/meminfo"):
            if ln.startswith("MemAvailable"):
                return round(int(ln.split()[1]) / 1048576, 2)
    except OSError:
        pass
    return None


def _cpu_snap():
    with open("/proc/stat") as fh:
        parts = [float(x) for x in fh.readline().split()[1:]]
    return sum(parts), parts[3] + parts[4]


def cpu_util_pct(sample=1.0):
    t0, i0 = _cpu_snap(); time.sleep(sample); t1, i1 = _cpu_snap()
    dt, di = t1 - t0, i1 - i0
    return round(100.0 * (1 - di / dt), 1) if dt > 0 else None


class CpuSampler:
    """CPU utilisation measured ACROSS the rollout, not after it. Sampling afterwards reports
    the idle machine and understates the rollout by roughly an order of magnitude."""

    def __enter__(self):
        self._t0, self._i0 = _cpu_snap()
        self._ram_min = ram_available_gib() or 1e9
        return self

    def sample_ram(self):
        r = ram_available_gib()
        if r is not None:
            self._ram_min = min(self._ram_min, r)

    def __exit__(self, *a):
        t1, i1 = _cpu_snap()
        dt, di = t1 - self._t0, i1 - self._i0
        self.util = round(100.0 * (1 - di / dt), 1) if dt > 0 else None
        self.ram_min = self._ram_min
        return False


# ---------------- §11.2 backend benchmark ----------------

def bench_backends(ckpt, reps=3):
    games = pickle.load(open(BATCH, "rb"))
    n_dec = sum(len(g) for g in games)
    pol = rlp.RLPolicy.load(ckpt)
    sd = pol.state_dict()
    flat = legacy_ppo.compute_gae(games, CFG["gamma"], CFG["lam"])
    orders = tp.precompute_order(len(flat), CFG["epochs"], np.random.default_rng(3))
    out = {"n_games": len(games), "n_decisions": n_dec, "reps": reps, "backends": {}}

    # legacy numpy/micrograd
    ts_ = []
    for _ in range(reps):
        p = rlp.RLPolicy.load(ckpt)
        o = legacy_ppo.AdamW(p.params(), lr=LR, wd=WD)
        t0 = time.time()
        legacy_ppo.ppo_update(p, games, CFG, o, ENT, rng=np.random.default_rng(3))
        ts_.append(time.time() - t0)
    out["backends"]["numpy_micrograd"] = {"update_seconds": float(np.median(ts_)),
                                          "all": ts_, "device": "cpu"}

    def bench_torch(device, dtype, autocast=None, label=None):
        times, gpu = [], {}
        for _ in range(reps):
            m = tm.TorchPolicy(pol.trunk.cfg, dtype=dtype, device=device).load_legacy_state(sd)
            o = tp.make_optimizer(m, LR, WD)
            if device.startswith("cuda"):
                torch.cuda.synchronize()
            t0 = time.time()
            tp.ppo_update_torch(m, games, CFG, o, ENT, orders=orders, device=device,
                                flat=flat, autocast_dtype=autocast)
            if device.startswith("cuda"):
                torch.cuda.synchronize()
                gpu = gpu_stats()
            times.append(time.time() - t0)
        return {"update_seconds": float(np.median(times)), "all": times,
                "device": device, "dtype": str(dtype),
                "autocast": str(autocast) if autocast else None, **gpu}

    out["backends"]["torch_cpu_fp32"] = bench_torch("cpu", torch.float32)
    if torch.cuda.is_available():
        out["backends"]["torch_cuda_fp32"] = bench_torch("cuda", torch.float32)
        out["backends"]["torch_cuda_bf16"] = bench_torch("cuda", torch.float32,
                                                         autocast=torch.bfloat16)
    base = out["backends"]["numpy_micrograd"]["update_seconds"]
    for k, v in out["backends"].items():
        v["speedup_vs_numpy"] = round(base / v["update_seconds"], 3)
    return out


# ---------------- §11.1 worker calibration ----------------

def bench_workers(ckpt, target_games, nprocs, device, dtype):
    from cg.teachers import make_fresh
    deck = make_fresh("dragapult", ce.SOURCES).deck
    sha = ce.sha256_file(ckpt)
    pol = rlp.RLPolicy.load(ckpt)
    sd = pol.state_dict()
    rows = []
    for nproc in nprocs:
        rng = np.random.default_rng(555)
        jobs = []
        for i in range(target_games):
            jobs.append({"policy_ckpt": ckpt, "policy_version": 1, "policy_sha256": sha,
                         "arm": "CAL", "seed": 999, "game_index": i,
                         "opponent": ("teacher", ["dragapult", "mega_lucario", "iono"][i % 3]),
                         "seat": int(i % 2), "rng_seed": int(rng.integers(0, 1 << 30)),
                         "deck": deck})
        ram_before = ram_available_gib()
        with CpuSampler() as smp:
            t0 = time.time()
            res = ct.run_rollout(jobs, nproc)
            roll_s = time.time() - t0
            smp.sample_ram()
        cpu = smp.util
        ram_min = smp.ram_min
        transitions = [r["transitions"] for r in res
                       if r["meta"]["terminal"] and r["transitions"]]
        n_games = len(transitions)
        n_dec = sum(len(t) for t in transitions)
        failures = sum(1 for r in res if r["meta"].get("exception_count", 0) > 0)

        m = tm.TorchPolicy(pol.trunk.cfg, dtype=dtype, device=device).load_legacy_state(sd)
        o = tp.make_optimizer(m, LR, WD)
        if device.startswith("cuda"):
            torch.cuda.synchronize()
        t1 = time.time()
        tp.ppo_update_torch(m, transitions, CFG, o, ENT, rng=np.random.default_rng(4),
                            device=device)
        if device.startswith("cuda"):
            torch.cuda.synchronize()
        up_s = time.time() - t1
        g = gpu_stats()

        # Same transitions through the legacy backend, so end-to-end CUDA speedup (§11.2) is
        # measured rather than extrapolated from a different batch.
        p_np = rlp.RLPolicy.load(ckpt)
        o_np = legacy_ppo.AdamW(p_np.params(), lr=LR, wd=WD)
        t2 = time.time()
        legacy_ppo.ppo_update(p_np, transitions, CFG, o_np, ENT, rng=np.random.default_rng(4))
        up_np_s = time.time() - t2

        # scale to a full registered rollout (256 games AND >=32,768 decisions)
        dec_per_game = n_dec / max(n_games, 1)
        full_games = max(256, int(np.ceil(32768 / max(dec_per_game, 1e-9))))
        full_roll = roll_s * full_games / max(n_games, 1)
        full_up = up_s * (full_games * dec_per_game) / max(n_dec, 1)
        full_up_np = up_np_s * (full_games * dec_per_game) / max(n_dec, 1)
        cycle = full_roll + full_up
        cycle_np = full_roll + full_up_np
        rows.append({
            "workers": nproc, "probe_games": n_games, "probe_decisions": n_dec,
            "rollout_seconds": round(roll_s, 2), "update_seconds": round(up_s, 2),
            "decisions_per_game": round(dec_per_game, 2),
            "games_per_hour_rollout_only": round(3600 * n_games / roll_s, 1),
            "decisions_per_hour": round(3600 * n_dec / roll_s, 1),
            "cpu_util_pct": cpu, "ram_available_gib_before": ram_before,
            "ram_available_gib_after": ram_min, "process_failures": failures,
            "projected_full_rollout_seconds": round(full_roll, 1),
            "projected_update_seconds": round(full_up, 1),
            "projected_cycle_seconds": round(cycle, 1),
            "projected_games_per_hour_end_to_end": round(3600 * full_games / cycle, 1),
            "numpy_update_seconds": round(up_np_s, 2),
            "projected_numpy_update_seconds": round(full_up_np, 1),
            "projected_numpy_cycle_seconds": round(cycle_np, 1),
            "projected_numpy_games_per_hour_end_to_end": round(3600 * full_games / cycle_np, 1),
            "ppo_update_speedup_cuda_vs_numpy": round(full_up_np / full_up, 3),
            "end_to_end_speedup_cuda_vs_numpy": round(cycle_np / cycle, 3),
            "stable": bool(failures == 0 and (ram_min or 99) >= 8.0),
            **g,
        })
    return rows


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--stage", required=True, choices=["backend", "workers", "all"])
    p.add_argument("--probe-games", type=int, default=150)
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--windows", type=int, default=3,
                   help="repeated calibration windows; §11.1 bounds variance across them")
    a = p.parse_args(argv)
    os.makedirs(ART, exist_ok=True); os.makedirs(LOGD, exist_ok=True)
    result = {}

    if a.stage in ("backend", "all"):
        b = bench_backends(a.checkpoint, a.reps)
        json.dump(b, open(os.path.join(ART, "backend_benchmark.json"), "w"), indent=2)
        result["backend"] = {k: v["update_seconds"] for k, v in b["backends"].items()}

    if a.stage in ("workers", "all"):
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        cost = a.probe_games * len(WORKER_CANDIDATES) * a.windows
        windows = []
        for w in range(a.windows):
            windows.append(bench_workers(a.checkpoint, a.probe_games, WORKER_CANDIDATES,
                                         dev, torch.float32))
        # §11.1: choose the highest STABLE end-to-end throughput, where stability requires
        # no worker failure, >=8 GiB RAM headroom, and <=5% throughput variance ACROSS
        # repeated calibration windows. A single window cannot establish that, and the
        # per-window winner did in fact move between windows.
        per_cfg = {}
        for n in WORKER_CANDIDATES:
            vals = [r["projected_games_per_hour_end_to_end"]
                    for win in windows for r in win if r["workers"] == n]
            rows_n = [r for win in windows for r in win if r["workers"] == n]
            mean = float(np.mean(vals)); sd = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
            cv = (sd / mean) if mean else 1.0
            per_cfg[n] = {
                "windows": vals, "mean_games_per_hour": round(mean, 1),
                "stdev": round(sd, 1), "coefficient_of_variation": round(cv, 4),
                "variance_within_5pct": bool(cv <= 0.05),
                "no_failures": all(r["process_failures"] == 0 for r in rows_n),
                "ram_headroom_ok": all((r["ram_available_gib_after"] or 0) >= 8.0
                                       for r in rows_n),
                "mean_cpu_util_pct": round(float(np.mean([r["cpu_util_pct"] for r in rows_n])), 1),
                "mean_end_to_end_speedup_vs_numpy": round(float(np.mean(
                    [r["end_to_end_speedup_cuda_vs_numpy"] for r in rows_n])), 3),
                "mean_ppo_update_speedup_vs_numpy": round(float(np.mean(
                    [r["ppo_update_speedup_cuda_vs_numpy"] for r in rows_n])), 3),
            }
            per_cfg[n]["stable"] = bool(per_cfg[n]["variance_within_5pct"]
                                        and per_cfg[n]["no_failures"]
                                        and per_cfg[n]["ram_headroom_ok"])
        eligible = {n: v for n, v in per_cfg.items() if v["stable"]}
        chosen = max(eligible or per_cfg, key=lambda n: (eligible or per_cfg)[n]["mean_games_per_hour"])
        doc = {"candidates": WORKER_CANDIDATES,
               "probe_games_per_candidate": a.probe_games,
               "calibration_windows": a.windows,
               "calibration_games_spent": cost,
               "budget_note": "Calibration games count against the 124,000 hard maximum "
                              "(§14); the cost is computed before the run.",
               "constraints": {"min_ram_available_gib": 8.0, "no_worker_failures": True,
                               "no_gpu_oom": True, "max_variance_across_windows": 0.05},
               "per_configuration": per_cfg,
               "windows": windows,
               "selected_workers": chosen,
               "selection_rule": "highest mean end-to-end games/hour among configurations "
                                 "that are stable across repeated windows (§11.1)",
               "any_configuration_unstable": [n for n, v in per_cfg.items() if not v["stable"]],
               "device_used_for_update": dev}
        json.dump(doc, open(os.path.join(ART, "worker_calibration.json"), "w"), indent=2)
        result["workers"] = {"selected": chosen,
                             "per_config": {n: (v["mean_games_per_hour"],
                                                v["coefficient_of_variation"], v["stable"])
                                            for n, v in per_cfg.items()},
                             "games_spent": cost}

    with open(os.path.join(LOGD, "throughput_calibration.txt"), "a") as fh:
        fh.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
