"""Методы кластеризации атрибутированной сети.

  kmeans           — только атрибуты (без графа); базовая линия
  ward             — агломеративная кластеризация Уорда по атрибутам
  spectral         — спектральная кластеризация по графу (Ng–Jordan–Weiss), только структура
  leiden           — оптимизация модулярности (Traag et al., 2019), разрешение γ подбирается
                     бисекцией под заданное k
  agc              — Adaptive Graph Convolution (Zhang et al., IJCAI 2019): низкочастотный
                     графовый фильтр X̄ = ((I + S)/2)^p X, S = D^{-1/2}(W+I)D^{-1/2}, затем k-means.
                     Атрибуты «сглаживаются» по рёбрам — узел описывается собой и соседями,
                     т.е. метод использует И атрибуты, И структуру сети.
  temporal_leiden  — мультислойный Leiden (Mucha et al., 2010): слои-месяцы, каждый МО
                     связан сам с собой в соседних месяцах с весом ω; метки согласованы во времени.
"""
from __future__ import annotations

import igraph as ig
import leidenalg as la
import numpy as np
import scipy.sparse as sp
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import AgglomerativeClustering, KMeans, SpectralClustering


def to_igraph(W: sp.csr_matrix) -> ig.Graph:
    U = sp.triu(W, k=1).tocoo()
    g = ig.Graph(n=W.shape[0], edges=list(zip(U.row.tolist(), U.col.tolist())), directed=False)
    g.es["weight"] = U.data.tolist()
    return g


def kmeans(X, k, seed, n_init=20, init=None):
    if init is not None:
        km = KMeans(k, init=init, n_init=1, random_state=seed).fit(X)
    else:
        km = KMeans(k, n_init=n_init, random_state=seed).fit(X)
    return km.labels_, km.cluster_centers_


def ward(X, k):
    return AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(X)


def spectral(W, k, seed):
    A = W.copy()
    # изолированные вершины ломают спектральное вложение — добавляем слабую петлю
    A = A + sp.identity(A.shape[0]) * 1e-6
    return SpectralClustering(k, affinity="precomputed", random_state=seed,
                              assign_labels="cluster_qr").fit_predict(A)


def _leiden_at(g, gamma, seed):
    p = la.find_partition(g, la.RBConfigurationVertexPartition, weights="weight",
                          resolution_parameter=gamma, seed=seed, n_iterations=-1)
    return np.array(p.membership)


def _merge_small(labels, W, min_size):
    """Мелкие сообщества (< min_size) присоединяются к соседу с максимальным суммарным весом."""
    labels = labels.copy()
    while True:
        ks, cnt = np.unique(labels, return_counts=True)
        small = ks[cnt < min_size]
        if len(small) == 0 or len(ks) <= 2:
            break
        c = small[np.argmin(cnt[cnt < min_size])]
        idx = np.where(labels == c)[0]
        w = np.asarray(W[idx].sum(0)).ravel()
        w_by = {kk: w[labels == kk].sum() for kk in ks if kk != c}
        labels[idx] = max(w_by, key=w_by.get)
    _, labels = np.unique(labels, return_inverse=True)
    return labels


def leiden(W, k, seed, min_size=10):
    """Подбор γ бисекцией: число сообществ (после слияния мелких) ≈ k."""
    g = to_igraph(W)
    lo, hi = 0.01, 10.0
    best = None
    for _ in range(30):
        gamma = np.sqrt(lo * hi)
        lab = _merge_small(_leiden_at(g, gamma, seed), W, min_size)
        n = len(np.unique(lab))
        if best is None or abs(n - k) < abs(best[1] - k):
            best = (lab, n, gamma)
        if n == k:
            break
        if n < k:
            lo = gamma
        else:
            hi = gamma
    return best[0], best[2]


def agc_filter(X, W, p):
    n = W.shape[0]
    A = W + sp.identity(n)
    d = np.asarray(A.sum(1)).ravel()
    Dm = sp.diags(1 / np.sqrt(d))
    S = Dm @ A @ Dm
    G = (sp.identity(n) + S) / 2
    Xf = X.copy()
    for _ in range(p):
        Xf = G @ Xf
    return Xf


def agc(X, W, k, p, seed, n_init=20, init=None):
    Xf = agc_filter(X, W, p)
    lab, cents = kmeans(Xf, k, seed, n_init, init)
    return lab, cents, Xf


def temporal_leiden(Ws, gamma, omega, seed):
    """Мультислойное разбиение; возвращает [T, N] меток, согласованных во времени."""
    graphs = []
    for W in Ws:
        g = to_igraph(W)
        g.vs["id"] = list(range(W.shape[0]))
        graphs.append(g)
    membership, _ = la.find_partition_temporal(graphs, la.RBConfigurationVertexPartition,
                                               interslice_weight=omega, vertex_id_attr="id",
                                               weight_attr="weight", resolution_parameter=gamma,
                                               seed=seed, n_iterations=2)
    return np.array(membership)


def match_labels(prev, cur, k_cur=None):
    """Перенумерация cur так, чтобы метки максимально совпадали с prev (венгерский алгоритм)."""
    kp, kc = prev.max() + 1, cur.max() + 1
    M = np.zeros((kc, max(kp, kc)))
    for a, b in zip(cur, prev):
        M[a, b] += 1
    r, c = linear_sum_assignment(-M)
    mapping = dict(zip(r, c))
    nxt = max(kp, kc)
    for a in range(kc):
        if a not in mapping:
            mapping[a] = nxt
            nxt += 1
    return np.array([mapping[a] for a in cur])
