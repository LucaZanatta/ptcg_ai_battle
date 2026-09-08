# Superseded: `ft_k1` from the first sweep launch

These four files (`ft_k1_summary.json`, `ft_k1_games.jsonl`, `ft_k1_calibration.jsonl`,
`ft_k1_traces.jsonl`) are moved here rather than deleted, because a result that vanishes cannot
be audited and a result that stays in place becomes evidence.

## What happened

The first sweep was launched at 11:32 and stopped at 12:00 once three defects in the runner were
identified (see commit `f992caa`): a per-game wall clock that cut high-K arms earlier in decision
space than low-K arms, an agent seed derived from completion timing, and no runnable M04
definition. `pkill -f c022_sweep.sh` killed the driver script but the `ft_k1` arm it had already
spawned survived as an orphan and ran to completion at 12:02, writing these files — and writing
into the relaunched sweep's log through its inherited file descriptor, which is why the log's
first line is truncated mid-word.

## Why they must not be used

The summary's own `config` block is the proof: it has no `decision_budget` field, because the
code that produced it predates the fix.

```json
"config": {"branch": "...", "k_worlds": 1, "budget_protocol": "fixed_total",
           "simulations_per_decision": 256, "graph_reuse": false,
           "match_clock_seconds": 0.0, "decision_seconds_cap": 0.0,
           "decision_wall_ceiling_seconds": 300.0}
```

Two specific problems:

1. **Games were cut by wall clock, not by a decision budget.** 4 of 60 games were abandoned and
   excluded from the field score. Under the corrected runner every K is cut at the same decision,
   so this arm's surviving subsample is not comparable with the arms it would have been the
   control for.
2. **Its agent seeds are not reproducible.** They were derived from `len(results) +
   len(running)`, which depends on completion timing, so re-running the identical command would
   not reproduce this run.

Its headline reading was `field_score 0.1739` on 46 completed games, Wilson 95% `[0.0909,
0.3072]`. It is recorded here for provenance and is not cited anywhere as a c022 result.

This is the stale-artifact defect family this repository has shipped before: the counts look
right, the file is in the right directory, and the attribution is wrong. The corrected `ft_k1`
lives in `results/mcgs/fixed_total_simulations/` and carries `decision_budget` in its config.

---

# Superseded: two `m04_k1_reuse` arms

`m04_from_sweep2/` and `m04_from_sweep3/` are the K=1 identity arm from the second and third
sweep launches. Both predate the D13 fix (the SEARCHED path emitting a single option when
`minCount > 1`), and both are quarantined for that reason.

`m04_from_sweep2/` additionally predates the unscored-category accounting: its summary has no
`unscored` field at all, so its 6 missing games are invisible in it. It is the second orphan —
`pkill -f c022_sweep.sh` killed the driver at 12:00 and again at 12:20, and both times the arm
already spawned survived and ran to completion.

`m04_from_sweep3/` DOES carry the accounting, which is how D13 was found: `unscored: 10`,
`unscored_status_histogram: {"INVALID|DONE": 10}`, and crucially
`decision_budget_exhausted_decisions: 0` — proving the invalid actions came from the searched
path rather than the out-of-budget fallback. Its `games_accounted: 49` against `games: 60` is an
artifact of my killing it mid-run, not a code defect.

Neither is cited as a c022 result. `m04_from_sweep3/` is genuinely useful evidence *about a
defect*, and the defect log (D13) cites it as such.

The sweep script now traps EXIT and kills its whole process group, so a driver kill takes its
arms with it.
