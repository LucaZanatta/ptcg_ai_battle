from __future__ import annotations

import collections
import gzip
import json
import math
import pickle
import struct
from pathlib import Path

import policy_features as pf
import strategic_policy as sp
from cg.api import OptionType, SelectContext, to_observation_class

strategic_agent = sp.agent

ENABLE_READY_EVOLVE_GUARD = False
ENABLE_EMERGENCY_PETREL_GUARD = True
ENABLE_WALL_COMPOSITION_GUARD = True
ENABLE_END_ATTACH_GUARD = True

# High-certainty mechanics are routed away from the learned ranker and
# into the deterministic Pokémon TCG domain planner.
DOMAIN_ROUTED_CONTEXTS = (13, 15, 16, 39, 40)

# Kaggle executes submitted source with ``exec`` and may not define __file__.
# Resolve the packaged directory without assuming normal module import semantics.
if "__file__" in globals():
    BASE = Path(globals()["__file__"]).resolve().parent
else:
    _base_candidates = (Path("/kaggle_simulations/agent"), Path.cwd())
    BASE = next(
        (candidate for candidate in _base_candidates
         if (candidate / "models/policy_ensemble.bin.gz").is_file()),
        Path.cwd(),
    )
DECK = list(pf.DECK)

with gzip.open(BASE / "models/feature_schema.pkl.gz", "rb") as f:
    SCHEMA = pickle.load(f)
INTENT_TO_ID = {
    str(k): int(v)
    for k, v in json.loads((BASE / "final_schema.json").read_text(encoding="utf-8"))["intent_to_id"].items()
}

_RECORD = struct.Struct("<hBBBee")

def _load_ensemble(path: Path):
    raw = gzip.decompress(path.read_bytes())
    if raw[:4] != b"PTC2":
        raise ValueError("Unsupported policy asset")
    pos = 4
    model_count = raw[pos]
    pos += 1
    models = {}
    for _ in range(model_count):
        name_len = raw[pos]
        pos += 1
        name = raw[pos : pos + name_len].decode("ascii")
        pos += name_len
        tree_count = struct.unpack_from("<H", raw, pos)[0]
        pos += 2
        trees = []
        for _ in range(tree_count):
            node_count = raw[pos]
            pos += 1
            nodes = []
            for _ in range(node_count):
                nodes.append(_RECORD.unpack_from(raw, pos))
                pos += _RECORD.size
            trees.append(nodes)
        models[name] = trees
    if pos != len(raw):
        raise ValueError("Policy asset has trailing bytes")
    return models

MODELS = _load_ensemble(BASE / "models/policy_ensemble.bin.gz")
_HISTORY = []
_OPP_SEEN = collections.Counter()
_MATCHUP = "unknown"


def _reset():
    global _HISTORY, _OPP_SEEN, _MATCHUP
    _HISTORY = []
    _OPP_SEEN = collections.Counter()
    _MATCHUP = "unknown"


def _route(context: int):
    if context in DOMAIN_ROUTED_CONTEXTS:
        return None
    if context == 0:
        return "main"
    if context == 7:
        return "c7"
    if context in (3, 5, 8):
        return "low"
    if context in (13, 15, 16, 21, 22, 40, 43):
        return "mid"
    if context in (1, 2, 4, 27, 30, 34, 37, 38, 41):
        return "easy"
    return None


def _transform(row):
    maps = SCHEMA["category_maps"]
    values = []
    for name in SCHEMA["features"]:
        value = row.get(name, 0)
        if name in maps:
            try:
                value = value.item()
            except Exception:
                pass
            value = maps[name].get(value, -1)
        try:
            values.append(float(value))
        except Exception:
            values.append(float("nan"))
    return values


def _score(values, trees):
    total = 0.0
    for nodes in trees:
        node_index = 0
        while True:
            feature, flags, left, right, threshold, leaf_value = nodes[node_index]
            if flags & 1:
                total += leaf_value
                break
            value = values[feature]
            if math.isnan(value):
                node_index = left if flags & 2 else right
            else:
                node_index = left if value <= threshold else right
    return total


def _legal(action, select, option_count):
    minimum = int(select.get("minCount", 0) or 0)
    maximum = int(select.get("maxCount", 0) or 0)
    return (
        minimum <= len(action) <= maximum
        and len(action) == len(set(action))
        and all(isinstance(index, int) and 0 <= index < option_count for index in action)
    )


def _model_action(obs):
    select = obs.get("select") or {}
    options = select.get("option") or []
    option_count = len(options)
    selected_count = min(option_count, int(select.get("maxCount", 0) or 0))
    if selected_count <= 0:
        return [], []

    context = int(select.get("context", -1) if select.get("context") is not None else -1)
    model_name = _route(context)
    if model_name is None:
        return None, [pf.semantic(obs, option) for option in options]

    state = pf.base_state(obs, _HISTORY)
    semantics = [pf.semantic(obs, option) for option in options]
    semantic_keys = [
        (item["type"], item["source_id"], item["target_id"], item["attack_id"], item["area"], item["inplay_area"])
        for item in semantics
    ]
    counts = collections.Counter(semantic_keys)
    seen = collections.Counter()
    previous = _HISTORY[-1] if _HISTORY else {}
    scores = []

    for position, (option, item, key) in enumerate(zip(options, semantics, semantic_keys)):
        duplicate_rank = seen[key]
        seen[key] += 1
        row, _ = pf.option_row(obs, state, option, position, item, counts[key], duplicate_rank)
        values = _transform(row)
        values.extend(
            [
                float(INTENT_TO_ID.get(pf.intent_text(item), -1)),
                float(previous.get("type", -1)),
                float(previous.get("source_id", 0)),
                float(previous.get("target_id", 0)),
                float(previous.get("attack_id", 0)),
                float(len(_HISTORY)),
            ]
        )
        scores.append(_score(values, MODELS[model_name]))

    order = sorted(range(option_count), key=lambda index: (-scores[index], index))
    return sorted(order[:selected_count]), semantics




