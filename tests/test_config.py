"""Конфигурация: все разделы гиперпараметров на месте, пути отсчитываются от корня проекта."""
from pathlib import Path

from sbx.config import PROJECT_ROOT, load_config, load_names


def test_default_config_has_all_sections():
    cfg = load_config()
    for section in ["paths", "data", "features", "graph", "clustering", "dynamics", "outputs", "robustness", "intracity"]:
        assert section in cfg, section
    assert set(cfg["features"]["block_weights"]) == {"consumption_level", "consumption_structure", "seasonality",
                                                     "industry", "labour", "geography"}


def test_paths_are_absolute_and_inside_project():
    cfg = load_config("configs/default.yaml")
    for p in cfg["paths"].values():
        assert Path(p).is_absolute() and Path(p).is_relative_to(PROJECT_ROOT)


def test_names_cover_every_cluster():
    cfg, names = load_config(), load_names()
    assert len(names["clusters"]) == cfg["clustering"]["k"]
    assert all({"name", "short", "desc"} <= set(c) for c in names["clusters"].values())
