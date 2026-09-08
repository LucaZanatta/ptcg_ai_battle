# Defect: stale checkpoint-hash cache silently emptied every in-run evaluation after game 0

**Impact: the P1 adaptive curriculum never advanced past stage 0, and early stopping never
had data. This is disclosed as a limitation of the c012 curriculum result, not worked around.**

## Symptom

Every P1 seed finished with `final_curriculum_stage = 0` and `curriculum_changes = 0`. The
in-run evaluation records show why:

```text
pt=     0  t=0.30  f=0.40  iono=0.45  abom=0.35
pt=  5000  t=None  f=None  iono=None  abom=None
pt= 10000  t=None  f=None  iono=None  abom=None
pt= 15000  t=None  f=None  iono=None  abom=None
pt= 20000  t=None  f=None  iono=None  abom=None
pt= 25000  t=None  f=None  iono=None  abom=None
```

Only the game-zero evaluation produced scores.

## Root cause, verified rather than assumed

`cg.c009_eval.sha256_file` memoises by **path**:

```python
_SHA_CACHE: Dict[str, str] = {}
def sha256_file(path):
    if path in _SHA_CACHE:
        return _SHA_CACHE[path]
    ...
```

The trainer exports the live policy to a single path, `cur.npz`, and rewrites it every
update. In-run evaluation jobs pointed at that path. Pool workers persist across
`pool.map` calls, so from the second evaluation onward each worker returned the hash it had
cached the first time. `run_job` then compared that stale value against the job's real
`checkpoint_sha256`, recorded `checkpoint_hash_mismatch`, and returned `score = None`.

Reproduced directly:

```text
first  : 9f0f90cd15ac43f7
second : 9f0f90cd15ac43f7 (cached)
actual : fcc8d076533b4d38
CACHE RETURNS STALE HASH: True
```

The identity protocol behaved **correctly** — it detected that the bytes a worker hashed did
not match the bytes the job declared, and refused to score the game. The defect is that the
trainer handed it an unstable path, not that the check misfired.

## Consequences, stated plainly

1. **The adaptive escalation was never exercised.** All three P1 seeds ran the stage-0
   mixture (15% elite) for their entire 30,000-game budget. The 15% → 25% → 35% → 45%
   schedule and the §24 advance gates are therefore **untested by this run**.
2. **Early stopping could not fire.** §9's rules were implemented and wired, but received no
   evaluation scores after game 0, so no branch could stop early. Every seed ran to budget.
3. **P0 vs P1 remains a valid controlled comparison** of a different question than intended:
   *unchanged population* versus *fixed 15% elite self-play*, both from the same frozen
   incumbent with identical PPO, seeds, and budgets. That comparison is reported.

## Why it was not re-run

Phase 2 consumed 181,184 completed games against §48's hard maximum of 184,000. Re-running
the three P1 seeds would cost a further ~90,000 and breach that ceiling, which §56 makes a
`PARTIAL` condition in its own right. Exceeding a registered compute ceiling to rescue a
result is not a trade this contract permits, so the limitation is carried into the reported
conclusion instead.

## Fix

Each in-run evaluation now copies the live policy to an immutable, content-addressed path
before submitting jobs:

```python
eval_ckpt = os.path.join(os.path.dirname(cur_ckpt), f"inrun_{cur_sha[:12]}.npz")
if not os.path.exists(eval_ckpt):
    shutil.copyfile(cur_ckpt, eval_ckpt)
```

The path now varies with the content, so the per-path cache can never return a stale hash.
`cg/c009_eval.py` is **not** modified — it belongs to c009 and its behaviour was correct.

## How this should have been caught earlier

The trainer smoke test ran 848 games and produced exactly one evaluation (game zero), which
succeeded. A smoke long enough to reach a second evaluation point would have exposed it
immediately. Any future in-run-evaluation change should be smoked across **at least two**
evaluation points, and the trainer should treat an evaluation that returns zero scored games
as a hard error rather than as a `None` result that silently disables the gates.
