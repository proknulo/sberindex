"""Внутренние индексы качества кластеризации (ICVI).

Пространство атрибутов (точки x_i):
  SW     — средний силуэт (Rousseeuw, 1987), ∈ [−1, 1], ↑ лучше
  CH     — индекс Калински–Харабаша (1974), ↑ лучше
  S_Dbw  — Halkidi & Vazirgiannis (2001): Scat + Dens_bw, ↓ лучше

Граф (веса w_uv):
  AVI    — Average Isolability (Biswas et al.): среднее по кластерам
           I(C) = Σ_{u,v∈C} w_uv / (Σ_{u,v∈C} w_uv + Σ_{u∈C, v∉C} w_uv), ↑ лучше
  AVU    — Average Unifiability: среднее по парам кластеров
           U(C_i,C_j) = w(C_i,C_j) / (cut(C_i) + cut(C_j) − w(C_i,C_j)), ↓ лучше
  MQ     — Modularization Quality (Mancoridis et al., 1998):
           (1/k)Σ A_i − (2/(k(k−1)))Σ_{i<j} E_ij,  A_i = μ_i/N_i²,  E_ij = ε_ij/(2N_iN_j), ↑ лучше
  Q      — модулярность Ньюмана (дополнительно), ↑ лучше
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from sklearn.metrics import calinski_harabasz_score, silhouette_score


def s_dbw(X: np.ndarray, labels: np.ndarray) -> float:
    ks = np.unique(labels)
    k = len(ks)
    cents = np.array([X[labels == c].mean(0) for c in ks])
    var_all = np.linalg.norm(X.var(0))
    sig = [np.linalg.norm(X[labels == c].var(0)) for c in ks]
    scat = np.mean(sig) / var_all
    stdev = np.sqrt(np.sum(sig)) / k

    def density(pts, u):
        return np.sum(np.linalg.norm(pts - u, axis=1) <= stdev)

    dens = 0.0
    for a in range(k):
        for b in range(k):
            if a == b:
                continue
            pts = X[(labels == ks[a]) | (labels == ks[b])]
            u = (cents[a] + cents[b]) / 2
            m = max(density(pts, cents[a]), density(pts, cents[b]))
            dens += density(pts, u) / m if m > 0 else 0.0
    return float(scat + dens / (k * (k - 1)))


def _block_weights(W: sp.csr_matrix, labels: np.ndarray):
    ks, lab = np.unique(labels, return_inverse=True)
    k = len(ks)
    P = sp.csr_matrix((np.ones(len(lab)), (np.arange(len(lab)), lab)), shape=(len(lab), k))
    B = (P.T @ W @ P).toarray()            # B[i,j] = Σ_{u∈Ci, v∈Cj} w_uv (упорядоченные пары)
    sizes = np.bincount(lab, minlength=k).astype(float)
    return B, sizes


def graph_indices(W: sp.csr_matrix, labels: np.ndarray) -> dict:
    B, n = _block_weights(W, labels)
    k = len(n)
    intra = np.diag(B)
    cut = B.sum(1) - intra
    iso = intra / np.maximum(intra + cut, 1e-12)
    uni = []
    for i in range(k):
        for j in range(i + 1, k):
            den = cut[i] + cut[j] - B[i, j]
            uni.append(B[i, j] / den if den > 0 else 0.0)
    A = intra / n ** 2
    E = [B[i, j] / (2 * n[i] * n[j]) for i in range(k) for j in range(i + 1, k)]
    mq = A.mean() - (np.mean(E) if E else 0.0)
    m2 = B.sum()
    Q = float(np.sum(intra / m2 - (B.sum(1) / m2) ** 2))
    return {"AVI": float(iso.mean()), "AVU": float(np.mean(uni)) if uni else 0.0, "MQ": float(mq), "Q": Q}


def all_indices(X: np.ndarray, W: sp.csr_matrix, labels: np.ndarray, seed: int = 0) -> dict:
    if len(np.unique(labels)) < 2:
        return {"SW": np.nan, "CH": np.nan, "S_Dbw": np.nan, "AVI": np.nan, "AVU": np.nan, "MQ": np.nan, "Q": np.nan}
    res = {"SW": float(silhouette_score(X, labels, random_state=seed)),
           "CH": float(calinski_harabasz_score(X, labels)),
           "S_Dbw": s_dbw(X, labels)}
    res.update(graph_indices(W, labels))
    return res


# Направление «лучше» для ранжирования методов
HIGHER_BETTER = {"SW": True, "CH": True, "S_Dbw": False, "AVI": True, "AVU": False, "MQ": True, "Q": True}
