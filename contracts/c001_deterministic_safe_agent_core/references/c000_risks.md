# c000 risks relevant to c001

## High: legal-action correctness unproven

The baseline uses random sampling over `option` and has no isolated validation of count bounds, determinism, or malformed selection behavior. Invalid selections can forfeit games.

## Medium: real-agent latency unmeasured

The random baseline is fast, but c001 must measure the deterministic entrypoint itself and separate agent-call latency from engine runtime.

## Low: fragile paths and untracked source

Avoid absolute paths. Stage only exact c001 text files. Do not accidentally stage the engine binary, card PDFs, virtual environment, or scratch files.
