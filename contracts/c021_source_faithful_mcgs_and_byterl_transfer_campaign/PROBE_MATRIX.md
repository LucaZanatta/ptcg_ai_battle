# Mandatory Probe Matrix

Every probe requires executable tests, raw artifacts and a semantic validator. File existence is insufficient.

## Parent/source probes

| ID | Probe | Pass condition |
|---|---|---|
| P00 | Parent/control freeze | Exact identities/hashes and reproducible controls |
| P01 | MCGS official archive | Retrieved, hashed, inventoried, source files readable |
| P02 | MCGS paper/source map | Every relevant source function/equation mapped |
| P03 | ByteRL source search | Reproducible primary-source search and honest conclusion |
| P04 | License boundary | External source excluded/included according to documented license decision |

## MCGS probes

| ID | Probe | Pass condition |
|---|---|---|
| M01 | Abstraction fixtures | Keys merge/separate states for documented source-equivalent reasons |
| M02 | DAG transposition | Multiple paths share the expected node; collisions audited |
| M03 | Modified UCD numerical fixture | Production score matches independent calculation |
| M04 | Recursive incoming-edge update | Non-traversed incoming paths receive exact source update |
| M05 | Chance-node lifecycle | Hidden/random event creates and samples source-faithful chance outcomes |
| M06 | Sparse sampling | Threshold/count/probability behavior matches reference |
| M07 | Damped sampling | Sample budget decreases exactly under prescribed chance-depth conditions |
| M08 | Atomic-action graph reuse | Search graph survives/re-roots across sequential PTCG selections |
| M09 | Category filters | PTCG translations match documented source semantic role |
| M10 | Obliged actions | Mandatory action behavior triggers only in mapped fixtures |
| M11 | Rollout/terminal payoff | No leaf evaluator; returns derive from source-equivalent rollout/terminal result |
| M12 | Time allocation | Source schedule reproduced under fixed synthetic clock |
| M13 | Parallel equivalence | Parallel execution preserves statistical semantics within tolerance |
| M14 | Known-defect reproduction | Reference exhibits documented information-memory limitation |
| M15 | Corrected branch isolation | Fix exists only in separately named corrected branch |
| M16 | Throughput scaling | Valid measurements at 1/2/4/8/12 workers |
| M17 | Decision-value ablation | Search-executed actions compared with no-search control |

## ByteRL probes

| ID | Probe | Pass condition |
|---|---|---|
| B01 | Deck meta-environment | Complete legal constructed deck enters battle and receives terminal credit |
| B02 | Shared representation | Construction and battle use intended shared parameters |
| B03 | Slot/typed-state sensitivity | Active/bench/energy/status/tool changes affect intended tokens only |
| B04 | Dynamic option references | Every legal option maps to exact source/target/object |
| B05 | Autoregressive round trip | Complete action serializes, executes and reconstructs exactly |
| B06 | Joint log-probability | Sum of conditional logs matches independent enumeration fixture |
| B07 | Actor recurrent replay | Stored behavior checkpoint and h0/c0 reproduce recorded logits/log-probability |
| B08 | Episode reset | No recurrent leakage across episodes |
| B09 | FIFO semantics | Bounded ordering/blocking/age behavior proven under stress |
| B10 | Producer/consumer balance | Requested control policy operates and logs actual ratio |
| B11 | V-trace numerical fixture | Targets match independent reference implementation |
| B12 | UPGO numerical/live | Nonzero live contribution and exact fixture |
| B13 | Improved objective | Ratio clipping and policy loss match paper equations |
| B14 | Effective-batch equivalence | Microbatch/accumulation update matches full-batch fixture |
| B15 | OSFP period reset | Period-local evidence resets and old games cannot contaminate promotion |
| B16 | Immutable history | Historical checkpoint hashes never change |
| B17 | Mixture realization | Actual opponent sampling matches requested mixture statistically |
| B18 | Frozen promotion | Promotion evaluation uses one frozen learner checkpoint |
| B19 | BR0→BR3 delta audit | Adjacent stages differ only by registered published change |
| B20 | External generalization | Every milestone evaluated against frozen external controls |
| B21 | Value admission | Held-out calibration compared with constant/c020/heuristic baselines |
| B22 | Prior admission | Legal alignment, entropy, baseline suppression and ranking measured |

## Transfer/final probes

| ID | Probe | Pass condition |
|---|---|---|
| T01 | Parent fidelity gate | No transfer before MCGS and ByteRL method probes pass |
| T02 | Prior-only transfer | Identical search budget; only prior source differs |
| T03 | Value-only transfer | Runs only after B21 passes; only value differs |
| T04 | One-change invariant | Every transfer mode changes one registered component |
| F01 | Complete thin smoke | Both methods execute end-to-end before repair/scaling |
| F02 | One repair pass | Root defects and exact fixes documented; no hidden second cycle |
| F03 | Identity-safe final panel | Candidate/control IDs verified per game |
| F04 | Package/source identity | Package entrypoint/model/deck match evaluated candidate |
| F05 | Canonical final source | Git archive and plain copies match final commit hashes |
| F06 | Report consistency | Summary/status exactly match raw final aggregates |
| F07 | Semantic validator | Injected prior campaign defects are rejected |