def _action_has(obs_obj, action, predicate):
    options = list(obs_obj.select.option or [])
    return any(0 <= i < len(options) and predicate(options[i]) for i in action)


def _source_id(obs_obj, option):
    card = sp._source_card(obs_obj, option)
    return int(card.id) if card is not None else 0


def _visible_opponent_ids(obs_obj):
    visible = {int(p.id) for p in sp._all_opp(obs_obj)}
    visible.update(int(c.id) for c in (sp._opp(obs_obj).discard or []) if c is not None)
    return visible


def _best_index(obs_obj, indices):
    indices = list(indices)
    if not indices:
        return None
    if obs_obj.select.context == SelectContext.MAIN:
        return max(indices, key=lambda i: (sp._main_score(obs_obj, obs_obj.select.option[i]), -i))
    return max(indices, key=lambda i: (sp._score_non_main(obs_obj, obs_obj.select.option[i]), -i))



# -----------------------------------------------------------------------------
# Human-AI matchup planner
# -----------------------------------------------------------------------------
# Card-family signatures.  These identify public board archetypes, never a
# player or submission.  The memory is reset at the beginning of every game.
_WALL_IDS = {117, 344, 345, 756}
_GRASS_IDS = {25, 96, 1094, 1127, 1251}
_MIRROR_IDS = {sp.IMPIDIMP, sp.MORGREM, sp.GRIMMSNARL, sp.FROSLASS, sp.MUNKIDORI}


def _update_matchup(obs_obj):
    global _MATCHUP
    for pokemon in sp._all_opp(obs_obj):
        _OPP_SEEN[int(pokemon.id)] += 1
    for card in (sp._opp(obs_obj).discard or []):
        if card is not None:
            _OPP_SEEN[int(card.id)] += 1
    seen = set(_OPP_SEEN)
    if seen & _WALL_IDS:
        _MATCHUP = "wall"
    elif seen & _GRASS_IDS:
        _MATCHUP = "grass"
    elif len(seen & _MIRROR_IDS) >= 2:
        _MATCHUP = "mirror"
    return _MATCHUP


def _count_frost_line(obs_obj):
    return sp._count_in_play(obs_obj, sp.SNORUNT) + sp._count_in_play(obs_obj, sp.FROSLASS)


def _composition_targets(profile):
    # Active + five Bench slots.  Two attacker lines, two Froslass lines and
    # one/two Munkidori are the strongest complete boards for this exact deck.
    if profile == "grass":
        # Minimum functional core.  Extra Bench slots are allocated from the
        # actual hand and prize race instead of enforcing a rigid 2/2/2 board.
        return {"marnie": 2, "frost": 1, "munk": 1}
    if profile == "wall":
        return {"marnie": 2, "frost": 2, "munk": 2}
    if profile == "mirror":
        return {"marnie": 2, "frost": 2, "munk": 1}
    return {"marnie": 2, "frost": 1, "munk": 1}


def _card_group(cid):
    if cid in sp.MARNIE_LINE:
        return "marnie"
    if cid in {sp.SNORUNT, sp.FROSLASS}:
        return "frost"
    if cid == sp.MUNKIDORI:
        return "munk"
    return "other"


def _group_count(obs_obj, group):
    if group == "marnie":
        return sp._count_line(obs_obj, sp.MARNIE_LINE)
    if group == "frost":
        return _count_frost_line(obs_obj)
    if group == "munk":
        return sp._count_in_play(obs_obj, sp.MUNKIDORI)
    return 0


def _missing_groups(obs_obj, profile):
    targets = _composition_targets(profile)
    return {g: max(0, targets[g] - _group_count(obs_obj, g)) for g in targets}


def _option_target(obs_obj, option):
    try:
        return sp._target_card(obs_obj, option)
    except Exception:
        return None


def _select_indices(obs_obj, ordered_indices, *, allow_fewer=True):
    """Return a legal, priority-ordered multi-selection."""
    sel = obs_obj.select
    n = len(sel.option or [])
    minimum = max(0, min(int(sel.minCount), n))
    maximum = max(minimum, min(int(sel.maxCount), n))
    out = []
    seen = set()
    for index in ordered_indices:
        if isinstance(index, int) and 0 <= index < n and index not in seen:
            out.append(index)
            seen.add(index)
        if len(out) >= maximum:
            break
    if not allow_fewer and len(out) < maximum:
        for index in range(n):
            if index not in seen:
                out.append(index); seen.add(index)
            if len(out) >= maximum:
                break
    if len(out) < minimum:
        for index in range(n):
            if index not in seen:
                out.append(index); seen.add(index)
            if len(out) >= minimum:
                break
    return sorted(out[:maximum])


