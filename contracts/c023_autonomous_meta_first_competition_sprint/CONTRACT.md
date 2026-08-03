# c023 — Autonomous Meta-First Competition Sprint

## Mission

Operate autonomously until **Wednesday, August 5, 2026 at 20:00 Europe/Rome**.

Primary objective: maximize the probability of producing a materially stronger, legal, stable, packaged competition submission.

This is a competition campaign, not a general research campaign.

If no challenger succeeds, close honestly with:

- the strongest retained champion;
- the strongest failed challenger;
- evidence explaining the failure;
- the highest-value next action.

Do not manufacture a PASS because substantial work was completed.

## Operating authority

Work autonomously for the duration of the campaign. Do not stop after planning, wait for user feedback, or ask the user to choose branches.

You may:

- kill weak branches;
- replace initial candidates;
- merge branches;
- redirect compute and engineering effort;
- abandon ByteRL integration when it provides no measurable value;
- pursue a newly discovered approach when evidence suggests a higher expected competitive return.

The named approaches are hypotheses, not obligations.

### Non-negotiable constraints

Do not relax:

- the hard deadline;
- legality;
- reproducibility;
- evidence integrity;
- exact source capture;
- immutable champion preservation;
- honest status reporting;
- paired evaluation where technically possible.

## Hard deadline

```text
2026-08-05 20:00:00 Europe/Rome
```

Before the deadline:

- stop starting new experiments early enough to close cleanly;
- terminate or gracefully stop unfinished jobs;
- preserve partial evidence;
- regenerate reports from canonical raw data;
- validate packages;
- capture final Git and source evidence;
- create the result archive.

Do not extend the campaign because a curve is rising or a run is almost complete.

## Starting interpretation

Verify this interpretation against the repository and latest complete evidence before relying on it.

### MCGS

MCGS is currently far below the strong baseline. Multi-determinization reduced value variance but did not materially improve decisions or field results.

Default status:

```text
MCGS = archived control and research artifact
```

Do not spend substantial time repairing it unless genuinely new evidence changes its expected value.

### ByteRL

The recurrent architecture, FIFO actor–learner, state/action representation, autoregressive actions, and value head may contain reusable assets.

Full ByteRL fidelity and standalone competitiveness have not been established.

Default role:

```text
ByteRL = component source and diagnostic system
```

Potentially useful assets:

- value estimation;
- action priors;
- state representation;
- recurrent memory;
- replay disagreement analysis;
- candidate-action ranking.

Do not launch a large fresh training campaign unless it directly supports a competition hypothesis that can be evaluated before the deadline.

### Default competitive direction

```text
public/meta evidence
→ proven deck candidates
→ stateful deck-specific experts
→ deck–agent co-optimization
→ conservative learned-component admission
→ robust packaged finalists
```

Change this direction when measured evidence supports a better path.

## Establish the champion first

Before claiming improvement:

1. identify the strongest valid frozen champion;
2. locate its exact deck, agent, source, package, and score evidence;
3. reproduce its local evaluation;
4. test both seats where supported;
5. measure evaluation noise;
6. verify legality, runtime, and packaging;
7. freeze source, deck, agent, and package hashes.

Never overwrite or silently mutate the champion.

Every challenger must record:

- parent candidate;
- source commit;
- deck hash;
- agent hash;
- protocol;
- seeds;
- opponents;
- seats;
- requested/completed games;
- runtime;
- errors.

## Initial campaign structure

Begin with no more than three serious branches.

Suggested hypotheses:

### A — Meta-proven specialist

Select a strong public, official, or replay-supported deck and build a highly specialized stateful agent for it.

Archaludon/Cinderace is a candidate, not a requirement.

### B — Champion improvement

Mine the frozen champion’s losses and improve named decision classes without destroying its successful matchups.

### C — Counter-meta or complementary specialist

Select a deck with a materially different matchup profile that attacks common weaknesses of the broad-field champion.

Branches may be killed, merged, or replaced. A replacement requires a written evidence-based rationale.

Do not preserve three branches for symmetry. Concentrate resources on the strongest opportunity.

## Meta and replay intelligence

Use available public and repository evidence, including when accessible:

- public replays and game histories;
- official agents;
- public deck lists;
- competition discussions;
- local replay datasets;
- prior agents and result archives.

If internet or Kaggle access is unavailable, continue with local evidence and document the limitation.

Record external sources in `SOURCES.md`, including:

- source identifier or URL;
- retrieval date;
- extracted evidence;
- licensing or reuse considerations;
- whether code was copied, translated, or only studied.

Do not copy incompatible licensed code into submissions.

Required meta outputs:

- archetype taxonomy;
- deck-frequency evidence where available;
- matchup matrix;
- successful opening patterns;
- knockout/prize routes;
- failure taxonomy;
- candidate shortlist;
- executable opponent panel.

