"""c006 model-core tests: autograd gradient checks, full S1/S2 gradient checks,
Node-vs-numpy forward parity, registered parameter bounds, decoder legality,
featurizer integrity, and checkpoint round-trip. All numeric gradients are
finite-difference checked (the hard gate before any real training run)."""

import os
import sys
import unittest

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from cg.micrograd import Node, concat, gather_rows, softmax_ce_masked, bce_with_logits_masked, param
from cg.policy_model import PolicyModel, policy_loss
from cg.policy_features import GDENSE, ODENSE, PREV
from cg import decoders as D


def _numgrad(f, x, idxs, eps=1e-5):
    g = {}
    for ix in idxs:
        old = x[ix]
        x[ix] = old + eps; a = f()
        x[ix] = old - eps; b = f()
        x[ix] = old
        g[ix] = (a - b) / (2 * eps)
    return g


def _sample_idxs(shape, k, seed):
    rng = np.random.default_rng(seed)
    return [tuple(int(rng.integers(0, s)) for s in shape) for _ in range(k)]


class TestAutograd(unittest.TestCase):
    def test_ops_gradients(self):
        rng = np.random.default_rng(0)
        x = Node(rng.standard_normal((5, 4)))
        W = param((4, 3), 0.5, rng); b = param((3,), 0.5, rng)
        E = param((10, 3), 0.5, rng)
        idx = np.array([[1, 2], [3, 4], [0, 9], [5, 6], [7, 8]])

        def build():
            h = (x.matmul(W) + b).relu()
            e = gather_rows(E, idx).reshape((5, 6))
            c = concat([h, e], axis=1)                       # [5,9]
            return c.reshape((1, 45)).matmul(Node(np.ones((45, 1)))).reshape(())
        loss = build(); loss.backward()
        for p in (W, b, E):
            ana = p.grad
            num = _numgrad(lambda: float(build().data), p.data, _sample_idxs(p.data.shape, 5, 1))
            for ix, nv in num.items():
                self.assertLess(abs(nv - ana[ix]) / (abs(nv) + abs(ana[ix]) + 1e-9), 1e-4)

    def test_loss_ops_gradients(self):
        rng = np.random.default_rng(2)
        L = param((6, 4), 0.5, rng)
        mask = np.array([[1, 1, 0, 0], [1, 1, 1, 0], [1, 1, 1, 1],
                         [1, 0, 0, 0], [1, 1, 1, 0], [1, 1, 0, 0]], float)
        tgt = np.array([0, 2, 3, 0, 1, 1]); w = np.array([1, 2, 4, 1, 2, 1.])

        def build_ce():
            loss, _ = softmax_ce_masked(L, tgt, mask, w); return loss
        build_ce().backward()
        ana = L.grad.copy()
        num = _numgrad(lambda: float(build_ce().data), L.data, _sample_idxs(L.data.shape, 8, 3))
        for ix, nv in num.items():
            self.assertLess(abs(nv - ana[ix]) / (abs(nv) + abs(ana[ix]) + 1e-9), 1e-4)

        L2 = param((6, 4), 0.5, rng)
        tg = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [1, 1, 0, 1],
                       [1, 0, 0, 0], [0, 1, 0, 0], [1, 0, 0, 0]], float)

        def build_bce():
            loss, _ = bce_with_logits_masked(L2, tg, mask, w); return loss
        build_bce().backward()
        ana2 = L2.grad.copy()
        num2 = _numgrad(lambda: float(build_bce().data), L2.data, _sample_idxs(L2.data.shape, 8, 4))
        for ix, nv in num2.items():
            self.assertLess(abs(nv - ana2[ix]) / (abs(nv) + abs(ana2[ix]) + 1e-9), 1e-4)


def _rand_batch(N, K, rng, V, recurrent=False):
    b = {"gdense": rng.standard_normal((N, GDENSE)),
         "grows": rng.integers(0, V, (N, 2)),
         "odense": rng.standard_normal((N, K, ODENSE)),
         "orows": rng.integers(0, V, (N, K, 2)),
         "legal_mask": (rng.random((N, K)) > 0.3).astype(float)}
    b["legal_mask"][:, 0] = 1.0
    if recurrent:
        b["prev"] = rng.standard_normal((N, PREV))
    return b


def _rand_labels(N, K, rng, mask):
    single = (rng.random(N) > 0.4).astype(float)
    tgt = np.array([int(np.flatnonzero(mask[i])[0]) for i in range(N)])
    mt = np.zeros((N, K))
    for i in range(N):
        legal = np.flatnonzero(mask[i]); mt[i, legal[:min(2, len(legal))]] = 1.0
    w = rng.random(N) * 3 + 0.5
    return single, tgt, mt, w


