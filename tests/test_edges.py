"""Правила рёбер: графы симметричны, без петель и одинаковы при равных расстояниях на любой платформе."""
import numpy as np

from sbx.network.edges import attr_graph, geo_graph, knn_from_similarity


def test_attr_graph_symmetric_without_loops():
    X = np.random.default_rng(0).normal(size=(60, 5))
    W = attr_graph(X, k=5, sigma_nn=3)
    assert abs(W - W.T).max() < 1e-12
    assert W.diagonal().sum() == 0
    assert W.data.min() > 0 and W.data.max() <= 1


def test_geo_graph_deterministic_with_ties():
    # все расстояния равны: выбор соседей должен определяться порядком, а не реализацией сортировки
    D = np.full((12, 12), 50.0)
    np.fill_diagonal(D, 0)
    W1, W2 = geo_graph(D, k=3, scale_km=150), geo_graph(D.copy(), k=3, scale_km=150)
    assert (W1 != W2).nnz == 0
    assert set(W1[0].indices) >= {1, 2, 3}


def test_knn_from_similarity_keeps_k_strongest():
    S = np.array([[1, .9, .1, .2], [.9, 1, .3, .1], [.1, .3, 1, .8], [.2, .1, .8, 1]], dtype=float)
    W = knn_from_similarity(S, k=1)
    assert W[0, 1] > 0 and W[2, 3] > 0 and W[0, 2] == 0
