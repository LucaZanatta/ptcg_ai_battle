# c005 Policy-Improvement Hypothesis

## Target
The **unchanged c004 primary baseline** `det_starter` (deterministic
first-`maxCount` policy + starter deck `sha256:7e7bca6783…`, agent `c004.1`).

## Observed, captured failure pattern
`det_starter` uses a purely positional policy: in every decision it selects the
first `maxCount` options in engine order, never evaluating them. In the **MAIN**
context the engine offers action options of several `OptionType`s
(PLAY, ATTACH, EVOLVE, ABILITY, RETREAT, **ATTACK**, END, …). Because the policy
always takes option 0, it repeatedly **declines a legally-available ATTACK**.

From the captured gauntlet (`gauntlet_games.jsonl.gz`), for `det_starter`:
- **5,774** MAIN decisions;
- in **3,122** of them (54%) a legal `ATTACK` option was present in
  `observation.select.option` but was **not** chosen — the agent instead took the
  first option (typically `ATTACH` or `PLAY`).

Concrete examples (`tactical_failure_examples.jsonl`, 200 recorded, 3,122 total ≫ 5):
- options `[ATTACH, ATTACH, PLAY, ATTACH, ATTACH, ATTACK, END]` → chose index 0
  (`ATTACH`), declining the `ATTACK` at index 5;
- options `[PLAY, ATTACK, END]` → chose index 0 (`PLAY`), declining the `ATTACK`
  at index 1.

Passing up damage/knockouts turn after turn is the single most repeated tactical
defect and is a coherent, decodable decision problem (not a vague "play better").

## Hypothesis (one coherent decision problem: "when to attack in MAIN")
Adding a minimal, deck-agnostic **MAIN-action attack preference** — when the MAIN
option list contains a legal `ATTACK`, choose an `ATTACK` option (preferring the
highest-damage / knockout-securing attack, resolved via `all_attack()` damage and
the defender HP already present in the observation) instead of the positional
first option — will **raise win rate** against the frozen c004 field without
introducing reliability defects.

## Proposed intervention (for c005, NOT implemented here)
Implement a small MAIN-context scorer that: (1) detects legal `ATTACK` options;
(2) ranks them by expected damage / KO; (3) selects the best attack when the
scorer's damage exceeds a documented threshold, else defers to the current
first-option behavior. No search, no model, no deck-specific card lists, no deck
change. Everything else in the policy stays identical to `det_starter`.

## Evaluation protocol
- **Unchanged baseline:** the frozen c004 `det_starter` (this exact agent+deck).
- **Opponents:** the frozen c004 candidates — `det_starter` (self-baseline),
  `det_cabt`, `random_starter`, `random_cabt` — both seat orders, same sequential
  balanced protocol and stratified-bootstrap CIs used in c004.
- **Primary keep/reject criterion:** KEEP the modified agent only if its
  seat-balanced win rate **vs the unchanged `det_starter` baseline** has a 95%
  bootstrap CI **entirely above 0.55**, AND it introduces **zero** new reliability
  defects (0 invalid actions, 0 attributable exceptions, 0 timeouts). Otherwise
  REJECT and keep `det_starter` as the baseline.
- **Secondary check:** it must not *lose* ground (CI not below 0.45) against
  `det_cabt`, the backup.

## Non-goals for c005 (carried from c004)
No search/MCTS, no RL/imitation/models, no opponent modeling, no deck changes, no
new deck invention. The hypothesis is deliberately the smallest strategic step
beyond the positional baseline.
