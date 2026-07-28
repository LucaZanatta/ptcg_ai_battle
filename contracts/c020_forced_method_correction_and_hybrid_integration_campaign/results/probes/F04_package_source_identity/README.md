# F04 — Package/source identity

Each package is validated by EXTRACTING it, removing the repository source roots from `sys.path`, loading opponents by file path so no repo helper can put `cg` back, and playing real games from the extracted copy alone. Liveness is asserted from the agent's OWN counters, never from games completed: a package that silently degraded to the baseline passes every test built on win rate, and one did.