Meta analysis must change candidate selection, agent logic, deck construction, or evaluation weighting. Do not produce a descriptive report with no executable consequence.

## Agent design

Prefer stateful, deck-specific planning over one global action score.

A useful architecture may be:

```text
matchup classification
→ strategic route
→ game phase
→ turn objective
→ tactical action sequence
→ legal resolution
→ safe fallback
```

Relevant concepts may include:

- opening setup;
- preferred active and bench structure;
- evolution timing;
- energy allocation;
- attack-readiness timeline;
- first and second attacker preparation;
- prize mapping;
- knockout targeting;
- retreat and promotion;
- post-knockout recovery;
- resource conservation;
- deck-thinning sequence;
- ability usage;
- lethal or guaranteed-prize lines;
- matchup-specific routes.

Use the simplest design that reliably executes the deck’s real plan.

## Optimization loop

For each serious candidate:

1. evaluate on the development panel;
2. inspect raw losses;
3. assign losses to concrete failure classes;
4. select the highest-impact correctable class;
5. implement the smallest coherent correction;
6. run a quick paired screen;
7. discard regressions;
8. validate promising changes separately;
9. update deck and agent ledgers;
10. repeat.

Every material change must name the failure it addresses.

Examples:

- failed opening setup;
- wrong active selection;
- missing second attacker;
- wrong energy target;
- incorrect evolution order;
- wrong knockout target;
- missed attack;
- unnecessary retreat;
- bad promotion;
- exhausted recovery resources;
- exposed board liability;
- incorrect matchup route;
- timeout or illegal selection;
- neural override harmed a safe expert line.

Avoid blind parameter sweeps unless the parameter has a clear semantic role and the sweep can be validated before the deadline.

## Deck–agent co-optimization

Evaluate decks with their actual agents.

Prefer constrained mutations around strong seed lists:

- consistency counts;
- energy counts;
- recovery cards;
- search cards;
- evolution counts;
- secondary attackers;
- matchup technology;
- defensive or mobility cards.

For each mutation record:

- parent deck;
- changed cards/counts;
- intended failure or matchup correction;
- required agent changes;
- evaluation result;
- keep/kill decision.

Unrestricted card-space search is allowed only when evidence suggests it has higher expected value and it can finish before the deadline.

## Evaluation protocol

Adapt game counts to throughput and effect size, but remain statistically honest.

### Suggested layers

- Smoke: crashes, illegal actions, obvious strategic failure, runtime.
- Development: paired seeds and both seats, roughly 100–200 games where practical.
- Promotion: separate panel, roughly 400+ games where practical.
- Finalist: largest credible paired panel before packaging, ideally 1,000+ games when feasible.

These are guidelines, not rigid quotas.

Required measurements:

- requested/completed games;
- errors;
- wins/losses/draws;
- score and uncertainty;
- opponent breakdown;
- seat breakdown;
- runtime and decision latency;
- timeouts;
- illegal-action count;
- model inference cost where applicable;
- package size.

Maintain conceptually separate development, validation, and final holdout panels. Do not repeatedly tune against the final holdout.

Promote only on a material broad-field improvement or a strategically important matchup gain without unacceptable regressions.

Approximately +4 percentage points is a useful target, not an absolute rule. Smaller gains may be retained when precise, strategically important, or complementary.

## Kill and pivot rules

Kill or pause a branch when:

- it remains clearly below its parent after meaningful evaluation;
- two consecutive correction cycles fail;
- it wins only mirrors;
- it has a catastrophic common matchup;
- inference/search cost is excessive;
- it repeatedly causes illegal actions or timeouts;
- improvement disappears on validation;
- remaining work cannot finish before the deadline;
- another branch clearly has higher expected value.

Do not preserve a branch because substantial effort has already been spent.

You may pivot by:

- switching deck;
- changing agent design;
- reusing only working components;
- focusing on champion refinement;
- focusing on a matchup specialist;
- mining a different replay subset;
- simplifying an overengineered system;
- replacing a learned component with a deterministic rule;
- replacing a deterministic rule with a validated learned ranker;
- pursuing a newly discovered public/meta opportunity.

Record major pivots in `PIVOT_LEDGER.md` with:

- previous hypothesis;
- evidence against it;
- replacement hypothesis;
- expected value;
- cost;
- validation plan.

## ByteRL component admission

ByteRL components are optional and must earn inclusion.

Potential components:

- value head;
- policy prior;
- recurrent state;
- representation;
- autoregressive target ranking;
- replay disagreement detector.

### Value admission

Evaluate on new holdout data using grouped game-level statistics and, where possible:

