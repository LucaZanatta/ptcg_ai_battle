# Distillation Evaluation Protocol

## Core principle

The student must be judged as a game-playing policy, not merely as a classifier.

## Evaluation order

```text
offline imitation
→ reliability smoke
→ student–teacher head-to-head
→ strategic gauntlet
→ package validation
→ submit/do-not-submit
```

## Controls

- Frozen Dragapult teacher
- Same frozen Dragapult deck
- Official Lucario, Abomasnow, and Iono opponents
- Deterministic engineering control reported separately

## Non-inferiority

Use a one-sided 95% confidence lower bound on student score versus teacher.

```text
win = 1
draw = 0.5
loss = 0
margin = 0.05
pass threshold = lower bound >= 0.45
```

## No test leakage

The c005 test split is opened once after checkpoint selection.
