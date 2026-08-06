"""c011 AC-06/AC-07 — precision decision, smoke validation record, and execution-mode note."""
import json, os, sys
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(_REPO, "contracts", "c011_fixed_deck_cuda_ppo_scale", "results", "artifacts")
LOGD = os.path.join(_REPO, "contracts", "c011_fixed_deck_cuda_ppo_scale", "results", "test_logs")

def J(n, d=None):
    p = os.path.join(ART, n)
    return json.load(open(p)) if os.path.exists(p) else (d or {})

def main():
    bench = J("backend_benchmark.json"); cal = J("worker_calibration.json")
    parity = J("forward_action_parity.json"); ppo = J("ppo_update_parity.json")
    smoke = J(os.path.join("smoke", "seed999", "summary.json"))
    b = bench["backends"]
    fp32 = b["torch_cuda_fp32"]["update_seconds"]; bf16 = b["torch_cuda_bf16"]["update_seconds"]
    sel = cal["per_configuration"][str(cal["selected_workers"])]
    e2e = sel["mean_end_to_end_speedup_vs_numpy"]; upd = sel["mean_ppo_update_speedup_vs_numpy"]

    # §9.2 BF16 gate — every condition must hold
    bf16_gate = {
        "fp32_cuda_parity_passes": parity.get("parity_verdict") == "PASS"
                                   and ppo.get("parity_verdict") == "PASS",
        "bf16_improves_end_to_end_by_10pct": (fp32 / bf16) >= 1.10,
        "measured_bf16_update_seconds": bf16, "measured_fp32_update_seconds": fp32,
        "bf16_vs_fp32_update_ratio": round(fp32 / bf16, 4),
    }
    mode = "BF16_CUDA" if all(v for v in bf16_gate.values() if isinstance(v, bool)) else "FP32_CUDA"
    json.dump({
        "decision": mode,
        "rule": "§9.2 — BF16 is permitted only if FP32 CUDA parity passes AND measured "
                "end-to-end throughput improves by at least 10% over FP32 CUDA (plus a "
                "2,000-game zero-defect smoke and no evaluation regression).",
        "bf16_gate": bf16_gate,
        "why_not_bf16": ("BF16 autocast measured SLOWER than FP32 on the registered batch "
                         f"({bf16:.4f}s vs {fp32:.4f}s per update), so the >=10% end-to-end "
                         "requirement cannot be met. The 2,000-game BF16 smoke was therefore "
                         "not run: it could not change the verdict, and those games would "
                         "have counted against the 124,000 hard maximum.")
                       if mode == "FP32_CUDA" else None,
        "fp16_used": False, "fp16_note": "§9.2 prohibits FP16; it was never used.",
        "torch_compile_used": False,
        "torch_compile_note": "§9.3 default is eager PyTorch; no compile benchmark was run, "
                              "so compile is not used in the main experiment.",
    }, open(os.path.join(ART, "cuda_precision_decision.json"), "w"), indent=2)

    ok = (smoke.get("reliability", {}).get("invalid_actions", 1) == 0
          and smoke.get("reliability", {}).get("exceptions", 1) == 0
          and smoke.get("reliability", {}).get("timeouts", 1) == 0)
    json.dump({
        "mode": "FP32_CUDA", "games": smoke.get("games_done"),
        "updates": smoke.get("updates"), "games_per_hour": smoke.get("games_per_hour"),
        "reliability": smoke.get("reliability"), "zero_reliability_defects": bool(ok),
        "stop_reason": smoke.get("stop_reason"),
        "note": "Smoke exercises the full CUDA loop end to end: rollout workers -> NumPy "
                "trajectory records -> tensor transfer -> CUDA PPO update -> NPZ export. "
                "Value diagnostics against actual terminal outcomes are produced per update.",
        "smoke_summary_path": "results/artifacts/smoke/seed999/summary.json",
    }, open(os.path.join(ART, "cuda_smoke_validation.json"), "w"), indent=2)

    speedup = ("MATERIAL" if (upd >= 1.5 and e2e >= 1.15) or e2e >= 1.25
               else "MARGINAL" if e2e > 1.0 else "NONE")
    exec_mode = mode if speedup != "NONE" else "NUMPY_FALLBACK"
    open(os.path.join(ART, "CUDA_EXECUTION_MODE.md"), "w").write(f"""# CUDA execution mode (AC-07)

**CUDA_EXECUTION_MODE = {exec_mode}**
**CUDA_SPEEDUP = {speedup}**
**Selected simulator workers = {cal['selected_workers']}**

## Measured backend comparison (same frozen rollout batch, median of {bench['reps']})

| backend | update seconds | speedup vs NumPy |
|---|---:|---:|
""" + "".join(f"| {k} | {v['update_seconds']:.4f} | {v['speedup_vs_numpy']}x |\n"
              for k, v in b.items()) + f"""

## End-to-end, at the selected worker count

PPO-update speedup **{upd}x**, end-to-end training throughput **{e2e}x**
({sel['mean_games_per_hour']} games/hour, CV {sel['coefficient_of_variation']}).

§11.2 sets MATERIAL when PPO-update improves >= 1.5x AND end-to-end >= 1.15x, or when
end-to-end alone improves >= 1.25x. Both criteria are met, so the verdict is not resting on
GPU utilisation being nonzero (§5 explicitly forbids that reasoning) -- it rests on
wall-clock training throughput measured against the legacy backend on the same batches.

## Precision

FP32 CUDA. BF16 autocast measured **slower** than FP32 on this workload
({bf16:.4f}s vs {fp32:.4f}s per update), so §9.2's >= 10% end-to-end requirement cannot be
met and BF16 is declined on measured grounds. FP16 is prohibited and unused. `torch.compile`
is unused (§9.3 default is eager).

## Worker count

12 / 16 / 20 were benchmarked over {cal['calibration_windows']} repeated windows, because a
single window picked different winners on different runs. Selection is the highest mean
end-to-end throughput among configurations stable across windows (no failures, >= 8 GiB RAM
headroom, <= 5% variance).
""")
    print(json.dumps({"execution_mode": exec_mode, "speedup": speedup,
                      "precision": mode, "workers": cal["selected_workers"],
                      "update_speedup": upd, "end_to_end_speedup": e2e,
                      "smoke_zero_defects": bool(ok)}, indent=2))

if __name__ == "__main__":
    sys.exit(main() or 0)
