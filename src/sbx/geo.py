"""Подготовка геометрии МО для веб-карты.

Полигоны OSM из справочника СберИндекса проецируются в равновеликую коническую
проекцию Альберса для России (φ1=52°, φ2=64°, λ0=100°): Чукотка не разрывается
по 180-му меридиану, площади сопоставимы. Затем контуры упрощаются
(Дуглас–Пекер с сохранением топологии) и сериализуются в SVG-пути.
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import MultiPolygon, Polygon

ALBERS_RU = "+proj=aea +lat_1=52 +lat_2=64 +lat_0=0 +lon_0=100 +x_0=0 +y_0=0 +ellps=WGS84 +units=m +no_defs"


def _ring_path(coords, scale, x0, y_top):
    pts = [(round((x - x0) * scale, 1), round((y_top - y) * scale, 1)) for x, y in coords]
    return "M" + "L".join(f"{a} {b}" for a, b in pts) + "Z"


def svg_paths(ids: np.ndarray, raw: Path, width: float = 1000.0, tol_m: float = 3000.0):
    g = gpd.read_file(raw / "dict/t_dict_municipal_districts_poly.gpkg")
    g["territory_id"] = g["territory_id"].astype(int)
    g = g.sort_values("year_to").groupby("territory_id").tail(1)
    g = g[g.territory_id.isin(ids)].copy()
    g = g.to_crs(ALBERS_RU)
    g["geometry"] = g.geometry.simplify(tol_m, preserve_topology=True)
    x0, y0, x1, y1 = g.total_bounds
    scale = width / (x1 - x0)
    height = (y1 - y0) * scale
    paths = {}
    for tid, geom in zip(g.territory_id, g.geometry):
        polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
        parts = []
        for p in polys:
            if not isinstance(p, Polygon) or p.is_empty:
                continue
            # отбрасываем «пылинки» — острова площадью < 1 км² не видны на карте
            if p.area < 1e6 and len(polys) > 1:
                continue
            parts.append(_ring_path(p.exterior.coords, scale, x0, y1))
        paths[int(tid)] = "".join(parts)
    cent = g.set_index("territory_id").geometry.representative_point()
    cxy = {int(t): [round((p.x - x0) * scale, 1), round((y1 - p.y) * scale, 1)] for t, p in cent.items()}
    return paths, cxy, (width, height)


# ---------------------------------------------------------------- веб-карта на подложке (Leaflet)
# Координаты WGS84 кодируются целыми числами с шагом 1e-4° (≈10 м) и дельта-кодированием:
# кольцо [x0, y0, dx1, dy1, ...]. Это в 2,5–3 раза компактнее GeoJSON. Долготы < 0
# (восток Чукотки) сдвигаются на +360°, чтобы полигоны не разрывались по 180-му меридиану.
Q = 1e4


def _enc_ring(coords) -> list[int]:
    a = np.round(np.asarray(coords)[:, :2] * Q).astype(np.int64)
    d = np.vstack([a[:1], np.diff(a, axis=0)])
    d = d[np.any(d != 0, axis=1) | (np.arange(len(d)) == 0)]   # убрать повторы после квантования
    return d.ravel().tolist()


def _enc_geom(geom, min_area: float = 0.0) -> list:
    """(Multi)Polygon → [[кольцо, дыра, ...], ...]."""
    polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    out = []
    for p in polys:
        if not isinstance(p, Polygon) or p.is_empty or (len(polys) > 1 and p.area < min_area):
            continue
        out.append([_enc_ring(p.exterior.coords)] + [_enc_ring(r.coords) for r in p.interiors])
    return out


def _enc_lines(geom) -> list:
    from shapely.geometry import LineString, MultiLineString
    if isinstance(geom, (LineString,)):
        lines = [geom]
    elif isinstance(geom, MultiLineString):
        lines = geom.geoms
    else:
        lines = [x for x in getattr(geom, "geoms", [geom]) if isinstance(x, LineString)]
    return [_enc_ring(l.coords) for l in lines if not l.is_empty and len(l.coords) > 1]


def _shift_east(geom):
    from shapely.ops import transform
    return transform(lambda x, y, z=None: (np.where(x < 0, x + 360, x), y), geom)


def web_layers(ids: np.ndarray, raw: Path, tol_deg: float = 0.003, tol_other: float = 0.006,
               tol_region: float = 0.004) -> dict:
    """Слои для Leaflet: МО модели, остальные МО («нет в модели»), границы и подписи субъектов."""
    from shapely import make_valid
    g = gpd.read_file(raw / "dict/t_dict_municipal_districts_poly.gpkg")
    g["territory_id"] = g["territory_id"].astype(int)
    g = g.sort_values("year_to").groupby("territory_id").tail(1).set_index("territory_id")
    d = pd.read_excel(raw / "dict/t_dict_municipal_districts.xlsx")
    d = d.sort_values("year_to").groupby("territory_id").tail(1).set_index("territory_id")
    g = g.join(d[["region_code", "region_name", "municipal_district_name"]], how="left")
    valid = [make_valid(x) for x in g.geometry]

    # маска «всё, кроме России»: прямоугольник мира минус объединение всех МО справочника.
    # Строится в исходных долготах (−180…180): в соседней копии мира дыра Чукотки
    # совпадает с её полигоном, сдвинутым на +360°.
    from shapely import union_all
    from shapely.geometry import box
    land = union_all([x.simplify(0.01).buffer(0.02) for x in valid]).buffer(-0.02).simplify(0.01)
    mask = box(-180, -85, 180, 85).difference(land)
    russia = {"mask": _enc_geom(mask), "outline": _enc_lines(_shift_east(land).boundary)}

    g["geometry"] = [_shift_east(x) for x in valid]

    sel = g.index.isin(ids)
    mo = {int(t): _enc_geom(geom.simplify(tol_deg, preserve_topology=True), min_area=1e-4)
          for t, geom in g[sel].geometry.items()}
    # точка внутри каждого МО — место для значка типа на карте
    mo_pt = {int(t): [round(p.x, 4), round(p.y, 4)] for t, p in g[sel].geometry.representative_point().items()}
    other = [{"n": r.municipal_district_name, "r": r.region_name,
              "g": _enc_geom(r.geometry.simplify(tol_other, preserve_topology=True), min_area=1e-4)}
             for r in g[~sel].itertuples()]

    reg = g.dropna(subset=["region_code"]).dissolve(by="region_code", aggfunc={"region_name": "first"})
    regions = []
    for code, r in reg.iterrows():
        geom = make_valid(r.geometry).buffer(0)
        # подпись — в «центре» самой большой части субъекта
        parts = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
        pt = max(parts, key=lambda p: p.area).representative_point()
        regions.append({"code": int(code), "n": r.region_name,
                        "b": _enc_lines(geom.simplify(tol_region, preserve_topology=True).boundary),
                        "c": [round(pt.y, 3), round(pt.x, 3)], "a": round(geom.area, 1)})
    return {"q": Q, "mo": mo, "pt": mo_pt, "other": other, "regions": regions, "russia": russia}


def write_geo_js(ids: np.ndarray, raw: Path, landing: Path) -> None:
    import json
    layers = web_layers(ids, raw)
    js = "window.GEO = " + json.dumps(layers, ensure_ascii=False, separators=(",", ":")) + ";"
    (landing / "geo.js").write_text(js, encoding="utf-8")
    print("landing/geo.js", round(len(js) / 1e6, 2), "MB")


if __name__ == "__main__":
    # Пересборка только геометрии карты по уже готовому landing/data.js:
    # python -m sbx.geo --config configs/default.yaml
    import argparse
    import json

    import yaml
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    cfg = yaml.safe_load(open(ap.parse_args().config, encoding="utf-8"))
    land = Path(cfg["paths"]["landing"])
    s = (land / "data.js").read_text(encoding="utf-8")
    ids = np.array([m["id"] for m in json.loads(s[s.index("{"):s.rindex("}") + 1])["mos"]])
    write_geo_js(ids, Path(cfg["paths"]["raw"]), land)
