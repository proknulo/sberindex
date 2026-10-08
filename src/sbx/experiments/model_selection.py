"""Выбор модели: число кластеров k, правило построения рёбер и метод кластеризации.

  select_k            ICVI и устойчивость на подвыборках по k        → results/k_selection.csv
  compare_edge_rules  7 правил рёбер: структура сети и качество       → results/edge_rules*.csv
  compare_methods     9 методов на всех 24 месяцах + бутстрэп         → results/methods.csv
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.metrics import adjusted_rand_score

from ..clustering import evolutionary as Dy
from ..clustering import static as C
from ..config import log
from ..evaluation.indices import HIGHER_BETTER, all_indices
from ..network import edges as G
from .context import Context

EDGE_RULES = ["attr", "cosine", "corr", "lagcorr", "dtw", "geo", "hybrid"]
STATIC_METHODS = ["kmeans", "ward", "spectral", "leiden", "agc"]
ICVI = ["SW", "CH", "S_Dbw", "AVI", "AVU", "MQ"]


def run_method(name: str, X: np.ndarray, W: sp.csr_matrix, k: int, cfg: dict, seed: int) -> np.ndarray:
    """Запустить один статичный метод кластеризации по имени, вернуть метки."""
    cc = cfg["clustering"]
    if name == "kmeans":
        return C.kmeans(X, k, seed, cc["n_init"])[0]
    if name == "ward":
        return C.ward(X, k)
    if name == "spectral":
        return C.spectral(W, k, seed)
    if name == "leiden":
        return C.leiden(W, k, seed)[0]
    if name == "agc":
        return C.agc(X, W, k, cc["agc_power"], seed, cc["n_init"])[0]
    raise ValueError(name)


def rank_table(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    """Средний ранг методов по набору индексов с учётом направления «лучше»."""
    r = pd.DataFrame({c: df[c].rank(ascending=not HIGHER_BETTER[c]) for c in cols})
    return r.mean(1)


def graph_stats(W: sp.csr_matrix, mo: pd.DataFrame, road_km: np.ndarray | None) -> dict:
    """Описание структуры сети: плотность, степень, кластеризация, пространственная связность."""
    g = C.to_igraph(W)
    U = W.tocoo()
    same_region = (mo.region_code.to_numpy()[U.row] == mo.region_code.to_numpy()[U.col])
    same_type = (mo.mo_type.to_numpy()[U.row] == mo.mo_type.to_numpy()[U.col])
    d = road_km[U.row, U.col] if road_km is not None else np.array([np.nan])
    comps = g.connected_components()
    return {"edges": int(W.nnz // 2), "mean_degree": float(W.nnz / W.shape[0]),
            "mean_weight": float(U.data.mean()),
            "transitivity": float(g.transitivity_avglocal_undirected(mode="zero")),
            "components": len(comps), "giant_share": float(max(comps.sizes()) / W.shape[0]),
            "share_same_region": float(same_region.mean()), "share_same_type": float(same_type.mean()),
            "median_edge_km": float(np.nanmedian(d))}


def _subsamples(ctx: Context, n: int) -> list[np.ndarray]:
    """n случайных подвыборок МО долей clustering.subsample_frac (отсортированные индексы)."""
    N = len(ctx.mo)
    rng = np.random.default_rng(ctx.seed)
    frac = ctx.cfg["clustering"].get("subsample_frac", 0.8)
    return [np.sort(rng.choice(N, int(frac * N), replace=False)) for _ in range(n)]


def select_k(ctx: Context) -> pd.DataFrame:
    """ICVI и устойчивость по k в опорном месяце.

    ICVI почти монотонны по k (типично для континуальных социально-экономических данных),
    поэтому дополнительно используется критерий устойчивости (Ben-Hur et al., 2002):
    средний ARI между разбиением всей выборки и разбиениями подвыборок.
    """
    log("выбор k")
    cfg, seed, Xr = ctx.cfg, ctx.seed, ctx.Xr
    Wm = ctx.graph(cfg["graph"]["main_rule"], ctx.ref_t)
    boots = _subsamples(ctx, cfg["clustering"].get("k_selection_bootstrap", 20))
    rows = []
    for kk in range(cfg["clustering"]["k_range"][0], cfg["clustering"]["k_range"][1] + 1):
        for m in ["kmeans", "agc", "spectral"]:
            lab = run_method(m, Xr, Wm, kk, cfg, seed)
            st = [adjusted_rand_score(lab[b], run_method(m, Xr[b], Wm[b][:, b], kk, cfg, seed + i + 1))
                  for i, b in enumerate(boots)]
            rows.append({"k": kk, "method": m, **all_indices(Xr, Wm, lab, seed),
                         "stability": float(np.mean(st)), "stability_sd": float(np.std(st))})
    ksel = pd.DataFrame(rows)
    ksel.to_csv(ctx.out / "k_selection.csv", index=False)
    return ksel


def compare_edge_rules(ctx: Context) -> tuple[np.ndarray, np.ndarray]:
    """Сравнить 7 правил рёбер в опорном месяце; вернуть матрицы лучших лаговых корреляций и лагов.

    Для каждого правила — свойства графа (доля рёбер в регионе, медиана ребра, транзитивность) и
    индексы качества трёх методов; индексы на графе считаются и на собственном графе правила, и на
    атрибутном графе (столбцы @attr). Дополнительно — ARI между разбиениями AGC на разных графах.
    """
    log("сравнение правил рёбер")
    cfg, seed, Xr, k = ctx.cfg, ctx.seed, ctx.Xr, ctx.k
    rows, parts = [], {}
    W_ref_attr = ctx.graph("attr", ctx.ref_t)
    for rule in EDGE_RULES:
        t0 = time.time()
        W = ctx.graph(rule, ctx.ref_t)
        st = graph_stats(W, ctx.mo, ctx.ds.road_km)
        for m in ["spectral", "leiden", "agc"]:
            lab = run_method(m, Xr, W, k, cfg, seed)
            parts[(rule, m)] = lab
            ind = all_indices(Xr, W, lab, seed)
            ind_common = {f"{kk}@attr": v for kk, v in all_indices(Xr, W_ref_attr, lab, seed).items()
                          if kk in ("AVI", "AVU", "MQ", "Q")}
            rows.append({"rule": rule, "method": m, **st, **ind, **ind_common, "sec": time.time() - t0})
        log(f"  {rule}: {st['edges']} рёбер")
    pd.DataFrame(rows).to_csv(ctx.out / "edge_rules.csv", index=False)
    ari = pd.DataFrame([[adjusted_rand_score(parts[(a, "agc")], parts[(b, "agc")]) for b in EDGE_RULES] for a in EDGE_RULES],
                       index=EDGE_RULES, columns=EDGE_RULES)
    ari.to_csv(ctx.out / "edge_rules_ari_agc.csv")

    # лаговая структура «кто опережает кого» — для отчёта и итоговых выгрузок
    best, lag = G.lagcorr_matrix(ctx.rel[:, -1, :], cfg["graph"]["max_lag"])
    np.save(ctx.proc / "lagcorr_best.npy", best.astype(np.float32))
    np.save(ctx.proc / "lagcorr_lag.npy", lag)
    return best, lag


def _evolutionary_labels(ctx: Context, Ws: list[sp.csr_matrix], labels: dict) -> None:
    """Добавить в labels эволюционные методы и темпоральный Leiden."""
    cfg, seed, X, k = ctx.cfg, ctx.seed, ctx.X, ctx.k
    T = len(ctx.months)
    alpha = cfg["dynamics"]["evolutionary_alpha"]
    Xf = [C.agc_filter(X[t], Ws[t], cfg["clustering"]["agc_power"]) for t in range(T)]
    labels["agc_evolutionary"], _ = Dy.evolutionary_kmeans(Xf, k, alpha, seed, cfg["clustering"]["n_init"])
    labels["kmeans_evolutionary"], _ = Dy.evolutionary_kmeans(list(X), k, alpha, seed, cfg["clustering"]["n_init"])
    labels["spectral_evolutionary"] = Dy.evolutionary_spectral(Ws, k, alpha, seed)
    # темпоральный Leiden: разрешение γ подбирается по опорному месяцу
    _, gamma = C.leiden(Ws[ctx.ref_t], k, seed)
    TL = C.temporal_leiden(Ws, gamma, cfg["clustering"]["leiden_interslice"], seed)
    TL = np.array([C._merge_small(TL[t], Ws[t], 10) for t in range(T)])
    labels["temporal_leiden"] = np.array([TL[0]] + [C.match_labels(TL[t - 1], TL[t]) for t in range(1, T)])
    log("  temporal_leiden")


def compare_methods(ctx: Context) -> dict[str, np.ndarray]:
    """Разбиения всех 9 методов по 24 месяцам, их средние ICVI, метрики динамики и бутстрэп-устойчивость.

    Возвращает метки [T, N] каждого метода (для итоговой модели).
    """
    log("сравнение методов по месяцам")
    cfg, seed, X, k = ctx.cfg, ctx.seed, ctx.X, ctx.k
    T = len(ctx.months)
    Ws = ctx.main_graphs()
    labels = {}
    for m in STATIC_METHODS:
        L = []
        for t in range(T):
            lab = run_method(m, X[t], Ws[t], k, cfg, seed)
            L.append(lab if t == 0 else C.match_labels(L[-1], lab))
        labels[m] = np.array(L)
        log(f"  {m}")
    _evolutionary_labels(ctx, Ws, labels)

    rows = []
    for m, L in labels.items():
        per_t = pd.DataFrame([all_indices(X[t], Ws[t], L[t], seed) for t in range(T)])
        tm = Dy.temporal_metrics(L)
        rows.append({"method": m, **per_t.mean().to_dict(),
                     "k_mean": float(np.mean([len(np.unique(l)) for l in L])),
                     **{kk: v for kk, v in tm.items() if not kk.endswith("series")}})
    meth = pd.DataFrame(rows)

    # устойчивость к подвыборке узлов в опорном месяце; эволюционные версии наследуют её у статичных
    stab = {m: [] for m in STATIC_METHODS}
    for b, idx in enumerate(_subsamples(ctx, cfg["clustering"]["stability_bootstrap"])):
        Wb = Ws[ctx.ref_t][idx][:, idx]
        for m in stab:
            lab = run_method(m, ctx.Xr[idx], Wb, k, cfg, seed + b + 1)
            stab[m].append(adjusted_rand_score(labels[m][ctx.ref_t][idx], lab))
    meth["bootstrap_ARI"] = meth.method.map({m: float(np.mean(v)) for m, v in stab.items()})
    for evo, base in [("agc_evolutionary", "agc"), ("kmeans_evolutionary", "kmeans"), ("spectral_evolutionary", "spectral")]:
        meth.loc[meth.method == evo, "bootstrap_ARI"] = meth.loc[meth.method == base, "bootstrap_ARI"].values
    meth["rank_icvi"] = rank_table(meth, ICVI)
    meth.to_csv(ctx.out / "methods.csv", index=False)
    log("\n" + meth.round(3).to_string())
    return labels