def _setup_bench_plan(obs_obj, profile):
    """Choose Poffin targets by role coverage, hand coverage and seat tempo."""
    options = list(obs_obj.select.option or [])
    by_id = collections.defaultdict(list)
    for i, option in enumerate(options):
        by_id[_source_id(obs_obj, option)].append(i)

    if profile != "grass":
        return _select_indices(obs_obj, range(len(options)), allow_fewer=True)

    active = sp._active(obs_obj)
    inplay_marnie = _group_count(obs_obj, "marnie")
    inplay_frost = _group_count(obs_obj, "frost")
    inplay_munk = _group_count(obs_obj, "munk")
    hand = collections.Counter(sp._hand_ids(obs_obj))
    chosen = []

    # Poffin can only find Impidimp/Snorunt here.  Cover the role not already
    # represented by the Active first, then take the complementary role.  This
    # avoids two-copy tunnel vision while retaining a live attacker route.
    if inplay_marnie == 0 and by_id.get(sp.IMPIDIMP):
        chosen.append(by_id[sp.IMPIDIMP][0])
    if inplay_frost == 0 and by_id.get(sp.SNORUNT):
        chosen.append(by_id[sp.SNORUNT][0])

    # If one role is already covered by the Active or hand, use the second slot
    # to add redundancy where a future evolution is already available.
    if len(chosen) < int(obs_obj.select.maxCount):
        if (
            inplay_frost > 0 or hand[sp.SNORUNT] > 0
        ) and by_id.get(sp.IMPIDIMP) and inplay_marnie < 2:
            chosen.append(next((i for i in by_id[sp.IMPIDIMP] if i not in chosen), by_id[sp.IMPIDIMP][0]))
        elif (
            inplay_marnie > 0 or hand[sp.IMPIDIMP] > 0
        ) and by_id.get(sp.SNORUNT) and inplay_frost < 2:
            chosen.append(next((i for i in by_id[sp.SNORUNT] if i not in chosen), by_id[sp.SNORUNT][0]))

    # Still empty: prefer one of each, then a second Impidimp.  Three attacker
    # bodies are often correct against Grass weakness once the minimum damage
    # engine is represented; do not reserve Bench slots dogmatically.
    for cid in (sp.IMPIDIMP, sp.SNORUNT, sp.IMPIDIMP, sp.SNORUNT):
        for i in by_id.get(cid, []):
            if i not in chosen:
                chosen.append(i)
                break
        if len(chosen) >= int(obs_obj.select.maxCount):
            break
    return _select_indices(obs_obj, chosen, allow_fewer=True)


