# DEFECT — panel results were a function of machine load

**Found:** by chasing a 41-point swing in `C019_HYBRID_CONTROL` (0.19, then 0.605) that was far
outside the ±3.5-point panel variance the campaign had measured, instead of attributing it to
noise.

## The discrepancy that exposed it

c019 measured its own hybrid at **0.1375**. My c020 panel measured the same candidate, with a
verified-identical configuration — same 12 simulations, 1 determinization, 120 ms budget, same
checkpoint path, same calibration flag — at **0.605**.

Running c019's OWN panel tool on this machine, now, gave **0.10**. So the configuration was not
the difference; the harness was.

## Cause

`tools/c019_panel.py::_play` calls `torch.set_num_threads(1)`. My `tools/c020_panel.py::_worker`
did not, and neither did `tools/c020_mcts_run.py::_worker`.

Without it, every panel process spawns a full torch thread pool. With 6-10 panel processes the
machine is heavily oversubscribed, and the contention is charged against each agent's
**per-decision wall-clock budget** (`max_ms_per_decision`). A search-based candidate therefore
completes fewer simulations under load.

That inverts the measurement for a candidate whose search is HARMFUL. c019's hybrid is bad
precisely because its priors steer the search away from the baseline; starve the search and it
deviates less, so it scores **better**. The worse the search, the more load flatters it.

## Confirmation

Adding `torch.set_num_threads(1)` to the panel worker, same seeds, same machine:

| candidate | before | after | c019's own tool |
|---|---|---|---|
| `C019_HYBRID_CONTROL` | 0.605 | **0.225** | 0.10 / 0.1375 |
| `C019_PIMC_PUCT_CONTROL` | 0.38-0.46 | **0.55** | 0.40 / 0.50 |

Maximum game time fell from 42.1s to 8.5s at the same configuration, which is the contention
becoming visible.

## Scope

Every panel measurement of a torch-using candidate is affected: the three c019 controls, and
prospectively `C020_CORRECTED_BYTERL` and H1-H4. `C020_CORRECTED_MCTS` and the override ablation
arms use no torch in their hot path and are far less affected, though they were run alongside
torch-heavy jobs and are re-run for consistency rather than argued about.

The frozen baseline is unaffected — it is a scripted agent with no time budget and no torch.

This also explains, at least in part, the 0.525 / 0.595 / 0.5525 spread across baseline panels:
those runs happened under different concurrent load. The variance I attributed wholly to unpaired
environment randomness had a controllable component in it, and the "sd 0.035 at n=400" figure is
therefore an upper bound on the irreducible noise, not a measurement of it.

## Fix

`torch.set_num_threads(1)` in both `c020_panel._worker` and `c020_mcts_run._worker`, matching
c019. All affected measurements re-run.

## Pattern

Fourth defect in this campaign whose signature was a plausible-looking number: after a package
that searched 0 decisions while winning half its games, an option resolver that returned -1 for
everything while passing its source check, and `--append` that silently discarded the rows it was
asked to add. None was found by a test; all four were found by checking a number against something
it should have equalled.
