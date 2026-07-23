# c000 — Repository Audit and Baseline

> Governed by the Contract Execution Protocol. This file is the concrete c000
> contract (sections A–K). It is immutable once execution begins, except for
> files created under `results/`.

## A. Objective

Produce a concrete, evidence-backed audit of the current `ptcg_ai_battle`
repository and **reproduce the random-agent baseline** through the official
`kaggle_environments` `cabt` environment. On completion, `results/` must contain
a repository map, an environment/dependency report, catalogued entry points, a
verified minimal one-game command, baseline runtime measurements over multiple
games, and a ranked technical-risk list — ending in a definitive
`PASS` / `PARTIAL` / `BLOCKED` outcome. No source or strategy changes.

## B. Context

- Repo is a Kaggle "Pokémon TCG AI Battle" project. The engine is a compiled
  `libcg.so` loaded via `ctypes` (`starter_kit/sim.py`), wrapped by
  `starter_kit/game.py` and `starter_kit/api.py`.
- A `cg -> starter_kit` symlink at the repo root makes `from cg.api import ...`
  importable.
- `cabt` is confirmed present as a **built-in** `kaggle_environments` env;
  `test_engine.py` already drives it with a random agent.
- This is the first contract (`c000`); it has no prior contract dependencies.

## C. Inputs (read-only)

`starter_kit/` (`main.py`, `api.py`, `game.py`, `sim.py`, `utils.py`,
`deck.csv`, `libcg.so`), `test_engine.py`, `check.py`,
`pokemon-tcg-ai-battle-challenge-strategy/` (card data CSV/PDF), the `.venv/`
interpreter, the `kaggle_environments` `cabt` env, and git metadata.

## D. Scope

Create files **only** under
`contracts/c000_repository_audit_and_baseline/results/`. A throwaway measurement
helper may be written under `results/artifacts/`. No changes to project source.

## E. Non-goals

No agent/strategy improvements; no edits to `starter_kit/*`, `deck.csv`, or the
engine; no new dependencies; no deck changes; no rewriting/retraining; no
committing unrelated pre-existing untracked files (`tmp.txt`, `check.py`, `cg`,
strategy PDFs, `starter_kit/`).

## F. Implementation requirements

1. Repo map of all top-level entries (roles, sizes; excluding `.git`/`.venv`
   internals).
2. Environment report: OS, Python version, `pip freeze`, confirmation that
   `cabt` is registered.
3. Catalogue of entry points, deck files, engine, and existing run/test
   commands.
4. A minimal, exact command that runs **one** `cabt` game with the random agent,
   plus its captured output.
5. Baseline runtime measurement: at least 10 complete games, reporting per-game
   wall-clock and step count plus aggregate min/mean/max.
6. Ranked technical-risk list (at least 5, with severity).
7. All mandatory `results/` files from protocol §4 (`SUMMARY.md`, `STATUS.json`,
   `FILES_CHANGED.md`, `COMMANDS_RUN.md`, `ACCEPTANCE_CHECKLIST.md`,
   `GIT_REPORT.md`, `test_logs/`, `artifacts/`, `failures/`).

## G. Acceptance criteria (all mandatory, binary)

- **AC-01** — `results/artifacts/repo_map.md` lists every top-level entry with
  its role.
  Verification: inspect file. Evidence: `artifacts/repo_map.md`.
- **AC-02** — Environment report records the Python version and the
  `kaggle-environments` version and confirms `cabt` is a registered env.
  Verification: `python --version`, `pip freeze`, env-list check.
  Evidence: `artifacts/environment.md`, `test_logs/pip_freeze.txt`.
- **AC-03** — `results/artifacts/entry_points.md` names the agent function, deck
  file(s), engine library, and run/test harness with exact paths.
  Verification: inspect file. Evidence: `artifacts/entry_points.md`.
- **AC-04** — A documented minimal command runs **one** `cabt` game to
  completion (both players receive a terminal status; no exception).
  Verification: run the command. Evidence: `artifacts/RUN_ONE_GAME.md`,
  `test_logs/run_one_game.txt`.
- **AC-05** — At least 10 `cabt` games complete without exception; a metrics
  file reports per-game time and steps plus aggregate min/mean/max.
  Verification: run measurement script. Evidence:
  `artifacts/baseline_metrics.json`, `test_logs/baseline_run.txt`.
- **AC-06** — `results/artifacts/risks.md` lists at least 5 technical risks
  ranked by severity.
  Verification: inspect file. Evidence: `artifacts/risks.md`.
- **AC-07** — `STATUS.json` is present and valid, with a definitive
  `PASS`/`PARTIAL`/`BLOCKED` and matching criteria counts.
  Verification: parse JSON. Evidence: `results/STATUS.json`.

**Outcome mapping:** `PASS` = AC-04 and AC-05 reproduce the baseline and all
acceptance criteria pass. `PARTIAL` = repo mapped but a missing dependency
blocks AC-04/AC-05 (exact blocker captured in `failures/`). `BLOCKED` = repo
cannot be safely inspected or is incomplete.

## H. Required deliverables

All files in protocol §4, plus
`artifacts/{repo_map,environment,entry_points,RUN_ONE_GAME,risks}.md`,
`artifacts/baseline_metrics.json`, and
`test_logs/{pip_freeze,run_one_game,baseline_run}.txt`.

## I. Git requirements

- Base branch `main`; create `contract/c000_repository_audit_and_baseline` from
  the current HEAD.
- This contract **explicitly requests committing the
  `contracts/c000_repository_audit_and_baseline/` folder** (CONTRACT.md +
  populated `results/`) — commit message prefix `c000:`.
- Do **not** stage or commit the other pre-existing untracked files. No
  push/force/rebase/amend.
- Record before/after `git status`, branch, and commit hashes in
  `GIT_REPORT.md`.

## J. Stop conditions

Stop and set `BLOCKED`/`PARTIAL` rather than improvise if: `libcg.so` fails to
load (ABI/arch mismatch), `cabt` cannot construct a game, the deck fails
validation, or any acceptance step would require modifying project source.
Capture the exact error in `failures/`.

## K. Final response format

Return: the outcome (`PASS`/`PARTIAL`/`BLOCKED`), a one-line per-AC pass/fail
table, baseline metrics (min/mean/max seconds, mean steps), the minimal one-game
command, the top 3 risks, the commit hash(es), and the recommended next
contract.