def _search_choice(obs_obj, profile):
    """Matchup-aware search/recovery using current board deficits."""
    sel = obs_obj.select
    options = list(sel.option or [])
    effect = getattr(sel, "effect", None)
    effect_id = int(effect.id) if effect is not None else 0
    available = collections.defaultdict(list)
    for i, option in enumerate(options):
        available[_source_id(obs_obj, option)].append(i)
    targets = _composition_targets(profile)
    marnie = _group_count(obs_obj, "marnie")
    frost = _group_count(obs_obj, "frost")
    munk = _group_count(obs_obj, "munk")
    hand = collections.Counter(sp._hand_ids(obs_obj))
    discard = collections.Counter(sp._discard_ids(obs_obj))
    priorities = []

    if effect_id == sp.POKE_PAD:
        # Count pieces already secured in hand as well as pieces in play.  A
        # human player does not search a second Morgrem while one is already in
        # hand, and never builds the side engine before securing an attacker.
        marnie_bodies = marnie + hand[sp.IMPIDIMP] + hand[sp.MORGREM] + hand[sp.GRIMMSNARL]
        frost_bodies = frost + hand[sp.SNORUNT] + hand[sp.FROSLASS]
        munk_bodies = munk + hand[sp.MUNKIDORI]
        live_imp = sp._count_in_play(obs_obj, sp.IMPIDIMP)
        live_snorunt = sp._count_in_play(obs_obj, sp.SNORUNT)

        if marnie_bodies == 0:
            priorities.append(sp.IMPIDIMP)
        if live_imp > 0 and hand[sp.MORGREM] == 0 and sp._count_in_play(obs_obj, sp.MORGREM) == 0:
            priorities.append(sp.MORGREM)
        if marnie_bodies < 2:
            priorities.append(sp.IMPIDIMP)

        if live_snorunt > 0 and hand[sp.FROSLASS] == 0 and sp._count_in_play(obs_obj, sp.FROSLASS) < live_snorunt:
            priorities.append(sp.FROSLASS)
        if frost_bodies == 0:
            priorities.append(sp.SNORUNT)
        if munk_bodies == 0:
            priorities.append(sp.MUNKIDORI)

        # Flexible redundancy after the minimum core: an additional attacker
        # line is preferred when the existing line is exposed to Grass
        # weakness; otherwise complete the second Froslass/Munkidori resource.
        if marnie_bodies < 3:
            priorities += [sp.IMPIDIMP, sp.MORGREM]
        if frost_bodies < 2:
            priorities += [sp.SNORUNT, sp.FROSLASS]
        if munk_bodies < 2:
            priorities.append(sp.MUNKIDORI)

    elif effect_id == sp.SPIKEMUTH:
        # Fetch the exact next evolution step; avoid a third attacker line.
        if sp._mature_morgrem_exists(obs_obj):
            priorities.append(sp.GRIMMSNARL)
        if sp._mature_impidimp_exists(obs_obj):
            if hand[sp.RARE_CANDY]:
                priorities.append(sp.GRIMMSNARL)
            priorities.append(sp.MORGREM)
        if marnie < targets["marnie"]:
            priorities.append(sp.IMPIDIMP)

    elif effect_id == sp.PETREL:
        # Never risk losing to an empty Bench.  A top player first guarantees
        # another Basic before searching an evolution or disruption card.
        if len(sp._me(obs_obj).bench or []) == 0:
            priorities += [sp.POFFIN, sp.POKE_PAD]
        # Concrete board construction outranks blind disruption.  With mature
        # Snorunt in play, a Poké Pad is effectively a Froslass and must come
        # before Rare Candy in grass/wall races.
        if profile == "wall" and sp._opponent_tools(obs_obj):
            priorities.append(sp.TOOL_SCRAPPER)
        if profile in {"grass", "wall"} and sp._count_in_play(obs_obj, sp.SNORUNT) > 0 and sp._count_in_play(obs_obj, sp.FROSLASS) < targets["frost"]:
            priorities.append(sp.POKE_PAD)
        if marnie == 0:
            priorities += [sp.POKE_PAD, sp.POFFIN, sp.SPIKEMUTH, sp.DAWN]
        elif not sp._has_ready_grimmsnarl(obs_obj):
            priorities += [sp.RARE_CANDY, sp.SPIKEMUTH, sp.POKE_PAD, sp.DAWN]
        if frost < targets["frost"]:
            priorities += [sp.POKE_PAD, sp.POFFIN]
        if any(cid in discard for cid in (sp.GRIMMSNARL, sp.MORGREM, sp.IMPIDIMP, sp.SNORUNT, sp.FROSLASS, sp.MUNKIDORI, sp.DARK)):
            priorities.append(sp.NIGHT_STRETCHER)
        if sp._boss_ko_exists(obs_obj, 180):
            priorities.append(sp.BOSS)
        priorities += [sp.UNFAIR_STAMP, sp.LILLIE, sp.POKEGEAR]

    elif effect_id == sp.NIGHT_STRETCHER:
        if not sp._has_ready_grimmsnarl(obs_obj):
            priorities += [sp.GRIMMSNARL, sp.MORGREM, sp.IMPIDIMP]
        if frost < targets["frost"]:
            priorities += [sp.FROSLASS, sp.SNORUNT]
        # Once Froslass is online, a Darkness Energy on Munkidori is a complete
        # extra damage action and often better than a redundant Pokémon.
        if sp._count_in_play(obs_obj, sp.FROSLASS) and any(
            p.id == sp.MUNKIDORI and sp._energy_count(p) == 0 for p in sp._all_my(obs_obj)
        ):
            priorities.append(sp.DARK)
        if munk < targets["munk"]:
            priorities.append(sp.MUNKIDORI)
        priorities += [sp.DARK, sp.GRIMMSNARL, sp.MORGREM, sp.IMPIDIMP]

    elif effect_id == sp.POKEGEAR:
        # Boss only when it converts immediately; otherwise improve the hand.
        if sp._boss_ko_exists(obs_obj, 180) and sp._has_ready_grimmsnarl(obs_obj):
            priorities.append(sp.BOSS)
        if int(obs_obj.current.turn) <= 4:
            priorities.append(sp.DAWN)
        priorities += [sp.PETREL, sp.LILLIE]

    elif effect_id == sp.DAWN:
        # Dawn can return several stage classes.  Rank each class by the live
        # board rather than choosing duplicate bodies.
        if marnie < targets["marnie"]:
            priorities.append(sp.IMPIDIMP)
        if frost < targets["frost"]:
            priorities.append(sp.SNORUNT)
        if munk < targets["munk"]:
            priorities.append(sp.MUNKIDORI)
        if sp._count_in_play(obs_obj, sp.SNORUNT) > sp._count_in_play(obs_obj, sp.FROSLASS):
            priorities.append(sp.FROSLASS)
        if sp._mature_impidimp_exists(obs_obj):
            priorities.append(sp.MORGREM)
        if sp._mature_morgrem_exists(obs_obj) or (sp._mature_impidimp_exists(obs_obj) and hand[sp.RARE_CANDY]):
            priorities.append(sp.GRIMMSNARL)

    chosen = []
    used = set()
    for cid in priorities:
        for i in available.get(cid, []):
            if i not in used:
                chosen.append(i); used.add(i); break
    if chosen:
        return _select_indices(obs_obj, chosen, allow_fewer=True)
    return None


def _punk_up_energy_choice(obs_obj):
    """Attach exactly what the current and next attacker need, not all five."""
    sel = obs_obj.select
    options = list(sel.option or [])
    if sel.context == SelectContext.ATTACH_TO:
        marnie = [p for p in sp._all_my(obs_obj) if p.id in sp.MARNIE_LINE]
        # Ready the Active first and one backup second.  Extra Energy on an
        # Active Pokémon increases Myriad Leaf Shower damage, so stop at two.
        ordered = sorted(
            marnie,
            key=lambda p: (
                0 if p is sp._active(obs_obj) else 1,
                0 if p.id == sp.GRIMMSNARL else (1 if p.id == sp.MORGREM else 2),
                sp._energy_count(p),
            ),
        )
        needed = sum(max(0, 2 - sp._energy_count(p)) for p in ordered[:2])
        needed = max(0, min(len(options), needed))
        return _select_indices(obs_obj, list(range(needed)), allow_fewer=True)
    if sel.context == SelectContext.ATTACH_FROM:
        candidates = []
        for i, option in enumerate(options):
            p = sp._source_card(obs_obj, option)
            if p is None or p.id not in sp.MARNIE_LINE:
                continue
            deficit = max(0, 2 - sp._energy_count(p))
            active = 1 if p is sp._active(obs_obj) else 0
            stage = {sp.GRIMMSNARL: 3, sp.MORGREM: 2, sp.IMPIDIMP: 1}.get(p.id, 0)
            candidates.append((deficit, active, stage, -sp._energy_count(p), -i, i))
        if candidates:
            return [max(candidates)[-1]]
    return None


def _predicted_ogerpon_damage(obs_obj, my_active):
    opp = sp._opp_active(obs_obj)
    if opp is None or opp.id != 96 or my_active is None:
        return 0
    raw = 30 * (1 + sp._energy_count(opp) + sp._energy_count(my_active))
    data = sp.CARD_DB.get(my_active.id)
    weakness = str(getattr(data, "weakness", "") or "") if data is not None else ""
    if "{G}" in weakness:
        raw *= 2
    return raw


