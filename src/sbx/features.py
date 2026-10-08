"""Пространство атрибутов узлов динамической сети.

Для каждого МО i и месяца t строится вектор x_{i,t}, состоящий из блоков:

  consumption_level      log(расходы_{i,t}) − median_j log(расходы_{j,t})
                         уровень безналичных трат жителя относительно медианного МО
                         в том же месяце (снимает общую инфляцию и сезонность)
  consumption_structure  CLR-преобразование долей 6 категорий (продукты, здоровье,
                         общепит, транспорт, маркетплейсы, прочее) — композиционные
                         данные сравниваются в геометрии Эйчисона, а не как сырые доли
  seasonality            статические: амплитуда внутригодовых колебаний и «летний пик»
                         относительного уровня расходов (курортные и дачные территории)
  industry               CLR долей 11 укрупнённых секторов в среднесписочной численности
                         работников (Росстат, БДПМО), год месяца t
  labour                 log(зарплата / медиана по МО за год), доля работников крупных
                         и средних организаций в населении
  geography              log индекса доступности рынков, log численности населения

Каждый признак стандартизуется по всей панели (N·T наблюдений — поэтому изменения во
времени сохраняются), затем блок делится на sqrt(число признаков) и умножается на вес.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.impute import KNNImputer

from .data import CAT_SHORT, CATEGORIES, OKVED_GROUPS, OKVED_TOTAL, Dataset


@dataclass
class Features:
    """Признаки модели и их интерпретируемые значения."""
    X: np.ndarray                 # [T, N, D] взвешенные стандартизованные признаки
    names: list[str]
    blocks: dict[str, list[int]]  # блок -> индексы колонок
    raw: pd.DataFrame             # интерпретируемые (нестандартизованные) значения, MultiIndex (month, territory_id)
    imputed: pd.Series            # доля импутированных признаков Росстата по МО


def clr(shares: np.ndarray, eps: float) -> np.ndarray:
    """Центрированное лог-отношение долей (геометрия Эйчисона) с псевдосчётом eps."""
    s = shares + eps
    s = s / s.sum(-1, keepdims=True)
    ls = np.log(s)
    return ls - ls.mean(-1, keepdims=True)


def _smooth(a: np.ndarray, w: int) -> np.ndarray:
    """Центрированное скользящее среднее по оси времени (ось 1)."""
    if w <= 1:
        return a
    df = pd.DataFrame(a.reshape(a.shape[0], a.shape[1], -1).transpose(1, 0, 2).reshape(a.shape[1], -1))
    sm = df.rolling(w, center=True, min_periods=1).mean().to_numpy()
    return sm.reshape(a.shape[1], a.shape[0], -1).transpose(1, 0, 2).reshape(a.shape)


def _annual_panel(ds: Dataset, years: list[int]):
    """Годовые признаки Росстата: [len(years), N, ...] с заполнением по ближайшему году."""
    ids = ds.mo.index.to_numpy()
    sectors = sorted(set(OKVED_GROUPS.values()))
    emp = ds.rosstat.get("employees")
    wage = ds.rosstat.get("wage")
    pop = ds.rosstat.get("population")

    e = emp.assign(sector=emp.okved2.map(OKVED_GROUPS))
    e_sec = e.dropna(subset=["sector"]).groupby(["territory_id", "god", "sector"]).value.sum().unstack("sector")
    e_sec = e_sec.reindex(columns=sectors)
    e_sec["_total"] = e[e.okved2 == OKVED_TOTAL].set_index(["territory_id", "god"]).value
    w_tot = wage[wage.okved2 == OKVED_TOTAL].set_index(["territory_id", "god"]).value
    p_tot = pop[pop.mest == "11"].set_index(["territory_id", "god"]).value

    def by_year(obj):
        """Для каждого года берём строку МО из ближайшего года, где она есть (сначала прошлые,
        затем будущие). Строка берётся целиком, чтобы доли секторов и итог были из одного года."""
        out = []
        for y in years:
            order = [y] + [v for k in range(1, 6) for v in (y - k, y + k)]
            acc = obj.xs(y, level="god").reindex(ids) if y in obj.index.get_level_values("god") else None
            for yy in order[1:]:
                if yy not in obj.index.get_level_values("god"):
                    continue
                cur = obj.xs(yy, level="god").reindex(ids)
                if acc is None:
                    acc = cur
                    continue
                empty = acc.isna().all(axis=1) if isinstance(acc, pd.DataFrame) else acc.isna()
                acc[empty] = cur[empty]
            out.append(acc)
        return out

    sec = by_year(e_sec)
    wt, pt = by_year(w_tot), by_year(p_tot)
    return sectors, sec, wt, pt


def build_features(ds: Dataset, cfg: dict) -> Features:
    """Признаки x_{i,t}: 25 столбцов в шести блоках, винзоризация, стандартизация по панели, веса блоков."""
    fc, T = cfg["features"], len(ds.months)
    eps = fc["clr_pseudocount"]
    ids = ds.mo.index.to_numpy()
    cons = _smooth(ds.cons, cfg["data"]["smoothing_window"])
    total = _smooth(ds.cons_total[..., None], cfg["data"]["smoothing_window"])[..., 0]

    # --- потребление
    logt = np.log(total)
    level = logt - np.median(logt, axis=0, keepdims=True)                       # [N,T]
    shares = cons / cons.sum(-1, keepdims=True)                                 # [N,T,6]
    struct = clr(shares, eps)
    # сезонность: считаем по несглаженному ряду, внутри каждого года
    raw_rel = np.log(ds.cons_total) - np.median(np.log(ds.cons_total), axis=0, keepdims=True)
    months = pd.PeriodIndex(ds.months, freq="M")
    amp, summer = [], []
    for y in sorted(set(months.year)):
        m = months.year == y
        dev = raw_rel[:, m] - raw_rel[:, m].mean(1, keepdims=True)
        amp.append(dev.std(1))
        summer.append(dev[:, np.isin(months[m].month, [6, 7, 8])].mean(1))
    amp, summer = np.mean(amp, 0), np.mean(summer, 0)

    # --- Росстат
    years = sorted(set(months.year))
    sectors, sec, wt, pt = _annual_panel(ds, years)
    sectors_all = sectors + ["hidden"]
    ma = np.log(ds.market_access.to_numpy(dtype=float))

    rows = []
    for yi, y in enumerate(years):
        # Пустые ячейки БДПМО — это данные, скрытые по требованию конфиденциальности (обычно
        # 1–2 крупных работодателя). Их нельзя импутировать «как у соседей»: остаток
        # «итог − Σ раскрытых секторов» выделяется в сектор hidden — признак доминирования
        # одного предприятия (моногорода, ЗАТО, вахтовые МО).
        known = sec[yi][sectors]
        tot = sec[yi]["_total"].where(sec[yi]["_total"] > 0, known.sum(axis=1, min_count=1))
        has = tot.notna() & known.notna().any(axis=1)
        kn = known.fillna(0)
        hidden = (tot - kn.sum(axis=1)).clip(lower=0)
        denom = kn.sum(axis=1) + hidden
        sec_sh = kn.div(denom, axis=0).where(has)
        sec_sh["hidden"] = (hidden / denom).where(has)
        et_y = tot
        w_ok = wt[yi].where(wt[yi] > 0)
        p_ok = pt[yi].where(pt[yi] > 0)
        wage_rel = np.log(w_ok) - np.log(w_ok).median()
        emp_rate = et_y / p_ok
        rows.append(pd.DataFrame({**{f"sh_{s}": sec_sh[s] for s in sectors_all},
                                  "wage_rel": wage_rel, "emp_rate": emp_rate.clip(upper=1.5),
                                  "log_pop": np.log(p_ok), "log_ma": ma}, index=ids).assign(year=y))
    annual = pd.concat(rows).reset_index(names="territory_id").replace([np.inf, -np.inf], np.nan)

    # Импутация пропусков Росстата: kNN по потреблению и географии (похожие по тратам МО
    # похожи и по структуре экономики — это проверяется в отчёте на МО без пропусков).
    ann_cols = [c for c in annual.columns if c not in ("territory_id", "year")]
    miss_share = annual.groupby("territory_id")[ann_cols].apply(lambda g: g.isna().mean().mean())
    helper = np.column_stack([level.mean(1), struct.mean(1), amp, summer])
    helper = (helper - helper.mean(0)) / helper.std(0)
    filled = []
    for y in years:
        a = annual[annual.year == y].set_index("territory_id").reindex(ids)
        # доли секторов импутируем как доли, затем нормируем
        M = np.column_stack([helper, a[ann_cols].to_numpy()])
        M = KNNImputer(n_neighbors=fc.get("impute_neighbors", 10), weights="distance").fit_transform(M)[:, helper.shape[1]:]
        a[ann_cols] = M
        filled.append(a)

    # --- сборка панели
    names, blocks, cols = [], {}, []

    def add(block, fname, arr):  # arr: [N,T]
        """Добавить признак в блок."""
        blocks.setdefault(block, []).append(len(names))
        names.append(fname)
        cols.append(arr)

    add("consumption_level", "cons_level", level)
    for k, c in enumerate(CATEGORIES + ["Прочее"]):
        add("consumption_structure", f"clr_{CAT_SHORT[c]}", struct[..., k])
    add("seasonality", "season_amp", np.repeat(amp[:, None], T, 1))
    add("seasonality", "summer_peak", np.repeat(summer[:, None], T, 1))
    year_idx = np.array([years.index(y) for y in months.year])
    sec_sh = np.stack([f[[f"sh_{s}" for s in sectors_all]].to_numpy() for f in filled])   # [Y,N,S]
    sec_sh = np.clip(sec_sh, 0, None)
    sec_sh = sec_sh / sec_sh.sum(-1, keepdims=True)
    sec_clr = clr(sec_sh, eps)
    for k, s in enumerate(sectors_all):
        add("industry", f"clr_ind_{s}", sec_clr[year_idx, :, k].T)
    for c, b in [("wage_rel", "labour"), ("emp_rate", "labour"), ("log_ma", "geography"), ("log_pop", "geography")]:
        add(b, c, np.stack([f[c].to_numpy() for f in filled])[year_idx].T)

    Z = np.stack(cols, -1)                                                     # [N,T,D]
    flat = Z.reshape(-1, Z.shape[-1])
    lo, hi = np.nanpercentile(flat, [1, 99], axis=0)
    flat = np.clip(flat, lo, hi)
    flat = (flat - flat.mean(0)) / flat.std(0)
    Z = flat.reshape(Z.shape)
    for b, idx in blocks.items():
        Z[..., idx] *= fc["block_weights"][b] / np.sqrt(len(idx))
    X = Z.transpose(1, 0, 2)                                                   # [T,N,D]

    # интерпретируемые значения для профилей кластеров
    raw = {"cons_total_rub": ds.cons_total, "cons_level": level}
    for k, c in enumerate(CATEGORIES + ["Прочее"]):
        raw[f"share_{CAT_SHORT[c]}"] = shares[..., k]
    raw["season_amp"] = np.repeat(amp[:, None], T, 1)
    raw["summer_peak"] = np.repeat(summer[:, None], T, 1)
    for k, s in enumerate(sectors_all):
        raw[f"emp_share_{s}"] = sec_sh[year_idx, :, k].T
    for c in ["wage_rel", "emp_rate", "log_ma", "log_pop"]:
        raw[c] = np.stack([f[c].to_numpy() for f in filled])[year_idx].T
    idx = pd.MultiIndex.from_product([ds.months, ids], names=["month", "territory_id"])
    raw_df = pd.DataFrame({k: v.T.reshape(-1) for k, v in raw.items()}, index=idx)
    return Features(X=X.astype(np.float64), names=names, blocks=blocks, raw=raw_df, imputed=miss_share)
