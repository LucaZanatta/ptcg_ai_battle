# Clean-checkout reproducibility

Every c013 source file is committed on this branch and bundled in `c013_python_source_bundle.zip` together with the contract, command, inputs, references, dependency and machine snapshots, and the Git patch. A clean checkout at `a7d78dd56b7d4a9b75c5e5fa2e6828fc3bdfb477` plus the bundle reproduces the toolchain; the engine is `std::random_device`-seeded, so individual games are not bit-reproducible and every conclusion is stated with bootstrap intervals rather than exact replay.
