"""Загрузка и согласование исходных данных.

Единица анализа — муниципальное образование в постоянных границах (territory_id
из справочника СберИндекса). Все источники приводятся к этому ключу:
  * consumption.parquet — средние безналичные расходы жителя МО по категориям, месяц;
  * market_access.parquet — индекс доступности рынков (2024);
  * connection.parquet — автодорожные расстояния между центрами МО;
  * БДПМО Росстата — занятость и зарплаты по разделам ОКВЭД2, население (год);
  * справочник МО — названия, тип, регион, координаты центра, ОКТМО всех версий.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

CATEGORIES = ["Продовольствие", "Здоровье", "Общественное питание", "Транспорт", "Маркетплейсы"]
CAT_SHORT = {"Продовольствие": "food", "Здоровье": "health", "Общественное питание": "catering",
             "Транспорт": "transport", "Маркетплейсы": "marketplaces", "Прочее": "other"}
TOTAL = "Все категории"

# Разделы ОКВЭД2 (коды БДПМО) сведены в 11 укрупнённых секторов: так меньше нулей и шума
# в малых МО, а сектора остаются экономически различимыми.
OKVED_GROUPS = {
    "10000": "agri",          # A Сельское, лесное хозяйство, рыболовство
    "50000": "mining",        # B Добыча полезных ископаемых
    "20000": "manufacturing", # C Обрабатывающие производства
    "30000": "utilities",     # D Энергетика
    "40000": "utilities",     # E Водоснабжение, отходы
    "41000": "construction",  # F Строительство
    "45000": "trade",         # G Торговля
    "49000": "transport",     # H Транспортировка и хранение
    "55000": "hospitality",   # I Гостиницы и общепит
    "63000": "business",      # J Информация и связь
    "60000": "business",      # K Финансы и страхование
    "68000": "business",      # L Недвижимость
    "70000": "business",      # M Профессиональная и научная деятельность
    "80000": "business",      # N Административная деятельность
    "84000": "public",        # O Госуправление и оборона
    "85000": "public",        # P Образование
    "86000": "public",        # Q Здравоохранение и соцуслуги
    "90000": "leisure",       # R Культура, спорт, досуг
    "95000": "leisure",       # S Прочие услуги
}
OKVED_TOTAL = "101"
SECTOR_RU = {"agri": "Сельское хозяйство", "mining": "Добыча", "manufacturing": "Обработка",
             "utilities": "Энергетика и ЖКХ", "construction": "Строительство", "trade": "Торговля",
             "transport": "Транспорт и логистика", "hospitality": "Гостиницы и общепит",
             "business": "Рыночные услуги (IT, финансы, недвижимость, B2B)",
             "public": "Бюджетный сектор (госуправление, образование, здравоохранение)",
             "leisure": "Культура, досуг, прочие услуги",
             "hidden": "Не раскрыто (конфиденциальные данные крупных работодателей)"}


@dataclass
class Dataset:
    mo: pd.DataFrame            # справочник по отобранным МО (index = territory_id)
    months: list[str]
    cons: np.ndarray            # [N, T, 6] расходы по 5 категориям + «прочее», руб.
    cons_total: np.ndarray      # [N, T] все категории, руб.
    observed: np.ndarray        # [N, T] bool — наблюдение было в исходных данных
    market_access: pd.Series
    rosstat: dict[str, pd.DataFrame]
    road_km: np.ndarray | None  # [N, N] автодорожные расстояния


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


def month_range(a: str, b: str) -> list[str]:
    return [p.strftime("%Y-%m") for p in pd.period_range(a, b, freq="M")]


def load_all(cfg: dict) -> Dataset:
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
