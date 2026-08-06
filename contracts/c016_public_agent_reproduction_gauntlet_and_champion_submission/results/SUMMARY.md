# c016 — public-agent reproduction gauntlet and champion submission

**STATUS = PARTIAL** · operational PASS · evidence integrity PASS · competitive gate FAIL

## What c016 was for

c014 and c015 proved that packaging and submission work. They did not prove competitive strength. c016's central rule is that a rich public implementation must not be replaced by a smaller from-scratch priority table and called a reproduction — which is exactly what c014 and c015 did.

## Corrected operating truth (from raw artifacts, §9)

| branch | operational | evidence integrity | competitive strength | role |
|---|---|---|---|---|
| c014 custom Archaludon/Cinderace | PASS | PASS | WEAK | CONTROL |
| c015 custom Iono/Bellibolt | PASS | DEFECTIVE | FALSIFIED | ARCHIVE |

c015 carries **3 report-integrity defects** found by re-derivation, the most serious being a Mechanism B success rate asserted over a **zero denominator**. c016's validator implements exactly that check.

## Candidates

7 leads inventoried, 3 advanced, **3 classified EXACT**, 0 clean-room. Every advanced candidate is a byte-for-byte copy of an official sample agent — the identical hash is the anti-simplification proof.

## Result

**No candidate cleared the competitive gate.** Best candidate: `official_mega_lucario`. No package was uploaded — §2 and §18 forbid submitting a weak package merely to complete the contract.

Exact failed gates:

- base condition safe_control_ge_0.90
- base condition vs_c014_ge_0.65

## Final gauntlet (Stage B)

| candidate | vs Dragapult | vs Iono | vs Lucario | vs Abomasnow | vs c014 | vs c015 | field mean |
|---|---|---|---|---|---|---|---|
| `official_iono` | 0.29 | 0.54 | 0.22 | 0.71 | 0.9 | 0.92 | 0.49 |
| `official_mega_lucario` | 0.485 | 0.79 | 0.54 | 0.47 | 0.625 | 0.91 | 0.6 |
| `official_mega_abomasnow` | 0.5 | 0.27 | 0.51 | 0.45 | 0.69 | 0.93 | 0.41 |

Games: 360 screening + 2250 final + 2900 confirmation. Training games: **0**. Invalid 0 / exceptions 0 / timeouts 0. Worst p99 latency 1.8600570037961006 ms.

## The one next action

> fix one named defect: base condition safe_control_ge_0.90

## Known limitations

- no candidate cleared the competitive gate, so no package was uploaded. §2 and §18 explicitly forbid submitting a weak package to complete the contract.
- the public score is a live ladder rating; readings for c014 moved by more than 150 points within an hour, so no single reading establishes strength
- the competition's submission limit and file-size limit remain UNVERIFIED: the rules page is client-rendered and returns only its title to an unauthenticated fetch

