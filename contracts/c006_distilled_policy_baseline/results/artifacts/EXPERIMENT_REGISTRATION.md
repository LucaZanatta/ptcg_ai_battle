# c006 Experiment Registration (frozen before training)

Teacher: `dragapult`  |  Deck: `sha256:8055443275c86105b38198992c9556a642b833a47430aa97fb1a84c9ee4fdbab`

## Architectures & parameter ceilings
- **S1_STATELESS**: 152,673 params (target [150000, 500000], hard max 750000) — in target: True
- **S2_RECURRENT**: 273,441 params (target [250000, 650000], hard max 900000) — in target: True

## Seeds
- S1: [101, 202, 303]  |  S2: [111, 222, 333]

## Optimizer
- Adam lr=0.0015, betas=[0.9, 0.999], max_epochs={'S1_STATELESS': 40, 'S2_RECURRENT': 30}, patience=6, OMP_NUM_THREADS=1 for reproducibility

## Early-stopping metric
- importance_weighted_teacher_action_agreement (validation)

## Loss
- single: masked softmax cross-entropy; multi: masked per-option BCE; ordered: none present -> safe fallback (not trained as BCE)
- importance weights: {'FORCED': 0.0, 'ROUTINE': 1.0, 'TACTICAL': 2.0, 'HIGH_IMPACT': 4.0}

## Non-inferiority
- one-sided 95% lower bound (5th percentile, seat-balanced bootstrap); pass >= 0.45; margin 0.05

## Gates
- Memory: MEMORY_MATTERS if S2 improves high-impact test agreement by >= 2pp, OR game-level importance-weighted agreement 95% bootstrap interval > 0, OR material gameplay improvement; else MEMORY_NOT_JUSTIFIED
- Best student: reliability-eligible; passes non-inferiority; highest gauntlet strength; no major regression; higher high-impact test agreement; lower fallback; lower P99; smaller model. NONE if neither passes non-inferiority.
- Submission: SUBMIT iff best student exists AND non-inferiority passes AND no major regression AND perfect official-eval reliability AND package validation passes AND P99+size pass
- RL readiness: READY_FOR_RL iff best student exists AND submission gate passes (or misses only for non-policy operational issue) AND not materially weaker than teacher AND decoder covers >=99% of teacher decisions without strategic fallback AND memory decision resolved AND frozen checkpoint+eval reproducible

## Dataset freeze
- train/val/test sha256: {
  "train": "e5d5b3c880bf8c709b0e7add5f60785bfdb8ae7afc6bf078ede2bb14245c19b6",
  "validation": "760ca505a44c1a58fa703f1c6cbde5e0098715db3443d9b03ef3d43f3d725d58",
  "test": "123f3dfdf34d167d05a0b01741c676c6d3fb254e3672d9bfbbf66e0a0db8c4e6"
}
- card vocab source hash: `53aa2eeb7dc4872ed2a559eb73b8799ccd08d078c06fc4a7fa87dcc2ad578aa1`

Emergency correction policy: a single documented code-defect correction that invalidates all runs may restart every affected model fairly; otherwise no changes after freeze