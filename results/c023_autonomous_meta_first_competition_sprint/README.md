# c023 results — what is here and where to start

Start with **`EXECUTIVE_DECISION.md`**. It answers the contract's twelve questions and nothing
else in this tree contradicts it — every number in it is recomputed from raw games by
`tools/c023_validate.py` (check V01) and by `tools/c023_reports.py`.

## If you only read four files

| file | why |
|---|---|
| `EXECUTIVE_DECISION.md` | the twelve questions, answered |
| `ladder_replays/LADDER_CALIBRATION.md` | the first local↔ladder conversion this project has had, from 380 of our own public games |
| `META_REPORT.md` | what the ladder is actually playing, §5b what it paired *us* against, and the deck-versus-agent decomposition |
| `ACCEPTANCE_CHECKLIST.md` | every criterion, generated from artifacts, `NO_DATA` never silently upgraded to `PASS` |

## The decision trail

| file | contents |
|---|---|
| `champion.json` | who the champion is and the evidence that chose it — plus the *panel leader*, recorded separately because it is ineligible |
| `MATCHUP_MATRIX.csv` | every player against every player, recomputed from `games.jsonl` |
| `PANEL_SPLIT.json` | the dev/validation opponent split, **registered before any candidate was built**, and one amendment |
| `PREDICTIONS.md` | two predictions registered before the runs that tested them; both held |
| `PIVOT_LEDGER.md` | four redirections, each with the evidence that forced it |
| `DECISION_BOARD.json`, `STATUS.json` | machine-readable statuses, generated |

## What was tried

| file | contents |
|---|---|
| `DECK_CHANGE_LEDGER.md` | 17 deck mutations, and the +7.25 → −0.12 reversal that killed the branch |
| `AGENT_CHANGE_LEDGER.md` | every rule and planner variant, with the failure class each named |
| `FAILURE_TAXONOMY.md` | losses assigned to countable classes, from mined games |
| `BYTERL_COMPONENT_RESULTS.md` | why no learned component was admitted |
| `tuning/REGISTERED_PROTOCOL.md` | the score-constant search, its accept margin and its stages, fixed before it ran |

## The evidence itself

| path | contents |
|---|---|
| `raw_evaluations/<tag>/games.jsonl` | one line per game: identities, both agents' hashes, score, latency, errors |
| `raw_evaluations/<tag>/summary.json` | the aggregate — **always recomputable** from the line above it |
| `raw_evaluations/identity/` | proof each wrapper build is action-identical to its official base |
| `raw_evaluations/rule_fires/` | how often each enabled rule actually fired; `INERT` is a first-class outcome |
| `ladder_replays/` | our four submissions' real ladder records, mined from Kaggle episode replays |
| `candidate_manifests/` | one per candidate: parent, deck, hashes, params |
| `CANDIDATE_HISTORY.jsonl` | one line per candidate, assembled from those manifests and the raw games |
| `final_packages/` | the frozen champion archive, its manifest, and its **executed** clean validation |
| `source/`, `git/` | exact source archives, hashes, commit, diff, log |
| `failures/DEFECTS.md` | six defects found during the campaign, and how each presented |
| `superseded/README.md` | artifacts invalidated by something learned later, and why they are still cited |
| `UNRESOLVED_RISKS.md` | ten things this campaign could not settle |

## Reproducing any number here

```bash
.venv/bin/python tools/c023_validate.py --injections   # 11 checks, 9 injections
bash tools/c023_finalize.sh                            # regenerate every report from raw data
```

`--injections` is the part worth running: it corrupts a copy of the evidence in the exact way
each check exists to catch and asserts the check fires. A check that cannot be made to fail is
not a check.

## One thing to know before reading any comparison

**The measured run-to-run noise floor is ~2.4 points at 1,200 games per arm.** One candidate
(`chal_dp_base3`), three separate runs, scored 0.5042, 0.5125 and 0.5279 with nothing changed.
Differences smaller than that are not evidence, and this campaign's most instructive result is a
deck mutation that measured +7.25 points at 400 games and −0.12 at 1,200.
