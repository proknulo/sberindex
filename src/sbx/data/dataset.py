"""Сборка набора данных для модели: все источники, согласованные по territory_id."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .loaders import load_consumption, load_dictionary, load_road_matrix, load_rosstat, tensorize


@dataclass
class Dataset:
    """Согласованные по territory_id данные выборки МО за период модели."""
    mo: pd.DataFrame            # справочник по отобранным МО (index = territory_id)
    months: list[str]
    cons: np.ndarray            # [N, T, 6] расходы по 5 категориям + «прочее», руб.
    cons_total: np.ndarray      # [N, T] все категории, руб.
    observed: np.ndarray        # [N, T] bool — наблюдение было в исходных данных
    market_access: pd.Series
    rosstat: dict[str, pd.DataFrame]
    road_km: np.ndarray | None  # [N, N] автодорожные расстояния


def month_range(a: str, b: str) -> list[str]:
    """Список месяцев 'YYYY-MM' от a до b включительно."""
    return [p.strftime("%Y-%m") for p in pd.period_range(a, b, freq="M")]


def load_all(cfg: dict) -> Dataset:
    """Все источники, согласованные по territory_id и отфильтрованные по правилам выборки из конфига."""
    raw = Path(cfg["paths"]["raw"])
    months = month_range(*cfg["data"]["months"])
    latest, versions = load_dictionary(raw)
    wide = load_consumption(raw, months)
    ids = np.sort(wide.index.get_level_values(0).unique().to_numpy())
    cons, total, observed, ids = tensorize(wide, ids, months, cfg["data"]["min_months_observed"])
    ma = pd.read_parquet(raw / "hackathonlicence/market_access.parquet").set_index("territory_id")["market_access"]
    excl = set(cfg["data"].get("exclude_types", []))
    keep_ids = latest.index[~latest.mo_type.isin(excl)]
    mask = np.isin(ids, keep_ids)
    ids = ids[mask]
    mo = latest.loc[ids, ["name", "name_short", "mo_type", "status", "region_code", "region_name",
                          "lat", "lon", "oktmo8"]].copy()
    rosstat = load_rosstat(raw, versions)
    road = load_road_matrix(raw, ids)
    return Dataset(mo=mo, months=months, cons=cons[mask], cons_total=total[mask],
                   observed=observed[mask], market_access=ma.reindex(ids), rosstat=rosstat, road_km=road)
