"""c007 model-core tests: micrograd reduce/broadcast ops, encoder shapes/determinism,
v2 model forward, numerical gradient checks, and checkpoint round-trip. Hard gate
before training (mirrors c006 tests/test_c006_models.py)."""

import gzip
import json
import os
import sys
import unittest

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import micrograd as mg  # noqa: E402
from cg import state_encoder_v2 as enc  # noqa: E402
from cg import policy_model_v2 as pm  # noqa: E402

C006_SEQ = os.path.join(_REPO, "contracts", "c006_distilled_policy_baseline",
                        "results", "artifacts", "sequence_dataset")


def _numgrad(f, x, idxs, eps=1e-5):
    out = []
    for i in idxs:
        old = x[i]
        x[i] = old + eps; a = f()
        x[i] = old - eps; b = f()
        x[i] = old
        out.append((a - b) / (2 * eps))
    return np.array(out)


def _numgrad_kinkaware(f, x, idxs, eps=1e-5, kink_tol=1e-8):
    """Central differences with ReLU-kink detection. Returns (numeric, is_clean) where
    is_clean marks entries whose bracket is locally linear (|f(x+e)+f(x-e)-2f(x)| tiny),
    i.e. where the gradient is actually defined. Kink entries are excluded from the check."""
    num, clean = [], []
    f0 = f()
    for i in idxs:
        old = x[i]
        x[i] = old + eps; a = f()
        x[i] = old - eps; b = f()
        x[i] = old
        num.append((a - b) / (2 * eps))
        clean.append(abs(a + b - 2 * f0) < kink_tol)
    return np.array(num), np.array(clean)


def _load_feats(n=6, split="validation"):
    recs = []
    with gzip.open(os.path.join(C006_SEQ, f"{split}.jsonl.gz"), "rt") as fh:
        for i, line in enumerate(fh):
            recs.append(json.loads(line))
            if i + 1 >= n:
                break
    return [enc.encode(r["observation"], enc.initial_prev_state()) for r in recs], recs


def _collate(feats):
    B = len(feats)
    K = max(f["n_options"] for f in feats)
    b = {}
    for key in ("board_rows", "board_dyn", "hand_rows", "hand_dyn", "hand_mask",
                "disc_rows", "disc_mask", "global"):
        b[key] = np.stack([f[key] for f in feats])
    od = np.zeros((B, K, enc.OPT_DENSE)); orw = np.zeros((B, K, 2), dtype=np.int64)
    om = np.zeros((B, K))
    for i, f in enumerate(feats):
        n = f["n_options"]
        od[i, :f["opt_dense"].shape[0]] = f["opt_dense"]
        orw[i, :f["opt_rows"].shape[0]] = f["opt_rows"]
        om[i, :n] = 1.0
    b["opt_dense"] = od; b["opt_rows"] = orw; b["opt_mask"] = om
    return b, K


class TestMicrogradOps(unittest.TestCase):
    def test_reduce_sum_grad(self):
        rng = np.random.default_rng(0)
        X = rng.standard_normal((3, 4, 5))
        xn = mg.Node(X.copy(), requires_grad=True)
        loss = mg.reduce_sum(mg.reduce_sum(mg.reduce_sum(xn, 1), 1), 0)
        loss.backward()
        self.assertLess(np.abs(xn.grad - 1.0).max(), 1e-9)

    def test_reduce_max_grad(self):
        rng = np.random.default_rng(1)
        X = rng.standard_normal((3, 4, 5)); W = rng.standard_normal((3, 5))

        def f():
            xn = mg.Node(X.copy(), requires_grad=True)
            out = mg.reduce_max(xn, 1)
            return mg.reduce_sum(mg.reduce_sum(out * mg.Node(W), 1), 0), xn
        loss, xn = f()
        loss.backward()
        ng = _numgrad(lambda: (mg.reduce_sum(mg.reduce_sum(mg.reduce_max(mg.Node(X.copy()), 1) * mg.Node(W), 1), 0)).data,
                      X, [(0, 0, 0), (1, 2, 3), (2, 3, 4)])
        ag = np.array([xn.grad[i] for i in [(0, 0, 0), (1, 2, 3), (2, 3, 4)]])
        self.assertLess(np.abs(ag - ng).max(), 1e-6)

    def test_broadcast_to_grad(self):
        rng = np.random.default_rng(2)
        X = rng.standard_normal((3, 1, 4))
        xn = mg.Node(X.copy(), requires_grad=True)
        out = xn.broadcast_to((3, 5, 4))
        loss = mg.reduce_sum(mg.reduce_sum(mg.reduce_sum(out, 2), 1), 0)
        loss.backward()
        self.assertLess(np.abs(xn.grad - 5.0).max(), 1e-9)


