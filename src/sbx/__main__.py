"""Командная строка проекта: python -m sbx <шаг> [--config configs/default.yaml]

Шаги:
  data        скачать данные СберИндекса, справочник МО и выгрузку БДПМО Росстата
  pipeline    признаки → графы → выбор k → правила рёбер → методы → итоговая модель
  robustness  проверки устойчивости итоговой модели
  intracity   районы Москвы и Санкт-Петербурга
  figures     рисунки для отчёта
  landing     данные для лендинга (landing/data/)
  map         пересобрать только геометрию карты лендинга
  catalog     сохранить каталог наборов СберИндекса в data/sberindex_api/list.json
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .config import DEFAULT_CONFIG, PROJECT_ROOT, load_config


def _data(cfg):
    from .data import download
    download.run(cfg)


def _pipeline(cfg):
    from .experiments import pipeline
    pipeline.run(cfg)


def _robustness(cfg):
    from .evaluation import robustness
    robustness.run(cfg)


def _intracity(cfg):
    from .experiments import intracity
    intracity.run(cfg)


def _figures(cfg):
    from .reporting import figures
    figures.run(cfg)


def _landing(cfg):
    from .reporting import landing
    landing.run(cfg)


def _map(cfg):
    from .reporting import geo
    geo.rebuild_map(cfg)


def _catalog(cfg):
    from .data.download import catalog_api
    n = catalog_api.save_catalog(PROJECT_ROOT / "data" / "sberindex_api" / "list.json")
    print("наборов в каталоге:", n)


STEPS = {"data": _data, "pipeline": _pipeline, "robustness": _robustness, "intracity": _intracity,
         "figures": _figures, "landing": _landing, "map": _map, "catalog": _catalog}


def main(argv: list[str] | None = None) -> None:
    """Разобрать аргументы и выполнить шаг."""
    ap = argparse.ArgumentParser(prog="python -m sbx", description="Шаги проекта «Типы локальных экономик России».",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split("Шаги:")[1])
    ap.add_argument("step", choices=STEPS, help="что выполнить")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="файл гиперпараметров (по умолчанию configs/default.yaml)")
    args = ap.parse_args(argv)
    STEPS[args.step](load_config(args.config))


if __name__ == "__main__":
    main()
