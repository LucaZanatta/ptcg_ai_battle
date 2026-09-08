# Fixed user decisions

These are not suggestions. Preserve them in execution and reporting.

1. c019 implements **two real pipelines**, not another diluted proprietary approximation:
   - Hearthstone-style imperfect-information MCTS;
   - ByteRL-style end-to-end RL plus OSFP.
2. The two methods run as independent branches. Failure or weak data in one branch must not contaminate the other.
3. The existing project pipeline is retained as the shared harness and gradually receives correct, switchable blocks from the two pure methods.
4. Hybrid work is capped and opportunistic. Do not spend weeks or additional contracts engineering the hybrid before the pure methods work.
5. The hybrid may import only:
   - ByteRL policy logits as MCTS priors;
   - ByteRL value as an MCTS leaf evaluator;
   - MCTS visit distributions as an optional auxiliary target schema.
6. The hybrid is not required to train or submit in c019.
7. Build integration-first. Run thin real-output versions of both methods early, then scale.
8. Probes are observability tools, not a sequence of miniature blocking contracts. Continue the other branch when one probe or branch fails.
9. Only validity/safety defects block submission of the affected candidate: hidden-information leakage, illegality, package mismatch, unresolved source permission, evaluation identity corruption, crash/timeout risk.
10. Include the complete final code, focused source, milestone snapshots, raw games, search trees, actor unrolls, optimizer logs, checkpoints, payoff tables, packages, and hashes under `results/` so ChatGPT can audit and debug implementation details.
11. Submit each pure branch as soon as it becomes credible. Do not wait for the other branch or the hybrid.
12. No third method, no generic research platform, and no architecture reset during c019.
13. Be honest. A branch may be method-faithful and competitively weak. Report both facts separately.
14. Winning and external strength matter more than completing files or giving sophisticated names to weak blocks.
