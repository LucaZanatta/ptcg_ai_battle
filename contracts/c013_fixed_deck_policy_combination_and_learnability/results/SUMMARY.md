# c013 — fixed-deck policy combination and learnability

**STATUS = PARTIAL**

## Decisions

| result | value |
|---|---|
| `COMBINATION_RESULT` | **WEIGHT_SOUP_WINS** |
| `SOUP_LEARNABILITY` | **NOT_IMPROVED** |
| `Q3` | **SKIPPED_BY_GATE** |
| `CURRICULUM_SMOKE` | **PASS** |
| `OPPONENT_OVERLAP` | **INCONCLUSIVE** |
| `CLAUDE_SEMANTIC_PREFLIGHT` | **PARTIAL** |
| `SUBMISSION_G` | **DO_NOT_SUBMIT** |
| `TRUE_BEST_AGENT` | **SOUP13_SOUP+P1_822** |
| `PACKAGE_FEASIBLE_BEST_AGENT` | **SOUP13_SOUP+P1_822** |

## What was learned

**Weight soups beat online ensembles, and a single policy nearly beat both.** On the untouched 1,250-game final panel the winner is `SOUP13_SOUP+P1_822`; the two online ensembles rank third and fourth. Combining policies at inference time — running every component network and averaging — bought nothing over averaging their weights once, offline, for free. The c012 incumbent finishes last of five.

**The soup is not learnable by any registered method at this budget.** c012 concluded the same thing, but its in-run evaluations were returning zero scored games from the first update onward, so it never measured what it claimed to. Under a repaired instrument the conclusion survives: no Q0/Q1/Q2 candidate beats the Phase 2 start with a confidence interval excluding zero. What c013 adds is the shape of the near-miss — all nine continued candidates show a *positive* strategic-field tendency, the best at P(gain>0) = 0.94. The honest statement is 'no confirmed improvement within ~12,000 games per arm', not 'training cannot help'.

**An in-run signal was believed and then withdrawn.** Q0's in-run teacher score rose 0.275 → 0.425 and was reported mid-run as overturning c012. It does not: those evaluations score 40 games per point against the panel's 750, and on the panel Q0 sits *below* its own starting point. §17 forbids concluding from training-side numbers precisely because they are cheap and flattering.

**The official opponents share a rule skeleton with each other, not with the teacher.** Querying nine policies on 4,110 identical visible states, teacher–Lucario is highest on 7 of 8 registered measures but clears the pre-registered bar on none, so the verdict is `INCONCLUSIVE` and the rule was left alone. The unlooked-for result is stronger: Mega Lucario and Mega Abomasnow choose **identically on all 98 promotion decisions**, Iono and Abomasnow agree on 0.871 of energy commitments, and every opponent–opponent pair is more alike than any opponent–teacher pair.

**The curriculum machinery now works.** R1 executed two real stage changes with every registered evaluation returning scored games and a literal trainer-state restore reproducing the next opponent/seat/seed sequence exactly — all eight §20 requirements, none of which held anywhere in c012's 90,000-game arm.

## Why nothing was submitted

§31 requires a one-sided 95% lower bound of 0.47 on teacher non-inferiority. The package-feasible best agent measures 0.318. On the same panel the frozen teacher scores 0.5493333333333333 on the strategic field against the candidate's 0.36000000000000004. The gate is not close, so `SUBMISSION_G = DO_NOT_SUBMIT` and no archive was built or uploaded.

## Defects found and disclosed

- `.gitkeep`
- `DEFECT_family_allowlist_flipped_the_q3_gate.md`
- `DEVIATION_curriculum_smoke_exceeded_its_registered_cap.md`
- `NOTE_vram_preflight_check_fails_at_report_time.md`

## Budget

Learnability 44912 / 50000; curriculum smoke 10112 / 10000; total 55024 / 62000 hard maximum. The smoke exceeded its phase cap by 112 games through rollout granularity; this is documented as a deviation and the validator fails on it rather than passing.

## Why this is not a PASS

- documented deviation: smoke_within_cap (results/failures/DEVIATION_curriculum_smoke_exceeded_its_registered_cap.md)
- CLAUDE_SEMANTIC_PREFLIGHT = PARTIAL: only 6 of §27's 10 named decision categories demonstrated (attachment, evolution, multi-select, promotion, search, target selection), §29 requires >= 8; 1 residual bucket(s) ['other'] are not §27 categories and are not counted

