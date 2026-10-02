"""Экспорт результатов в landing/data.js для интерактивного лендинга (landing/index.html).

Запуск после пайплайна: python -m sbx.landing --config configs/default.yaml
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .geo import write_geo_js


def short_name(n: str) -> str:
    """«городской округ город Норильск» → «Норильск», «Тайшетский муниципальный район» → «Тайшетский р-н»."""
    import re
    n = re.sub(r"^(городской округ|муниципальный округ|муниципальный район)\s+(город-курорт|город-герой|город|город-порт|закрытое административно-территориальное образование)?\s*", "", n)
    n = n.replace(" муниципальный район", " р-н").replace(" муниципальный округ", " м.о.").replace(" городской округ", " г.о.")
    return n.strip()


def _r(x, n=3):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


def build(cfg_path: str):
    cfg = yaml.safe_load(open(cfg_path))
    res = Path(cfg["paths"]["results"])
    proc = Path(cfg["paths"]["processed"])
    land = Path(cfg["paths"]["landing"]); land.mkdir(parents=True, exist_ok=True)
    names = yaml.safe_load(open("configs/cluster_names.yaml", encoding="utf-8"))

    mo = pd.read_parquet(proc / "mo.parquet")
    L = np.load(res / "final_labels.npy")
    months = pd.read_csv(res / "final_labels.csv", index_col=0).columns.tolist()
    raw = pd.read_parquet(proc / "features_raw.parquet")
    summ = pd.read_csv(res / "final_mo_summary.csv", index_col=0)
    twins = json.load(open(res / "final_twins.json"))
    ids = mo.index.to_numpy()

    write_geo_js(ids, Path(cfg["paths"]["raw"]), land)   # полигоны МО и субъектов для карты → landing/geo.js

    # по МО: метки по месяцам + ключевые показатели (декабрь 2024 и средние)
    last = raw.xs(months[-1], level="month")
    mean = raw.groupby(level="territory_id").mean()
    mos = []
    for i, tid in enumerate(ids):
        r, m = last.loc[tid], mean.loc[tid]
        mos.append({
            "id": int(tid), "n": mo.loc[tid, "name"], "r": mo.loc[tid, "region_name"], "t": mo.loc[tid, "mo_type"],
            "L": L[:, i].tolist(),
            "cons": int(r["cons_total_rub"]), "pop": int(np.exp(r["log_pop"])),
            "wage": _r(np.exp(r["wage_rel"]), 3), "ma": _r(np.exp(r["log_ma"]), 0),
            "sh": {k: _r(m[f"share_{k}"], 3) for k in ["food", "health", "catering", "transport", "marketplaces", "other"]},
            "emp": {c[10:]: _r(m[c], 3) for c in raw.columns if c.startswith("emp_share_")},
            "sa": _r(m["season_amp"], 3), "sp": _r(m["summer_peak"], 3),
            "tw": twins.get(str(int(tid)), []), "imp": _r(mo.loc[tid, "rosstat_imputed_share"], 2),
            "sw": int(summ.loc[tid, "n_switches"]), "conf": _r(summ.loc[tid, "type_confidence"], 2),
        })

    prof = pd.read_csv(res / "final_profiles.csv", index_col=0)
    profz = pd.read_csv(res / "final_profiles_z.csv", index_col=0)
    clusters = []
    for c in prof.index:
        members = summ[summ.modal_cluster == c].sort_values("pop", ascending=False)
        clusters.append({"id": int(c), **names["clusters"][int(c)],
                         "size": int(round(prof.loc[c, "n_mo_mean"])),
                         "prof": {k: _r(v, 4) for k, v in prof.loc[c].items()},
                         "z": {k: _r(v, 3) for k, v in profz.loc[c].items()},
                         "examples": [short_name(n) for n in members.name.head(8)]})

    # аллювиальная диаграмма: кварталы (каждый 3-й месяц)
    q = list(range(0, len(months), 3)) + ([len(months) - 1] if (len(months) - 1) % 3 else [])
    flows = []
    for a, b in zip(q[:-1], q[1:]):
        M = pd.crosstab(L[a], L[b])
        for i in M.index:
            for j in M.columns:
                if M.loc[i, j] > 0:
                    flows.append([a, int(i), b, int(j), int(M.loc[i, j])])

    tm = json.load(open(res / "final_temporal.json"))
    methods = pd.read_csv(res / "methods.csv").round(4).to_dict("records")
    edges = pd.read_csv(res / "edge_rules.csv").round(4).to_dict("records")
    ksel = pd.read_csv(res / "k_selection.csv").round(4).to_dict("records")
    events = pd.read_csv(res / "final_events.csv").to_dict("records")
    emb = json.load(open(res / "embedding.json")) if (res / "embedding.json").exists() else None
    tr = pd.read_csv(res / "final_type_trajectories.csv")
    traj = {int(c): {col: [_r(v, 4) for v in g[col]] for col in ["cons_total_rub", "share_marketplaces", "share_food", "share_catering"]}
            for c, g in tr.groupby("type")}
    adj = json.load(open(res / "final_transition_adjacency.json"))
    rob = pd.read_csv(res / "robustness_sensitivity.csv").round(3).to_dict("records") if (res / "robustness_sensitivity.csv").exists() else []
    spat = json.load(open(res / "robustness_spatial.json")) if (res / "robustness_spatial.json").exists() else None

    data = {"months": months, "mos": mos, "clusters": clusters, "flows": flows, "qsteps": q,
            "temporal": tm, "traj": traj, "adj": adj["transitions_to_two_nearest_types_share"], "rob": rob, "spat": spat,
            "methods": methods, "edges": edges, "ksel": ksel, "events": events, "emb": emb,
            "meta": names.get("meta", {})}
    js = "window.DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";"
    (land / "data.js").write_text(js, encoding="utf-8")
    print("landing/data.js", round(len(js) / 1e6, 2), "MB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    build(ap.parse_args().config)
