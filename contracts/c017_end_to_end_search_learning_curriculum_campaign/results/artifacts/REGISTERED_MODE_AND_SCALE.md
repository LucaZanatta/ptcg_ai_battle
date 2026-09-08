# Registered decisions — search mode and campaign scale

Both are recorded **before** any search, trajectory, or training code was written, so neither is
a post-hoc rationalisation of what happened to work.

## 1. `OFFLINE_TEACHER_MODE` — registered, with the deciding fact

§11 offers online search or `OFFLINE_TEACHER_MODE`. **c017 runs in `OFFLINE_TEACHER_MODE`.**

The deciding fact is not a preference, it is a measured gap:

- the local `cabt` environment reports `actTimeout = 0`, which means the local build enforces
  **no** per-decision limit and therefore tells us nothing about the competition's;
- c014 established that the competition's published per-decision limit is **not obtainable** —
  the Kaggle rules page is client-rendered and an unauthenticated fetch returns only its title.
  That gap is recorded as `UNVERIFIED` in c014's and c016's fact sheets and has not closed.

§7.3 lists "crashes, corruption, or unacceptable timeout risk" as submission blocker #3.
Submitting an agent that runs a beam search on every decision, against a limit nobody has
verified, is precisely that risk. Offline mode removes it structurally:

- search runs **locally** and only to generate labels;
- the **submitted** artifact is the distilled policy, whose per-decision latency is measured
  directly and gated at p99 ≤ 250 ms.

Consequence, accepted openly: the "policy/value-guided search" candidate collapses to the
**learned-policy fallback** the contract explicitly permits (§1, §28). c017 will not submit an
online-search agent. If a verified per-decision limit becomes available later, that decision
should be revisited — it is a limitation of the available evidence, not of the method.

## 2. Scale — reduced from the contract's caps, with the reason

§6 sets a 72-hour envelope with two overnight runs and caps of 150,000 curriculum games and
25,000 search-teacher games. **That envelope is not available to this execution**, which is a
single continuous session that has already run c014, c015 and c016 end to end.

§6 also says: *"Do not extend the campaign merely because a block is 'close.' Preserve the best
trustworthy stage and finish."* §3.10 says to submit the strongest trustworthy stage even when a
later stage is weaker or tainted. Those two instructions decide the trade:

| block | contract cap | c017 actual target | ratio |
|---|---|---|---|
| search-teacher games | 25,000 | ~300 | ~1% |
| trajectory decisions | 150,000 | ~8,000 | ~5% |
| curriculum games | 150,000 | ~6,000 | ~4% |
| final panel | — | ~600 | — |

**A completed vertical run at reduced scale with honest evidence satisfies §2 and §46. A
half-finished run at full scale satisfies neither.** The reduction is therefore deliberate and is
reported as a stated deviation in `SUMMARY.md` and `STATUS.json`, not buried.

What this costs, stated plainly: any curriculum or distillation result at this scale is
**underpowered**. Promotion claims from it are marked `DIAGNOSTIC` unless they clear the
registered thresholds on the common final panel, and no stage will be submitted on the strength
of a training curve.

## 3. Three curriculum traps, pre-empted rather than rediscovered

The contract names these because earlier contracts in this project hit them:

1. **"Never compare a policy with itself at game zero."** c012's in-run evaluation compared the
   incumbent against itself at game 0 and the result was read as a promotion signal. Every c017
   advance gate compares against the **frozen baseline**; a game-zero evaluation is recorded as a
   reference point and is structurally barred from promoting anything.
2. **"Never trust stale checkpoint cache."** This is c012's defect exactly: `sha256_file`
   memoised by path, a trainer rewriting one `cur.npz`, and persistent workers returning a stale
   hash so every in-run evaluation scored nothing. c013 fixed it with content-addressed
   evaluation paths. c017 uses that pattern **from the first curriculum run**, not after a smoke
   rediscovers it.
3. **"Planned mix reported as actual."** It is easy to log the schedule (10% / 30% / 50%) instead
   of the opponent draw that actually happened. c017 records **both** per rollout, and the
   validator compares them.
