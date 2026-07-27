# Decision, promotion, submission, and kill rules

## Branch independence

- MCTS may finish, package, and submit while ByteRL is still training.
- ByteRL may finish, package, and submit even if MCTS fails.
- A branch may not consume the other branch’s data during its primary c019 evaluation.
- Hybrid smoke data is isolated and labeled `HYBRID_DIAGNOSTIC`.

## Base/deck freeze

Both pure methods should use the same frozen deck for a clean method comparison.

Default: exact official Mega Lucario deck and baseline package already present.

During the first two hours only, a different deck may replace it when all are true:

- already executable in the repository;
- reuse/submission permission is clear;
- extracted package already passes;
- external or robust local evidence is materially stronger;
- no new deck-agent implementation is required.

Record the choice before method results exist. After freeze, c019 does not change deck lists.

## MCTS credibility

MCTS is eligible for submission only when:

- method-fidelity validator passes;
- no hidden-information leakage;
- zero illegal actions/crashes/timeouts in package validation;
- branch-local baseline parity is established when search budget is zero;
- random-override collapse is not reproduced;
- common-panel field score is at least baseline +3 percentage points, or an important matchup is +5 points without more than 2-point field regression;
- cumulative match latency is safe with margin.

## ByteRL credibility

ByteRL is eligible for submission only when:

- method-fidelity validator passes;
- the primary checkpoint is produced by actual V-trace/UPGO actor-learner updates and OSFP;
- legal rate is 100%;
- recurrent/package inference is stable;
- final checkpoint beats the initial/random policy and at least two historical checkpoints materially;
- common-panel field score is at least baseline +2 points, or direct score versus baseline is at least 55% without broad-field collapse.

Do not upload a policy only because training loss decreased.

## Hybrid

Hybrid work is capped at 15% of engineering/compute time.

Test in this order only:

1. ByteRL priors + heuristic MCTS value.
2. Baseline priors + ByteRL value, only if value calibration beats constant and heuristic on held-out leaves.
3. Priors + value, only if 1 or 2 helps.

No hybrid promotion unless it beats the stronger pure parent by approximately 3 field points, materially improves a key matchup without field regression, or preserves strength with major latency reduction.

No second hybrid contract unless a c019 hybrid version externally beats both pure parent submissions.

## Final role assignment

- `CHAMPION`: strongest externally confirmed package.
- `CHALLENGER`: credible different method/package with complementary evidence.
- `DIAGNOSTIC`: method-faithful but not competitively strong.
- `ARCHIVE`: invalid, tainted, or clearly weak candidate.

A package existing does not make it a challenger.
