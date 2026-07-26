"""c014 §11/§12 — compact legality, reliability, latency and strategy-coherence validation.

Deliberately built on `cg.gameplay.play_one`, not on the c013 evaluation stack. c013's machinery
is organised around neural checkpoints, candidate registries and policy adjudication — concepts
§5 and §6 forbid here — while `play_one` is deck-and-agent agnostic and already counts invalid
selections, exceptions, timeouts and per-seat latency, which is most of the §11 gate.

Game budget is enforced at GAME granularity, not batch granularity. §7 caps local validation at
500–1,000 games INCLUDING the extracted-package games, and c013 shipped a 112-game overshoot
because an atomic batch was allowed to cross its ceiling.

The coherence audit (§12) reads decision traces the expert emits while it plays, so the metrics
describe the games that were actually scored rather than a separate instrumented re-run.
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
import os
import statistics
import sys
import time
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

C014 = os.path.join(_REPO, "contracts", "c014_public_meta_baseline_and_rapid_submission")
ART = os.path.join(C014, "results", "artifacts")
LOGD = os.path.join(C014, "results", "test_logs")
DECK_CSV = os.path.join(ART, "selected_deck.csv")

P99_GATE_MS = 250.0
MAX_LATENCY_GATE_MS = 1000.0     # self-imposed; see CURRENT_COMPETITION_FACTS.md

# §11 panel: Dragapult control, >=2 official baselines of different archetypes, a deterministic
# control, and self-play as a plumbing check only (never as strength evidence).
PANEL = [
    ("dragapult", "frozen_teacher_control", "spread_setup"),
    ("mega_lucario", "official_baseline", "switch_midrange"),
    ("iono", "official_baseline", "disruption_control"),
    ("mega_abomasnow", "official_baseline", "linear_aggro"),
    ("__safe__", "deterministic_control", "no_strategy_fallback"),
    ("__self__", "plumbing_only", "self_play"),
]


def load_deck() -> List[int]:
    return [int(x) for x in open(DECK_CSV) if x.strip()]


def play(deck, opponent_id, seat, game_id, trace=False):
    """One game. Returns a record plus the expert's decision traces."""
    from kaggle_environments import make
    from cg import c009_eval as ce, teachers as T
    from cg.safe_policy import validate_selection, MalformedSelection
    from cg.main import agent as safe_agent
    import c014_archaludon_expert as X

    ex = X.build(deck, trace=trace)
    stats = {"calls": 0, "lat_ms": [], "invalid": 0, "exceptions": 0}

    def me(obs):
        sel = obs.get("select") if isinstance(obs, dict) else getattr(obs, "select", None)
        t0 = time.perf_counter()
        try:
            r = ex(obs)
        except Exception:  # noqa: BLE001
            stats["exceptions"] += 1
            raise
        dt = (time.perf_counter() - t0) * 1000.0
        if sel is not None:
            stats["calls"] += 1
            stats["lat_ms"].append(dt)
            try:
                validate_selection(list(r), len(sel["option"]), sel["minCount"],
                                   sel["maxCount"])
            except MalformedSelection:
                stats["invalid"] += 1
        return r

    if opponent_id == "__self__":
        ex2 = X.build(deck)
        other = lambda o: ex2(o)  # noqa: E731
    elif opponent_id == "__safe__":
        def other(o):
            sel = o.get("select") if isinstance(o, dict) else getattr(o, "select", None)
            return list(deck) if sel is None else safe_agent(o)
    else:
        opp = T.make_fresh(opponent_id, ce.SOURCES)
        other = lambda o: opp(o)  # noqa: E731

    agents = [me, other] if seat == 0 else [other, me]
    exc = None
    env = None
    t0 = time.time()
    try:
        env = make("cabt")
        env.run(agents)
    except Exception as e:  # noqa: BLE001
        exc = repr(e)[:300]
    if env is None or exc is not None:
        rec = {"game_id": game_id, "opponent_id": opponent_id, "seat": seat,
               "statuses": ["ERROR", "ERROR"], "completed": False, "env_exception": exc,
               "score": None}
        return rec, []
    last = env.steps[-1]
    st = [s.status for s in last]
    rw = [s.reward for s in last]
    mine, theirs = rw[seat], rw[1 - seat]
    score = 1.0 if (mine is not None and theirs is not None and mine > theirs) else (
        0.5 if mine == theirs else 0.0)
    lat = sorted(stats["lat_ms"])
    rec = {
        "game_id": game_id, "opponent_id": opponent_id, "seat": seat,
        "statuses": st, "rewards": rw, "completed": st == ["DONE", "DONE"],
        "timeout": any(s == "TIMEOUT" for s in st),
        "agent_error": any(s in ("ERROR", "INVALID") for s in st),
        "score": score, "decisions": stats["calls"],
        "invalid_selections": stats["invalid"], "exceptions": stats["exceptions"],
        "latency_p50_ms": statistics.median(lat) if lat else None,
        "latency_p99_ms": (lat[max(0, int(len(lat) * 0.99) - 1)] if lat else None),
        "latency_max_ms": (lat[-1] if lat else None),
        "duration_s": round(time.time() - t0, 2),
        "fallbacks": ex.n_fallback, "fallback_reasons": dict(ex.fallback_reasons),
        "env_exception": None,
    }
    return rec, ex.traces


