# c000 findings relevant to c001

- c000 passed all 7 acceptance criteria.
- Verified harness: `kaggle_environments.make("cabt")`.
- Verified Python command prefix: `.venv/bin/python`.
- Competition agent entrypoint: `starter_kit/main.py:agent(obs_dict)`.
- Observation conversion: `cg.api.to_observation_class`.
- Deck phase: `obs.select is None`; current agent returns `starter_kit/deck.csv`.
- Action phase: current random baseline selects `maxCount` distinct indices from `obs.select.option`.
- Current deck has 60 rows and 9 unique IDs.
- c000 completed 10/10 baseline games without exception.
- `starter_kit/`, root `cg`, card assets, and scratch files were pre-existing untracked entries.
- No project source was changed by c000.
