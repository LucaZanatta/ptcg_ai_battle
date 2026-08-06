# CUDA execution mode (AC-07)

**CUDA_EXECUTION_MODE = FP32_CUDA**
**CUDA_SPEEDUP = MATERIAL**
**Selected simulator workers = 16**

## Measured backend comparison (same frozen rollout batch, median of 3)

| backend | update seconds | speedup vs NumPy |
|---|---:|---:|
| numpy_micrograd | 2.1689 | 1.0x |
| torch_cpu_fp32 | 0.6166 | 3.518x |
| torch_cuda_fp32 | 0.1646 | 13.179x |
| torch_cuda_bf16 | 0.1718 | 12.627x |


## End-to-end, at the selected worker count

PPO-update speedup **14.178x**, end-to-end training throughput **2.869x**
(36199.0 games/hour, CV 0.042).

§11.2 sets MATERIAL when PPO-update improves >= 1.5x AND end-to-end >= 1.15x, or when
end-to-end alone improves >= 1.25x. Both criteria are met, so the verdict is not resting on
GPU utilisation being nonzero (§5 explicitly forbids that reasoning) -- it rests on
wall-clock training throughput measured against the legacy backend on the same batches.

## Precision

FP32 CUDA. BF16 autocast measured **slower** than FP32 on this workload
(0.1718s vs 0.1646s per update), so §9.2's >= 10% end-to-end requirement cannot be
met and BF16 is declined on measured grounds. FP16 is prohibited and unused. `torch.compile`
is unused (§9.3 default is eager).

## Worker count

12 / 16 / 20 were benchmarked over 3 repeated windows, because a
single window picked different winners on different runs. Selection is the highest mean
end-to-end throughput among configurations stable across windows (no failures, >= 8 GiB RAM
headroom, <= 5% variance).
