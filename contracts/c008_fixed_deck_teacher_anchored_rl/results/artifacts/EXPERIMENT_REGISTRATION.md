# c008 Experiment Registration (frozen before training)

Teacher `dragapult` | deck `sha256:8055443275c86105b38198992c9556a642b833a47430aa97fb1a84c9ee4fdbab` | ref 54948560
chain c005 4137d983c6a0 -> c006 08ebac883854 -> c007 1f3fc63aaa36 -> c008 init 1f3fc63aaa36

## Policy
- cg.rl_policy (c007 V2-A trunk + value head + STOP logit): 562,819 params (pure numpy)

## Arms & budgets (maxima; early-stops bound compute; screening != training budget)
- R0 random init, seeds [101, 202], <= 10,000 games, lr 0.0003
- R1 V2-A init, seeds [101, 202], <= 30,000 games, lr 0.0001
- R2 V2-A init + decaying teacher replay + reference KL, seeds [101, 202, 303], <= 50,000 games, lr 0.0001 (primary hypothesis)
- total max 230,000 games

## PPO
- gamma 0.997 lambda 0.95 clip 0.2 vf 0.5 ent 0.01->0.002 epochs 4 rollout collect until >=128 games AND >=8192 trainable decisions minibatch 512 AdamW wd 1e-05
- reward {'win': 1, 'draw': 0, 'loss': -1, 'intermediate': 0, 'shaping': 'none (§9.6)'}; consecutive trainable steps treated as adjacent for gamma-discounting (forced steps carry no decision value)

## R2 anchors
- teacher replay: 0-20%:0.50; 20-50%:0.50->0.15; 50-80%:0.15->0.05; 80-100%:0.05 (train split only)
- reference KL: 0-20%:0.05; 20-60%:0.05->0.01; 60-100%:0.01
- on-policy teacher action: DISABLED — synchronized instrumented-teacher shadow after divergent RL actions is not proven; R2 uses offline replay + reference KL only (§10.3)

## Opponent population
- {'teacher_dragapult': 0.35, 'mega_lucario': 0.2, 'iono': 0.2, 'lagged_selfplay': 0.15, 'control': 0.1} (before lagged: 15% redistributed proportionally across teacher/lucario/iono (-> 0.42/0.24/0.24, control 0.10)); seats 50% seat0 / 50% seat1
- held-out: Mega Abomasnow — excluded from training, used only in final test eval after checkpoint selection; never influences selection

## Screening
- 1000, 2500, 5000, then every 5000; 20 games/seat/strategic-opponent (teacher,lucario,iono) + 10 games/seat vs control = 140 games
- checkpoint selection: 0.40*teacher + 0.25*lucario + 0.25*iono + 0.10*control

## Early-stop
- R0: control<0.60 at 2500; teacher<0.15 AND lucario<0.25 AND iono<0.25 at 5000; no blend improvement >2pp over two consecutive evals
- R1/R2: teacher<0.20 AND strategic<0.30 at 10000; teacher<0.35 AND strategic<0.40 at 20000; after 20000: no blend improvement >1.5pp over three consecutive evals

## Final gates
- non-inferiority: teacher one-sided 95% LB >= 0.47
- major regression: candidate point <= teacher point - 0.07 AND bootstrap P(regression) >= 90% (blocks submission)
- reproducible improvement: global field > teacher with 90% interval > 0, OR one matchup >=+5pp @ >=90% with non-inferiority pass and no major regression
- submission: SUBMISSION_D=SUBMIT iff BEST_RL_ARM!=NONE AND non-inferiority passes AND reproducible improvement exists AND no major regression AND reliability passes AND package/size/runtime pass. Never submit for rising training reward / beating another RL arm / offline agreement / a lucky seed.

_one complete restart only for a documented implementation defect affecting all comparable runs_
