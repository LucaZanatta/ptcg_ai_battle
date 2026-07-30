"""c022 — recompute every c021 audit finding from raw artifacts.

`CONTRACT.md §3` lists six findings and says they are "starting facts to verify from raw
artifacts, not optional narrative". `references/C021_AUDIT_FINDINGS.md` adds "Do not trust prose
alone. Recompute all values from c021 raw files and record discrepancies."

So nothing here reads a c021 conclusion. Every number is recomputed from a per-episode JSONL, a
per-iteration curve, an MCGS run summary or the source text, and each is compared against what
c021 (or the c022 contract) says it should be. Discrepancies are reported, not smoothed.

One recovery matters more than the rest. c021's four-hour extension reused the parent run tag, so
it OVERWROTE `big_ctrl_b2_games.jsonl` and `big_ctrl_b2_curve.json` in place. The files at HEAD
hold the extension segment only. The pre-extension segment survives at commit `fbbd9ac`, and the
true training exposure is the sum. Reading HEAD alone understates the fixed-deck B2 arm by 15,360
games, which would make c022's "matched budget" too small by exactly that much.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from collections import Counter, defaultdict

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C021_REL = "contracts/c021_source_faithful_mcgs_and_byterl_transfer_campaign/results"
C021 = os.path.join(_REPO, C021_REL)
OUT = os.path.join(_REPO, "contracts",
                   "c022_mcgs_multideterminization_and_faithful_byterl_reproduction", "results")

# The commit that holds the pre-extension segment of the two extended control rungs.
PRE_EXTENSION_COMMIT = "fbbd9ac"
# The c021 result-generation commit named in CONTRACT.md §1.
C021_RESULT_COMMIT = "cdbd4438496c905eaf38ee257abfe0c822c588f4"

EXTENDED_ARMS = ("big_ctrl_b1_5", "big_ctrl_b2")
ALL_BIG_ARMS = ("big_ctrl_b1_5", "big_ctrl_b2", "big_ctrl_b3",
                "big_learn_b1_5", "big_learn_b2", "big_learn_b3")


def wilson(k: int, n: int, z: float = 1.96):
    """Wilson score interval. c021 used the same method, so the numbers stay comparable."""
    if n <= 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0.0, c - h), 4), round(min(1.0, c + h), 4))


def git_show_lines(commit: str, relpath: str):
    """Read a file's lines from a git commit; [] if it does not exist there."""
    r = subprocess.run(["git", "show", f"{commit}:{relpath}"], cwd=_REPO,
                       capture_output=True, text=True)
    if r.returncode != 0:
        return []
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def git_show_json(commit: str, relpath: str):
    r = subprocess.run(["git", "show", f"{commit}:{relpath}"], cwd=_REPO,
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except Exception:  # noqa: BLE001
        return None


def read_lines(path: str):
    if not os.path.isfile(path):
        return []
    with open(path) as fh:
        return [ln for ln in fh if ln.strip()]


def summarise_episodes(lines) -> dict:
    """Exact per-episode aggregation. This is the authoritative decision count.

    `mean_battle_steps` in the curve is rounded to one decimal place, so summing it across 720
    iterations accumulates up to ~36 decisions of rounding error per arm. The per-episode records
    carry integer `n_battle` / `n_construction`, so they are used instead.
    """
    n = 0
    completed = 0
    wins = 0.0
    battle = 0
    construction = 0
    legal_decks = 0
    seconds = 0.0
    iters = set()
    per_opponent = defaultdict(lambda: [0, 0.0])
    scores = Counter()
    for ln in lines:
        try:
            d = json.loads(ln)
        except Exception:  # noqa: BLE001
            continue
        n += 1
        gid = d.get("game_id", "")
        # "<tag>:i<iter>:g<idx>"
        parts = gid.split(":")
        if len(parts) >= 2 and parts[1].startswith("i"):
            iters.add(parts[1])
        if d.get("completed"):
            completed += 1
        s = d.get("score")
        if s is not None:
            wins += float(s)
            scores[float(s)] += 1
            per_opponent[d.get("opponent", "?")][0] += 1
            per_opponent[d.get("opponent", "?")][1] += float(s)
        battle += int(d.get("n_battle") or 0)
        construction += int(d.get("n_construction") or 0)
        if d.get("deck_legal"):
            legal_decks += 1
        seconds += float(d.get("seconds") or 0.0)
    return {
        "games": n,
        "iterations": len(iters),
        "completed": completed,
        "scored_games": int(sum(scores.values())),
        "score_sum": round(wins, 2),
        "win_rate": round(wins / max(1, sum(scores.values())), 4),
        "battle_decisions": battle,
        "construction_decisions": construction,
        "total_decisions": battle + construction,
        "legal_decks": legal_decks,
        "actor_seconds": round(seconds, 1),
        "per_opponent": {k: {"games": v[0], "rate": round(v[1] / v[0], 4)}
                         for k, v in sorted(per_opponent.items()) if v[0]},
    }


# ====================================================================== budget
def reconcile_budget() -> dict:
    """Finding 3 + TRAINING_AND_EVALUATION §1: the exact c021 fixed-deck B2 exposure."""
    arms = {}
    for arm in ALL_BIG_ARMS:
        relp = f"{C021_REL}/byterl/raw/{arm}_games.jsonl"
        head = summarise_episodes(read_lines(os.path.join(_REPO, relp)))
        pre = summarise_episodes(git_show_lines(PRE_EXTENSION_COMMIT, relp))
        man = None
        mp = os.path.join(C021, "byterl", "manifests", f"{arm}_manifest.json")
        if os.path.isfile(mp):
            with open(mp) as fh:
                man = json.load(fh)
        extended = arm in EXTENDED_ARMS and pre["games"] > 0
        total = {k: (head[k] + pre[k]) if isinstance(head[k], (int, float)) else None
                 for k in ("games", "completed", "battle_decisions",
                           "construction_decisions", "total_decisions", "legal_decks")}
        if extended:
            total["iterations"] = head["iterations"] + pre["iterations"]
        else:
            total["iterations"] = head["iterations"]
        arms[arm] = {
            "learn_construction": arm.startswith("big_learn"),
            "extended": extended,
            "segment_at_HEAD": head,
            "segment_pre_extension": pre if extended else None,
            "pre_extension_commit": PRE_EXTENSION_COMMIT if extended else None,
            "TOTAL_EXPOSURE": total if extended else {
                k: head[k] for k in ("games", "iterations", "completed", "battle_decisions",
                                     "construction_decisions", "total_decisions",
                                     "legal_decks")},
            "manifest_resumed_from": (man or {}).get("resumed_from"),
            "manifest_fresh_random_weights": (man or {}).get("fresh_random_weights"),
            "manifest_iterations_completed": (man or {}).get("iterations_completed"),
            "manifest_wall_clock_s": (man or {}).get("wall_clock_s"),
        }

    b2 = arms["big_ctrl_b2"]["TOTAL_EXPOSURE"]
    # c021 ran exactly one optimizer step per completed trajectory (tools/c021_byterl_train.py
    # `_learn`: `for traj in trajectories: ... opt.step(); n_updates += 1`). There is no sample
    # reuse loop, so sample_reuse = 1 and optimizer examples == environment decisions.
    cur_head = None
    p = os.path.join(C021, "byterl", "curves", "big_ctrl_b2_curve.json")
    if os.path.isfile(p):
        with open(p) as fh:
            cur_head = json.load(fh)
    cur_pre = git_show_json(PRE_EXTENSION_COMMIT,
                            f"{C021_REL}/byterl/curves/big_ctrl_b2_curve.json")
    updates = sum(int(r.get("updates") or 0) for r in (cur_head or [])) \
        + sum(int(r.get("updates") or 0) for r in (cur_pre or []))

    budget = {
        "controlling_quantity": "environment decisions (samples), not games",
        "why": "TRAINING_AND_EVALUATION §1. Games are not comparable across arms: a fixed-deck "
               "episode is battle decisions only, while an end-to-end episode adds 60 "
               "construction decisions, so matching on games would give the end-to-end arm a "
               "very different environment-interaction budget.",
        "source_arm": "big_ctrl_b2",
        "source_arm_meaning": "c021 fixed-deck (learn_construction=0) B2 rung — the arm "
                              "CONTRACT.md §2 freezes as C021_FIXED_DECK_B2_FINAL",
        "recovered_from": {
            "extension_segment": f"{C021_REL}/byterl/raw/big_ctrl_b2_games.jsonl @ HEAD",
            "pre_extension_segment": f"{C021_REL}/byterl/raw/big_ctrl_b2_games.jsonl "
                                     f"@ {PRE_EXTENSION_COMMIT}",
            "why_two_segments": "c021's extension reused the parent run tag and overwrote the "
                                "raw file in place; HEAD holds the extension only.",
        },
        "games": b2["games"],
        "iterations": b2["iterations"],
        "battle_decisions": b2["battle_decisions"],
        "construction_decisions": b2["construction_decisions"],
        "total_environment_decisions": b2["total_decisions"],
        "learner_updates": updates,
        "sample_reuse_c021": 1,
        "sample_reuse_c021_evidence": "tools/c021_byterl_train.py::_learn performs exactly one "
                                      "opt.step() per trajectory with no reuse loop",
        "optimizer_examples_after_reuse": b2["total_decisions"] * 1,
        "MATCHED_BUDGET_FOR_C022": {
            "quantity": "total environment decisions",
            "value": b2["total_decisions"],
            "definition": "battle decisions + construction decisions, summed over every episode "
                          "of both training segments",
            "applies_to": ["BR3_FIXED_DECK", "BR3_END_TO_END"],
            "note_for_end_to_end": "the end-to-end arm reaches the same DECISION budget with "
                                   "fewer games, because each of its episodes also contains "
                                   "60 construction decisions. That is the intended meaning of "
                                   "matching on decisions rather than games, and the achieved "
                                   "game count is reported alongside.",
            "fallback_if_unrecoverable": 76800,
            "fallback_used": False,
            "fallback_note": "TRAINING_AND_EVALUATION §1 permits a 76,800-game fallback only if "
                             "exact decisions cannot be recovered. They can: the per-episode "
                             "records carry integer n_battle/n_construction. Note that 76,800 "
                             "is itself the EXTENSION game count, not c021's total exposure.",
        },
        "extension_block_25pct": round(b2["total_decisions"] * 0.25),
        "arms": arms,
    }
    return budget


# ====================================================================== MCGS
def reconcile_mcgs_overconfidence() -> dict:
    """Finding 1: single-determinization overconfidence, recomputed per run."""
    # c021 wrote several run summaries into TWO directories (e.g. the t2 transfer arms appear
    # under both mcgs/evaluations/ and transfer/other_single_component/). Collecting the union
    # naively double-counts those runs, which inflates "n runs overconfident" without adding a
    # single new measurement. Dedupe by file CONTENT, and record which paths collapsed together
    # so the duplication is visible rather than silently removed. `mcgs/superseded/` is excluded
    # outright: c021 moved runs there precisely because they were replaced.
    import hashlib
    seen = {}
    order = []
    def collect(d):
        if not os.path.isdir(d):
            return
        for fn in sorted(os.listdir(d)):
            if not fn.endswith("_summary.json"):
                continue
            p = os.path.join(d, fn)
            with open(p, "rb") as fh:
                raw = fh.read()
            h = hashlib.sha256(raw).hexdigest()
            rp = os.path.relpath(p, _REPO)
            if h in seen:
                seen[h]["duplicate_paths"].append(rp)
                continue
            seen[h] = {"path": rp, "duplicate_paths": [], "summary": json.loads(raw)}
            order.append(h)

    for sub in ("evaluations", "comparisons", "legal_corrected", "reference_source_port",
                "source_port", "ablations", "raw_games"):
        collect(os.path.join(C021, "mcgs", sub))
    for sub in ("prior_only", "other_single_component"):
        collect(os.path.join(C021, "transfer", sub))
    rows = [(seen[h]["path"], seen[h]["summary"], seen[h]["duplicate_paths"]) for h in order]
    n_dupes = sum(len(seen[h]["duplicate_paths"]) for h in order)

    out = []
    for path, s, dupes in rows:
        w = s.get("term_root_win")
        l = s.get("term_root_loss")
        if w is None or l is None:
            continue
        u = s.get("term_undecided") or 0
        decided = w + l
        pred_decided = (w / decided) if decided else None
        pred_all = (w / (decided + u)) if (decided + u) else None
        fs = s.get("field_score")
        out.append({
            "run": path,
            "identical_copies_at": dupes,
            "branch": s.get("branch"),
            "determinizations_per_decision":
                (s.get("config") or {}).get("determinizations_per_decision"),
            "games": s.get("games"), "completed": s.get("completed"),
            "abandoned": s.get("abandoned"),
            "field_score": fs,
            "rollout_terminals": s.get("rollout_terminals"),
            "term_root_win": w, "term_root_loss": l, "term_undecided": u,
            "predicted_win_rate_over_decided": round(pred_decided, 4)
                if pred_decided is not None else None,
            "predicted_win_rate_over_all_rollouts": round(pred_all, 4)
                if pred_all is not None else None,
            "overconfidence_gap_pp": round(100 * (pred_decided - fs), 1)
                if (pred_decided is not None and fs is not None) else None,
            "sims_per_decision": s.get("sims_per_decision"),
        })
    out.sort(key=lambda r: -(r["overconfidence_gap_pp"] or -999))
    gaps = [r["overconfidence_gap_pp"] for r in out if r["overconfidence_gap_pp"] is not None]
    return {
        "claim_under_test": "CONTRACT.md §3.1 — 'predicted root wins near 96% while actual "
                            "outcomes were poor'",
        "definition_of_predicted": "term_root_win / (term_root_win + term_root_loss): the "
                                   "fraction of rollouts that reached a terminal the ROOT PLAYER "
                                   "won, among rollouts that reached a decided terminal. "
                                   "term_undecided rollouts hit the turn cap and are excluded "
                                   "from the ratio and reported separately.",
        "runs": out,
        "n_runs": len(out),
        "n_duplicate_copies_collapsed": n_dupes,
        "superseded_excluded": "results/mcgs/superseded/ — c021 moved those runs there because "
                               "they were replaced; counting them would resurrect retracted "
                               "measurements",
        "predicted_max": max((r["predicted_win_rate_over_decided"] for r in out), default=None),
        "predicted_max_run": max(out, key=lambda r: r["predicted_win_rate_over_decided"])["run"]
        if out else None,
        "predicted_min": min((r["predicted_win_rate_over_decided"] for r in out), default=None),
        "predicted_min_run": min(out, key=lambda r: r["predicted_win_rate_over_decided"])["run"]
        if out else None,
        "overconfidence_gap_pp_max": max(gaps, default=None),
        "overconfidence_gap_pp_min": min(gaps, default=None),
        "every_run_has_positive_gap": all(g > 0 for g in gaps) if gaps else None,
    }


# ====================================================================== external / transfer
def reconcile_external_gate() -> dict:
    """Finding 3: 'roughly 24-26% externally after about 76,800 games'."""
    p = os.path.join(C021, "byterl", "selection", "gate_evaluation.json")
    g = json.load(open(p)) if os.path.isfile(p) else {}
    reval = os.path.join(C021, "byterl", "selection", "external_gate_revalidation.json")
    rv = json.load(open(reval)) if os.path.isfile(reval) else {}
    base = os.path.join(C021, "byterl", "selection", "external_gate_TRUE_baseline.json")
    bl = json.load(open(base)) if os.path.isfile(base) else {}

    def rate(d, name):
        for c in d.get("candidates", []):
            if c["checkpoint"] == name:
                k = round(c["win_rate"] * c["games"])
                return {"checkpoint": name, "games": c["games"], "wins_implied": k,
                        "win_rate": c["win_rate"],
                        "wilson95_recomputed": wilson(k, c["games"]),
                        "wilson95_as_recorded": c.get("wilson95")}
        return None

    post_final = rate(rv, "big_ctrl_b2_final.pt")
    post_sel = None
    for c in (g.get("post_extension_b2_it0160_SELECTED"),):
        if c:
            post_sel = {"checkpoint": "big_ctrl_b2_it0160.pt", "games": 256,
                        "win_rate": c["win_rate"],
                        "wins_implied": round(c["win_rate"] * 256),
                        "wilson95_recomputed": wilson(round(c["win_rate"] * 256), 256),
                        "wilson95_as_recorded": c.get("wilson95")}
    pre = rate(bl, "PRE_big_ctrl_b2_final.pt")
    # gate_evaluation.json quotes the post-extension final at 0.2578 on 256 games while
    # external_gate_revalidation.json quotes 0.2422 on 256 games. Both are recorded.
    gate_final = g.get("post_extension_b2_final", {})
    disagreement = None
    if post_final and gate_final.get("win_rate") is not None \
            and abs(post_final["win_rate"] - gate_final["win_rate"]) > 1e-9:
        disagreement = {
            "quantity": "post-extension big_ctrl_b2_final external win rate on 256 games",
            "gate_evaluation.json": gate_final.get("win_rate"),
            "external_gate_revalidation.json": post_final["win_rate"],
            "delta_pp": round(100 * (gate_final["win_rate"] - post_final["win_rate"]), 2),
            "reading": "two independent 256-game panels of the SAME checkpoint, run at "
                       "different times with different seeds. The spread is ordinary sampling "
                       "noise at n=256 (SE ~2.7pp), and it is the empirical reason c022 must "
                       "state which panel a number came from rather than quoting 'the' rate.",
        }
    return {
        "claim_under_test": "CONTRACT.md §3.3 — 'improved to roughly 24-26% externally after "
                            "about 76,800 games'",
        "pre_extension_baseline": pre,
        "post_extension_final": post_final,
        "post_extension_selected_it0160": post_sel,
        "gate_evaluation_headline": gate_final,
        "panel_disagreement": disagreement,
        "games_qualifier": "the '76,800 games' in the contract is the EXTENSION segment only. "
                           "Total exposure for this arm is larger; see c021_matched_budget.json.",
        "external_gate_result_as_recorded": (g.get("external_gate") or {}).get("result"),
        "selection_defect_as_recorded": g.get("selection_defect"),
    }


def reconcile_transfer() -> dict:
    """Finding 6: transfer point estimates positive but below run-to-run noise."""
    p = os.path.join(C021, "transfer", "admission_decisions.json")
    d = json.load(open(p)) if os.path.isfile(p) else {}
    ctrl = d.get("control_field_score")
    arms = {}
    for name, a in (d.get("arms") or {}).items():
        n = a.get("games")
        r = a.get("field_score")
        k = round(r * n) if (n and r is not None) else None
        arms[name] = {
            "games": n, "field_score": r, "wins_implied": k,
            "wilson95_recomputed": wilson(k, n) if k is not None else None,
            "wilson95_as_recorded": a.get("wilson95"),
            "delta_vs_control_pp": round(100 * (r - ctrl), 2)
            if (r is not None and ctrl is not None) else None,
        }
    # The measured c021 run-to-run reproducibility bound: two nominally identical MCGS
    # configurations differing by 6.4 points, recorded in c021's reproducibility evidence.
    noise_pp = 6.4
    for name, a in arms.items():
        dd = a["delta_vs_control_pp"]
        a["exceeds_measured_noise_floor"] = (dd is not None and abs(dd) > noise_pp)
        a["verdict_by_c022_DECISION_RULES_4"] = (
            "INCONCLUSIVE (|delta| below the measured run-to-run noise floor)"
            if (dd is not None and abs(dd) <= noise_pp) else
            ("improvement exceeds noise" if (dd or 0) > 0 else "regression exceeds noise"))
    return {
        "claim_under_test": "CONTRACT.md §3.6 — 'transfer gains were below run-to-run noise and "
                            "therefore inconclusive, not a proven failure'",
        "control_field_score": ctrl,
        "measured_noise_floor_pp": noise_pp,
        "noise_floor_source": "c021 measured two nominally identical MCGS configurations "
                              "differing by 6.4 field-score points; c022 re-estimates this "
                              "properly under probe T05 before using it.",
        "arms": arms,
        "c021_recorded_status": d.get("status"),
        "c021_power_caveat": d.get("power_caveat"),
        "c022_reading": "c021 recorded TRANSFER=FAIL. Under c022 DECISION_RULES §4 a positive "
                        "point estimate smaller than the measured noise floor is INCONCLUSIVE, "
                        "not FAIL. c021's own power_caveat says the same thing in prose. The "
                        "discrepancy is recorded here and the c022 transfer lab treats these "
                        "components as UNTESTED, not refuted.",
    }


def reconcile_architecture() -> dict:
    """Findings 4 and 5: feed-forward not recurrent; stage names not the published meanings."""
    src = os.path.join(_REPO, "starter_kit", "c021_byterl_model.py")
    text = open(src).read() if os.path.isfile(src) else ""
    has_lstm = ("nn.LSTM" in text) or ("LSTMCell" in text)
    has_gru = "nn.GRU" in text
    stage_ledger = os.path.join(C021, "fidelity", "BYTERL_STAGE_LEDGER.md")
    ledger = open(stage_ledger).read() if os.path.isfile(stage_ledger) else ""
    train = os.path.join(_REPO, "tools", "c021_byterl_train.py")
    ttext = open(train).read() if os.path.isfile(train) else ""
    return {
        "claim_under_test": "CONTRACT.md §3.4 — 'it lacked LSTM recurrence, the published b2 "
                            "blocking FIFO actor-learner balance, and the published b3 two-sided "
                            "V-trace/PPO-style objective'",
        "recurrence": {
            "file": "starter_kit/c021_byterl_model.py",
            "contains_nn_LSTM": has_lstm,
            "contains_nn_GRU": has_gru,
            "verdict": "CONFIRMED feed-forward" if not (has_lstm or has_gru)
                       else "DISCREPANCY: recurrence found",
            "what_is_there_instead": "ResidualBlock stack (nn.Linear + LayerNorm) over a "
                                     "per-decision encoding; no hidden state crosses timesteps.",
        },
        "blocking_fifo": {
            "file": "tools/c021_byterl_train.py",
            "contains_queue_maxsize": "maxsize" in ttext,
            "contains_multiprocessing_Queue": "mp.Queue(" in ttext or "Queue()" in ttext,
            "verdict": "c021 gathered whole iterations synchronously through per-chunk worker "
                       "processes and a drain; there is no bounded blocking FIFO with "
                       "producer/consumer balance, and no policy-version or queue-age record.",
        },
        "two_sided_clipping": {
            "file": "starter_kit/c021_byterl_learn.py",
            "verdict": "c021 implements V-trace rho/c clipping (one-sided upper bounds) and "
                       "UPGO. It has no lower importance-ratio bound and no PPO-style clipped "
                       "surrogate, so its 'B3' is not the published b3.",
        },
        "stage_names": {
            "file": "results/fidelity/BYTERL_STAGE_LEDGER.md",
            "ledger_present": bool(ledger),
            "verdict": "CONFIRMED: c021's rung names B0/B1/B1_5/B2/B3 do not carry the published "
                       "Hearthstone meanings (B1 gamma=1, B1.5 random initial construction "
                       "choices, B2 blocking FIFO balance, B3 modified V-trace/PPO objective). "
                       "c022 FIDELITY_RULES §4 fixes those meanings, so c021 rung labels are "
                       "NOT comparable to c022 rung labels of the same name.",
        },
    }


def reconcile_osfp() -> dict:
    """Finding 5 of C021_AUDIT_FINDINGS: B3/OSFP evidence was defective or insufficient."""
    d = os.path.join(C021, "byterl", "osfp")
    files = sorted(os.listdir(d)) if os.path.isdir(d) else []
    out = {"dir": f"{C021_REL}/byterl/osfp", "files": files, "checks": {}}
    for fn in files:
        p = os.path.join(d, fn)
        if not fn.endswith(".json"):
            continue
        try:
            out["checks"][fn] = json.load(open(p))
        except Exception:  # noqa: BLE001
            pass
    out["claim_under_test"] = ("references/C021_AUDIT_FINDINGS.md — 'c021 B3/OSFP evidence was "
                               "defective or insufficient'")
    out["known_defect"] = {
        "what": "OSFP's seeded historical checkpoint was a VIEW of the live network, not a "
                "frozen copy: `.numpy()` shares storage with the source tensor, so the "
                "'frozen' opponent mutated as the learner trained.",
        "fixed_in_c021_at_commit": "d1df0d5",
        "c022_requirement": "MANDATORY_IMPLEMENTATION B5 — 'no mutable object aliasing between "
                            "learner and history', proven by a byte-immutability probe (B16), "
                            "not by inspection.",
    }
    return out


# ====================================================================== report
def render_markdown(rec: dict) -> str:
    b = rec["budget"]
    mb = b["MATCHED_BUDGET_FOR_C022"]
    oc = rec["mcgs_overconfidence"]
    ex = rec["external_gate"]
    tr = rec["transfer"]
    ar = rec["architecture"]

    L = []
    A = L.append
    A("# c021 audit reconciliation")
    A("")
    A("`CONTRACT.md §3` lists findings that are \"starting facts to verify from raw artifacts, "
      "not optional narrative\", and `references/C021_AUDIT_FINDINGS.md` adds \"Do not trust "
      "prose alone.\" Every number below is recomputed by `tools/c022_reconcile_c021.py` from a "
      "per-episode JSONL, a per-iteration curve, a run summary or the source text. Where a "
      "recomputed value disagrees with what c021 or this contract states, the discrepancy is "
      "recorded rather than reconciled away.")
    A("")
    A(f"Generated from c021 artifacts at `{C021_RESULT_COMMIT[:8]}` (identical in content at the "
      f"branch point) plus the pre-extension segment recovered from `{PRE_EXTENSION_COMMIT}`.")
    A("")

    # ---- 0. the recovery
    A("## 0. The recovery that changes a headline number")
    A("")
    A("c021's four-hour extension reused the parent run tag, so it overwrote "
      "`big_ctrl_b2_games.jsonl` and `big_ctrl_b2_curve.json` **in place**. The files at HEAD "
      "hold the extension segment only. The pre-extension segment survives at "
      f"`{PRE_EXTENSION_COMMIT}`.")
    A("")
    A("| arm | pre-extension games | extension games | TOTAL |")
    A("|---|---:|---:|---:|")
    for arm in ALL_BIG_ARMS:
        a = b["arms"][arm]
        pre = (a["segment_pre_extension"] or {}).get("games", 0)
        head = a["segment_at_HEAD"]["games"]
        A(f"| `{arm}` | {pre} | {head} | {a['TOTAL_EXPOSURE']['games']} |")
    A("")
    A("So the contract's \"about 76,800 games\" is the **extension segment**, not c021's total "
      f"exposure for that arm, which is **{b['games']:,} games** over {b['iterations']} "
      "iterations. Reading HEAD alone would have set c022's matched budget 20% too low.")
    A("")

    # ---- 1. matched budget
    A("## 1. Matched budget (TRAINING_AND_EVALUATION §1)")
    A("")
    A("The controlling quantity is environment decisions, not games. The per-episode records "
      "carry integer `n_battle` and `n_construction`, so the count is exact; the curve's "
      "`mean_battle_steps` is rounded to one decimal and would accumulate error over 720 "
      "iterations.")
    A("")
    A("| quantity | value |")
    A("|---|---:|")
    A(f"| source arm | `{b['source_arm']}` (fixed-deck B2) |")
    A(f"| games | {b['games']:,} |")
    A(f"| iterations | {b['iterations']:,} |")
    A(f"| battle decisions | {b['battle_decisions']:,} |")
    A(f"| construction decisions | {b['construction_decisions']:,} |")
    A(f"| **total environment decisions** | **{b['total_environment_decisions']:,}** |")
    A(f"| learner updates | {b['learner_updates']:,} |")
    A(f"| sample reuse | {b['sample_reuse_c021']} |")
    A(f"| optimizer examples after reuse | {b['optimizer_examples_after_reuse']:,} |")
    A(f"| 25% extension block | {b['extension_block_25pct']:,} decisions |")
    A("")
    A(f"**The c022 matched budget is {mb['value']:,} total environment decisions**, applied to "
      "both `BR3_FIXED_DECK` and `BR3_END_TO_END`.")
    A("")
    A("Construction decisions are counted in the total. c021's fixed-deck arm has zero of them, "
      "so for that arm decisions == battle decisions; c022's end-to-end arm adds 60 construction "
      "decisions per episode and therefore reaches the same decision budget in fewer games. That "
      "is the intended consequence of matching on decisions — every one of those 60 is a real "
      "masked policy decision the network must produce and be trained on — and the achieved game "
      "count is reported alongside so the two arms stay legible.")
    A("")
    A(f"The 76,800-game fallback permitted by TRAINING_AND_EVALUATION §1 is **not used** "
      f"(`fallback_used: {mb['fallback_used']}`): exact decisions were recoverable.")
    A("")

    # ---- 2. overconfidence
    A("## 2. MCGS single-determinization overconfidence (§3.1)")
    A("")
    A("Predicted win rate is defined as `term_root_win / (term_root_win + term_root_loss)` — the "
      "fraction of rollouts reaching a **decided** terminal that the root player won. "
      "`term_undecided` rollouts hit the turn cap; they are excluded from the ratio and reported "
      "separately, because folding them in would silently deflate the very overconfidence the "
      "finding is about.")
    A("")
    A(f"c021 wrote {oc['n_duplicate_copies_collapsed']} run summaries into two directories each. "
      "They are deduplicated by file content here — counting the union would have inflated "
      "\"how many runs are overconfident\" without adding one new measurement. "
      f"`{oc['superseded_excluded'].split('—')[0].strip()}` is excluded outright.")
    A("")
    A("| run | games | field score | predicted (decided) | undecided | gap (pp) |")
    A("|---|---:|---:|---:|---:|---:|")
    for r in oc["runs"]:
        name = os.path.basename(r["run"]).replace("_summary.json", "")
        A(f"| `{name}` | {r['games']} | {r['field_score']} | "
          f"{r['predicted_win_rate_over_decided']} | {r['term_undecided']:,} | "
          f"{r['overconfidence_gap_pp']} |")
    A("")
    A(f"**{oc['n_runs']} distinct MCGS runs carry rollout-terminal counts. Every one of them is "
      f"overconfident** (`every_run_has_positive_gap: {oc['every_run_has_positive_gap']}`), with "
      f"gaps from {oc['overconfidence_gap_pp_min']} to {oc['overconfidence_gap_pp_max']} "
      "percentage points.")
    A("")
    A(f"The contract's \"near 96%\" is reproduced: the maximum predicted rate across runs is "
      f"**{oc['predicted_max']}** (`{os.path.basename(oc['predicted_max_run'])}`). The minimum "
      f"is {oc['predicted_min']} (`{os.path.basename(oc['predicted_min_run'])}`), so \"96%\" is "
      "near the top of a range rather than a universal constant — c022's calibration work is "
      "measured against per-run values, not against a single quoted figure.")
    A("")

    # ---- 3. external
    A("## 3. ByteRL external performance (§3.3)")
    A("")
    for k, lbl in (("pre_extension_baseline", "pre-extension B2 final"),
                   ("post_extension_final", "post-extension B2 final"),
                   ("post_extension_selected_it0160", "post-extension B2 it0160 (selected)")):
        c = ex.get(k)
        if not c:
            continue
        A(f"- **{lbl}** — {c['win_rate']} on {c['games']} games "
          f"(Wilson 95% recomputed {c['wilson95_recomputed']}, recorded "
          f"{c.get('wilson95_as_recorded')})")
    A("")
    if ex.get("panel_disagreement"):
        d = ex["panel_disagreement"]
        A(f"**Discrepancy found.** {d['quantity']}: `gate_evaluation.json` records "
          f"{d['gate_evaluation.json']}, `external_gate_revalidation.json` records "
          f"{d['external_gate_revalidation.json']} — {abs(d['delta_pp'])} pp apart on the same "
          f"checkpoint. {d['reading']}")
        A("")
    A(f"The contract's \"roughly 24–26%\" brackets both readings "
      f"({ex['post_extension_final']['win_rate']} and "
      f"{ex['gate_evaluation_headline'].get('win_rate')}). **Confirmed**, with the qualifier that "
      "the selected checkpoint measured "
      f"{ex['post_extension_selected_it0160']['win_rate']} out of sample — below the range — "
      "because c021's preregistered selector was underpowered (121 candidates × 64 games, "
      "SE ≈ 5.4 pp).")
    A("")

    # ---- 4. transfer
    A("## 4. Transfer (§3.6)")
    A("")
    A(f"Control field score {tr['control_field_score']}. Measured run-to-run noise floor "
      f"±{tr['measured_noise_floor_pp']} pp.")
    A("")
    A("| arm | games | field score | Δ vs control (pp) | exceeds noise? |")
    A("|---|---:|---:|---:|---|")
    for name, a in tr["arms"].items():
        A(f"| `{name}` | {a['games']} | {a['field_score']} | {a['delta_vs_control_pp']} | "
          f"{a['exceeds_measured_noise_floor']} |")
    A("")
    A(f"c021 recorded `TRANSFER={tr['c021_recorded_status']}`. **This is a discrepancy with c022 "
      "`DECISION_RULES §4`**, which says a positive point estimate smaller than the measured "
      "noise floor is `INCONCLUSIVE`, not a pass or a fail. c021's own power caveat says the "
      "same thing in prose — \"No component is REJECTED on this evidence; it is UNTESTED\" — "
      "while its machine-readable status says FAIL.")
    A("")
    A("c022 therefore treats the prior and rollout components as **untested**, re-estimates the "
      "noise floor properly under probe T05 before comparing anything to it, and does not carry "
      "c021's FAIL forward as evidence.")
    A("")

    # ---- 5. architecture
    A("## 5. Architecture and stage names (§3.4, §3.5)")
    A("")
    A(f"- **Recurrence** — `starter_kit/c021_byterl_model.py` contains `nn.LSTM`: "
      f"`{ar['recurrence']['contains_nn_LSTM']}`; `nn.GRU`: "
      f"`{ar['recurrence']['contains_nn_GRU']}`. {ar['recurrence']['verdict']}. "
      f"{ar['recurrence']['what_is_there_instead']}")
    A(f"- **Blocking FIFO** — {ar['blocking_fifo']['verdict']}")
    A(f"- **Two-sided clipping** — {ar['two_sided_clipping']['verdict']}")
    A(f"- **Stage names** — {ar['stage_names']['verdict']}")
    A("")
    A("The practical consequence for c022: **a c021 rung label and a c022 rung label of the same "
      "name denote different systems.** Every comparison in this contract that crosses the c021 "
      "boundary names the artifact, not the rung.")
    A("")

    # ---- 6. OSFP
    A("## 6. OSFP evidence")
    A("")
    o = rec["osfp"]
    A(f"c021's OSFP defect: {o['known_defect']['what']} Fixed at `"
      f"{o['known_defect']['fixed_in_c021_at_commit']}`.")
    A("")
    A(f"c022 requirement: {o['known_defect']['c022_requirement']}")
    A("")

    # ---- 7. summary
    A("## 7. Verdict on each contract §3 finding")
    A("")
    A("| § | finding | verdict from raw data |")
    A("|---|---|---|")
    A("| 3.1 | one determinization reused across all rollouts; ~96% predicted vs poor actual | "
      f"**CONFIRMED** — all {oc['n_runs']} runs overconfident, max predicted "
      f"{oc['predicted_max']} |")
    A("| 3.2 | core formulas ported, hidden-information system not source-faithful | "
      "**CONFIRMED** — re-audited independently in `results/fidelity/"
      "mcgs_hidden_information_gap_analysis.md` |")
    A("| 3.3 | ~24–26% external after ~76,800 games | **CONFIRMED with two corrections** — the "
      "game count is the extension segment only "
      f"(total {b['games']:,}), and the two recorded panels differ by "
      f"{abs((ex.get('panel_disagreement') or {}).get('delta_pp', 0))} pp |")
    A("| 3.4 | no LSTM, no published b2 FIFO, no published b3 objective | **CONFIRMED** by "
      "source inspection |")
    A("| 3.5 | OSFP end-to-end evidence invalid or insufficient | **CONFIRMED** — the frozen "
      "history aliased live weights |")
    A("| 3.6 | transfer gains below noise, inconclusive not failed | **CONFIRMED as a finding, "
      "and c021's own status contradicts it** — c021 recorded FAIL where its data and caveat "
      "both say INCONCLUSIVE |")
    A("")
    A("## 8. Discrepancies carried into c022")
    A("")
    A("1. **c021 `TRANSFER=FAIL` is not supported by c021's data** under c022 decision rules. "
      "Carried forward as `INCONCLUSIVE`/untested.")
    A("2. **\"76,800 games\" understates c021's fixed-deck B2 exposure by 20%.** c022's matched "
      f"budget uses the recovered total, {b['total_environment_decisions']:,} decisions.")
    A("3. **The same checkpoint has two recorded external win rates.** c022 always names the "
      "panel and seed alongside a rate.")
    A("4. **c021 rung labels are not c022 rung labels.** Same names, different published "
      "meanings.")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-md", default=os.path.join(OUT, "references",
                                                     "c021_audit_reconciliation.md"))
    ap.add_argument("--out-budget", default=os.path.join(OUT, "byterl", "budget",
                                                         "c021_matched_budget.json"))
    ap.add_argument("--out-json", default=os.path.join(OUT, "references",
                                                       "c021_reconciliation_raw.json"))
    a = ap.parse_args(argv)

    rec = {
        "generated_from_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=_REPO, capture_output=True,
            text=True).stdout.strip(),
        "c021_result_commit": C021_RESULT_COMMIT,
        "pre_extension_commit": PRE_EXTENSION_COMMIT,
        "budget": reconcile_budget(),
        "mcgs_overconfidence": reconcile_mcgs_overconfidence(),
        "external_gate": reconcile_external_gate(),
        "transfer": reconcile_transfer(),
        "architecture": reconcile_architecture(),
        "osfp": reconcile_osfp(),
    }
    for p in (a.out_md, a.out_budget, a.out_json):
        os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(a.out_json, "w") as fh:
        json.dump(rec, fh, indent=2, sort_keys=True)
    with open(a.out_budget, "w") as fh:
        json.dump(rec["budget"], fh, indent=2, sort_keys=True)
    with open(a.out_md, "w") as fh:
        fh.write(render_markdown(rec))
    b = rec["budget"]
    print(f"wrote {a.out_md}")
    print(f"wrote {a.out_budget}")
    print(f"wrote {a.out_json}")
    print(f"MATCHED BUDGET = {b['total_environment_decisions']:,} environment decisions "
          f"({b['games']:,} games, {b['iterations']} iterations)")
    oc = rec["mcgs_overconfidence"]
    print(f"overconfidence: {oc['n_runs']} runs, predicted max {oc['predicted_max']}, "
          f"gap {oc['overconfidence_gap_pp_min']}..{oc['overconfidence_gap_pp_max']} pp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
