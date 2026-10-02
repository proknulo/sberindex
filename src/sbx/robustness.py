"""Проверки надёжности итогового разбиения: python -m sbx.robustness --config configs/default.yaml

1. Чувствительность к весам блоков признаков: каждый вес ×0.5 и ×1.5 (и исключение блока),
   пересчёт итоговой модели, ARI с базовым решением (по опорному месяцу и по всей панели).
2. Чувствительность к гиперпараметрам графа: k в kNN, порядок фильтра p, α эволюционной модели.
3. Пространственная связность (внешняя валидация): доля пар «соседей по дороге» (5 ближайших
   МО по автодорожному расстоянию) в одном кластере против нулевой модели — случайных
   перестановок меток (1000 раз). Географическое соседство в модель не входит (кроме индекса
   доступности рынков), поэтому связность — независимое свидетельство, что типы отражают
   реальные экономико-географические образования, а не шум.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import adjusted_rand_score

from . import dynamics as Dy
from . import graphs as G
from .data import load_all
from .features import build_features


def fit_final(ds, cfg):
    F = build_features(ds, cfg)
    X = F.X
    gc, cc = cfg["graph"], cfg["clustering"]
    Ws = [G.attr_graph(X[t], gc["knn"], gc["self_tuning_neighbor"]) for t in range(len(X))]
    return Dy.evolutionary_spectral(Ws, cc["k"], cfg["dynamics"]["evolutionary_alpha"], cfg["seed"])


def panel_ari(A, B):
    return float(adjusted_rand_score(A.ravel(), B.ravel()))


def main(cfg_path):
    cfg = yaml.safe_load(open(cfg_path, encoding="utf-8"))
    res = Path(cfg["paths"]["results"])
    ds = load_all(cfg)
    base = np.load(res / "final_labels.npy")
    ref = ds.months.index("2024-06")
    rows = []

    def best_jaccard(a, b):
        """Для каждого базового типа — максимальный Жаккар с каким-либо типом варианта."""
        return [max(len(set(np.where(a == c)[0]) & set(np.where(b == d)[0])) /
                    len(set(np.where(a == c)[0]) | set(np.where(b == d)[0])) for d in np.unique(b))
                for c in range(a.max() + 1)]

    def run(name, c):
        L = fit_final(ds, c)
        J = best_jaccard(base[ref], L[ref])
        rows.append({"variant": name, "ARI_ref_month": float(adjusted_rand_score(base[ref], L[ref])),
                     "ARI_panel": panel_ari(base, L), "switch_rate": Dy.temporal_metrics(L)["switch_rate"],
                     **{f"J_type{t + 1}": round(j, 3) for t, j in enumerate(J)}})
        print(rows[-1], flush=True)

    for b in cfg["features"]["block_weights"]:
        for f in (0.5, 1.5, 0.0):
            c = copy.deepcopy(cfg)
            c["features"]["block_weights"][b] *= f
            run(f"{b} ×{f}", c)
    for k in (10, 20):
        c = copy.deepcopy(cfg); c["graph"]["knn"] = k; run(f"kNN k={k}", c)
    for s_nn in (4, 10):
        c = copy.deepcopy(cfg); c["graph"]["self_tuning_neighbor"] = s_nn; run(f"σ: сосед №{s_nn}", c)
    for a in (0.6, 1.0):
        c = copy.deepcopy(cfg); c["dynamics"]["evolutionary_alpha"] = a; run(f"эволюц. α={a}", c)
    for s in (1, 7):
        c = copy.deepcopy(cfg); c["seed"] = s; run(f"seed={s}", c)
    pd.DataFrame(rows).to_csv(res / "robustness_sensitivity.csv", index=False)

    # пространственная связность
    D = ds.road_km.copy()
    D[np.isnan(D)] = np.inf
    np.fill_diagonal(D, np.inf)
    nb = np.argsort(D, axis=1)[:, :5]
    ok = np.isfinite(np.take_along_axis(D, nb, 1))
    rng = np.random.default_rng(0)
    out = {}
    for name, lab in [("2024-06", base[ref])]:
        obs = float((lab[nb] == lab[:, None])[ok].mean())
        null = [float((p[nb] == p[:, None])[ok].mean()) for p in (rng.permutation(lab) for _ in range(1000))]
        out = {"observed_same_cluster_share": obs, "null_mean": float(np.mean(null)), "null_sd": float(np.std(null)),
               "z": float((obs - np.mean(null)) / np.std(null)), "p_value": float((np.sum(np.array(null) >= obs) + 1) / 1001)}
    json.dump(out, open(res / "robustness_spatial.json", "w", encoding="utf-8"), indent=1)
    print(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    main(ap.parse_args().config)
