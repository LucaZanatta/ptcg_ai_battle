# DEFECT — the mandatory end-turn veto never fired, and four leaf features were always zero

**Found:** by auditing runtime feature distributions after the B2 inertness finding — asking of
every mechanism "does it actually take a nonzero value in production?" rather than "is it
implemented?"

**Severity: material.** This is the correction aimed most directly at `C019_AUDIT_FINDINGS` #4,
and it was inert.

## The measurement that exposed it

Across **36,000 logged leaf samples** from the post-repair scaled run:

| feature | nonzero |
|---|---|
| `productive_attack` | **0.0%** |
| `unproductive_end_turn` | **0.0%** |
| `critical_resource_cost` | **0.0%** |
| `lethal` | **0.0%** |
| `terminal` | 0.0% (expected — a depth-16 search rarely reaches a terminal) |
| `survival` | 99.7% |
| `typed_energy_ready` | 97.6% |
| `backup_ready` | 89.3% |

## Cause

Both `_annotate_line` and `looks_like_end_turn` identified actions by **substring-matching words
against `str(action_key)`**:

```python
if any(h in str(action_key).lower() for h in ("end", "endturn", "pass", "finish")):
```

The canonical key is `(select_type, select_context, option_type, fields, card_id, attack_id)` — a
tuple of integers — and `CanonicalOption` carries no name, text or label. The match could never
succeed. `looks_like_end_turn` returned `False` for **every action ever passed to it**.

Two consequences:

1. `line.attacked` and `line.ended_turn` were never set, so `productive_attack` and
   `unproductive_end_turn` were permanently zero. Those are the two features `MANDATORY_CHANGES
   A6` adds specifically so the evaluator can tell "ended the turn having attacked" from "ended
   the turn having done nothing" — the distinction a prize/HP objective cannot express and the
   one audit #4 is about.
2. **The mandatory A8 end-turn veto never fired.** `decide_override` consulted
   `looks_like_end_turn`, which always said no.

## This explains a result I had already reported

The M09 ablation measured `overrides on, veto ON` at 0.3038 against `veto OFF` at 0.3217 and I
reported the veto as "recovering almost none of it". That reading was wrong in an important way:
the two arms were not veto-on versus veto-off, they were **veto-inert versus veto-disabled** —
the same configuration twice. The ~0.018 gap between them is noise between two runs of one thing.

The honest statement is that the ablation did not measure the veto at all. It must be re-run.

## Fix

Detection is now structural, from the engine's `OptionType` — `END = 14`, `ATTACK = 13`, and a
productive set `{PLAY, ATTACH, EVOLVE, ABILITY, RETREAT, ATTACK}` — read from the canonical key's
third element, which *is* `option_type`. `is_productive` replaces "not-looking-like-end-turn" in
the agent's `baseline_productive` context. `critical_resource_cost` is incremented on
PLAY/EVOLVE/ABILITY.

## The tests were validating the bug

`test_end_turn_over_productive_play_is_vetoed` passed throughout, because it used the string key
`"END_TURN"` — which contains "end" and therefore exercised the substring path. The test was
green against a format the engine never produces.

That is the same failure as the c019 promotion tests the audit criticises, in my own suite: a
fixture chosen to make the mechanism look exercised rather than to reproduce production. All the
override tests now use real integer-tuple keys, and a negative-control test asserts explicitly
that no end-turn hint word appears anywhere in `str(key)` — so the old approach cannot be
reintroduced and pass.

56 tests pass.

## Scope

MCTS only. The corrected ByteRL branch does not use `LineContext` or the override gate. The
ByteRL retrain in flight is unaffected by this defect.
