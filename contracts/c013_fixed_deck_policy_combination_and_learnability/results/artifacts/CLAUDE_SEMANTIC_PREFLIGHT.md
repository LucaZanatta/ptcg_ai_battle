# AC-13 — Claude Opus semantic preflight

**CLAUDE_SEMANTIC_PREFLIGHT = PARTIAL**

This is a semantic-understanding preflight, not teacher qualification. No teacher-superiority claim is made and no policy was trained on these labels.

## What Claude was shown

c012's Claude test handed the model bare option indices `a0..aN`, which measured formatting rather than understanding. Here each state carries real card names and card text decoded from the engine's own card database, typed legal actions, and decoded state features. Options that genuinely have no card attached in the visible encoding are labelled as positional or numeric choices rather than left as undecoded indices — an honest 'no card here' instead of a decode that looks broken.

## Measured

| metric | value | §29 requirement |
|---|---|---|
| primary labels | 28 | 20–30 |
| schema valid (strict) | 0.821 | — |
| schema valid (after delimiter repair) | 1.000 | 100% |
| delimiter repair rate | 0.179 | — |
| legal-action rate | 1.000 | 100% |
| hidden-information violations | 0 | 0 |
| semantically grounded rationales | 1.000 | — |
| model verified as Opus | 1.000 | required |
| repeat top-1 consistency | 0.900 | ≥ 0.80 |
| decision categories | 7 | ≥ 8 |

## Schema repair, reported rather than hidden

Claude occasionally emitted a complete label whose final `}` was missing. The strict parser scored those as unparseable, which understates a fully-formed answer; silently patching them would overstate schema compliance. Both rates are therefore published, the repair appends only missing closing delimiters and cannot synthesise field content, and the raw evidence on disk is never rewritten.

## Why this is not a PASS

- only 6 of §27's 10 named decision categories demonstrated (attachment, evolution, multi-select, promotion, search, target selection), §29 requires >= 8; 1 residual bucket(s) ['other'] are not §27 categories and are not counted

The category shortfall is a limitation of **my benchmark construction**, not of the model. The sampler stratified states by dominant option type, which yields attachment, search, evolution, target, promotion and multi-select but never draws `attack`, `setup`, or the two matchup-failure categories §27 names. Correcting it needs a sampler that stratifies by game phase and by opponent, and a fresh labelling run: §25 caps the preflight at 30 primary states and 28 are already spent, so it cannot be repaired by adding states to this run.

## Model identity

Every call resolved `claude-opus-5` with non-zero Opus output tokens. A `claude-haiku-4-5` entry also appears in `modelUsage`; that is Claude Code's own background model and is explicitly **not** accepted as the labeller — the verification requires Opus tokens specifically.

