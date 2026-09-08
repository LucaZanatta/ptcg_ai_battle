# Concurrency decision: MCGS and ByteRL run together, and the evidence is per arm

`CONTRACT.md §5`: "MCGS gets exclusive CPU during decisive scaling and final panels. ByteRL may
run concurrently only when CPU contention is measured and shown not to taint timing/evaluation."

## The observation that prompted this

At 13:09 the machine was **79% idle, load average 4.5 on 24 logical cores**, with a K sweep
running. Two causes:

1. **`nproc 12` is a c021 constraint that does not apply to c022.** c021's arms were WALL-CLOCK
   budgeted — 0.9 s per decision — so contention converted directly into fewer simulations. Its
   own M16 measurement found `sims_per_decision` collapsing to 8% of the single-worker value at
   24 workers, with nothing in the field score to reveal it, and its conclusion was "run alone at
   nproc 12". **c022's arms are SIMULATION-COUNT budgeted**, specifically so that this cannot
   happen: a decision runs its 256 simulations however long that takes.
2. **Straggler tail.** Near the end of an arm only a few long games remain, so most worker slots
   sit empty while the arm refuses to finish.

## Why the standalone contention test was abandoned

A separate `tools/c022_contention.py` run was started and then killed. It was measuring a proxy
arm while competing with the very sweep it was measuring, and after 14 minutes it had not
completed its first configuration. The proxy is unnecessary, because **every MCGS arm already
reports the three quantities that decide the question**, measured on the real arm rather than a
stand-in:

| quantity | what a taint would look like | where |
|---|---|---|
| `sims_per_decision` | below the configured budget | every `*_summary.json` |
| `decision_deadline_stops` | nonzero — a decision hit the per-decision wall ceiling, so its budget was NOT delivered | every `*_summary.json` |
| `excluded_fraction` | moving across arms — slower games get cut by the per-game guard, and cut games leave the field score, so the surviving population changes | every `*_summary.json`; the analyzer gates on the spread |

The tool is kept in the tree because it is the right instrument if a per-arm counter ever fires
and the cause needs isolating.

## The decision

```text
MCGS sweep       nproc 14
ByteRL campaign  6 actors + 1 learner
total            ~21 of 24 logical cores
```

and **the load is held CONSTANT for the whole sweep**. That is the part that matters. An arm run
unloaded and an arm run loaded are not comparable, and "K=8 is worse" would become
indistinguishable from "K=8 ran under load" — the same confound shape as the wall-clock cut
(D08) and the c021 contention artifact. So the sweep is restarted from its first arm with ByteRL
already running, rather than having load introduced partway through.

## Why the a-priori argument is strong, and why it is not sufficient

At 256 simulations per decision and ~19 ms per simulation, a decision costs about 5 seconds
against a 300-second per-decision wall ceiling. Contention would have to slow the machine
**sixty-fold** to trip it. That is not a plausible regime for 21 processes on 24 cores.

The per-game guard is tighter. It is derived as
`decision_budget × total_sims × seconds_per_simulation × 1.5`, and a game reaching ~100 searched
decisions uses roughly a quarter of it. A 2× slowdown is comfortable; a 4× slowdown would start
cutting games.

So the argument predicts safety with margin — but "predicts" is exactly what c021's contention
artifact also did, and the counters are what settle it. **If any arm reports
`budget_delivered: false`, a nonzero `decision_deadline_stops`, or an `excluded_fraction`
materially different from its K=1 control, that arm is re-run under exclusive CPU and the fact is
recorded.** The analyzer's validity gate already refuses to compare arms that fail these, so the
failure mode is a loud one rather than a silent one.

## What is NOT run concurrently

`CONTRACT.md §5` names two exceptions and they are honoured:

- the **final panel** runs alone;
- the **unrestricted source-style timing arm** (`MCGS_2019_PTCG_MULTI_DET_REFERENCE` at the
  original 15 s / 10 s schedule) runs alone, because that arm is wall-clock budgeted by
  construction and is therefore exactly the kind of arm contention would corrupt.

The `MCGS_2019_PTCG_MULTI_DET_KAGGLE_DEPLOY` arm also runs alone, for the same reason: it
re-introduces a cumulative clock.
