"""Отслеживание кластеров во времени.

Два подхода, которые сравниваются в отчёте:

1. Эволюционная кластеризация (Chakrabarti, Kumar, Tomkins, KDD 2006), вариант для k-means.
   Центры месяца t инициализируются центрами месяца t−1, после сходимости сглаживаются:
       c_t ← α·c_t + (1−α)·c_{t−1},
   и точки переназначаются к ближайшему сглаженному центру. Это минимизирует
       α·SnapshotCost(C_t, X_t) + (1−α)·HistoryCost(C_t, C_{t−1}):
   кластеры следуют за данными, но не «дрожат» от шума. Метки согласованы по построению.

2. Независимые снимки + сопоставление (Greene, Doyle, Cunningham, ASONAM 2010).
   Кластеры соседних месяцев сопоставляются по мере Жаккара J(A,B) = |A∩B|/|A∪B|,
   фиксируются события: продолжение, слияние, разделение, рождение, исчезновение.

Метрики динамики: ARI/NMI между соседними месяцами, доля МО, сменивших кластер,
число переходов на МО, матрица переходов.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

from .static import kmeans, match_labels, spectral


def evolutionary_kmeans(Xs: list[np.ndarray], k: int, alpha: float, seed: int, n_init: int = 20,
                        init_centers: np.ndarray | None = None):
    """Эволюционный k-means (Chakrabarti et al., 2006): центры месяца сглаживаются с прошлыми."""
    labels, centers = [], []
    prev = init_centers
    for X in Xs:
        if prev is None:
            lab, c = kmeans(X, k, seed, n_init)
        else:
            lab, c = kmeans(X, k, seed, init=prev)
            c = alpha * c + (1 - alpha) * prev
            d = ((X[:, None, :] - c[None]) ** 2).sum(-1)
            lab = d.argmin(1)
        labels.append(lab)
        centers.append(c)
        prev = c
    return np.array(labels), np.array(centers)


def evolutionary_spectral(Ws, k: int, alpha: float, seed: int):
    """Эволюционная спектральная кластеризация: PCQ (Chi et al., KDD 2007) с экспоненциальной памятью.

    PCQ требует, чтобы разбиение месяца t было хорошим и для текущей сети, и для истории:
        Cost_t = α·NC(C_t | W_t) + (1−α)·NC(C_t | W̃_{t−1}),
    что решается спектральной кластеризацией сглаженной матрицы
        W̃_t = α·W_t + (1−α)·W̃_{t−1}        (W̃_0 = W_0).
    Экспоненциальная память (вместо одного прошлого месяца) гасит перестройки границ, не
    подкреплённые данными, а сезонные сдвиги, повторяющиеся несколько месяцев, сохраняет.
    Метки согласуются с предыдущим месяцем венгерским алгоритмом.
    """
    L, Wt = [], None
    for t, W in enumerate(Ws):
        Wt = W if t == 0 else (alpha * W + (1 - alpha) * Wt).tocsr()
        lab = spectral(Wt, k, seed)
        L.append(lab if t == 0 else match_labels(L[-1], lab))
    return np.array(L)


def temporal_metrics(L: np.ndarray) -> dict:
    """L: [T, N] метки."""
    ari = [adjusted_rand_score(L[t], L[t + 1]) for t in range(len(L) - 1)]
    nmi = [normalized_mutual_info_score(L[t], L[t + 1]) for t in range(len(L) - 1)]
    switch = [(L[t] != L[t + 1]).mean() for t in range(len(L) - 1)]
    n_switch = (L[1:] != L[:-1]).sum(0)
    return {"ARI_consecutive": float(np.mean(ari)), "NMI_consecutive": float(np.mean(nmi)),
            "switch_rate": float(np.mean(switch)), "never_switch_share": float((n_switch == 0).mean()),
            "ARI_first_last": float(adjusted_rand_score(L[0], L[-1])),
            "ari_series": ari, "switch_series": switch}


def transition_matrix(L: np.ndarray) -> np.ndarray:
    """Матрица переходов между кластерами по всем парам соседних месяцев (число МО)."""
    k = L.max() + 1
    M = np.zeros((k, k), dtype=int)
    for t in range(len(L) - 1):
        np.add.at(M, (L[t], L[t + 1]), 1)
    return M


def events(L_prev: np.ndarray, L_next: np.ndarray, theta: float) -> list[dict]:
    """События между двумя разбиениями (Greene et al., 2010): продолжение, слияние, разделение, рождение, исчезновение."""
    A = [set(np.where(L_prev == a)[0]) for a in np.unique(L_prev)]
    B = [set(np.where(L_next == b)[0]) for b in np.unique(L_next)]
    ak, bk = np.unique(L_prev), np.unique(L_next)
    out = []
    for i, a in enumerate(A):
        succ = [j for j, b in enumerate(B) if len(a & b) / len(b) >= theta]
        if not any(len(a & b) / len(a) >= theta for b in B) and len(succ) < 2:
            out.append({"type": "исчезновение/распад", "from": [int(ak[i])], "to": []})
        if len(succ) >= 2:
            out.append({"type": "разделение", "from": [int(ak[i])], "to": [int(bk[j]) for j in succ]})
    for j, b in enumerate(B):
        pred = [i for i, a in enumerate(A) if len(a & b) / len(a) >= theta]
        if len(pred) >= 2:
            out.append({"type": "слияние", "from": [int(ak[i]) for i in pred], "to": [int(bk[j])]})
        if not any(len(a & b) / len(b) >= theta for a in A):
            out.append({"type": "рождение", "from": [], "to": [int(bk[j])]})
    return out


def event_log(L: np.ndarray, months: list[str], theta: float) -> pd.DataFrame:
    """Журнал событий кластеров по всем соседним месяцам."""
    rows = []
    for t in range(len(L) - 1):
        for e in events(L[t], L[t + 1], theta):
            rows.append({"month_from": months[t], "month_to": months[t + 1], **e})
    return pd.DataFrame(rows, columns=["month_from", "month_to", "type", "from", "to"])
