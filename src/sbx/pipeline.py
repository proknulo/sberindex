"""Полный пайплайн: python -m sbx.pipeline --config configs/default.yaml

Шаги:
  1. данные → признаки узлов x_{i,t}                                       (features.py)
  2. выбор числа кластеров k по ICVI                                       results/k_selection.csv
  3. сравнение правил построения рёбер (структура сети + качество)          results/edge_rules.csv
  4. сравнение методов кластеризации по всем месяцам + устойчивость         results/methods.csv
  5. итоговая динамическая модель, события, профили кластеров              results/final_*.csv
  6. экспорт данных для интерактивного лендинга                            landing/data.js
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import adjusted_rand_score

from . import clustering as C
from . import dynamics as Dy
from . import graphs as G
from .data import load_all
from .features import build_features
from .validity import HIGHER_BETTER, all_indices


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def graph_stats(W, mo: pd.DataFrame, road_km: np.ndarray | None) -> dict:
    """Описание структуры сети: плотность, степень, кластеризация, пространственная связность."""
    import igraph as ig
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


def run_method(name, X, W, k, cfg, seed):
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
    r = pd.DataFrame({c: df[c].rank(ascending=not HIGHER_BETTER[c]) for c in cols})
    return r.mean(1)


def main(cfg_path: str):
    cfg = yaml.safe_load(open(cfg_path))
    seed = cfg["seed"]
    out = Path(cfg["paths"]["results"]); out.mkdir(parents=True, exist_ok=True)
    proc = Path(cfg["paths"]["processed"]); proc.mkdir(parents=True, exist_ok=True)
    k = cfg["clustering"]["k"]
    gc = cfg["graph"]

    # ------------------------------------------------------------------ 1. данные и признаки
    log("загрузка данных")
    ds = load_all(cfg)
    F = build_features(ds, cfg)
    X, months, mo = F.X, ds.months, ds.mo
    T, N, D = X.shape
    log(f"МО: {N}, месяцев: {T}, признаков: {D}")
    F.raw.to_parquet(proc / "features_raw.parquet")
    np.save(proc / "features_X.npy", X)
    mo.assign(rosstat_imputed_share=F.imputed.reindex(mo.index)).to_parquet(proc / "mo.parquet")
    struct_idx = F.blocks["consumption_structure"]
    rel = G.relative_series(ds.cons, ds.cons_total)

    graphs_cache: dict[tuple[str, int], object] = {}

    def graph(rule, t):
        key = (rule, t)
        if key not in graphs_cache:
            graphs_cache[key] = G.build_graphs_for_month(rule, t, X, rel, gc, ds.road_km, struct_idx)
        return graphs_cache[key]

    ref_t = months.index("2024-06") if "2024-06" in months else T // 2
    Xr = X[ref_t]

    # ------------------------------------------------------------------ 2. выбор k
    log("выбор k")
    # ICVI почти монотонны по k (типично для континуальных социально-экономических данных),
    # поэтому дополнительно используется критерий устойчивости (Ben-Hur et al., 2002):
    # средний ARI между разбиением всей выборки и разбиениями 80%-подвыборок.
    rows = []
    Wm = graph(gc["main_rule"], ref_t)
    rng = np.random.default_rng(seed)
    boots = [np.sort(rng.choice(N, int(0.8 * N), replace=False)) for _ in range(20)]
    for kk in range(cfg["clustering"]["k_range"][0], cfg["clustering"]["k_range"][1] + 1):
        for m in ["kmeans", "agc", "spectral"]:
            lab = run_method(m, Xr, Wm, kk, cfg, seed)
            st = [adjusted_rand_score(lab[b], run_method(m, Xr[b], Wm[b][:, b], kk, cfg, seed + i + 1))
                  for i, b in enumerate(boots)]
            rows.append({"k": kk, "method": m, **all_indices(Xr, Wm, lab, seed),
                         "stability": float(np.mean(st)), "stability_sd": float(np.std(st))})
    ksel = pd.DataFrame(rows)
    ksel.to_csv(out / "k_selection.csv", index=False)

    # ------------------------------------------------------------------ 3. правила рёбер
    log("сравнение правил рёбер")
    rules = ["attr", "cosine", "corr", "lagcorr", "dtw", "geo", "hybrid"]
    rows, parts = [], {}
    W_ref_attr = graph("attr", ref_t)
    for rule in rules:
        t0 = time.time()
        W = graph(rule, ref_t)
        st = graph_stats(W, mo, ds.road_km)
        for m in ["spectral", "leiden", "agc"]:
            lab = run_method(m, Xr, W, k, cfg, seed)
            parts[(rule, m)] = lab
            ind = all_indices(Xr, W, lab, seed)
            ind_common = {f"{kk}@attr": v for kk, v in all_indices(Xr, W_ref_attr, lab, seed).items()
                          if kk in ("AVI", "AVU", "MQ", "Q")}
            rows.append({"rule": rule, "method": m, **st, **ind, **ind_common, "sec": time.time() - t0})
        log(f"  {rule}: {st['edges']} рёбер")
    er = pd.DataFrame(rows)
    er.to_csv(out / "edge_rules.csv", index=False)
    ari = pd.DataFrame([[adjusted_rand_score(parts[(a, "agc")], parts[(b, "agc")]) for b in rules] for a in rules],
                       index=rules, columns=rules)
    ari.to_csv(out / "edge_rules_ari_agc.csv")

    # лаговая структура: кто опережает кого (для отчёта)
    best, lag = G.lagcorr_matrix(rel[:, -1, :], gc["max_lag"])
    np.save(proc / "lagcorr_best.npy", best.astype(np.float32))
    np.save(proc / "lagcorr_lag.npy", lag)

    # ------------------------------------------------------------------ 4. методы по всем месяцам
    log("сравнение методов по месяцам")
    Ws = [graph(gc["main_rule"], t) for t in range(T)]
    labels = {}
    for m in ["kmeans", "ward", "spectral", "leiden", "agc"]:
        L = []
        for t in range(T):
            lab = run_method(m, X[t], Ws[t], k, cfg, seed)
            L.append(lab if t == 0 else C.match_labels(L[-1], lab))
        labels[m] = np.array(L)
        log(f"  {m}")
    alpha = cfg["dynamics"]["evolutionary_alpha"]
    Xf = [C.agc_filter(X[t], Ws[t], cfg["clustering"]["agc_power"]) for t in range(T)]
    labels["agc_evolutionary"], centers = Dy.evolutionary_kmeans(Xf, k, alpha, seed, cfg["clustering"]["n_init"])
    labels["kmeans_evolutionary"], _ = Dy.evolutionary_kmeans(list(X), k, alpha, seed, cfg["clustering"]["n_init"])
    labels["spectral_evolutionary"] = Dy.evolutionary_spectral(Ws, k, alpha, seed)
    # темпоральный Leiden: γ подбирается по опорному месяцу
    _, gamma = C.leiden(Ws[ref_t], k, seed)
    TL = C.temporal_leiden(Ws, gamma, cfg["clustering"]["leiden_interslice"], seed)
    TL = np.array([C._merge_small(TL[t], Ws[t], 10) for t in range(T)])
    labels["temporal_leiden"] = np.array([TL[0]] + [C.match_labels(TL[t - 1], TL[t]) for t in range(1, T)])
    log("  temporal_leiden")

    rows = []
    for m, L in labels.items():
        per_t = pd.DataFrame([all_indices(X[t], Ws[t], L[t], seed) for t in range(T)])
        tm = Dy.temporal_metrics(L)
        rows.append({"method": m, **per_t.mean().to_dict(),
                     "k_mean": float(np.mean([len(np.unique(l)) for l in L])),
                     **{kk: v for kk, v in tm.items() if not kk.endswith("series")}})
    meth = pd.DataFrame(rows)

    # устойчивость к подвыборке (бутстрэп 80% узлов) в опорном месяце
    rng = np.random.default_rng(seed)
    stab = {m: [] for m in ["kmeans", "ward", "spectral", "leiden", "agc"]}
    for b in range(cfg["clustering"]["stability_bootstrap"]):
        idx = np.sort(rng.choice(N, int(0.8 * N), replace=False))
        Wb = Ws[ref_t][idx][:, idx]
        for m in stab:
            lab = run_method(m, Xr[idx], Wb, k, cfg, seed + b + 1)
            stab[m].append(adjusted_rand_score(labels[m][ref_t][idx], lab))
    meth["bootstrap_ARI"] = meth.method.map({m: float(np.mean(v)) for m, v in stab.items()})
    meth.loc[meth.method == "agc_evolutionary", "bootstrap_ARI"] = meth.loc[meth.method == "agc", "bootstrap_ARI"].values
    meth.loc[meth.method == "kmeans_evolutionary", "bootstrap_ARI"] = meth.loc[meth.method == "kmeans", "bootstrap_ARI"].values
    meth.loc[meth.method == "spectral_evolutionary", "bootstrap_ARI"] = meth.loc[meth.method == "spectral", "bootstrap_ARI"].values
    meth["rank_icvi"] = rank_table(meth, ["SW", "CH", "S_Dbw", "AVI", "AVU", "MQ"])
    meth.to_csv(out / "methods.csv", index=False)
    log("\n" + meth.round(3).to_string())

    # ------------------------------------------------------------------ 5. итоговая модель
    final_name = cfg["clustering"]["final_method"]
    L = labels[final_name]
    # упорядочим кластеры по среднему уровню расходов (детерминированная нумерация)
    lvl = F.raw["cons_level"].to_numpy().reshape(T, N)
    order = np.argsort([-lvl[L == c].mean() for c in range(L.max() + 1)])
    remap = np.empty_like(order); remap[order] = np.arange(len(order))
    L = remap[L]
    np.save(out / "final_labels.npy", L)
    lab_df = pd.DataFrame(L.T, index=mo.index, columns=months)
    lab_df.to_csv(out / "final_labels.csv")

    tm = Dy.temporal_metrics(L)
    json.dump({kk: v for kk, v in tm.items()}, open(out / "final_temporal.json", "w"), indent=1)
    Dy.event_log(L, months, cfg["dynamics"]["match_min_jaccard"]).to_csv(out / "final_events.csv", index=False)
    pd.DataFrame(Dy.transition_matrix(L)).to_csv(out / "final_transitions.csv")

    # профили кластеров: медианы интерпретируемых признаков
    raw = F.raw.copy()
    raw["cluster"] = L.reshape(-1)
    prof = raw.groupby("cluster").median()
    prof["n_mo_mean"] = raw.groupby(["cluster"]).size() / T
    prof.to_csv(out / "final_profiles.csv")
    # профиль в z-оценках (для «ДНК» кластеров)
    z = (raw.drop(columns="cluster") - raw.drop(columns="cluster").mean()) / raw.drop(columns="cluster").std()
    z["cluster"] = raw["cluster"]
    z.groupby("cluster").mean().to_csv(out / "final_profiles_z.csv")

    # модальный кластер МО и число переходов
    modal = pd.Series([np.bincount(L[:, i]).argmax() for i in range(N)], index=mo.index)
    summary = mo[["name", "region_name", "mo_type"]].copy()
    summary["modal_cluster"] = modal
    summary["n_switches"] = (L[1:] != L[:-1]).sum(0)
    summary["n_distinct"] = [len(np.unique(L[:, i])) for i in range(N)]
    summary["cons_total_rub_2024"] = F.raw.xs("2024-12", level="month")["cons_total_rub"].reindex(mo.index)
    summary["pop"] = np.exp(F.raw.xs("2024-12", level="month")["log_pop"].reindex(mo.index))
    summary["type_confidence"] = [np.mean(L[:, i] == modal.iloc[i]) for i in range(N)]
    summary.to_csv(out / "final_mo_summary.csv")

    # траектории типов: медианы ключевых признаков по месяцам для МО с данным модальным типом
    # (фиксированный состав — чтобы видеть изменение экономики типа, а не смену состава)
    r = F.raw.copy()
    r["type"] = np.tile(modal.to_numpy(), T)
    traj_cols = ["cons_total_rub", "cons_level", "share_food", "share_marketplaces", "share_catering",
                 "share_transport", "share_health"]
    r.groupby(["type", r.index.get_level_values("month")])[traj_cols].median().to_csv(out / "final_type_trajectories.csv")
    sd = r.groupby(level="month").cons_level.std()
    sd.to_csv(out / "final_sigma_convergence.csv")

    # «соседство» переходов: доля переходов между типами, соседними в пространстве признаков
    cent = np.array([X.mean(0)[modal.to_numpy() == c].mean(0) for c in range(k)])
    dc = np.linalg.norm(cent[:, None] - cent[None], axis=-1)
    nearest = {c: set(np.argsort(dc[c])[1:3]) for c in range(k)}
    TM = Dy.transition_matrix(L)
    off = [(a, b, TM[a, b]) for a in range(k) for b in range(k) if a != b and TM[a, b] > 0]
    share_adj = sum(v for a, b, v in off if b in nearest[a] or a in nearest[b]) / max(1, sum(v for *_, v in off))
    # лидеры и последователи: для сильных лаговых пар (max corr > 0.7, лаг ≠ 0) — доля пар,
    # где МО данного типа опережает МО другого типа
    iu = np.triu_indices(N, 1)
    b_, l_ = best[iu], lag[iu]
    strong = (b_ > 0.7) & (l_ != 0)
    lead = np.zeros((k, k))
    m_ = modal.to_numpy()
    for i, j, ll in zip(iu[0][strong], iu[1][strong], l_[strong]):
        a, c = (m_[i], m_[j]) if ll > 0 else (m_[j], m_[i])
        lead[a, c] += 1
    off_lead = lead.sum(1) - np.diag(lead)
    off_follow = lead.sum(0) - np.diag(lead)
    pd.DataFrame({"leads": off_lead, "follows": off_follow, "lead_share": off_lead / (off_lead + off_follow)}
                 ).to_csv(out / "final_leadlag.csv", index_label="type")

    json.dump({"transitions_to_two_nearest_types_share": float(share_adj),
               "centroid_distance": np.round(dc, 3).tolist()}, open(out / "final_transition_adjacency.json", "w"), indent=1)

    # внешняя валидация: смесь типов МО и регионов в кластерах
    pd.crosstab(summary.modal_cluster, summary.mo_type).to_csv(out / "final_cluster_x_type.csv")

    # «экономические двойники»: ближайшие по среднему вектору атрибутов МО из других регионов
    Xm = X.mean(0)
    from sklearn.neighbors import NearestNeighbors
    nn = NearestNeighbors(n_neighbors=30).fit(Xm)
    dist, idx = nn.kneighbors(Xm)
    reg = mo.region_code.to_numpy()
    twins = {}
    for i in range(N):
        cand = [int(j) for j in idx[i, 1:] if reg[j] != reg[i]][:5]
        twins[int(mo.index[i])] = [int(mo.index[j]) for j in cand]
    json.dump(twins, open(out / "final_twins.json", "w"))

    # раскладка сети для лендинга: UMAP по признакам опорного месяца
    import umap
    xy = umap.UMAP(n_neighbors=30, min_dist=0.25, random_state=seed).fit_transform(Xr)
    U = __import__("scipy.sparse", fromlist=["triu"]).triu(Ws[ref_t], k=1).tocoo()
    json.dump({"ids": [int(i) for i in mo.index], "xy": np.round(xy, 3).tolist(),
               "lab": L[ref_t].tolist(), "edges": np.column_stack([U.row, U.col]).tolist()},
              open(out / "embedding.json", "w"))
    log("готово")
    return cfg, ds, F, labels, L


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    main(ap.parse_args().config)
