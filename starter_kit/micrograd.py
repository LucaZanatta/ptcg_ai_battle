"""Minimal batched reverse-mode autodiff over numpy (c006).

Just enough to define compact feed-forward and GRU policies and train them with
Adam, entirely in numpy — so the trained model's forward pass is the SAME code
used for offline eval, gameplay, and the Kaggle submission (no framework at
inference, no train/serve skew). Ops are vectorized over batch dimensions, so the
graph depth is O(network depth) regardless of batch size; a GRU over a padded
sequence builds O(sequence length) nodes.

Every op registers a backward closure; :func:`Node.backward` runs reverse-mode
accumulation in topological order. Gradients are numerically checked in tests.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np


def _unbroadcast(grad: np.ndarray, shape) -> np.ndarray:
    """Sum ``grad`` down to ``shape`` (reverse of numpy broadcasting)."""
    while grad.ndim > len(shape):
        grad = grad.sum(axis=0)
    for i, s in enumerate(shape):
        if s == 1 and grad.shape[i] != 1:
            grad = grad.sum(axis=i, keepdims=True)
    return grad.reshape(shape)


class Node:
    __slots__ = ("data", "grad", "_backward", "_parents", "requires_grad")

    def __init__(self, data, requires_grad=False, _parents=(), _backward=None):
        self.data = np.asarray(data, dtype=np.float64)
        self.requires_grad = requires_grad or any(p.requires_grad for p in _parents)
        self.grad = None
        self._parents = tuple(_parents)
        self._backward = _backward

    # ---- construction helpers ----
    def _child(self, data, backward):
        return Node(data, _parents=(self,), _backward=backward)

    @staticmethod
    def _binop(a, b, data, backward):
        return Node(data, _parents=(a, b), _backward=backward)

    # ---- elementwise ----
    def __add__(self, other):
        other = other if isinstance(other, Node) else Node(other)
        out = Node._binop(self, other, self.data + other.data, None)

        def bw(g):
            if self.requires_grad:
                self._accum(_unbroadcast(g, self.data.shape))
            if other.requires_grad:
                other._accum(_unbroadcast(g, other.data.shape))
        out._backward = bw
        return out

    def __radd__(self, other):
        return self.__add__(other)

    def __neg__(self):
        out = self._child(-self.data, None)
        out._backward = lambda g: self._accum(-g) if self.requires_grad else None
        return out

    def __sub__(self, other):
        return self.__add__(-other if isinstance(other, Node) else Node(-np.asarray(other, dtype=np.float64)))

    def __mul__(self, other):
        other = other if isinstance(other, Node) else Node(other)
        out = Node._binop(self, other, self.data * other.data, None)

        def bw(g):
            if self.requires_grad:
                self._accum(_unbroadcast(g * other.data, self.data.shape))
            if other.requires_grad:
                other._accum(_unbroadcast(g * self.data, other.data.shape))
        out._backward = bw
        return out

    def __rmul__(self, other):
        return self.__mul__(other)

    def matmul(self, other):
        out = Node._binop(self, other, self.data @ other.data, None)

        def bw(g):
            if self.requires_grad:
                self._accum(g @ other.data.T)
            if other.requires_grad:
                other._accum(self.data.T @ g)
        out._backward = bw
        return out

    def relu(self):
        m = self.data > 0
        out = self._child(self.data * m, None)
        out._backward = lambda g: self._accum(g * m) if self.requires_grad else None
        return out

    def tanh(self):
        t = np.tanh(self.data)
        out = self._child(t, None)
        out._backward = lambda g: self._accum(g * (1 - t * t)) if self.requires_grad else None
        return out

    def sigmoid(self):
        s = 1.0 / (1.0 + np.exp(-self.data))
        out = self._child(s, None)
        out._backward = lambda g: self._accum(g * s * (1 - s)) if self.requires_grad else None
        return out

    def one_minus(self):
        out = self._child(1.0 - self.data, None)
        out._backward = lambda g: self._accum(-g) if self.requires_grad else None
        return out

    def reshape(self, shape):
        old = self.data.shape
        out = self._child(self.data.reshape(shape), None)
        out._backward = lambda g: self._accum(g.reshape(old)) if self.requires_grad else None
        return out

    def broadcast_to(self, shape):
        """Differentiable numpy broadcast; backward sums the broadcast axes back down."""
        old = self.data.shape
        out = self._child(np.broadcast_to(self.data, shape).copy(), None)
        out._backward = lambda g: self._accum(_unbroadcast(g, old)) if self.requires_grad else None
        return out

    def _accum(self, g):
        if self.grad is None:
            self.grad = np.zeros_like(self.data)
        self.grad += g

    def backward(self):
        topo, seen = [], set()

        def build(v):
            if id(v) in seen:
                return
            seen.add(id(v))
            for p in v._parents:
                build(p)
            topo.append(v)
        build(self)
        for v in topo:
            v.grad = None
        self.grad = np.ones_like(self.data)
        for v in reversed(topo):
            if v._backward is not None and v.grad is not None:
                v._backward(v.grad)


# ---- free functions ----

def matmul(a, b):
    return a.matmul(b)


def concat(nodes: List[Node], axis=-1):
    datas = [n.data for n in nodes]
    out = Node(np.concatenate(datas, axis=axis), _parents=tuple(nodes), _backward=None)
    sizes = [d.shape[axis] for d in datas]
    ax = axis if axis >= 0 else datas[0].ndim + axis

    def bw(g):
        idx = 0
        splits = []
        for s in sizes:
            splits.append(idx + s)
            idx += s
        parts = np.split(g, splits[:-1], axis=ax)
        for n, part in zip(nodes, parts):
            if n.requires_grad:
                n._accum(part)
    out._backward = bw
    return out


def gather_rows(table: Node, idx: np.ndarray):
    """table[V,E] -> out[...,E] indexed by integer idx[...]; scatter-add backward."""
    idx = np.asarray(idx, dtype=np.int64)
    out = Node(table.data[idx], _parents=(table,), _backward=None)

    def bw(g):
        if table.requires_grad:
            grad = np.zeros_like(table.data)
            np.add.at(grad, idx.reshape(-1), g.reshape(-1, table.data.shape[1]))
            table._accum(grad)
    out._backward = bw
    return out


def softmax_ce_masked(logits: Node, target_idx, mask, weight=None):
    """Weighted masked softmax cross-entropy. logits[N,K], target_idx[N], mask[N,K]∈{0,1}.

    Rows are averaged with per-row ``weight`` (default 1); masked-out logits get
    -inf so they contribute 0 probability. Returns a scalar Node.
    """
    z = logits.data.copy()
    neg = (mask == 0)
    z[neg] = -1e30
    z = z - z.max(axis=1, keepdims=True)
    ez = np.exp(z)
    p = ez / ez.sum(axis=1, keepdims=True)
    N = logits.data.shape[0]
    w = np.ones(N) if weight is None else np.asarray(weight, dtype=np.float64)
    tgt = np.asarray(target_idx, dtype=np.int64)
    wsum = w.sum() if w.sum() > 0 else 1.0
    logp = np.log(p[np.arange(N), tgt] + 1e-30)
    loss = -(w * logp).sum() / wsum
    out = Node(loss, _parents=(logits,), _backward=None)

    def bw(g):
        if logits.requires_grad:
            grad = p.copy()
            grad[np.arange(N), tgt] -= 1.0
            grad = grad * (w[:, None] / wsum)
            logits._accum(g * grad)
    out._backward = bw
    return out, p


def bce_with_logits_masked(logits: Node, targets, mask, weight=None):
    """Weighted masked binary cross-entropy over legal options. logits/targets/mask [N,K].

    Only legal (mask==1) entries contribute; each row is averaged over its legal
    entries, then rows are averaged with per-row ``weight``.
    """
    m = np.asarray(mask, dtype=np.float64)
    t = np.asarray(targets, dtype=np.float64)
    x = logits.data
    s = 1.0 / (1.0 + np.exp(-x))
    N = x.shape[0]
    w = np.ones(N) if weight is None else np.asarray(weight, dtype=np.float64)
    per_row_n = np.maximum(m.sum(axis=1), 1.0)
    # elementwise bce
    bce = np.log1p(np.exp(-np.abs(x))) + np.maximum(x, 0) - x * t
    row_loss = (bce * m).sum(axis=1) / per_row_n
    wsum = w.sum() if w.sum() > 0 else 1.0
    loss = (w * row_loss).sum() / wsum
    out = Node(loss, _parents=(logits,), _backward=None)

    def bw(g):
        if logits.requires_grad:
            grad = (s - t) * m / per_row_n[:, None]
            grad = grad * (w[:, None] / wsum)
            logits._accum(g * grad)
    out._backward = bw
    return out, s


def reduce_sum(x: Node, axis, keepdims=False):
    """Sum over ``axis`` with broadcast backward (c007 DeepSets set-pooling)."""
    data = np.sum(x.data, axis=axis, keepdims=keepdims)
    out = Node(data, _parents=(x,), _backward=None)

    def bw(g):
        if x.requires_grad:
            gg = g
            if not keepdims:
                gg = np.expand_dims(gg, axis=axis)
            x._accum(np.broadcast_to(gg, x.data.shape).copy())
    out._backward = bw
    return out


def reduce_max(x: Node, axis, keepdims=False):
    """Max over ``axis``; gradient routed to the argmax positions (ties split evenly).

    For masked max-pool, set padded entries to a large negative value before calling
    so they never win (and thus receive no gradient). c007 DeepSets set-pooling.
    """
    mx = np.max(x.data, axis=axis, keepdims=True)
    data = mx if keepdims else np.max(x.data, axis=axis, keepdims=False)
    out = Node(data, _parents=(x,), _backward=None)

    def bw(g):
        if x.requires_grad:
            is_max = (x.data == mx).astype(np.float64)
            counts = np.sum(is_max, axis=axis, keepdims=True)
            gg = g
            if not keepdims:
                gg = np.expand_dims(gg, axis=axis)
            x._accum(is_max / np.maximum(counts, 1.0) * gg)
    out._backward = bw
    return out


def param(shape, scale, rng):
    return Node(rng.standard_normal(shape) * scale, requires_grad=True)
