# c020 Decision, Promotion, Submission, and Kill Rules

## No method or deck choice

The methods and deck are fixed. Claude does not select alternatives.

## Independent pure branches

- Corrected MCTS and corrected ByteRL scale independently.
- A strong pure branch is packaged/submitted without waiting for the other or hybrid.
- MCTS data does not train corrected ByteRL in c020.
- ByteRL enters MCTS only through H1–H4 adapters after the corrected pure checkpoint exists.

## Registered final evidence

Freeze before final results:

- candidate configs/hashes;
- opponent panel;
- seeds and seats;
- game counts;
- metric and confidence calculations;
- package latency budget;
- H4 blend alpha;
- MCTS override thresholds.

## MCTS promotion

Promote only when the gate in CONTRACT §10 passes. Diagnostic tactical fixture gains alone do not substitute for gameplay.

## ByteRL promotion

Promote only when semantic correctness and gameplay gates both pass. Loss reduction alone is insufficient.

## Hybrid promotion

Hybrid must beat the stronger corrected pure parent or materially preserve strength with lower cost. Complexity is not evidence.

## Role assignment

- `CHAMPION`: strongest externally confirmed package.
- `CHALLENGER`: credible different package with complementary or near-competitive evidence.
- `DIAGNOSTIC`: semantically valid but weak or unsubmitted.
- `ARCHIVE`: defective, tainted, or clearly inferior.

## Submission

Automatic upload after clean package validation and gate pass. Score may remain `PENDING`. Do not upload known weak/tainted candidates merely to complete the contract.

## Kill after c020

At c020 end, do not propose another broad architecture contract. The next action must be exactly one externally relevant move derived from results, such as:

- scale the winning corrected method;
- fix one measured remaining defect in the winning method;
- submit a credible package whose score was pending;
- archive the hybrid if it failed to beat parents.