def _promotion_choice(obs_obj, profile):
    options = list(obs_obj.select.option or [])
    scored = []
    opp_active = sp._opp_active(obs_obj)
    for i, option in enumerate(options):
        p = sp._source_card(obs_obj, option)
        if p is None:
            continue
        e = sp._energy_count(p)
        hp = sp._remaining_hp(p)
        score = 0
        if p.id == sp.GRIMMSNARL and e >= 2:
            score += 9000
        elif p.id in {sp.MORGREM, sp.IMPIDIMP} and e >= 2:
            score += 5000
        elif p.id == sp.MUNKIDORI:
            score += 2400 - 500 * e
        elif p.id in {sp.MORGREM, sp.IMPIDIMP}:
            score += 2100 - 250 * e
        elif p.id == sp.SNORUNT:
            score += 700
        elif p.id == sp.FROSLASS:
            score += 300
        score += hp

        if profile == "grass" and opp_active is not None and opp_active.id == 96:
            predicted = _predicted_ogerpon_damage(obs_obj, p)
            # Preserve two-prize attackers if they cannot immediately fight back.
            if predicted >= hp:
                score -= 7000 if p.id == sp.GRIMMSNARL else 2200
            if p.id == sp.MUNKIDORI and e == 0:
                score += 3500
        if profile == "wall" and p.id == sp.GRIMMSNARL and e >= 2:
            # Even into an immune Active, Shadow Bullet can pressure a vulnerable
            # Bench target while the counter engine works.
            score += 1800
        scored.append((score, -i, i))
    return [max(scored)[-1]] if scored else None


def _manual_attach_choice(obs_obj, profile):
    options = list(obs_obj.select.option or [])
    candidates = []
    frost_online = sp._count_in_play(obs_obj, sp.FROSLASS) > 0
    for i, option in enumerate(options):
        if option.type != OptionType.ATTACH or _source_id(obs_obj, option) != sp.DARK:
            continue
        target = _option_target(obs_obj, option)
        if target is None:
            continue
        e = sp._energy_count(target)
        score = 0
        if target.id == sp.GRIMMSNARL:
            score = 10000 if e < 2 else (-5000 if profile == "grass" else 500)
            if target is sp._active(obs_obj): score += 1500
        elif target.id in {sp.MORGREM, sp.IMPIDIMP}:
            score = 7500 if e < 2 else (-4500 if profile == "grass" else 300)
            if target is sp._active(obs_obj): score += 900
        elif target.id == sp.MUNKIDORI:
            score = 9200 if e == 0 and frost_online else (5200 if e == 0 else -3000)
        else:
            score = -6000
        candidates.append((score, -i, i))
    return [max(candidates)[-1]] if candidates else None


