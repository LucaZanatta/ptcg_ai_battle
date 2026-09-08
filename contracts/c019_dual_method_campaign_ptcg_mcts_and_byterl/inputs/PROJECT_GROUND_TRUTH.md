# Project ground truth entering c019

## Repository/Git

Expected c018 branch:

```text
contract/c018_complete_integrated_search_learning_curriculum_campaign
```

Expected c018 final commit from `results(19)`:

```text
4cbae35888b21cbfccb6ebf4f5f5bfc5e05bd757
```

Resolve the actual repository state from Git history. Do not blindly reset to this hash when newer c018 result-generation commits exist. Record the chosen parent and all candidates.

## Existing baseline and external roles

- Temporary externally confirmed champion/control: Dragapult, historically around 719.7 in captured evidence.
- Existing submitted calibration challenger: exact official Mega Lucario, submission reference `55011215`.
- c018 local field result for exact official Mega Lucario: 58.0% over its registered panel.
- c018 MCTS-like/search, distilled, PPO, and guided candidates: archive/diagnostic only; none may initialize a c019 pure method by default.

## What c018 proved

- Official native search API works at scale:
  - 42,857 successful roots;
  - 609,875 successful `search_step` calls.
- Actual CUDA training and optimizer updates can run at scale:
  - 81,920 simulator games;
  - 66,604 PPO optimizer steps.
- Packaging, evidence capture, and complete source bundling work.

## What c018 did not implement correctly

### Search

- Search overrode a stateful baseline without branch-local policy memory.
- It expanded alternatives only at the root.
- Deeper continuation repeatedly used option index `0`.
- Configured beam width was not used as a real beam.
- No UCT/PUCT selection, visit-count policy, or value backup existed.
- Leaf evaluation was shallow.
- Determinization could duplicate filler card IDs and create impossible hidden zones.

### Learning/curriculum

- Teacher labels came from the defective search branch.
- Learned value MSE was worse than a constant predictor.
- Self-play percentage rose mechanically; there were zero performance-driven promotions.
- The system was not ByteRL/OSFP.

## Key source hashes from the c018 evidence bundle

```text
cg/api.py                       593f1298e52a635f90f8f505a52113e9af114f444c293404e37906f18ee06ced
tools/c018_search.py            de136713d4884f17983e96fb59024a6a19304be00188e4818c7c61229ea02d52
tools/c018_curriculum.py        da5bedef98250613519eb64999a74355471c5472bfa4d7f8cbe0806d33b9cf60
tools/c018_guided.py            73662f99185e5198e0bbe0540a1b3492f5b2f7b2437b613fac03a3f124434396
c018 STATUS.json                080b4d6ebd394a89ad2b94b7f6765ae0de37d3923112296c368a680f3bd322fa
c018 final_panel_results.json   6aed7b10663428a5fb82afdc5b9b2ab387d181a8471c2fc688a7b48132f9360f
```

## Hardware

- Ubuntu 24.04
- Ryzen 9 7900X, 12 physical cores / 24 threads
- 61 GiB RAM
- RTX 5070, approximately 12 GiB VRAM
- custom PyTorch/CUDA infrastructure
- prior measured simulator throughput around 39,000 games/hour for the older fixed-deck PPO path

Use calibration rather than assuming prior throughput transfers to the recurrent actor-learner.
