"""Загрузчики исходных источников, приведённых к territory_id (МО в постоянных границах).

  * consumption.parquet — средние безналичные расходы жителя МО по категориям, месяц;
  * connection.parquet — автодорожные расстояния между центрами МО;
  * БДПМО Росстата — занятость и зарплаты по разделам ОКВЭД2, население (год);
  * справочник МО — названия, тип, регион, координаты центра, ОКТМО всех версий.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .catalog import CATEGORIES, TOTAL


def _oktmo8(s: str) -> str:
    return "".join(ch for ch in str(s) if ch.isdigit())[:8]


def load_dictionary(raw: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Возвращает (последняя версия каждого МО, таблица ОКТМО→territory_id по всем версиям)."""
    d = pd.read_excel(raw / "dict/t_dict_municipal_districts.xlsx")
    d["oktmo8"] = d["oktmo"].map(_oktmo8)
    versions = d[["territory_id", "oktmo8", "year_from", "year_to"]].copy()
    latest = (d.sort_values(["territory_id", "year_to", "year_from"])
                .groupby("territory_id").tail(1).set_index("territory_id"))
    latest = latest.rename(columns={
        "municipal_district_name": "name", "municipal_district_name_short": "name_short",
        "municipal_district_type": "mo_type", "municipal_district_status": "status",
        "municipal_district_center_lat": "lat", "municipal_district_center_lon": "lon"})
    return latest, versions


def load_consumption(raw: Path, months: list[str]):
    """Средние траты жителя по категориям за период в широком формате; «прочее» = все − сумма пяти."""
    c = pd.read_parquet(raw / "hackathonlicence/consumption.parquet")
    c = c[(c.date >= months[0]) & (c.date <= months[-1])]
    wide = c.pivot_table(index=["territory_id", "date"], columns="category", values="value")
    wide["Прочее"] = (wide[TOTAL] - wide[CATEGORIES].sum(axis=1)).clip(lower=0)
    return wide


def tensorize(wide: pd.DataFrame, ids: np.ndarray, months: list[str], min_obs: int):
    """[N,T,C] тензор с заполнением пропусков линейной интерполяцией по времени внутри МО."""
    cols = CATEGORIES + ["Прочее", TOTAL]
    full_idx = pd.MultiIndex.from_product([ids, months], names=["territory_id", "date"])
    w = wide.reindex(full_idx)[cols]
    observed = w[TOTAL].notna().to_numpy().reshape(len(ids), len(months))
    keep = observed.sum(1) >= min_obs
    w = (w.groupby(level=0, group_keys=False)
          .apply(lambda g: g.interpolate(limit_direction="both")))
    arr = w.to_numpy().reshape(len(ids), len(months), len(cols))
    return arr[keep, :, :6], arr[keep, :, 6], observed[keep], ids[keep]


def load_rosstat(raw: Path, versions: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Привязка ОКТМО из БДПМО к territory_id с учётом годов действия версии МО."""
    out = {}
    for name in ["employees", "wage", "population"]:
        f = raw / f"rosstat/{name}.parquet"
        if not f.exists():
            continue
        r = pd.read_parquet(f)
        r["god"] = r["god"].astype(int)
        m = r.merge(versions, on="oktmo8", how="inner")
        m = m[(m.god >= m.year_from) & (m.god <= m.year_to)] if len(m) else m
        # Если одному ОКТМО соответствует несколько версий, берём любую действующую (они совпадают по территории)
        m = m.drop_duplicates([c for c in r.columns if c not in ("mo_name", "region_db", "value")] + ["territory_id"])
        out[name] = m.drop(columns=["year_from", "year_to"])
    return out


def load_road_matrix(raw: Path, ids: np.ndarray) -> np.ndarray:
    """Матрица автодорожных расстояний (км) между центрами МО в порядке ids; нет дороги — NaN."""
    con = pd.read_parquet(raw / "hackathonlicence/connection.parquet",
                          filters=[("type", "==", "highway")],
                          columns=["territory_id_x", "territory_id_y", "distance"])
    pos = pd.Series(np.arange(len(ids)), index=ids)
    con = con[con.territory_id_x.isin(pos.index) & con.territory_id_y.isin(pos.index)]
    D = np.full((len(ids), len(ids)), np.nan)
    i, j = pos[con.territory_id_x].to_numpy(), pos[con.territory_id_y].to_numpy()
    D[i, j] = con.distance.to_numpy()
    D[j, i] = con.distance.to_numpy()
    np.fill_diagonal(D, 0.0)
    return D
