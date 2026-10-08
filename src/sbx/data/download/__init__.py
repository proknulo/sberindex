"""Скачивание исходных данных: открытые наборы СберИндекса и БДПМО Росстата (python -m sbx data)."""
from __future__ import annotations

from pathlib import Path

from ...config import CERTS_DIR
from . import rosstat, sberindex


def run(cfg: dict) -> None:
    """Скачать всё в paths.raw: набор конкурса и справочник МО СберИндекса, затем показатели Росстата."""
    raw = Path(cfg["paths"]["raw"])
    sberindex.download(raw, CERTS_DIR)
    rosstat.download(raw, CERTS_DIR)
