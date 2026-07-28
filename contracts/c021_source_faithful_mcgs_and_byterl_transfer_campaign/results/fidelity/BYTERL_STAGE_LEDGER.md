# ByteRL stage ledger — B0 → B1 → B1.5 → B2 → B3

The ladder is **cumulative**: each rung adds exactly one component and keeps everything below it,
so a change in strength is attributable. Running only the top rung would leave every component
unattributed.

| Rung | Adds | Network | V-trace | UPGO | OSFP | Opponent |
|---|---|---|---|---|---|---|
| B0 | — (floor) | no | no | no | no | scripted field |
| B1 | fresh random network in the loop | yes | no | no | no | scripted field |
| B1.5 | V-trace policy-gradient learning | yes | yes | no | no | scripted field |
| B2 | UPGO | yes | yes | yes | no | scripted field |
| B3 | OSFP self-play | yes | yes | yes | yes | **frozen checkpoints of itself** |

## Two arms, run separately

| Arm | Deck | Purpose |
|---|---|---|
| `fctrl_*` | frozen permitted deck | CONTROL. Isolates battle learning, so "could not learn battle play" is distinguishable from "learned battle play but could not build a deck". |
| `flearn_*` | learned construction | The `MANDATORY_IMPLEMENTATION B2` requirement: one episode is construct → validate → battle → terminal reward reaching BOTH stages. |

## Reading B3

B3's win rate is measured against **frozen checkpoints of itself**. A mirror match sits near 0.5
by construction, so B3's number is **not comparable** to the rungs that play the scripted field,
and `DECISION_RULES §4` forbids submitting a checkpoint selected only on self-play. The report
marks it `win_rate_is_self_play: true` / `comparable_to_field: false` for exactly this reason.

## Promotion

Promotion requires a win rate ≥ 0.55 over at least 48 games. Where no rung reaches it, no
promotion fires, the seeded period-0 checkpoint is played throughout, and
`osfp/promotion_history.jsonl` is empty — which is the honest record, not a missing artifact.

## Fresh weights

Every rung starts from **fresh random weights**: no distillation from a scripted teacher, no warm
start from a c0xx checkpoint. A warm start would make every learning-period comparison
meaningless. Pinned by `BYTERL_FRESH_RANDOM_WEIGHTS` in the semantic validator.
