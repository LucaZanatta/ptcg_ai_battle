# Clean checkout & run (c012)

Branch as above, final HEAD `12a091d905e32cd92654e31ae2f5ae91b09ecde4`, repo root, `.venv/bin/python`.

Deterministic: dependency/immutability verification, the c011 repair tests (RNG restore and true continuation, both pinned to deterministic torch), the curriculum hash lock, the content-aware validator and the source-bundle validator.

Not bit-reproducible: the games themselves (the cabt engine seeds from `std::random_device`), and Claude Code responses. All conclusions are stated with bootstrap intervals and the raw per-game records ship.

Externally provided (gitignored): cabt SDK + libcg.so, kaggle-environments, torch, the c005 teacher sources and the c007-c011 artifacts. No file under c005-c011 is written.