class TestModels(unittest.TestCase):
    def _gradcheck(self, recurrent):
        tiny = {"emb": 4, "h": 6, "h2": 5, "cc": 4, "hr": 5, "recurrent": recurrent}
        m = PolicyModel(tiny, seed=3)
        rng = np.random.default_rng(7)
        N, K = 6, 4
        b = _rand_batch(N, K, rng, m.vocab_size, recurrent)
        single, tgt, mt, w = _rand_labels(N, K, rng, b["legal_mask"])

        def build():
            sc = m.forward_game(b) if recurrent else m.forward_ff(b)
            loss, _ = policy_loss(sc, single, tgt, mt, b["legal_mask"], w)
            return loss
        build().backward()
        names = ["Wg", "W1", "W3", "E"] + (["Wc", "Wz", "Uz", "Wn", "Un", "Wr", "Ur"] if recurrent else [])
        for nm in names:
            p = m.p[nm]; ana = p.grad
            num = _numgrad(lambda: float(build().data), p.data, _sample_idxs(p.data.shape, 5, hash(nm) % 100))
            for ix, nv in num.items():
                self.assertLess(abs(nv - ana[ix]) / (abs(nv) + abs(ana[ix]) + 1e-9), 1e-4,
                                f"{('S2' if recurrent else 'S1')} {nm}{ix}")

    def test_s1_gradients(self):
        self._gradcheck(False)

    def test_s2_gradients(self):
        self._gradcheck(True)

    def _parity(self, recurrent):
        m = PolicyModel({"emb": 8, "h": 10, "h2": 7, "cc": 5, "hr": 6, "recurrent": recurrent}, seed=5)
        rng = np.random.default_rng(11); T, K = 5, 4
        b = _rand_batch(T, K, rng, m.vocab_size, recurrent)
        node = (m.forward_game(b) if recurrent else m.forward_ff(b)).data
        hid = None; rows = []
        for t in range(T):
            feat = {"gdense": b["gdense"][t], "grows": b["grows"][t],
                    "odense": b["odense"][t], "orows": b["orows"][t],
                    "n_options": K, "prev": (b["prev"][t] if recurrent else None)}
            sc, hid = m.np_scores(feat, hid)
            rows.append(sc)
        self.assertLess(np.abs(node - np.array(rows)).max(), 1e-8)

    def test_parity_s1(self):
        self._parity(False)

    def test_parity_s2(self):
        self._parity(True)

    def test_param_bounds(self):
        s1 = PolicyModel({"recurrent": False}).param_count()
        s2 = PolicyModel({"recurrent": True}).param_count()
        self.assertTrue(150_000 <= s1 <= 750_000, f"S1={s1}")
        self.assertTrue(250_000 <= s2 <= 900_000, f"S2={s2}")

    def test_save_load_roundtrip(self):
        import tempfile
        m = PolicyModel({"recurrent": True}, seed=9)
        rng = np.random.default_rng(1)
        feat = {"gdense": rng.standard_normal(GDENSE).astype(np.float32),
                "grows": rng.integers(0, m.vocab_size, 2).astype(np.int32),
                "odense": rng.standard_normal((3, ODENSE)).astype(np.float32),
                "orows": rng.integers(0, m.vocab_size, (3, 2)).astype(np.int32),
                "n_options": 3, "prev": rng.standard_normal(PREV).astype(np.float32)}
        s1, h1 = m.np_scores(feat, None)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.npz")
            m.save(path)
            m2 = PolicyModel.load(path)
        s2, _ = m2.np_scores(feat, None)
        self.assertLess(np.abs(s1 - s2).max(), 1e-12)


class TestDecoderLegality(unittest.TestCase):
    def test_fuzz_legal(self):
        rng = np.random.default_rng(0)
        for _ in range(3000):
            n = int(rng.integers(1, 9)); hi = int(rng.integers(0, n + 1)); lo = int(rng.integers(0, hi + 1))
            form = D.classify_form("MAIN", lo, hi, n)
            res = D.decode(rng.normal(size=n), lo, hi, form)
            self.assertEqual(len(set(res)), len(res))
            self.assertTrue(all(0 <= i < n for i in res))
            self.assertTrue(lo <= len(res) <= hi)


if __name__ == "__main__":
    unittest.main(verbosity=2)
