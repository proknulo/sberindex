"""Правила построения рёбер между МО.

Все графы неориентированные, взвешенные, разреженные (kNN), вес ∈ (0, 1].
Для узла i берутся k ближайших по мере сходства соседей; ребро (i, j) существует,
если j ∈ kNN(i) ИЛИ i ∈ kNN(j) (симметризация объединением), вес — максимум двух.

Правила:
  attr     — сходство векторов атрибутов x_{i,t}: гауссово ядро с самонастраивающимся
             масштабом  w_ij = exp(−‖x_i − x_j‖² / (σ_i σ_j)),  σ_i — расстояние до
             7-го соседа (Zelnik-Manor & Perona, 2004). Узлы «похожи по устройству экономики».
  cosine   — косинусное сходство векторов структуры расходов (CLR) — классика для профилей трат.
  corr     — корреляция Пирсона рядов относительных расходов по категориям в окне W мес.:
             «МО ведут себя одинаково во времени».
  lagcorr  — max_{|ℓ|≤L} corr(s_i(t), s_j(t+ℓ)): одна территория опережает другую;
             знак оптимального лага сохраняется для анализа «лидер/последователь».
  dtw      — Dynamic Time Warping расстояние между z-нормированными рядами (полоса Сакоэ–Тибы),
             переводится в сходство тем же гауссовым ядром.
  geo      — автодорожная близость: w_ij = exp(−d_ij / d0) для k ближайших по дороге МО.
  hybrid   — α·W_attr + (1−α)·W_corr: структурное сходство, подкреплённое синхронной динамикой.
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from numba import njit, prange
from sklearn.neighbors import NearestNeighbors


def _symmetrize(rows, cols, vals, n) -> sp.csr_matrix:
    W = sp.csr_matrix((vals, (rows, cols)), shape=(n, n))
    W = W.maximum(W.T)
    W.setdiag(0)
    W.eliminate_zeros()
    return W


def knn_from_similarity(S: np.ndarray, k: int) -> sp.csr_matrix:
    """kNN-граф по плотной матрице сходства (чем больше, тем ближе)."""
    n = S.shape[0]
    S = S.copy()
    np.fill_diagonal(S, -np.inf)
    # устойчивая сортировка: при равных значениях порядок одинаков на любой платформе и версии NumPy
    idx = np.argsort(-S, axis=1, kind="stable")[:, :k]
    rows = np.repeat(np.arange(n), k)
    cols = idx.ravel()
    vals = np.clip(S[rows, cols], 1e-6, None)
    return _symmetrize(rows, cols, vals, n)


def knn_from_distance(D: np.ndarray | None, k: int, sigma_nn: int, X: np.ndarray | None = None) -> sp.csr_matrix:
    """kNN-граф с самонастраивающимся гауссовым ядром по евклидовым расстояниям или матрице D."""
    if X is not None:
        nn = NearestNeighbors(n_neighbors=max(k, sigma_nn) + 1).fit(X)
        dist, idx = nn.kneighbors(X)
    else:
        idx = np.argsort(D, axis=1, kind="stable")[:, : max(k, sigma_nn) + 1]
        dist = np.take_along_axis(D, idx, 1)
    sigma = dist[:, sigma_nn] + 1e-12
    n = dist.shape[0]
    rows = np.repeat(np.arange(n), k)
    cols = idx[:, 1:k + 1].ravel()
    d = dist[:, 1:k + 1].ravel()
    vals = np.exp(-(d ** 2) / (sigma[rows] * sigma[cols]))
    return _symmetrize(rows, cols, np.clip(vals, 1e-6, None), n)


def attr_graph(X_t: np.ndarray, k: int, sigma_nn: int) -> sp.csr_matrix:
    """Основное правило: kNN-граф по признакам месяца с самонастраивающимся гауссовым ядром."""
    return knn_from_distance(None, k, sigma_nn, X=X_t)


def cosine_graph(V: np.ndarray, k: int) -> sp.csr_matrix:
    """kNN-граф по косинусному сходству векторов (CLR-структура трат)."""
    Vn = V / (np.linalg.norm(V, axis=1, keepdims=True) + 1e-12)
    return knn_from_similarity(Vn @ Vn.T, k)


def _znorm(S: np.ndarray) -> np.ndarray:
    """z-нормировка по времени (последняя ось)."""
    m = S.mean(-1, keepdims=True)
    s = S.std(-1, keepdims=True) + 1e-9
    return (S - m) / s


def corr_matrix(S: np.ndarray) -> np.ndarray:
    """S: [N, C, W] — несколько рядов на узел; корреляция = среднее по категориям."""
    Z = _znorm(S)
    N, C, W = Z.shape
    Zf = Z.reshape(N, C * W) / np.sqrt(C * W)
    return Zf @ Zf.T


def lagcorr_matrix(s: np.ndarray, max_lag: int) -> tuple[np.ndarray, np.ndarray]:
    """s: [N, W]. Возвращает (max корреляцию, лаг-аргмакс). lag>0: i опережает j."""
    best = np.full((s.shape[0], s.shape[0]), -np.inf)
    arg = np.zeros_like(best, dtype=np.int8)
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            a, b = s[:, : s.shape[1] - lag], s[:, lag:]
        else:
            a, b = s[:, -lag:], s[:, : s.shape[1] + lag]
        za, zb = _znorm(a), _znorm(b)
        c = za @ zb.T / a.shape[1]
        upd = c > best
        best[upd] = c[upd]
        arg[upd] = lag
    return best, arg


@njit(parallel=True, cache=True)
def _dtw_all(Z, band):
    n, L = Z.shape
    D = np.zeros((n, n))
    for i in prange(n):
        for j in range(i + 1, n):
            acc = np.full((L + 1, L + 1), np.inf)
            acc[0, 0] = 0.0
            for a in range(1, L + 1):
                lo = max(1, a - band)
                hi = min(L, a + band)
                for b in range(lo, hi + 1):
                    cost = (Z[i, a - 1] - Z[j, b - 1]) ** 2
                    m = acc[a - 1, b - 1]
                    if acc[a - 1, b] < m:
                        m = acc[a - 1, b]
                    if acc[a, b - 1] < m:
                        m = acc[a, b - 1]
                    acc[a, b] = cost + m
            D[i, j] = np.sqrt(acc[L, L])
            D[j, i] = D[i, j]
    return D


def dtw_matrix(s: np.ndarray, band: int) -> np.ndarray:
    """Матрица DTW-расстояний между z-нормированными рядами (полоса Сакоэ–Тибы)."""
    return _dtw_all(_znorm(s).astype(np.float64), band)


def geo_graph(road_km: np.ndarray, k: int, scale_km: float) -> sp.csr_matrix:
    """kNN-граф дорожной близости: вес exp(−d / scale_km) для k ближайших по дороге МО."""
    D = np.where(np.isnan(road_km), np.inf, road_km)
    np.fill_diagonal(D, np.inf)
    # дорожные расстояния часто совпадают до 0,1 км: устойчивая сортировка делает выбор соседей детерминированным
    idx = np.argsort(D, axis=1, kind="stable")[:, :k]
    n = D.shape[0]
    rows = np.repeat(np.arange(n), k)
    cols = idx.ravel()
    d = D[rows, cols]
    ok = np.isfinite(d)
    return _symmetrize(rows[ok], cols[ok], np.clip(np.exp(-d[ok] / scale_km), 1e-6, None), n)


def normalize_max(W: sp.csr_matrix) -> sp.csr_matrix:
    """Нормировать веса графа на максимальный вес."""
    return W / W.max() if W.nnz else W


def hybrid(W_attr: sp.csr_matrix, W_dyn: sp.csr_matrix, alpha: float) -> sp.csr_matrix:
    """Гибридный граф: α·W_attr + (1 − α)·W_dyn после нормировки обоих на максимум."""
    return (alpha * normalize_max(W_attr) + (1 - alpha) * normalize_max(W_dyn)).tocsr()


# ---------------------------------------------------------------- ряды для динамических правил
def relative_series(cons: np.ndarray, total: np.ndarray) -> np.ndarray:
    """[N, C+1, T]: log-расходы по 5 категориям и итог относительно медианы МО в том же месяце."""
    L = np.log(np.concatenate([cons[..., :5], total[..., None]], -1) + 1.0)   # [N,T,6]
    L = L - np.median(L, axis=0, keepdims=True)
    return L.transpose(0, 2, 1)


def build_graphs_for_month(rule: str, t: int, X: np.ndarray, rel: np.ndarray, gcfg: dict,
                           road_km: np.ndarray | None = None, struct_idx=None) -> sp.csr_matrix:
    """Граф для месяца t по правилу rule. Динамические правила используют окно [t−W+1, t]."""
    k, snn, W = gcfg["knn"], gcfg["self_tuning_neighbor"], gcfg["corr_window"]
    lo = max(0, t - W + 1)
    hi = max(t + 1, lo + W)          # в первые месяцы окно смотрит вперёд (иначе рядов нет)
    hi = min(hi, rel.shape[-1])
    lo = hi - W if hi - W >= 0 else 0
    if rule == "attr":
        return attr_graph(X[t], k, snn)
    if rule == "cosine":
        return cosine_graph(X[t][:, struct_idx], k)
    if rule == "corr":
        return knn_from_similarity(corr_matrix(rel[:, :, lo:hi]), k)
    if rule == "lagcorr":
        best, _ = lagcorr_matrix(rel[:, -1, lo:hi], gcfg["max_lag"])
        return knn_from_similarity(best, k)
    if rule == "dtw":
        D = dtw_matrix(rel[:, -1, lo:hi], gcfg["dtw_window"])
        return knn_from_distance(D, k, snn)
    if rule == "geo":
        return geo_graph(road_km, k, gcfg["geo_scale_km"])
    if rule == "hybrid":
        return hybrid(attr_graph(X[t], k, snn),
                      knn_from_similarity(corr_matrix(rel[:, :, lo:hi]), k), gcfg["hybrid_alpha"])
    raise ValueError(rule)
