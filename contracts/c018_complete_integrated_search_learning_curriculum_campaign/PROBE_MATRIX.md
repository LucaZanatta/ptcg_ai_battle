# c018 Probe Matrix

Probes are diagnostic and normally non-blocking. A failure taints dependent artifacts. Submission blockers are defined in CONTRACT.md §8.2.

| ID | Probe | Minimum evidence | Primary downstream dependency |
|---|---|---|---|
| P01 | Native search lifecycle | `search_begin`, distinct child IDs, release/end, repeated-root memory test | all search artifacts |
| P02 | Real successor branching | distinct simulator successor observations, depth >1 trace | search trust |
| P03 | Hidden-information audit | static/runtime field-access log, blind-profile separation | submission eligibility |
| P04 | Legality and fallback | legal replay, baseline retained, timeout fallback | package safety |
| P05 | Tactical fixtures | real successor traces and leaf decomposition | evaluator/search quality |
| P06 | Search latency | step/decision/match time, memory, fallback rate | online package safety |
| P07 | Trajectory integrity | legal mask/action/root identity and round-trip | distillation data |
| P08 | Outcome/split integrity | game outcome reconciliation and game-level splits | model evidence |
| P09 | Distillation update proof | optimizer steps, changed hash, finite gradients | distilled model trust |
| P10 | Reload/held-out metrics | exact reload, policy/value metrics, legality | model packaging |
| P11 | PPO update proof | actual games, optimizer steps, changed hash | curriculum trust |
| P12 | Freshness/identity | current content hash, identity-safe eval, no game-zero promotion | promotion claims |
| P13 | Exact continuation | uninterrupted/resumed equivalence | training reproducibility |
| P14 | Mix/collapse | planned vs actual mix, entropy, cross-play | curriculum quality |
| P15 | Guidance comparison | same real roots, heuristic vs learned ordering/value | guided-search claim |
| P16 | Guided latency | policy/value/search/full-match latency | guided package safety |
| P17 | Final gameplay | frozen panel, identical seeds/seats, raw games | selection/submission |
| P30 | End-to-end real smoke | real outputs through every interface | integration status |
| P90 | Evidence validator | raw-data-derived consistency checks | final status |

Every probe directory must contain:

```text
probe.json
README.md
inputs_manifest.json
outputs_manifest.json
raw/ or explicit raw-path references
```

`probe.json` fields:

```json
{
  "probe_id": "Pxx",
  "status": "PASS|WARN|FAIL_TAINTED|NOT_EXERCISED",
  "source_commit": "...",
  "config_hash": "...",
  "checks": {},
  "taints": [],
  "submission_blocker": false,
  "raw_evidence": []
}
```
