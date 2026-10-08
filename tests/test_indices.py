"""Тесты индексов качества (AVI, AVU, MQ, S_Dbw) на графах и облаках точек с известным ответом."""
import numpy as np
import scipy.sparse as sp

from sbx.evaluation.indices import graph_indices, s_dbw


def two_cliques(bridge=0.0):
    W = np.zeros((6, 6))
    W[:3, :3] = 1
    W[3:, 3:] = 1
    np.fill_diagonal(W, 0)
    W[2, 3] = W[3, 2] = bridge
    return sp.csr_matrix(W)


def test_perfect_partition():
    r = graph_indices(two_cliques(), np.array([0, 0, 0, 1, 1, 1]))
    assert r["AVI"] == 1.0 and r["AVU"] == 0.0
    # MQ: A_i = 6/9 (упорядоченные пары внутри), E = 0
    assert abs(r["MQ"] - 6 / 9) < 1e-12
    assert abs(r["Q"] - 0.5) < 1e-12


def three_cliques():
    W = np.zeros((9, 9))
    for a in range(3):
        W[3 * a:3 * a + 3, 3 * a:3 * a + 3] = 1
    np.fill_diagonal(W, 0)
    for i, j in [(2, 3), (5, 6), (8, 0)]:
        W[i, j] = W[j, i] = 1
    return sp.csr_matrix(W)


def test_true_partition_beats_shuffled():
    good = graph_indices(three_cliques(), np.repeat([0, 1, 2], 3))
    bad = graph_indices(three_cliques(), np.tile([0, 1, 2], 3))
    assert good["AVI"] > bad["AVI"] and good["AVU"] <= bad["AVU"] and good["MQ"] > bad["MQ"]


def test_unifiability_degenerate_for_two_clusters():
    # при k=2 разрез каждого кластера равен весу между ними => U = 1 для любого разбиения
    assert graph_indices(two_cliques(1.0), np.array([0, 0, 0, 1, 1, 1]))["AVU"] == 1.0


def test_sdbw_prefers_separated():
    rng = np.random.default_rng(0)
    X = np.vstack([rng.normal(0, .3, (50, 2)), rng.normal(5, .3, (50, 2))])
    true = np.repeat([0, 1], 50)
    rand = rng.integers(0, 2, 100)
    assert s_dbw(X, true) < s_dbw(X, rand)