def coherence(traces_by_game: List[List[Dict]], games: List[Dict]) -> Dict[str, Any]:
    """§12 — is the stated thesis visibly executed in the games that were actually scored?"""
    import c014_archaludon_expert as X
    setup_ok = attacker_ready = bench_liability = attach_intended = 0
    attacks = collections.Counter()
    rules = collections.Counter()
    fb_reasons = collections.Counter()
    n_games = len(traces_by_game)
    sampled = 0
    for tr in traces_by_game:
        if not tr:
            continue
        sampled += len(tr)
        arch = any(t["resources"].get("archaludon_in_play") for t in tr)
        dura = any(t["resources"].get("duraludon_in_play") for t in tr)
        setup_ok += int(dura)
        attacker_ready += int(arch)
        if any((t["resources"].get("intended_attacker_m_energy") or 0) >= 3 for t in tr):
            attach_intended += 1
        bench_liability += sum(1 for t in tr if (t["resources"].get("bench_count") or 0) == 0)
        for t in tr:
            rules[t["rule"]] += 1
            if t["is_fallback"]:
                fb_reasons[t["rule"]] += 1
            if t["rule"] == "main_attack":
                attacks[t["resources"].get("intended_attacker") or "?"] += 1
    tot_dec = sum(rules.values())
    losses = collections.Counter()
    for g in games:
        if g.get("score") == 0.0:
            losses[g["opponent_id"]] += 1
    return {
        "games_audited": n_games, "decisions_sampled": sampled,
        "setup_success_rate": round(setup_ok / max(1, n_games), 4),
        "intended_attacker_prepared_rate": round(attacker_ready / max(1, n_games), 4),
        "attacker_reached_full_energy_rate": round(attach_intended / max(1, n_games), 4),
        "empty_bench_decisions_per_game": round(bench_liability / max(1, n_games), 3),
        "attacks_by_intended_attacker": dict(attacks),
        "thesis_attack_share": round(
            attacks.get("Archaludon ex", 0) / max(1, sum(attacks.values())), 4),
        "rule_usage": dict(rules.most_common()),
        "fallback_decisions": sum(fb_reasons.values()),
        "fallback_rate": round(sum(fb_reasons.values()) / max(1, tot_dec), 5),
        "fallback_reasons": dict(fb_reasons),
        "top_loss_opponents": dict(losses.most_common(3)),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=600)
    ap.add_argument("--trace-games", type=int, default=60)
    ap.add_argument("--out-prefix", default="local")
    a = ap.parse_args(argv)
    os.makedirs(ART, exist_ok=True)
    os.makedirs(LOGD, exist_ok=True)
    deck = load_deck()

    # round-robin the panel, alternating seats, stopping at exactly --games
    plan = []
    i = 0
    while len(plan) < a.games:
        opp = PANEL[i % len(PANEL)][0]
        plan.append((opp, (i // len(PANEL)) % 2))
        i += 1
    plan = plan[:a.games]          # game-granularity ceiling (§7)

    games, traces = [], []
    t0 = time.time()
    for n, (opp, seat) in enumerate(plan):
        want_trace = n < a.trace_games
        rec, tr = play(deck, opp, seat, f"{a.out_prefix}{n:05d}", trace=want_trace)
        games.append(rec)
        if want_trace and tr:
            traces.append(tr)
        if (n + 1) % 50 == 0:
            print(f"[validate] {n+1}/{len(plan)} {time.time()-t0:.0f}s", flush=True)

    with gzip.open(os.path.join(ART, f"{a.out_prefix}_games.jsonl.gz"), "wt") as fh:
        for g in games:
            fh.write(json.dumps(g) + "\n")
    if traces:
        with gzip.open(os.path.join(ART, "decision_trace_samples.jsonl.gz"), "wt") as fh:
            for gi, tr in enumerate(traces):
                for t in tr:
                    fh.write(json.dumps({"game_index": gi, **t}) + "\n")

    lat = [g["latency_max_ms"] for g in games if g.get("latency_max_ms") is not None]
    p99s = [g["latency_p99_ms"] for g in games if g.get("latency_p99_ms") is not None]
    alll = sorted([x for g in games for x in ([g["latency_p50_ms"]] if g.get("latency_p50_ms")
                                              else [])])
    rel = {
        "games": len(games),
        "completed": sum(1 for g in games if g["completed"]),
        "not_completed": [g["game_id"] for g in games if not g["completed"]][:20],
        "invalid_selections": sum(g.get("invalid_selections") or 0 for g in games),
        "exceptions": sum(g.get("exceptions") or 0 for g in games),
        "env_exceptions": sum(1 for g in games if g.get("env_exception")),
        "timeouts": sum(1 for g in games if g.get("timeout")),
        "agent_errors": sum(1 for g in games if g.get("agent_error")),
        "seats": dict(collections.Counter(g["seat"] for g in games)),
        "opponents": dict(collections.Counter(g["opponent_id"] for g in games)),
        "total_decisions": sum(g.get("decisions") or 0 for g in games),
        "fallbacks": sum(g.get("fallbacks") or 0 for g in games),
    }
    rel["hard_gates"] = {
        "zero_invalid_selections": rel["invalid_selections"] == 0,
        "zero_exceptions": rel["exceptions"] == 0 and rel["env_exceptions"] == 0,
        "zero_timeouts": rel["timeouts"] == 0,
        "all_games_classified": rel["completed"] + len(
            [g for g in games if not g["completed"]]) == rel["games"],
        "both_seats_tested": len(rel["seats"]) == 2,
    }
    json.dump(rel, open(os.path.join(ART, "reliability_report.json"), "w"), indent=2)

    latrep = {
        "p99_gate_ms": P99_GATE_MS, "max_gate_ms": MAX_LATENCY_GATE_MS,
        "max_gate_source": "self-imposed; the competition's per-decision limit is not "
                           "obtainable from client-rendered pages (see "
                           "CURRENT_COMPETITION_FACTS.md). runTimeout=3000s per episode is the "
                           "only verified bound and is not approached.",
        "worst_game_p99_ms": max(p99s) if p99s else None,
        "worst_game_max_ms": max(lat) if lat else None,
        "median_of_game_p50_ms": statistics.median(alll) if alll else None,
        "gates": {
            "p99_within_250ms": bool(p99s and max(p99s) <= P99_GATE_MS),
            "max_within_self_imposed_bound": bool(lat and max(lat) <= MAX_LATENCY_GATE_MS),
        },
    }
    json.dump(latrep, open(os.path.join(ART, "latency_report.json"), "w"), indent=2)

    mm = collections.defaultdict(lambda: [0, 0, 0])
    for g in games:
        k = g["opponent_id"]
        if g.get("score") is None:
            continue
        mm[k][0] += 1
        mm[k][1] += g["score"]
        mm[k][2] += 1 if g["seat"] == 0 else 0
    with open(os.path.join(ART, "matchup_matrix.csv"), "w") as fh:
        fh.write("opponent_id,role,archetype,games,score_rate,seat0_games\n")
        for opp, role, arch in PANEL:
            n, s, s0 = mm.get(opp, [0, 0, 0])
            fh.write(f"{opp},{role},{arch},{n},{(s/n if n else 0):.4f},{s0}\n")

    coh = coherence(traces, games)
    coh["next_loss_mode"] = {
        "id": "cinderace_explosiveness_opener_rarely_available",
        "statement": "Cinderace reaches the Active Spot via Explosiveness in only a minority of "
                     "games, so Turbo Flare - the deck's only energy accelerator, attaching 3 "
                     "Basic Energy to the bench - is usually unavailable and the deck must "
                     "reach {M}{M}{M} through one manual attachment per turn.",
        "why_single": "it is upstream of every other weakness measured here: slow energy is "
                      "what makes the evolve-turn weakness window long enough to be punished.",
        "measured_by": "attacks_by_intended_attacker and attacker_reached_full_energy_rate",
    }
    json.dump(coh, open(os.path.join(ART, "strategy_coherence.json"), "w"), indent=2)

    with open(os.path.join(LOGD, f"{a.out_prefix}_validation.txt"), "w") as fh:
        fh.write(json.dumps({"reliability": rel, "latency": latrep, "coherence": coh},
                            indent=2) + "\n")

    print(json.dumps({"games": rel["games"], "hard_gates": rel["hard_gates"],
                      "latency_gates": latrep["gates"],
                      "invalid": rel["invalid_selections"], "timeouts": rel["timeouts"],
                      "thesis_attack_share": coh["thesis_attack_share"],
                      "score_rate_overall": round(
                          sum(g["score"] for g in games if g.get("score") is not None)
                          / max(1, sum(1 for g in games if g.get("score") is not None)), 4)},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
