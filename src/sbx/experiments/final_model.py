"""Итоговая модель и её выгрузки в results/.

  final_labels.*            типы МО по месяцам (нумерация по убыванию трат жителя)
  final_temporal.json,      метрики динамики, события слияния и разделения, матрица переходов
  final_events.csv, final_transitions.csv
  final_profiles*.csv       медианы и z-профили признаков типов («ДНК»)
  final_mo_summary.csv      основной тип МО, число смен, уверенность
  final_type_trajectories.csv, final_sigma_convergence.csv   экономика типов во времени
  final_transition_adjacency.json, final_leadlag.csv         соседство переходов, лидеры и последователи
  final_cluster_x_type.csv  типы × вид МО
  final_twins.json          «экономические двойники» из других регионов
  embedding.json            раскладка сети для лендинга (UMAP)
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.neighbors import NearestNeighbors

from ..clustering import evolutionary as Dy
from ..config import log
from .context import Context


def _save_json(obj, path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)


def order_by_spending(ctx: Context, L: np.ndarray) -> np.ndarray:
    """Перенумеровать кластеры по убыванию среднего уровня трат (детерминированная нумерация)."""
    T, N = L.shape
    lvl = ctx.F.raw["cons_level"].to_numpy().reshape(T, N)
    order = np.argsort([-lvl[L == c].mean() for c in range(L.max() + 1)])
    remap = np.empty_like(order)
    remap[order] = np.arange(len(order))
    return remap[L]


def save_labels_and_dynamics(ctx: Context, L: np.ndarray) -> None:
    """Метки, метрики динамики, журнал событий и матрица переходов."""
    out = ctx.out
    np.save(out / "final_labels.npy", L)
    pd.DataFrame(L.T, index=ctx.mo.index, columns=ctx.months).to_csv(out / "final_labels.csv")
    _save_json(Dy.temporal_metrics(L), out / "final_temporal.json")
    Dy.event_log(L, ctx.months, ctx.cfg["dynamics"]["match_min_jaccard"]).to_csv(out / "final_events.csv", index=False)
    pd.DataFrame(Dy.transition_matrix(L)).to_csv(out / "final_transitions.csv")


def save_profiles(ctx: Context, L: np.ndarray) -> None:
    """Профили типов: медианы интерпретируемых признаков и средние z-оценки («ДНК» типов)."""
    T = len(ctx.months)
    raw = ctx.F.raw.copy()
    raw["cluster"] = L.reshape(-1)
    prof = raw.groupby("cluster").median()
    prof["n_mo_mean"] = raw.groupby(["cluster"]).size() / T
    prof.to_csv(ctx.out / "final_profiles.csv")
    feats = raw.drop(columns="cluster")
    z = (feats - feats.mean()) / feats.std()
    z["cluster"] = raw["cluster"]
    z.groupby("cluster").mean().to_csv(ctx.out / "final_profiles_z.csv")


def save_mo_summary(ctx: Context, L: np.ndarray) -> pd.Series:
    """Основной (модальный) тип МО, число смен типа и уверенность; вернуть модальные типы."""
    N = L.shape[1]
    mo, raw = ctx.mo, ctx.F.raw
    modal = pd.Series([np.bincount(L[:, i]).argmax() for i in range(N)], index=mo.index)
    summary = mo[["name", "region_name", "mo_type"]].copy()
    summary["modal_cluster"] = modal
    summary["n_switches"] = (L[1:] != L[:-1]).sum(0)
    summary["n_distinct"] = [len(np.unique(L[:, i])) for i in range(N)]
    last = raw.xs(ctx.months[-1], level="month")
    summary["cons_total_rub_2024"] = last["cons_total_rub"].reindex(mo.index)
    summary["pop"] = np.exp(last["log_pop"].reindex(mo.index))
    summary["type_confidence"] = [np.mean(L[:, i] == modal.iloc[i]) for i in range(N)]
    summary.to_csv(ctx.out / "final_mo_summary.csv")
    # внешняя проверка: смесь видов МО (городские округа, районы…) в типах
    pd.crosstab(summary.modal_cluster, summary.mo_type).to_csv(ctx.out / "final_cluster_x_type.csv")
    return modal


def save_trajectories(ctx: Context, modal: pd.Series) -> None:
    """Медианы ключевых признаков по месяцам при фиксированном составе типа и σ-конвергенция трат."""
    r = ctx.F.raw.copy()
    r["type"] = np.tile(modal.to_numpy(), len(ctx.months))
    cols = ["cons_total_rub", "cons_level", "share_food", "share_marketplaces", "share_catering",
            "share_transport", "share_health"]
    r.groupby(["type", r.index.get_level_values("month")])[cols].median().to_csv(ctx.out / "final_type_trajectories.csv")
    r.groupby(level="month").cons_level.std().to_csv(ctx.out / "final_sigma_convergence.csv")


def save_transition_structure(ctx: Context, L: np.ndarray, modal: pd.Series, best: np.ndarray, lag: np.ndarray) -> None:
    """Доля переходов между соседними в пространстве признаков типами и «лидеры/последователи» по лагам."""
    k, X, N = ctx.k, ctx.X, L.shape[1]
    m_ = modal.to_numpy()
    cent = np.array([X.mean(0)[m_ == c].mean(0) for c in range(k)])
    dc = np.linalg.norm(cent[:, None] - cent[None], axis=-1)
    nearest = {c: set(np.argsort(dc[c])[1:3]) for c in range(k)}
    TM = Dy.transition_matrix(L)
    off = [(a, b, TM[a, b]) for a in range(k) for b in range(k) if a != b and TM[a, b] > 0]
    share_adj = sum(v for a, b, v in off if b in nearest[a] or a in nearest[b]) / max(1, sum(v for *_, v in off))

    # сильные лаговые пары (max corr > 0.7, лаг ≠ 0): доля пар, где МО данного типа опережает МО другого
    iu = np.triu_indices(N, 1)
    b_, l_ = best[iu], lag[iu]
    strong = (b_ > 0.7) & (l_ != 0)
    lead = np.zeros((k, k))
    for i, j, ll in zip(iu[0][strong], iu[1][strong], l_[strong]):
        a, c = (m_[i], m_[j]) if ll > 0 else (m_[j], m_[i])
        lead[a, c] += 1
    off_lead = lead.sum(1) - np.diag(lead)
    off_follow = lead.sum(0) - np.diag(lead)
    pd.DataFrame({"leads": off_lead, "follows": off_follow, "lead_share": off_lead / (off_lead + off_follow)}
                 ).to_csv(ctx.out / "final_leadlag.csv", index_label="type")
    _save_json({"transitions_to_two_nearest_types_share": float(share_adj),
                "centroid_distance": np.round(dc, 3).tolist()}, ctx.out / "final_transition_adjacency.json")


def save_twins(ctx: Context) -> None:
    """«Экономические двойники»: ближайшие по среднему вектору признаков МО из других регионов."""
    oc = ctx.cfg.get("outputs", {})
    Xm = ctx.X.mean(0)
    _, idx = NearestNeighbors(n_neighbors=oc.get("twins_candidates", 30)).fit(Xm).kneighbors(Xm)
    reg = ctx.mo.region_code.to_numpy()
    twins = {}
    for i in range(len(Xm)):
        cand = [int(j) for j in idx[i, 1:] if reg[j] != reg[i]][:oc.get("twins_per_mo", 5)]
        twins[int(ctx.mo.index[i])] = [int(ctx.mo.index[j]) for j in cand]
    with open(ctx.out / "final_twins.json", "w", encoding="utf-8") as f:
        json.dump(twins, f)


def save_embedding(ctx: Context, L: np.ndarray) -> None:
    """Раскладка сети для лендинга: UMAP по признакам опорного месяца и рёбра его графа."""
    import umap
    oc = ctx.cfg.get("outputs", {})
    xy = umap.UMAP(n_neighbors=oc.get("umap_neighbors", 30), min_dist=oc.get("umap_min_dist", 0.25),
                   random_state=ctx.seed).fit_transform(ctx.Xr)
    U = sp.triu(ctx.graph(ctx.cfg["graph"]["main_rule"], ctx.ref_t), k=1).tocoo()
    with open(ctx.out / "embedding.json", "w", encoding="utf-8") as f:
        json.dump({"ids": [int(i) for i in ctx.mo.index], "xy": np.round(xy, 3).tolist(),
                   "lab": L[ctx.ref_t].tolist(), "edges": np.column_stack([U.row, U.col]).tolist()}, f)


def export_final_model(ctx: Context, labels: dict[str, np.ndarray], best: np.ndarray, lag: np.ndarray) -> np.ndarray:
    """Взять разбиение итогового метода (clustering.final_method), упорядочить типы и сохранить все выгрузки."""
    L = order_by_spending(ctx, labels[ctx.cfg["clustering"]["final_method"]])
    save_labels_and_dynamics(ctx, L)
    save_profiles(ctx, L)
    modal = save_mo_summary(ctx, L)
    save_trajectories(ctx, modal)
    save_transition_structure(ctx, L, modal, best, lag)
    save_twins(ctx)
    save_embedding(ctx, L)
    log("готово")
    return L
