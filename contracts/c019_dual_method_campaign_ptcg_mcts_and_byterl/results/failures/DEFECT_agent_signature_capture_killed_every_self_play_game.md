# DEFECT — default-argument closure capture silently replaced the model with a config object

**Severity: would have invalidated the entire ByteRL branch.** Caught by the method-fidelity
validator, which recounted completed games from raw rows instead of trusting the summary.

## Symptom

The scaled ByteRL run reported 20,000 games and 2,500 optimizer steps for learning period 0 and
looked healthy. The raw per-game rows said otherwise:

```text
completed: {False: 12000}
mean steps per game: 0.8
```

Twelve thousand games, none completed, averaging under one decision each. Training was running on
essentially empty trajectories.

## Cause

`kaggle_environments` inspects the agent callable's signature and passes
`(observation, configuration)` to anything that accepts two parameters. The opponent was built
with default-argument capture:

```python
def opp_agent(obs, _m=opp_model, _d=deck):     # accepts three parameters
    return _self_play_action(_m, obs, _d)
```

The environment therefore called `opp_agent(observation, configuration)`, binding `configuration`
over `_m`. Inside, `model.forward(...)` raised `AttributeError: 'Struct' object has no attribute
'forward'`, the seat was marked `ERROR`, and the game ended immediately.

## Why it survived three earlier tests

- `play_game` against a scripted teacher: the teacher was wrapped as `lambda o: tea(o)`, a
  one-parameter callable, so the environment passed only the observation.
- `_self_play_action` driving both seats directly: same, one-parameter wrappers.
- The first ByteRL smoke: 25% of its games were against teachers, so *some* games completed and
  the aggregate did not look empty.

Each test exercised a one-parameter agent. The defect only appears with the multi-parameter form,
which is exactly what the actor used.

## Fix

Agent callables are now produced by factory functions returning a genuine one-parameter closure:

```python
def make_model_agent(m, d):
    def agent(obs):
        return _self_play_action(m, obs, d)
    return agent
```

Result: 96/96 games complete, mean 63.7 steps, balanced outcomes (50 wins / 46 losses), and 60
optimizer steps for the same 96 games instead of 12.

## Two further defects found while chasing this

1. **Multi-select contexts were ignored.** The actor returned one option index where the engine
   required `minCount` of them, which is an invalid action. Now it samples `minCount..maxCount`
   options without replacement.
2. **Opponent recurrent state leaked across games** (B02 violation). `_OPP_STATE` was keyed by
   model id at module level and never cleared, so a game began with the previous game's LSTM
   state. Now reset at every game boundary.

## Generalisable lesson

A silently-failed game is indistinguishable from a short game in any aggregate. The only reason
this was caught before 160,000 wasted games is that the validator recounts `completed` from raw
per-game rows rather than reading the training summary's own totals — the exact principle c018
established after its curriculum reported progress it had not made.
