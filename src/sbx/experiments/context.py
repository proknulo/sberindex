"""Общий контекст шагов анализа: данные, признаки, опорный месяц и кэш графов."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

from ..config import log
from ..data import Dataset, load_all
from ..features import Features, build_features
from ..network import edges as G


@dataclass
class Context:
    """Всё, что нужно шагам пайплайна: конфиг, данные, признаки и графы по правилам и месяцам."""
    cfg: dict
    ds: Dataset
    F: Features
    rel: np.ndarray                 # [N, 6, T] относительные ряды трат для динамических правил
    ref_t: int                      # индекс опорного месяца
    out: Path                       # results/
    proc: Path                      # data/processed/
    _graphs: dict = field(default_factory=dict, repr=False)

    @property
    def X(self) -> np.ndarray:
        """Признаки [T, N, D]."""
        return self.F.X

    @property
    def months(self) -> list[str]:
        """Месяцы модели 'YYYY-MM'."""
        return self.ds.months

    @property
    def mo(self) -> pd.DataFrame:
        """Справочник отобранных МО (index = territory_id)."""
        return self.ds.mo

    @property
    def seed(self) -> int:
        """Зерно случайных процессов."""
        return self.cfg["seed"]

    @property
    def k(self) -> int:
        """Итоговое число типов."""
        return self.cfg["clustering"]["k"]

    @property
    def Xr(self) -> np.ndarray:
        """Признаки опорного месяца [N, D]."""
        return self.X[self.ref_t]

    def graph(self, rule: str, t: int) -> sp.csr_matrix:
        """Граф правила rule в месяце t (с кэшем)."""
        key = (rule, t)
        if key not in self._graphs:
            self._graphs[key] = G.build_graphs_for_month(rule, t, self.X, self.rel, self.cfg["graph"],
                                                         self.ds.road_km, self.F.blocks["consumption_structure"])
        return self._graphs[key]

    def main_graphs(self) -> list[sp.csr_matrix]:
        """Графы основного правила для всех месяцев."""
        return [self.graph(self.cfg["graph"]["main_rule"], t) for t in range(len(self.months))]


def build_context(cfg: dict) -> Context:
    """Загрузить данные, построить признаки и сохранить промежуточные таблицы в data/processed."""
    out = Path(cfg["paths"]["results"]); out.mkdir(parents=True, exist_ok=True)
    proc = Path(cfg["paths"]["processed"]); proc.mkdir(parents=True, exist_ok=True)
    log("загрузка данных")
    ds = load_all(cfg)
    F = build_features(ds, cfg)
    T, N, D = F.X.shape
    log(f"МО: {N}, месяцев: {T}, признаков: {D}")
    F.raw.to_parquet(proc / "features_raw.parquet")
    np.save(proc / "features_X.npy", F.X)
    ds.mo.assign(rosstat_imputed_share=F.imputed.reindex(ds.mo.index)).to_parquet(proc / "mo.parquet")
    ref_m = cfg["data"].get("reference_month", "2024-06")
    ref_t = ds.months.index(ref_m) if ref_m in ds.months else T // 2
    return Context(cfg=cfg, ds=ds, F=F, rel=G.relative_series(ds.cons, ds.cons_total), ref_t=ref_t, out=out, proc=proc)
