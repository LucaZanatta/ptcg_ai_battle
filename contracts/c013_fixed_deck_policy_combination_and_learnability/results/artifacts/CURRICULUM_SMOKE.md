# AC-11 — adaptive-curriculum smoke test

**CURRICULUM_SMOKE = PASS**

§18: this validates **execution machinery only**. 5,000 games per arm cannot support a claim about whether the adaptive curriculum helps, and none is made here.

Every requirement below exists because c012 shipped a 90,000-game arm in which none of them held: a stale per-path checkpoint-hash cache emptied every in-run evaluation after game zero, so the gates never ran, the stage never advanced past 0, and early stopping never received a score.

## R0 seed 1001 — unchanged population (control)

5104 completed games, 12 updates, final stage 0 after 0 stage change(s). Reliability: {'invalid_actions': 0, 'exceptions': 0, 'timeouts': 0}.

| registered point | games | stage | teacher | field | scored |
|---|---|---|---|---|---|
| 0 | 0 | 0 | 0.250 | 0.350 | 100/100 |
| 2500 | 2592 | 0 | 0.300 | 0.400 | 100/100 |
| 5000 *(backfilled)* | 5104 | 0 | 0.425 | 0.400 | 100/100 |

| §20 requirement | passed | evidence |
|---|---|---|
| non-zero scored games at every registered evaluation | **yes** | 3/3 evaluations scored; points [0, 2500, 5000] |
| all three registered evaluation points covered | **yes** | points covered [0, 2500, 5000], required [0, 2500, 5000]; backfilled [5000] |
| checkpoint hashes refreshed correctly | **yes** | 12 distinct checkpoint hashes observed |
| all progression gates computed | **yes** | 2 gate evaluations; every evaluation record carries a gates dict |
| curriculum stage changes at least once (adaptive arm) | **yes** | stage_changes=0, final_stage=0 (control arm: no change expected) |
| curriculum history preserved | **yes** | 0 history entries |
| early-stop code path exercised | **yes** | a deterministic fixture drives the stop condition without ending the run |
| trainer state saved and restored mid-run | **yes** | 1 save/restore cycle(s); continuation_kind=literal |
| next opponent/seat/seed sequence reproduced after restore | **yes** | expected [['iono', 0, 639292282], ['mega_lucario', 1, 374230924], ['lagged::lagged_g2592.npz', 0, 294381893]] == restored [['iono', 0, 639292282], ['mega_lucario', 1, 374230924], ['lagged::lagged_g2592.npz', 0, 294381893]] |

## R1 seed 1002 — adaptive elite curriculum

5008 completed games, 12 updates, final stage 2 after 2 stage change(s). Reliability: {'invalid_actions': 0, 'exceptions': 0, 'timeouts': 0}.

| registered point | games | stage | teacher | field | scored |
|---|---|---|---|---|---|
| 0 | 0 | 0 | 0.250 | 0.350 | 100/100 |
| 2500 | 2528 | 1 | 0.300 | 0.350 | 100/100 |
| 5000 *(backfilled)* | 5008 | 2 | 0.225 | 0.350 | 100/100 |

| §20 requirement | passed | evidence |
|---|---|---|
| non-zero scored games at every registered evaluation | **yes** | 3/3 evaluations scored; points [0, 2500, 5000] |
| all three registered evaluation points covered | **yes** | points covered [0, 2500, 5000], required [0, 2500, 5000]; backfilled [5000] |
| checkpoint hashes refreshed correctly | **yes** | 12 distinct checkpoint hashes observed |
| all progression gates computed | **yes** | 2 gate evaluations; every evaluation record carries a gates dict |
| curriculum stage changes at least once (adaptive arm) | **yes** | stage_changes=2, final_stage=2 |
| curriculum history preserved | **yes** | 2 history entries |
| early-stop code path exercised | **yes** | a deterministic fixture drives the stop condition without ending the run |
| trainer state saved and restored mid-run | **yes** | 1 save/restore cycle(s); continuation_kind=literal |
| next opponent/seat/seed sequence reproduced after restore | **yes** | expected [['dragapult', 0, 301960232], ['SOUP13_SOUP+P1_833', 1, 46363138], ['mega_lucario', 1, 663620729]] == restored [['dragapult', 0, 301960232], ['SOUP13_SOUP+P1_833', 1, 46363138], ['mega_lucario', 1, 663620729]] |

## Budget

10112 completed games against a registered maximum of 10000 — **112 over**.

This overshoot is a rollout-granularity effect and is documented as a deviation in `results/failures/`; it is not rounded away here. The 62,000 hard training maximum is not approached.

