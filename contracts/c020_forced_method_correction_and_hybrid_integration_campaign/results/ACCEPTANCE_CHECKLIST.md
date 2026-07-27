# c020 acceptance checklist

- [x] **AC-01 parent/branch/controls/immutability** — parent a1d322e291e5, controls frozen at a1d322e291e5
- [x] **AC-02 forced MCTS corrections A1-A8** — validated semantically
- [x] **AC-03 forced ByteRL corrections B1-B8** — validated semantically
- [x] **AC-04 mandatory hybrid H0-H4** — ['H0', 'H1', 'H2', 'H3', 'H4']
- [x] **AC-05 complete smoke and one repair pass** — F01 recorded
- [ ] **AC-06 scaled pure branches** — missed: ['live searched decisions', 'real search_step expansions', 'decisions with 4 legal determinizations', 'complete sampled tree traces', 'common-panel baseline vs corrected-MCTS games', 'conservative-override ablation games', 'actual simulator training games', 'optimizer steps', 'complete corrected OSFP learning periods', 'immutable historical additions', 'games involving historical checkpoints', 'evaluation games across milestones/panels']
- [x] **AC-07 frozen panel and ablations** — ['panelsmoke', 'ctrlcheck']
- [x] **AC-08 packages and automatic submissions** — ['c020_mcts_smoke']
- [ ] **AC-09 complete code and raw evidence** — source bundle
- [x] **AC-10 evidence validator and honest status** — 33 negative controls
