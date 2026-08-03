# Defects found and fixed during c023

Five. Two would have destroyed the campaign's evidence, two would have quietly biased it, and one
was a live bug in a third-party agent that this harness had to route around. Each is recorded
with how it presented, because the presentation is the part that generalises.

---

## D1 — `multiprocessing.Pool` hangs forever when the engine aborts a worker

**How it presented.** The first real evaluation run stalled with every worker at 0% CPU and the
parent blocked on a pipe read. No exception, no error count, no output — a run that looked like
it was working and would have hung until the deadline.

**Root cause.** Several public agents call the engine's `search_begin` API without releasing every
handle. `libcg.so`'s handle buffer has **capacity 7**, and the eighth allocation throws an
*uncaught C++ exception*: `terminate called after throwing an instance of 'std::runtime_error' —
what(): buffer full. capacity:7`. `std::terminate` fires, the worker dies by SIGABRT, and
`imap_unordered` waits forever for a result that will never arrive.

**Fix.** The harness forks **one child per game**. An engine abort becomes a recorded outcome —
`engine_process_deaths`, reported per arm — instead of a deadlock, and every game additionally
gets genuinely fresh engine and agent state. The parent pre-imports the heavy modules so a fork
costs milliseconds where a spawn would cost ~3 s.

**Observed since.** Zero process deaths across the campaign's ~40,000 games.

---

## D2 — a `sys.path` restore made a strong opponent play its mindless fallback

**How it presented.** `pub_tetsutani_grimmsnarl` — the highest-voted public kernel, and the agent
that would become the campaign's most important opponent — scored **1 of 6** against the Dragapult
sample with a p99 decision latency of 3 ms. It read as a weak agent.

**Root cause.** The player loader restored `sys.path` after importing the agent's `main.py`.
tetsutani's entry point imports its policy **lazily, at the first real decision** — long after the
loader returns — so that import failed, its own `except Exception` caught it, and it played
`_fallback_action` (the first k legal option indices) for the entire game.

**Fix.** The agent's directory stays on `sys.path` for the life of the process (one game). And an
integrity probe was added to the harness rather than a comment: every decision is compared against
the mindless legal fallback, and `trivial_fallback_rate` is reported per arm. A broken agent now
reads as broken.

**After the fix**, the same agent went **8 of 8** with a p99 of 298 ms, and ended the campaign as
the panel leader on the ladder-weighted score.

**Why it matters beyond this bug.** The failure mode is silent by construction: a fallback that
returns legal actions cannot be distinguished from a weak policy by any outcome-based check. The
detector has to compare against the fallback itself.

---

## D3 — a 400-game screen produced a +7.25-point winner that did not exist

**How it presented.** `dpdeck_d01_rarecandy3_helmet0` scored 0.5575 against a 0.4850 control on
400 games, with a clean mechanistic story (Rare Candy is the only turn-two Dragapult ex enabler,
scored 40000 by the agent; Lucky Helmet is a singleton scored 15).

**Root cause.** Screen noise mined across thirteen arms. Two *identical* policies measured 0.4850
and 0.5166 on the same panel in two runs — a 3.2-point floor — and at 400 games the largest of
thirteen arms is expected 5–6 points above the control under the null.

**Fix.** The confirmation stage was run as registered: 1,200 games each. d01 went to **−0.12**.
The promotion rule in `PANEL_SPLIT.json` (screen ≥400, confirm ≥1,000, validate on a disjoint
panel) was written before any of this and is what caught it.

**Not a bug in code.** A bug in inference, which is the kind this repository has shipped before.

---

## D4 — enabled rules iterated in `PYTHONHASHSEED` order

**How it presented.** It did not — it was caught by reading, before any multi-rule candidate ran.

**Root cause.** `RULES_ON` was a `set`. Two rules that can fire on the same decision would have
resolved in an order that varies between processes, making a candidate a *distribution over
policies* rather than one policy — and making its games non-comparable with each other.

**Fix.** `sorted(...)`. Recorded because the same defect is invisible in any single run and only
appears as unexplained variance.

---

## D5 — the determinization hid the same cards in the prizes every time

**How it presented.** It did not; found while reviewing the planner before its decisive run.

**Root cause.** The planner reconstructs our unseen cards exactly (deck list minus everything
visible) and then splits them between deck and prizes. The pool was built with
`sorted(remain.items())` and the first *k* went to the prizes — so across every decision of every
game, the **same** cards were always the hidden ones. That is a systematic bias, not a sample: the
planner would consistently believe particular cards were unavailable.

**Fix.** The pool is rotated by a per-decision counter, so the prize assignment varies across
decisions while staying deterministic within a process.

---

---

## D6 — a third lazy-initialisation defect, and a mid-campaign harness change

**How it presented.** Adding `pub_prvsiyan_crustle_wall` to the panel — the Crustle Wall agent our
own ladder replays identified as the champion's worst real matchup — failed immediately with
`FileNotFoundError: /kaggle_simulations/agent/deck.csv`.

**Root cause.** That agent reads its `deck.csv` **on first call**, not at import. The loader
chdir'd into the agent's directory for the import and restored the working directory before the
deck handshake, so the relative `open("deck.csv")` fell through to the Kaggle production path,
which does not exist here. Structurally identical to D2: work deferred past the point where the
loader had set things up.

**Fix.** The working directory is now set to the agent's own package **for the duration of every
call**, including the deck handshake, and restored afterwards. Two agents share a process, so the
cwd cannot simply be left set.

**Why this does not invalidate earlier evaluations — and why that claim needs stating.** This is a
harness change made partway through the campaign, and `MATCHUP_MATRIX.csv` merges runs from both
sides of it. It is sound because:

1. **No other player reads a file at call time.** The four official samples and the five other
   public agents all read `deck.csv` at import, when the loader already had the cwd set. For them
   the change is a no-op.
2. **It was verified, not assumed.** `tools/c023_identity.py` was re-run after the change:
   `chal_dp_base4` remains action-identical to `official_dragapult`, 0 mismatches over 456
   decisions.
3. **The change can only make a previously-broken agent work**, never change a working one's
   choices: `os.chdir` has no effect on an agent that touches no relative path during a call.

The alternative — re-running 40,000 games to eliminate a difference that provably does not exist —
would have cost the campaign's remaining Crustle work for nothing.

## Non-defect: a third-party agent's engine crash is not ours

The `buffer full. capacity:7` abort originates in public agents that leak search handles. c023's
own `planner.py` releases every handle it creates on every path including exceptions, and
`engine_process_deaths` is reported per arm precisely so that claim is monitored rather than
asserted. Observed: zero.