def _main_repair(obs_obj, chosen, fallback, profile):
    sel = obs_obj.select
    options = list(sel.option or [])
    if sel.context != SelectContext.MAIN or not options:
        return chosen
    targets = _composition_targets(profile)
    missing = _missing_groups(obs_obj, profile)

    chosen_idx = chosen[0] if chosen else -1
    chosen_option = options[chosen_idx] if 0 <= chosen_idx < len(options) else None

    # 0a. Survival before greed: with no Bench, establish any legal Basic
    # before attacking, ending, or spending the supporter on a non-setup line.
    if len(sp._me(obs_obj).bench or []) == 0 and chosen_option is not None:
        unsafe = chosen_option.type in {OptionType.ATTACK, OptionType.END}
        unsafe = unsafe or (chosen_option.type == OptionType.PLAY and _source_id(obs_obj, chosen_option) in {sp.LILLIE, sp.BOSS, sp.DAWN})
        if unsafe:
            for ids in ({sp.POFFIN}, {sp.POKE_PAD}, {sp.IMPIDIMP, sp.SNORUNT, sp.MUNKIDORI}, {sp.SPIKEMUTH}, {sp.PETREL}):
                idx = [i for i,o in enumerate(options) if o.type == OptionType.PLAY and _source_id(obs_obj,o) in ids]
                best = _best_index(obs_obj, idx)
                if best is not None:
                    return [best]

    # 0b. Against Ogerpon, do not retreat a one-prize pivot into a Grimmsnarl
    # that cannot take the current Active in one Shadow Bullet.  The opponent
    # will add another Energy with Teal Dance and convert that retreat into two
    # prizes.  Use the pivot turn to finish the engine instead.
    if profile == "grass" and chosen_option is not None and chosen_option.type == OptionType.RETREAT:
        opp_active = sp._opp_active(obs_obj)
        if opp_active is not None and opp_active.id == 96 and sp._remaining_hp(opp_active) > 180:
            active = sp._active(obs_obj)
            if active is not None and active.id != sp.GRIMMSNARL:
                for idx in (
                    [i for i,o in enumerate(options) if o.type == OptionType.EVOLVE and _source_id(obs_obj,o) == sp.FROSLASS],
                    [i for i,o in enumerate(options) if o.type == OptionType.PLAY and _source_id(obs_obj,o) in {sp.POFFIN,sp.POKE_PAD,sp.SPIKEMUTH,sp.PETREL,sp.DAWN,sp.LILLIE}],
                    [i for i,o in enumerate(options) if o.type == OptionType.ATTACH and getattr(_option_target(obs_obj,o),'id',0) == sp.MUNKIDORI],
                    [i for i,o in enumerate(options) if o.type == OptionType.END],
                ): 
                    best = _best_index(obs_obj, idx)
                    if best is not None:
                        return [best]

    # 0c. Put critical Pokémon onto the Bench before a draw supporter can
    # shuffle them away or before ending the turn.  This is the human habit of
    # converting known resources into board state before taking fresh cards.
    if chosen_option is not None and sp._bench_free(obs_obj) > 0:
        immediate_ko = any(
            o.type == OptionType.ATTACK
            and int(getattr(o, "attackId", 0) or 0) == sp.SHADOW_BULLET
            and sp._ko_target_exists(obs_obj, 180)
            for o in options
        )
        postpone = chosen_option.type in {OptionType.ATTACK, OptionType.END}
        postpone = postpone or (chosen_option.type == OptionType.PLAY and _source_id(obs_obj, chosen_option) in {sp.LILLIE, sp.DAWN, sp.PETREL, sp.BOSS})
        if postpone and not immediate_ko:
            play_by_id = collections.defaultdict(list)
            for i, option in enumerate(options):
                if option.type == OptionType.PLAY:
                    play_by_id[_source_id(obs_obj, option)].append(i)
            # Reserve the five Bench slots for the complete role pattern.
            wanted = []
            if missing.get("marnie", 0) > 0: wanted.append(sp.IMPIDIMP)
            if missing.get("frost", 0) > 0: wanted.append(sp.SNORUNT)
            if missing.get("munk", 0) > 0: wanted.append(sp.MUNKIDORI)
            # In Grass races, an existing attacker line means Snorunt and the
            # first Munkidori come before a redundant second evolution body.
            if profile == "grass" and _group_count(obs_obj, "marnie") >= 1:
                wanted = [sp.SNORUNT, sp.MUNKIDORI, sp.IMPIDIMP]
            for cid in wanted:
                if play_by_id.get(cid):
                    return [play_by_id[cid][0]]

    # 1. Resolve all useful Munkidori abilities before supporter/attack/end.
    if chosen_option is not None and (
        chosen_option.type in {OptionType.ATTACK, OptionType.END}
        or (chosen_option.type == OptionType.PLAY and _source_id(obs_obj, chosen_option) in {sp.BOSS, sp.LILLIE, sp.PETREL, sp.DAWN})
    ):
        abilities = [i for i,o in enumerate(options) if o.type == OptionType.ABILITY and _source_id(obs_obj,o) == sp.MUNKIDORI]
        best = _best_index(obs_obj, abilities)
        if best is not None:
            return [best]

    # 2. Evolve a live Froslass line before filling the Bench or attacking in
    # matchups where counters are required for one-hit prize turns.
    if profile in {"grass", "wall", "mirror"} and _count_frost_line(obs_obj) <= targets["frost"]:
        f_evolve = [i for i,o in enumerate(options) if o.type == OptionType.EVOLVE and _source_id(obs_obj,o) == sp.FROSLASS]
        if f_evolve and not any(o.type == OptionType.ATTACK and int(getattr(o,'attackId',0) or 0) == sp.SHADOW_BULLET and sp._ko_target_exists(obs_obj,180) for o in options):
            return [_best_index(obs_obj, f_evolve)]

    # 3. Prevent bench flooding.  Reserve every remaining slot for missing roles.
    if chosen_option is not None and chosen_option.type == OptionType.PLAY:
        cid = _source_id(obs_obj, chosen_option)
        group = _card_group(cid)
        if group in targets:
            current = _group_count(obs_obj, group)
            free = sp._bench_free(obs_obj)
            missing_total = sum(missing.values())
            redundant = current >= targets[group] and missing_total > 0 and free <= missing_total
            consumes_reserved = free <= missing_total and missing.get(group, 0) <= 0
            if redundant or consumes_reserved:
                # Prefer completing a missing role, then evolution/energy/search.
                replacement_groups = [g for g in ("marnie","frost","munk") if missing.get(g,0) > 0]
                replacement_ids = {
                    "marnie": {sp.IMPIDIMP},
                    "frost": {sp.SNORUNT},
                    "munk": {sp.MUNKIDORI},
                }
                for group2 in replacement_groups:
                    idx = [i for i,o in enumerate(options) if o.type == OptionType.PLAY and _source_id(obs_obj,o) in replacement_ids[group2]]
                    if idx:
                        return [_best_index(obs_obj, idx)]
                priorities = [
                    [i for i,o in enumerate(options) if o.type == OptionType.EVOLVE],
                    [i for i,o in enumerate(options) if o.type == OptionType.ATTACH],
                    [i for i,o in enumerate(options) if o.type == OptionType.PLAY and _source_id(obs_obj,o) in {sp.POKE_PAD,sp.POFFIN,sp.SPIKEMUTH,sp.RARE_CANDY,sp.PETREL,sp.DAWN,sp.POKEGEAR,sp.LILLIE}],
                    [i for i,o in enumerate(options) if o.type == OptionType.ATTACK],
                    [i for i,o in enumerate(options) if o.type == OptionType.END],
                ]
                for idx in priorities:
                    best = _best_index(obs_obj, idx)
                    if best is not None:
                        return [best]

    # 4. Matchup-specific Boss logic: remove Pinsir before Slow Crunch, or pull
    # a vulnerable Dwebble/Kangaskhan when the Active is attack-immune.
    if chosen_option is not None and chosen_option.type == OptionType.PLAY and _source_id(obs_obj, chosen_option) == sp.BOSS:
        useful = sp._has_ready_grimmsnarl(obs_obj) and sp._boss_ko_exists(obs_obj, 180)
        if profile == "grass":
            useful = useful or any(p.id == 25 and sp._remaining_hp(p) <= 180 for p in (sp._opp(obs_obj).bench or []) if p is not None)
        if profile == "wall":
            useful = useful or any(p.id in {344,756} and sp._remaining_hp(p) <= 180 for p in (sp._opp(obs_obj).bench or []) if p is not None)
        if not useful:
            for idx in (
                [i for i,o in enumerate(options) if o.type == OptionType.EVOLVE],
                [i for i,o in enumerate(options) if o.type == OptionType.ATTACH],
                [i for i,o in enumerate(options) if o.type == OptionType.PLAY and _source_id(obs_obj,o) in {sp.PETREL,sp.DAWN,sp.LILLIE,sp.POKEGEAR,sp.POKE_PAD,sp.SPIKEMUTH}],
                [i for i,o in enumerate(options) if o.type == OptionType.ATTACK],
            ):
                best = _best_index(obs_obj, idx)
                if best is not None: return [best]

    # 5. Correct Darkness attachment targets using board and matchup math.
    if chosen_option is not None and chosen_option.type == OptionType.ATTACH:
        better = _manual_attach_choice(obs_obj, profile)
        if better is not None:
            return better

    return chosen


