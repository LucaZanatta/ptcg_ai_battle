from .manual_policy import DECK, choose
PLAYER_NAME = 'adaptive council'
BUILD_ID = 'ptcg_adaptive_council_hierarchical_rule_strategy_v24_no_learning'

def agent(obs_dict: dict) -> list[int]:
    return choose(obs_dict)
