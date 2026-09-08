# Mandatory Probe Matrix

## MCGS

| ID | Probe | Pass condition |
|---|---|---|
| M01 | Source hidden-info map | Every source save/restore/determinization function mapped |
| M02 | Repeated world generation | Same public root, legal distinct hidden worlds |
| M03 | No leakage | Policy receives no inaccessible hidden contents |
| M04 | K=1 identity | New K1 reproduces frozen c021/source-port behavior within deterministic tolerance |
| M05 | Fixed-total K sweep | K1/2/4/8 use exactly equal total simulations |
| M06 | Fixed-per-world K sweep | Each world receives identical simulations |
| M07 | Aggregation fixture | Independent calculation matches production aggregation |
| M08 | Calibration | Predicted/actual calibration improves over c021 control |
| M09 | World disagreement | Per-world action/value variance logged correctly |
| M10 | Action stability | Repeated-seed stability measured on frozen decisions |
| M11 | Source timing arm | Original-style 15/10-second schedule executes or exact blocker recorded |
| M12 | Deploy separation | Kaggle budget changes do not modify reference branch |
| M13 | Paired field panel | Candidate/control use matched seeds and identities |

## ByteRL

| ID | Probe | Pass condition |
|---|---|---|
| B01 | Architecture | LSTM hidden size 256 and shared representations verified |
| B02 | Slot identity | Active and each bench position remain distinct |
| B03 | Dynamic references | Every legal option points to correct source/target objects |
| B04 | Autoregressive legality | Every emitted complete sequence maps to one legal action |
| B05 | Joint log-probability | Sum of token log-probs matches independent reference |
| B06 | Hidden-state replay | Learner recomputation matches actor trace before update |
| B07 | Burn-in/unroll | Gradients and recurrence obey registered sequence boundaries |
| B08 | FIFO | Bounded, blocking, true FIFO, consume-once semantics |
| B09 | Production balance | Producer/consumer ratio and queue age remain controlled |
| B10 | Policy versions | Behavior version and lag recorded for every unroll |
| B11 | V-trace fixture | Exact independent numerical agreement |
| B12 | UPGO fixture | Exact independent numerical agreement |
| B13 | B3 clipping fixture | Two-sided ratio and PPO-style objective agreement |
| B14 | Stage delta | Adjacent BR stages differ only by published change |
| B15 | OSFP local reset | Payoff/count accumulators reset each period |
| B16 | Frozen history | Historical checkpoints are byte-immutable |
| B17 | Promotion | Threshold/forced-promotion behavior matches reference interpretation |
| B18 | Full card pool | E2E arm uses legal permitted pool; reduced pool labelled smoke only |
| B19 | Return propagation | Terminal outcome trains construction and battle decisions |
| B20 | Matched budget | Exact c021 sample exposure recovered and matched |
| B21 | External trajectory | Fixed milestones and confidence intervals exist |
| B22 | Plateau validator | Stop/continue decision recomputed from raw metrics |
| B23 | Value calibration | Compared with constant, heuristic, c021 and outcome baselines |
| B24 | Prior admission | Ranking, entropy, suppression and MCGS effect measured |

## Transfer/final

| ID | Probe | Pass condition |
|---|---|---|
| T01 | Parent gates | No transfer before MCGS and ByteRL fidelity gates |
| T02 | Prior-only | Only prior changes; worlds/sims/seeds identical |
| T03 | Rollout-only | Only default policy changes |
| T04 | Value-only | Runs only after value admission |
| T05 | Noise floor | Nominally identical controls estimate run-to-run noise |
| F01 | Candidate identity | Deck/model/source/package verified for every game |
| F02 | Canonical final source | Git archive/plain export/package agree |
| F03 | Report consistency | All reported numbers recompute from raw data |
| F04 | Defect injection | Validators reject c019–c021 known defects |
