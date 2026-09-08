# Opponent and policy overlap (AC-06)

**OPPONENT_OVERLAP = SUPPORTED**

Mean top-1 agreement across 15 policy pairs on 63 identical frozen states: **0.8433862433862435**

## Pairwise top-1 agreement

- `SOUP_622+633|S_622_g39983` — 0.921
- `SOUP_622+633|S_633_g30176` — 0.921
- `C_522_g20220|S_611_g40127` — 0.905
- `C_522_g20220|S_622_g39983` — 0.889
- `C_522_g20220|SOUP_622+633` — 0.873
- `SOUP_622+633|S_611_g40127` — 0.873
- `C_522_g20220|S_633_g30176` — 0.857
- `S_611_g40127|S_622_g39983` — 0.857
- `S_611_g40127|S_633_g30176` — 0.857
- `S_622_g39983|S_633_g30176` — 0.857
- `C_522_g20220|I0_incumbent` — 0.825
- `I0_incumbent|S_622_g39983` — 0.794
- `I0_incumbent|S_611_g40127` — 0.762
- `I0_incumbent|SOUP_622+633` — 0.730
- `I0_incumbent|S_633_g30176` — 0.730

## Gain attribution (descriptive)

- dragapult: 0.250 -> 0.379 (+0.129)
- iono: 0.458 -> 0.452 (-0.007)
- mega_abomasnow: 0.250 -> 0.298 (+0.048)
- mega_lucario: 0.458 -> 0.395 (-0.063)

Learned elites agree with one another far more than they agree with the rule teacher, so an elite-only population would narrow the state distribution. That is the risk the adaptive curriculum caps elite share at 45% to manage.
