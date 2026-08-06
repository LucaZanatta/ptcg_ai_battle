# Results and Source-Bundle Protocol

- c005 through c010 are immutable.
- Raw games and trainer-state lineage are the source of truth.
- Every aggregate must reproduce raw games exactly.
- CUDA is gated by semantic parity and measured throughput.
- The backend may change; the registered PPO algorithm may not.
- All new checkpoints must preserve full trainer state.
- The frozen teacher must be measured on the same strategic panel used for submission gates.
- `c011_python_source_bundle.zip` must contain all tracked Python source plus every executed c011 Python file, tests, manifests, dependency snapshots, Git evidence, contract files, and entrypoint/import inventories.
- Never include credentials, environments, caches, checkpoints, or datasets in the Python source bundle.
- File existence is never sufficient for acceptance.
