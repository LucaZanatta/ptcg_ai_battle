"""c022 B3 — an asynchronous versioned actor producing recurrent unrolls.

`MANDATORY_IMPLEMENTATION B3` requires actual asynchronous versioned actors and one learner:
actors pull immutable versioned weights, each unroll stores its initial LSTM `h0/c0`, the queue is
a bounded FIFO on which producers block, samples are consumed once, and policy version, queue age,
occupancy, production/consumption ratio and actor blocking are all recorded.

An episode here is one complete PTCG game, and — in the end-to-end arm — the 60 construction
decisions that precede it (`B6`, `B19`: the terminal game return trains both stages). The episode
is cut into fixed-length unrolls; each unroll carries the recurrent state as it was **at that
unroll's first decision**, so the learner can replay the unroll exactly without replaying the
episode.

The state stored is the state BEFORE the first decision of the unroll, not after it. Storing the
state after would make the learner's first replayed step start one decision ahead of the actor's,
and every subsequent hidden state in the unroll would be wrong — silently, because the shapes
match and the losses stay finite. `PROBE_MATRIX B06` exists to catch exactly that, and it can only
catch it if the convention is fixed here.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_core as K  # noqa: E402
from cg import c021_byterl_deck as DK  # noqa: E402
from cg import c022_byterl_action as AC  # noqa: E402
from cg import c022_byterl_encode as EN  # noqa: E402
from cg import c022_byterl_model as M  # noqa: E402

UNROLL_LENGTH = 32

# B1.5's delta: how many of the 60 construction choices are drawn uniformly instead of from the
# policy. The papers say "random initial deck-construction selections" without a count, so this
# is a CHOSEN value recorded in UNRESOLVED_REFERENCE_CHOICES.md.
RANDOM_INITIAL_CONSTRUCTION_STEPS = 10


@dataclass
class Step:
    """One environment decision, with everything the learner needs to replay it."""

    stage: int
    enc: Dict[str, np.ndarray]
    seq: Dict[str, Any]                 # the token sequence, from ActionSequence.to_json()
    behaviour_logp: float               # the COMPLETE joint log-probability
    value: float
    reward: float = 0.0
    min_count: int = 1
    max_count: int = 1

    def to_json(self) -> Dict[str, Any]:
        return {"stage": self.stage, "seq": self.seq,
                "behaviour_logp": round(self.behaviour_logp, 6),
                "value": round(self.value, 6), "reward": self.reward,
                "min_count": self.min_count, "max_count": self.max_count}


@dataclass
class Unroll:
    """A fixed-length slice of one episode, with its recurrent start."""

    steps: List[Step]
    h0: np.ndarray
    c0: np.ndarray
    # The actor's state AFTER the unroll's last decision. This is what makes probe B06 real:
    # comparing the learner's stored start against itself is trivially zero and would pass under
    # a zeroed or shifted start. Comparing the learner's RECOMPUTED end state against the actor's
    # observed end state exercises the whole chain -- encoding, recurrence, and the boundary
    # convention -- and is nonzero the moment any of them disagree.
    h_end: np.ndarray
    c_end: np.ndarray
    policy_version: int
    episode_id: str
    unroll_index: int
    bootstrap_value: float
    is_episode_end: bool
    created_at: float = field(default_factory=time.time)

    def __len__(self) -> int:
        return len(self.steps)


class VersionedWeights:
    """An actor's local copy of the learner's published weights.

    `pull` loads only when the published version is newer, so an actor that is already current
    pays nothing. The blob is deserialized into the actor's OWN network object; nothing is shared
    with the learner's tensors, which is the same aliasing discipline `HistoricalPolicy` enforces
    for OSFP history and which c021 got wrong there.
    """

    def __init__(self, net: M.ByteRLRecurrentNet):
        self.net = net
        self.version = -1
        self.pulls = 0
        self.last_pull_time = 0.0

    def pull(self, shared) -> bool:
        """Load the published weights, if newer.

        The version and the blob are read as ONE value. Reading them as two keys is a race: the
        learner writes the blob and the version separately, so an actor can read version N and
        then fetch the blob the learner has meanwhile replaced with version N+1's. Every unroll
        that actor produced would then be LABELLED N while actually generated under N+1.

        That is not a cosmetic mislabelling. The importance ratio pi/mu is computed against the
        behaviour log-probability, and probe B06 replays an unroll under the weights its recorded
        version names — so a mislabelled unroll makes the fidelity check fail against a policy
        that never produced it. It is exactly how this defect was found: the B06 exact-weights
        assertion reported a recurrence delta of 1.07 where the same replay run in-process was
        identically zero.
        """
        try:
            pub = shared.get("published")
        except Exception:  # noqa: BLE001
            return False
        if not pub:
            return False
        v, blob = pub
        v = int(v)
        if v <= self.version or blob is None:
            return False
        import io
        self.net.load_state_dict(
            torch.load(io.BytesIO(blob), map_location="cpu", weights_only=False))
        self.net.eval()
        self.version = v
        self.pulls += 1
        self.last_pull_time = time.time()
        return True


class EpisodeRunner:
    """Plays one episode and emits unrolls.

    `learn_construction` selects the arm:

        False  FIXED_DECK_BATTLE_CONTROL              battle decisions only
        True   END_TO_END_DECK_CONSTRUCTION_AND_BATTLE  60 construction decisions, then battle
    """

    def __init__(self, net: M.ByteRLRecurrentNet, pool: DK.CardPool, rng,
                 learn_construction: bool, fixed_deck: Optional[List[int]] = None,
                 unroll_length: int = UNROLL_LENGTH, temperature: float = 1.0,
                 max_options: int = EN.MAX_OPTIONS,
                 random_initial_construction: bool = False):
        self.net = net
        self.pool = pool
        self.rng = rng
        self.learn_construction = bool(learn_construction)
        self.fixed_deck = list(fixed_deck) if fixed_deck else None
        self.unroll_length = int(unroll_length)
        self.temperature = float(temperature)
        self.battle_head = AC.BattleActionHead(net)
        self.construction_head = AC.ConstructionActionHead(net)
        self.max_options = int(max_options)
        self.random_initial_construction = bool(random_initial_construction)
        self.reset()

    def reset(self):
        self.steps: List[Step] = []
        self.state = self.net.initial_state(1)
        # The recurrent state before step i0 for every unroll boundary i0. Captured as the
        # episode runs, because reconstructing it later by re-running the network would be a
        # SECOND code path that could disagree with the first -- and probe B06 would then be
        # comparing the learner against a reconstruction rather than against what the actor
        # actually did.
        #
        # This list is per-instance. It was briefly a class attribute, which every EpisodeRunner
        # in a process would have shared: episode 2's unroll starts would have been appended to
        # episode 1's list and every unroll after the first episode would have replayed from the
        # wrong state.
        self._start_states: List[Tuple[np.ndarray, np.ndarray]] = []
        self.deck: List[int] = []
        self.n_construction = 0
        self.n_battle = 0
        self.illegal_sequences = 0
        self.option_truncations = 0
        self.max_options_seen = 0
        self.random_initial_choices = 0

    # ---------------------------------------------------------------- construction
    @torch.no_grad()
    def build_deck(self) -> Tuple[List[int], bool]:
        """B6/B19: 60 masked autoregressive choices, each a trained decision.

        `random_initial_construction` is the **B1.5 delta** (`FIDELITY_RULES §4`: "B1 with
        published random initial deck-construction selections"). The first
        `RANDOM_INITIAL_CONSTRUCTION_STEPS` choices are drawn UNIFORMLY from the legal mask
        instead of from the policy.

        The behaviour log-probability recorded for those steps is the UNIFORM one, not the
        network's. That is the whole correctness content of this feature: V-trace's importance
        ratio is `pi(a|s) / mu(a|s)`, and `mu` is whatever actually chose the action. Recording
        the network's log-probability while sampling uniformly would make every ratio on those
        steps wrong, and no loss curve would show it.

        `SEMANTIC_GAME_ADAPTER` — the exact Hearthstone schedule has no literal PTCG equivalent;
        the step count is recorded in `UNRESOLVED_REFERENCE_CHOICES.md`.
        """
        if not self.learn_construction:
            self.deck = list(self.fixed_deck or DK.greedy_reference_deck(self.pool))
            return self.deck, True
        partial: List[int] = []
        for step_i in range(DK.CONSTRUCTION_STEPS):
            self._note_boundary()
            enc = EN.encode_construction(partial, self.pool)
            tt = EN.to_torch(enc)
            h, self.state = self.net.step(EN.obs_parts(tt), self.state)
            if (self.random_initial_construction
                    and step_i < RANDOM_INITIAL_CONSTRUCTION_STEPS):
                seq = self._uniform_construction_choice(tt["pool_mask"])
                self.random_initial_choices += 1
            else:
                seq = self.construction_head.sample(h, tt["pool_mask"], rng=self.rng,
                                                    temperature=self.temperature)
            v = float(self.net.value(h, tt["stage"]).item())
            partial.append(self.pool.card_ids[seq.chosen_elements[0]])
            self.steps.append(Step(stage=EN.STAGE_CONSTRUCTION, enc=enc, seq=seq.to_json(),
                                   behaviour_logp=seq.joint_logp, value=v))
            self.n_construction += 1
        self.deck = partial
        legal, _detail = DK.legality(partial, self.pool)
        return partial, legal

    def _uniform_construction_choice(self, pool_mask) -> AC.ActionSequence:
        """A uniform draw over the legal pool, with the UNIFORM behaviour log-probability."""
        import numpy as _np
        m = pool_mask[0].detach().cpu().numpy()
        legal_idx = _np.nonzero(m > 0)[0]
        if legal_idx.size == 0:
            legal_idx = _np.arange(m.shape[0])
        idx = int(self.rng.choice(legal_idx))
        logp = float(-_np.log(max(1, legal_idx.size)))
        seq = AC.ActionSequence(stage=1)
        seq.tokens.append(AC.Token(AC.TOK_POOL, idx, logp, int(legal_idx.size)))
        seq.chosen_elements = [idx]
        seq.count = 1
        seq.joint_logp = logp
        return seq

    # ---------------------------------------------------------------- battle
    @torch.no_grad()
    def act(self, obs_dict: dict) -> List[int]:
        sel = obs_dict.get("select") if isinstance(obs_dict, dict) else None
        if sel is None:
            return list(self.deck)
        opts = K.canonical_options(sel)
        if not opts:
            return [0]
        if len(opts) == 1:
            # Not a decision: one legal answer. Recording it would train the policy on a choice
            # it never made and inflate the decision count the matched budget is measured in.
            return K.to_select_payload([opts[0]], sel)

        from cg import api as A
        self._note_boundary()
        o = A.to_observation_class(obs_dict)
        enc = EN.encode_battle(o)
        tt = EN.to_torch(enc)
        h, self.state = self.net.step(EN.obs_parts(tt), self.state)

        n = int(enc["n_options"])
        self.max_options_seen = max(self.max_options_seen, int(enc["n_options_true"]))
        if int(enc["n_options_true"]) > self.max_options:
            self.option_truncations += 1
        legal = tt["opt_mask"].clone()
        legal[:, n:] = 0.0
        k_min, k_max = AC.select_bounds(sel, n)
        seq = self.battle_head.sample(h, tt["opt"], tt["option_cards"], legal,
                                      k_min, k_max, rng=self.rng,
                                      temperature=self.temperature)
        ok, why = AC.sequence_is_legal(sel, opts[:n], seq)
        if not ok:
            # Counted, never silently repaired. B04's pass condition is that every emitted
            # sequence maps to one legal action; a repaired illegal action teaches the policy
            # that the illegal choice was fine.
            self.illegal_sequences += 1
        v = float(self.net.value(h, tt["stage"]).item())
        self.steps.append(Step(stage=EN.STAGE_BATTLE, enc=enc, seq=seq.to_json(),
                               behaviour_logp=seq.joint_logp, value=v,
                               min_count=k_min, max_count=k_max))
        self.n_battle += 1
        return AC.to_payload(sel, opts[:n], seq)

    # ---------------------------------------------------------------- unrolls
    def finish(self, reward: float, episode_id: str, policy_version: int) -> List[Unroll]:
        """Cut the episode into unrolls and attach the terminal return.

        `B19`: the terminal game result trains BOTH construction and battle decisions. With
        gamma = 1.0 (B1 and above) the discounted return is the terminal reward at every step, so
        placing the reward on the last step and discounting with 1.0 propagates it to all of them
        — including the 60 construction decisions, which is the whole point of the end-to-end arm.
        """
        if not self.steps:
            return []
        self.steps[-1].reward = float(reward)
        out: List[Unroll] = []
        # The start states were captured live by `_note_boundary`, because reconstructing them
        # afterwards would be a second code path that could disagree with the first. Unroll u's
        # END state is unroll u+1's START state, and the final unroll's end state is the
        # episode's final state -- so no extra bookkeeping is needed to record it.
        n = len(self.steps)
        n_unrolls = (n + self.unroll_length - 1) // self.unroll_length
        final_h = self.state[0].detach().cpu().numpy().copy()
        final_c = self.state[1].detach().cpu().numpy().copy()
        for i0 in range(0, n, self.unroll_length):
            u = i0 // self.unroll_length
            chunk = self.steps[i0:i0 + self.unroll_length]
            h0, c0 = self._start_state_for(i0)
            if u + 1 < n_unrolls:
                h_end, c_end = self._start_states[u + 1]
            else:
                h_end, c_end = final_h, final_c
            out.append(Unroll(steps=chunk, h0=h0, c0=c0, h_end=h_end, c_end=c_end,
                              policy_version=int(policy_version),
                              episode_id=episode_id,
                              unroll_index=u,
                              bootstrap_value=0.0 if (i0 + self.unroll_length >= n)
                              else float(self.steps[i0 + self.unroll_length].value),
                              is_episode_end=(i0 + self.unroll_length >= n)))
        return out

    def _start_state_for(self, i0: int) -> Tuple[np.ndarray, np.ndarray]:
        """The recurrent state BEFORE step `i0`."""
        return self._start_states[i0 // self.unroll_length]

    def _note_boundary(self):
        """Called BEFORE every recorded decision, by both stage paths.

        `.detach().cpu().numpy().copy()` — all four. `.numpy()` alone SHARES STORAGE with the
        tensor, so the stored "start state" would keep changing as the LSTM advanced and every
        unroll would replay from the episode's final state. That is exactly the defect c021 hit
        in its OSFP freeze, where a `.numpy()` view made a frozen opponent mutate under training;
        the same one-word mistake here would be invisible because the shapes and the losses would
        all still be right.
        """
        if len(self.steps) % self.unroll_length == 0:
            self._start_states.append(
                (self.state[0].detach().cpu().numpy().copy(),
                 self.state[1].detach().cpu().numpy().copy()))
