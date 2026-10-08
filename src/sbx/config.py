"""Конфигурация проекта: загрузка YAML и пути.

Все гиперпараметры лежат в configs/default.yaml, тексты и названия типов — в
configs/cluster_names.yaml. Относительные пути из раздела `paths` отсчитываются от корня
проекта, поэтому шаги можно запускать из любой папки.
"""
from __future__ import annotations

import time
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "default.yaml"
NAMES_CONFIG = PROJECT_ROOT / "configs" / "cluster_names.yaml"
CERTS_DIR = PROJECT_ROOT / "certs"


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    """Прочитать конфиг; пути из `paths` превращаются в абсолютные относительно корня проекта."""
    path = Path(path)
    if not path.is_absolute() and not path.exists():
        path = PROJECT_ROOT / path
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["paths"] = {k: str(v if Path(v).is_absolute() else PROJECT_ROOT / v) for k, v in cfg["paths"].items()}
    return cfg


def load_names() -> dict:
    """Названия, описания типов и тексты лендинга (configs/cluster_names.yaml)."""
    return yaml.safe_load(NAMES_CONFIG.read_text(encoding="utf-8"))


def log(*args) -> None:
    """Печать с меткой времени."""
    print(time.strftime("%H:%M:%S"), *args, flush=True)
