"""Статичные рисунки для методологического отчёта (results/figures/*.png)."""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

matplotlib.use("Agg")
plt.rcParams.update({"figure.dpi": 130, "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "font.family": "DejaVu Sans"})

# Первые 8 цветов — смысловая палитра типов, как на лендинге (landing/index.html, PAL): цвет следует
# фишке типа — черепица дома (пригороды), лёд (Северо-Восток), сырая нефть (ресурсные центры), огни города,
# море (Сибирь и ДВ), кирпич завода, хвоя (сельская Сибирь), спелый колос (аграрная глубинка).
# Остальные — запасные для k > 8 при выборе числа кластеров.
PALETTE = ["#E07B39", "#7CC6EE", "#7A5230", "#7B4FC9", "#14808F", "#C2452D", "#2E8B57", "#E0B12E",
           "#5E8C2E", "#D05FA8", "#6B7785", "#A63A1E", "#2A8C6B", "#9C7FD6"]

RULE_RU = {"attr": "Атрибуты (гаусс. ядро)", "cosine": "Косинус структуры трат", "corr": "Корреляция динамики",
           "lagcorr": "Лаговая корреляция", "dtw": "DTW", "geo": "Дорожная близость", "hybrid": "Гибрид (атрибуты+динамика)"}
METHOD_RU = {"kmeans": "K-means", "ward": "Ward", "spectral": "Спектральная", "leiden": "Leiden",
             "agc": "AGC", "agc_evolutionary": "AGC эволюционная", "kmeans_evolutionary": "K-means эволюционная",
             "temporal_leiden": "Темпоральный Leiden"}


def k_selection(res: Path, fig: Path):
    d = pd.read_csv(res / "k_selection.csv")
    cols = ["SW", "CH", "S_Dbw", "AVI", "AVU", "MQ", "Q", "stability"]
    f, axs = plt.subplots(2, 4, figsize=(12.5, 5.2))
    for ax, c in zip(axs.ravel(), cols):
        for m, g in d.groupby("method"):
            ax.plot(g.k, g[c], marker="o", ms=3, label=METHOD_RU.get(m, m))
            if c == "stability":
                ax.fill_between(g.k, g[c] - g["stability_sd"], g[c] + g["stability_sd"], alpha=.15)
        ax.set_title({"stability": "Устойчивость (бутстрэп ARI) ↑"}.get(c, c + (" ↓" if c in ("S_Dbw", "AVU") else " ↑")))
        ax.axvline(8, color="#999", lw=.8, ls="--")
        ax.set_xlabel("k")
    axs[0, 0].legend(frameon=False)
    f.suptitle("Выбор числа кластеров: внутренние индексы качества (июнь 2024)")
    f.tight_layout()
    f.savefig(fig / "k_selection.png")
    plt.close(f)


def edge_rules(res: Path, fig: Path):
    d = pd.read_csv(res / "edge_rules.csv")
    d = d[d.method == "spectral"].set_index("rule")
    cols = ["share_same_region", "median_edge_km", "transitivity", "SW", "AVI", "MQ"]
    titles = ["Доля рёбер внутри региона", "Медианная длина ребра, км", "Транзитивность",
              "SW (атрибуты)", "AVI (свой граф)", "MQ (свой граф)"]
    f, axs = plt.subplots(2, 3, figsize=(11, 5.6))
    for ax, c, t in zip(axs.ravel(), cols, titles):
        ax.barh([RULE_RU[r] for r in d.index], d[c], color=PALETTE[:len(d)])
        ax.set_title(t)
        ax.invert_yaxis()
    for ax in axs[:, 1:].ravel():
        ax.set_yticklabels([])
    f.suptitle("Как правило построения рёбер меняет сеть и кластеры (спектральная кластеризация, k = 8)")
    f.tight_layout()
    f.savefig(fig / "edge_rules.png")
    plt.close(f)


def methods(res: Path, fig: Path):
    d = pd.read_csv(res / "methods.csv").set_index("method")
    cols = ["SW", "CH", "S_Dbw", "AVI", "AVU", "MQ", "ARI_consecutive", "bootstrap_ARI"]
    z = d[cols].copy()
    for c in cols:
        s = z[c] if c not in ("S_Dbw", "AVU") else -z[c]
        z[c] = (s - s.min()) / (s.max() - s.min() + 1e-12)
    f, ax = plt.subplots(figsize=(9, 4))
    im = ax.imshow(z.to_numpy(), cmap="Greens", aspect="auto")
    ax.set_xticks(range(len(cols)), [c + (" ↓" if c in ("S_Dbw", "AVU") else "") for c in cols], rotation=30, ha="right")
    ax.set_yticks(range(len(z)), [METHOD_RU.get(m, m) for m in z.index])
    for i in range(len(z)):
        for j, c in enumerate(cols):
            ax.text(j, i, f"{d[c].iloc[i]:.2f}" if abs(d[c].iloc[i]) < 100 else f"{d[c].iloc[i]:.0f}",
                    ha="center", va="center", fontsize=7.5)
    ax.set_title("Сравнение методов (средние по 24 месяцам; цвет — лучше/хуже в столбце)")
    f.tight_layout()
    f.savefig(fig / "methods.png")
    plt.close(f)


def cluster_map(res: Path, fig: Path, raw: Path, names: dict[int, str], month: str = "2024-06"):
    labels = pd.read_csv(res / "final_labels.csv", index_col=0)
    g = gpd.read_file(raw / "dict/t_dict_municipal_districts_poly.gpkg")
    g["territory_id"] = g["territory_id"].astype(int)
    g = g.sort_values("year_to").groupby("territory_id").tail(1)
    g = g.merge(labels[[month]].rename(columns={month: "cl"}), left_on="territory_id", right_index=True)
    g = g.to_crs("+proj=aea +lat_1=52 +lat_2=64 +lon_0=100 +ellps=WGS84")
    f, ax = plt.subplots(figsize=(12, 6.5))
    for c, sub in g.groupby("cl"):
        sub.plot(ax=ax, color=PALETTE[c], linewidth=0.05, edgecolor="white", label=names.get(c, str(c)))
    ax.set_axis_off()
    handles = [matplotlib.patches.Patch(color=PALETTE[c], label=f"{c + 1}. {names.get(c, c)}") for c in sorted(g.cl.unique())]
    ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=7.5)
    ax.set_title(f"Типы локальных экономик, {month}")
    f.tight_layout()
    f.savefig(fig / "map_clusters.png")
    plt.close(f)


def dna(res: Path, fig: Path, names: dict[int, str], cols: list[str], col_ru: dict[str, str]):
    z = pd.read_csv(res / "final_profiles_z.csv", index_col=0)[cols]
    f, ax = plt.subplots(figsize=(11, 0.45 * len(z) + 2))
    im = ax.imshow(z.to_numpy(), cmap="RdBu_r", vmin=-1.5, vmax=1.5, aspect="auto")
    ax.set_xticks(range(len(cols)), [col_ru.get(c, c) for c in cols], rotation=40, ha="right")
    ax.set_yticks(range(len(z)), [f"{i + 1}. {names.get(i, i)}" for i in z.index])
    plt.colorbar(im, ax=ax, shrink=0.7, label="z-оценка (среднее по кластеру)")
    ax.set_title("«ДНК» кластеров: отклонение от среднего по всем МО")
    f.tight_layout()
    f.savefig(fig / "cluster_dna.png")
    plt.close(f)


def dynamics(res: Path, fig: Path, names: dict[int, str], months: list[str]):
    L = np.load(res / "final_labels.npy")
    k = L.max() + 1
    share = np.array([[np.mean(L[t] == c) for c in range(k)] for t in range(len(L))])
    tm = json.load(open(res / "final_temporal.json", encoding="utf-8"))
    f, axs = plt.subplots(1, 2, figsize=(12, 4), gridspec_kw={"width_ratios": [2, 1.2]})
    axs[0].stackplot(range(len(months)), share.T * 100, colors=PALETTE[:k],
                     labels=[f"{c + 1}. {names.get(c, c)}" for c in range(k)])
    axs[0].set_xticks(range(0, len(months), 3), months[::3], rotation=30)
    axs[0].set_ylabel("% МО")
    axs[0].set_xlim(0, len(months) - 1)
    axs[0].legend(fontsize=6.5, loc="upper left", bbox_to_anchor=(1, 1), frameon=False)
    axs[0].set_title("Состав кластеров во времени")
    axs[1].plot(range(1, len(months)), np.array(tm["switch_series"]) * 100, marker="o", color="#1f2328")
    axs[1].set_xticks(range(1, len(months), 3), months[1::3], rotation=30)
    axs[1].set_title("Доля МО, сменивших кластер за месяц, %")
    f.tight_layout()
    f.savefig(fig / "dynamics.png")
    plt.close(f)
