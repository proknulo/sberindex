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