def _counter_target_choice(obs_obj, profile):
    """Threat-aware Adrena-Brain and Shadow Bullet target selection."""
    sel = obs_obj.select
    options = list(sel.option or [])
    if sel.context not in {SelectContext.DAMAGE_COUNTER, SelectContext.DAMAGE}:
        return None
    scored = []
    for i, option in enumerate(options):
        p = sp._source_card(obs_obj, option)
        if p is None:
            continue
        active = p in (sp._opp(obs_obj).active or [])
        if sel.context == SelectContext.DAMAGE:
            score = sp._damage_target_score(p, 30, active, attack_damage=True, bench=not active)
        else:
            score = sp._damage_target_score(p, 30, active, attack_damage=False)
        e = sp._energy_count(p)
        if profile == "grass":
            if p.id == 25: score += 9000
            if p.id == 96:
                score += 500 * e
                # Counters can hit a Benched Tera Pokémon even when attack damage cannot.
                if sel.context == SelectContext.DAMAGE_COUNTER: score += 1600
        elif profile == "wall":
            if p.id == 344: score += 8000
            if p.id == 117: score += 4500
            if p.id == 756: score += 3200 + 250 * e
            if p.id == 345 and sel.context == SelectContext.DAMAGE_COUNTER: score += 3800
        elif profile == "mirror":
            if p.id in {sp.FROSLASS, sp.MUNKIDORI}: score += 5000
            if p.id == sp.GRIMMSNARL: score += 1800
        scored.append((score, -i, i))
    return [max(scored)[-1]] if scored else None

# The public wrapper activates the matchup specialist only after a positive
# archetype signature; otherwise this module remains on its frozen baseline.
_SPECIALIST_ON = False


def _human_ai_override(obs_dict, chosen, fallback):
    if not _SPECIALIST_ON:
        return chosen
    try:
        obs_obj = to_observation_class(obs_dict)
        sel = obs_obj.select
        options = list(sel.option or [])
        if not options:
            return chosen
        profile = _update_matchup(obs_obj)
        # This specialist is activated only after the opponent reveals the
        # Grass/Ogerpon family.  Every other matchup remains byte-for-byte
        # behaviorally on the frozen baseline path.
        if profile != "grass":
            return chosen
        effect = getattr(sel, "effect", None)
        effect_id = int(effect.id) if effect is not None else 0

        if sel.context == SelectContext.SETUP_BENCH_POKEMON:
            return _setup_bench_plan(obs_obj, profile)
        if sel.context == SelectContext.TO_BENCH and effect_id == sp.POFFIN:
            return _setup_bench_plan(obs_obj, profile)
        if sel.context == SelectContext.TO_HAND:
            search = _search_choice(obs_obj, profile)
            if search is not None:
                return search
        if effect_id == sp.GRIMMSNARL and sel.context in {SelectContext.ATTACH_TO, SelectContext.ATTACH_FROM}:
            punk = _punk_up_energy_choice(obs_obj)
            if punk is not None:
                return punk
        if sel.context in {SelectContext.TO_ACTIVE, SelectContext.SWITCH}:
            promoted = _promotion_choice(obs_obj, profile)
            if promoted is not None:
                return promoted
        target = _counter_target_choice(obs_obj, profile)
        if target is not None:
            return target
        if sel.context == SelectContext.MAIN:
            return _main_repair(obs_obj, chosen, fallback, profile)
        return chosen
    except Exception:
        return chosen

