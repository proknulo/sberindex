"""Внутригородская структура Москвы и Санкт-Петербурга: python -m sbx intracity

Внутригородские территории исключены из основной модели: это части единого рынка
труда, и данных БДПМО по ним нет. Здесь они кластеризуются той же схемой
(kNN-граф с самонастраивающимся ядром → эволюционная спектральная кластеризация), но
только по блокам трат: уровень, структура (CLR), сезонность. k выбирается по тому же
правилу устойчивости (наибольшее k с бутстрэп-ARI ≥ 0.8).
"""
from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score

from ..clustering import evolutionary as Dy
from ..clustering import static as C
from ..data import load_all
from ..evaluation.indices import all_indices
from ..features import build_features
from ..network import edges as G

INTRA = "внутригородская территория города федерального значения"


def run(cfg: dict) -> None:
    """Кластеризация внутригородских территорий Москвы и Санкт-Петербурга по блокам трат."""
    c = copy.deepcopy(cfg)
    c["data"]["exclude_types"] = []
    ds = load_all(c)
    F = build_features(ds, c)
    mask = (ds.mo.mo_type == INTRA).to_numpy()
    cols = [i for b in ("consumption_level", "consumption_structure", "seasonality") for i in F.blocks[b]]
    X = F.X[:, mask][:, :, cols]
    mo = ds.mo[mask]
    T, N, _ = X.shape
    gc = cfg["graph"]
    ic, cc = cfg.get("intracity", {}), cfg["clustering"]
    Ws = [G.attr_graph(X[t], ic.get("knn", 10), gc["self_tuning_neighbor"]) for t in range(T)]
    ref = ds.months.index(cfg["data"].get("reference_month", "2024-06"))
    rng = np.random.default_rng(cfg["seed"])
    boots = [np.sort(rng.choice(N, int(cc.get("subsample_frac", 0.8) * N), replace=False)) for _ in range(cc.get("k_selection_bootstrap", 20))]
    rows = []
    k_lo, k_hi = ic.get("k_range", [3, 8])
    for k in range(k_lo, k_hi + 1):
        lab = C.spectral(Ws[ref], k, cfg["seed"])
        st = np.mean([adjusted_rand_score(lab[b], C.spectral(Ws[ref][b][:, b], k, cfg["seed"] + i + 1))
                      for i, b in enumerate(boots)])
        rows.append({"k": k, "stability": st, **all_indices(X[ref], Ws[ref], lab)})
    ks = pd.DataFrame(rows)
    thr = cc.get("k_stability_threshold", 0.8)
    k = int(ks[ks.stability >= thr].k.max()) if (ks.stability >= thr).any() else int(ks.loc[ks.stability.idxmax(), "k"])
    L = Dy.evolutionary_spectral(Ws, k, cfg["dynamics"]["evolutionary_alpha"], cfg["seed"])
    raw = F.raw.loc[(slice(None), mo.index), :]
    lvl = raw["cons_level"].to_numpy().reshape(T, N)
    order = np.argsort([-lvl[L == c].mean() for c in range(L.max() + 1)])
    remap = np.empty_like(order); remap[order] = np.arange(len(order)); L = remap[L]
    modal = np.array([np.bincount(L[:, i]).argmax() for i in range(N)])
    out = Path(cfg["paths"]["results"])
    ks.to_csv(out / "intracity_k_selection.csv", index=False)
    summ = mo[["name", "region_name"]].assign(modal_cluster=modal, n_switches=(L[1:] != L[:-1]).sum(0),
                                              type_confidence=(L == modal[None, :]).mean(0))
    summ.to_csv(out / "intracity_summary.csv")
    # типы районов по месяцам (для карты и CSV) и интерпретируемые признаки (для карточек района)
    pd.DataFrame(L.T, index=mo.index, columns=ds.months).to_csv(out / "intracity_labels.csv")
    proc = Path(cfg["paths"]["processed"]); proc.mkdir(parents=True, exist_ok=True)
    raw.to_parquet(proc / "intracity_raw.parquet")
    r = raw[[c for c in raw.columns if c.startswith(("cons_", "share_", "season", "summer"))]].copy()
    r["cluster"] = np.tile(modal, T)
    prof = r.groupby("cluster").median()
    prof["n"] = np.bincount(modal)
    prof["share_moscow"] = summ.groupby("modal_cluster").region_name.apply(lambda s: (s == "Москва").mean())
    prof.to_csv(out / "intracity_profiles.csv")
    print(ks.round(3).to_string())
    print("k =", k)
    print(prof.round(3).T.to_string())
    for c in range(k):
        print(c, "; ".join(summ[summ.modal_cluster == c].name.str.replace(INTRA + " ", "").head(10)))