- early-game states;
- mid-game states;
- late-game states;
- states generated by strong expert agents;
- unseen opponents and seeds;
- sibling successor-state ranking;
- calibration and ranking metrics.

State-outcome correlation alone is insufficient.

### Conservative integration

Start with isolated tests:

```text
A0: deterministic specialist or champion
A1: same agent + value reranking only in approved decision classes
A2: same agent + recurrent policy prior only as tie-breaker
```

The expert remains the fallback.

Do not combine neural components until one isolated component passes.

### Training

Fresh training is allowed only when:

- it supports a concrete candidate;
- known fidelity defects are corrected;
- the output can be evaluated before the deadline;
- it does not block higher-value expert-agent work.

Internal return or self-play improvement alone is not a continuation criterion.

## Unexpected opportunities

Pursue an unlisted approach when:

1. concrete evidence supports it;
2. it can produce a valid candidate before the deadline;
3. expected value exceeds current work;
4. it can be objectively evaluated;
5. the pivot is documented.

Examples:

- a much stronger public deck;
- a reproducible high-performing legal agent;
- a critical champion bug;
- a narrow dominant meta counter;
- a replay-trained classifier with a large uplift;
- a simple deterministic agent outperforming a complex branch.

Flexibility is not permission for uncontrolled architecture exploration.

## Time management

Early campaign:

- champion truth;
- opponent panel;
- meta evidence;
- candidate shortlist;
- initial failure taxonomy.

Middle campaign:

- specialist development;
- champion improvement;
- deck–agent mutation;
- paired evaluation;
- loss mining.

Late campaign:

- strongest one or two candidates;
- new holdout validation;
- timing and legality;
- packages;
- source capture;
- final decision.

Do not begin a new high-risk architecture without enough time to validate and package it.

## Submission handling

Prepare valid packages and exact upload commands.

Do not overwrite the frozen champion package.

Do not upload unless explicit autonomous-submission authorization already exists in the repository.

Without explicit authorization:

```text
prepare packages; do not upload
```

For each package record:

- source commit;
- deck;
- agent;
- configuration;
- validation result;
- matchup profile;
- runtime;
- package hash;
- recommended upload order.

## Required outputs

Canonical directory:

```text
results/c023_autonomous_meta_first_competition_sprint/
```

Required files:

- `EXECUTIVE_DECISION.md`
- `STATUS.json`
- `DECISION_BOARD.json`
- `ACCEPTANCE_CHECKLIST.md`
- `SOURCES.md`
- `META_REPORT.md`
- `MATCHUP_MATRIX.csv`
- `CANDIDATE_HISTORY.jsonl`
- `FAILURE_TAXONOMY.md`
- `PIVOT_LEDGER.md`
- `DECK_CHANGE_LEDGER.md`
- `AGENT_CHANGE_LEDGER.md`
- `BYTERL_COMPONENT_RESULTS.md`
- `LEADERBOARD_SUBMISSION_PLAN.md`
- `UNRESOLVED_RISKS.md`

Required directories:

- `raw_evaluations/`
- `candidate_manifests/`
- `final_packages/`
- `source/`
- `git/`
- `failures/`
- `superseded/`

### Executive decision questions

Answer explicitly:

1. What is the frozen champion?
2. What is the strongest challenger?
3. How much better or worse is it?
4. Which matchups drive the result?
5. Which candidate should be submitted first?
6. Is there a complementary second candidate?
7. What was killed?
8. What pivots occurred?
9. Did ByteRL provide measurable value?
10. What remains uncertain?
11. What should happen in the next 24–48 hours?
12. Was this a competitive success, research success, or failure?

Use explicit statuses:

- PASS
- PARTIAL
- FAIL
- INCONCLUSIVE
- NOT_RUN
- COMPUTE_LIMITED
- INVALID
- SUPERSEDED

Do not convert missing or invalid evidence into PASS.

## Source and evidence integrity

Capture exact final source:

- canonical Git commit or bundle;
- `git status`;
- `git diff`;
- Git log;
- full source archive;
- focused changed-source archive;
- package manifests and hashes;
- environment/dependencies;
- raw evaluation logs;
- seeds and protocols.

Regenerate summaries after final experiments.

The validator must reject:

- stale files;
- zero-game summaries;
- timestamp mismatches;
- run-ID mismatches;
- incomplete arms;
- missing hashes;
- report/raw-data disagreement.

Move invalid or superseded artifacts out of active result directories.

## Final acceptance

Competitive success requires at least one valid, stable, packaged, evidence-backed challenger that materially improves the champion or provides a clearly valuable complementary matchup profile.

Research progress alone is not competitive success.

If nothing passes:

- retain the champion;
- package no misleading challenger;
- report the failure;
- preserve reusable improvements;
- identify the next highest-value move.

Prioritize winning decisions over protecting prior work.
