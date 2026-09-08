# H03 — Switchability

Pure MCTS output is unchanged with adapters disabled, and this is structural rather than tested-by-hope: `c019_mcts.py` imports nothing from any ByteRL module, and the providers are constructor arguments defaulting to `None`. The reverse holds too — the ByteRL actor imports nothing from MCTS (§16).

**Status: PASS.**