class TestEncoder(unittest.TestCase):
    def test_shapes_and_determinism(self):
        feats, recs = _load_feats(5)
        f = feats[0]
        self.assertEqual(f["board_rows"].shape, (enc.N_BOARD,))
        self.assertEqual(f["board_dyn"].shape, (enc.N_BOARD, enc.SLOT_DYN))
        self.assertEqual(f["global"].shape, (enc.GLOBAL,))
        self.assertEqual(f["opt_dense"].shape[1], enc.OPT_DENSE)
        g = enc.encode(recs[0]["observation"], enc.initial_prev_state())
        self.assertTrue(np.array_equal(f["global"], g["global"]))


class TestModelV2(unittest.TestCase):
    def test_param_count_in_band(self):
        m = pm.ModelV2(seed=0)
        self.assertGreaterEqual(m.param_count(), 500_000)
        self.assertLessEqual(m.param_count(), 2_000_000)

    def test_forward_shapes(self):
        feats, _ = _load_feats(6)
        b, K = _collate(feats)
        m = pm.ModelV2(seed=0)
        out = m.forward(b)
        self.assertEqual(out["scores"].data.shape, (6, K))
        self.assertTrue(np.isfinite(out["scores"].data).all())
        self.assertEqual(out["plan_logits"].data.shape[0], 6)

    def test_gradient_numerical(self):
        feats, _ = _load_feats(6)
        b, K = _collate(feats)
        tiny = dict(D=8, Hs=6, BV=10, Hh=6, HV=6, Hd=5, DV=5, GH=8, CTX=10, OH=8, OH2=8, SH=8)
        m = pm.ModelV2(tiny, seed=3, aux=True)
        tgt = np.zeros(6, dtype=np.int64)
        val = np.array([1.0, 0.0, 0.5, 1.0, 0.0, 0.5])

        def loss_fn():
            o = m.forward(b)
            la, _ = mg.softmax_ce_masked(o["scores"], tgt, b["opt_mask"])
            lv, _ = mg.bce_with_logits_masked(o["value_logit"].reshape((6, 1)),
                                              val.reshape((6, 1)), np.ones((6, 1)))
            return la + lv
        loss = loss_fn()
        loss.backward()
        rng = np.random.default_rng(11)
        for name in ("ctx", "score", "opt", "sem", "glob", "board", "handv", "emb"):
            W = m.p[name]
            # probe many random entries; assert only on entries whose bracket is locally
            # linear (gradient defined). ReLU kinks are excluded, not smoothed over.
            r = rng.integers(0, W.data.shape[0], 40)
            c = rng.integers(0, W.data.shape[1], 40)
            idxs = list(zip(r.tolist(), c.tolist()))
            ag = np.array([W.grad[i] for i in idxs])
            ng, clean = _numgrad_kinkaware(lambda: loss_fn().data, W.data, idxs)
            self.assertGreaterEqual(int(clean.sum()), 3, f"too few clean probes for {name}")
            err = np.abs(ag - ng)[clean]
            self.assertLess(float(err.max()), 1e-5, f"grad mismatch {name}")

    def test_checkpoint_roundtrip(self):
        import tempfile
        feats, _ = _load_feats(4)
        b, _ = _collate(feats)
        m = pm.ModelV2(seed=7)
        s0 = m.score_np(b)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "m.npz")
            m.save(p)
            m2 = pm.ModelV2.load(p)
        s1 = m2.score_np(b)
        self.assertLess(np.abs(s0 - s1).max(), 1e-12)
        self.assertEqual(m.param_count(), m2.param_count())


if __name__ == "__main__":
    unittest.main()
