# Search roots

Root observations are not stored separately: each root is identified inside the trajectory rows (`game_index`, `decision_index`, `context`, `n_options`) and the sampled full traces live in `search/traces/`. Storing every root observation for 42,857 searched decisions would add hundreds of MB of duplicated state for no audit value beyond what the traces already give.