def _tactical_override(obs_dict, chosen, fallback):
    """Small, high-confidence tactical repairs from domain analysis.

    The learned ranker remains the default.  These guards fire only when a
    locally dominant action is available or a known setup dead-end is about to
    be repeated.
    """
    try:
        obs_obj = to_observation_class(obs_dict)
        sel = obs_obj.select
        options = list(sel.option or [])
        if not options or not chosen:
            return chosen

        # 1) Never take a weak Impidimp/Morgrem attack before a ready active
        #    Grimmsnarl evolution.  Evolving preserves the attack and upgrades
        #    it to Shadow Bullet while also activating Punk Up.
        if ENABLE_READY_EVOLVE_GUARD and sel.context == SelectContext.MAIN:
            weak_attack = _action_has(
                obs_obj,
                chosen,
                lambda o: o.type == OptionType.ATTACK
                and int(getattr(o, "attackId", 0) or 0)
                in (sp.FILCH, sp.CORKSCREW_IMPIDIMP, sp.CORKSCREW_MORGREM),
            )
            if weak_attack:
                ready_evolutions = []
                active = sp._active(obs_obj)
                for i, option in enumerate(options):
                    if option.type != OptionType.EVOLVE:
                        continue
                    source = sp._source_card(obs_obj, option)
                    target = sp._target_card(obs_obj, option)
                    if (
                        source is not None and source.id == sp.GRIMMSNARL
                        and target is active and sp._energy_count(target) >= 2
                    ):
                        ready_evolutions.append(i)
                best = _best_index(obs_obj, ready_evolutions)
                if best is not None:
                    return [best]

        # 2) Petrel emergency setup: with no Marnie line in play, do not spend
        #    the search on a disruption card.  Recover a route to Impidimp.
        effect = getattr(sel, "effect", None)
        effect_id = int(effect.id) if effect is not None else 0
        if ENABLE_EMERGENCY_PETREL_GUARD and (
            sel.context == SelectContext.TO_HAND
            and effect_id == sp.PETREL
            and sp._count_line(obs_obj, sp.MARNIE_LINE) == 0
            and sp._bench_free(obs_obj) > 0
            and sp._count_in_play(obs_obj, sp.FROSLASS) == 0
        ):
            setup_priority = [sp.POKE_PAD, sp.SPIKEMUTH, sp.POFFIN]
            if any(cid in sp._discard_ids(obs_obj) for cid in sp.MARNIE_LINE):
                setup_priority.append(sp.NIGHT_STRETCHER)
            setup_priority.append(sp.DAWN)
            for wanted in setup_priority:
                indices = [i for i, option in enumerate(options) if _source_id(obs_obj, option) == wanted]
                if indices:
                    return [indices[0]]

        # 3) Mega Kangaskhan + Mysterious Rock Inn Crustle requires damage
        #    counters.  Preserve the second Froslass slot instead of adding a
        #    third Munkidori while the second Froslass line is still missing.
        opponent_ids = _visible_opponent_ids(obs_obj)
        wall_match = 756 in opponent_ids and 345 in opponent_ids
        froslass_lines = sp._count_in_play(obs_obj, sp.FROSLASS) + sp._count_in_play(obs_obj, sp.SNORUNT)
        munkidori_count = sp._count_in_play(obs_obj, sp.MUNKIDORI)
        chose_munkidori = _action_has(obs_obj, chosen, lambda o: _source_id(obs_obj, o) == sp.MUNKIDORI)
        if ENABLE_WALL_COMPOSITION_GUARD and wall_match and munkidori_count >= 2 and froslass_lines < 2 and chose_munkidori:
            # Directly complete or start the missing Froslass line when offered.
            for wanted in (sp.FROSLASS, sp.SNORUNT):
                indices = [i for i, option in enumerate(options) if _source_id(obs_obj, option) == wanted]
                if indices:
                    return [indices[0]]

            # Otherwise keep the bench slot.  Prefer a ready evolution, then a
            # current attack, then the strategic fallback, excluding another
            # Munkidori play/search.
            if sel.context == SelectContext.MAIN:
                priorities = [
                    [i for i, o in enumerate(options) if o.type == OptionType.EVOLVE and _source_id(obs_obj, o) == sp.GRIMMSNARL],
                    [i for i, o in enumerate(options) if o.type == OptionType.ATTACK],
                    [i for i, o in enumerate(options) if o.type == OptionType.ATTACH and getattr(sp._target_card(obs_obj, o), "id", 0) in sp.MARNIE_LINE],
                    [i for i, o in enumerate(options) if o.type == OptionType.ABILITY],
                ]
                for indices in priorities:
                    best = _best_index(obs_obj, indices)
                    if best is not None:
                        return [best]
            if fallback and not _action_has(obs_obj, fallback, lambda o: _source_id(obs_obj, o) == sp.MUNKIDORI):
                return fallback

        # 4) End-turn anti-stall guard: if no Grimmsnarl is ready, never pass a
        #    legal Darkness attachment to the Marnie line that still needs it.
        if ENABLE_END_ATTACH_GUARD and sel.context == SelectContext.MAIN and _action_has(obs_obj, chosen, lambda o: o.type == OptionType.END):
            if not sp._has_ready_grimmsnarl(obs_obj):
                attach_indices = []
                for i, option in enumerate(options):
                    if option.type != OptionType.ATTACH or _source_id(obs_obj, option) != sp.DARK:
                        continue
                    target = sp._target_card(obs_obj, option)
                    if target is not None and target.id in sp.MARNIE_LINE and sp._energy_count(target) < 2:
                        attach_indices.append(i)
                best = _best_index(obs_obj, attach_indices)
                if best is not None:
                    return [best]
    except Exception:
        return chosen
    return chosen


def agent(obs):
    global _HISTORY
    if not obs or obs.get("select") is None:
        _reset()
        try:
            strategic_agent(obs)
        except Exception:
            pass
        return list(DECK)

    select = obs.get("select") or {}
    options = select.get("option") or []
    option_count = len(options)

    try:
        fallback = strategic_agent(obs)
    except Exception:
        fallback = []

    try:
        action, semantics = _model_action(obs)
    except Exception:
        action, semantics = None, [pf.semantic(obs, option) for option in options]

    chosen = fallback if action is None else action
    chosen = _tactical_override(obs, chosen, fallback)
    chosen = _human_ai_override(obs, chosen, fallback)
    if not _legal(chosen, select, option_count):
        chosen = fallback
    if not _legal(chosen, select, option_count):
        chosen = list(range(min(option_count, int(select.get("maxCount", 0) or 0))))

    _HISTORY = (_HISTORY + [semantics[index] for index in chosen if 0 <= index < option_count])[-8:]
    return chosen
