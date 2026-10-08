"""Основной пайплайн анализа: python -m sbx pipeline

  1. данные → признаки узлов x_{i,t}                                   context.build_context
  2. выбор числа кластеров k по ICVI и устойчивости                    model_selection.select_k
  3. сравнение 7 правил построения рёбер                               model_selection.compare_edge_rules
  4. сравнение 9 методов кластеризации по всем месяцам                 model_selection.compare_methods
  5. итоговая динамическая модель и её выгрузки                        final_model.export_final_model

Результаты — в results/, промежуточные таблицы — в data/processed/.
"""
from __future__ import annotations

from .context import build_context
from .final_model import export_final_model
from .model_selection import compare_edge_rules, compare_methods, select_k


def run(cfg: dict) -> None:
    """Весь анализ от данных до итоговых выгрузок."""
    ctx = build_context(cfg)
    select_k(ctx)
    best, lag = compare_edge_rules(ctx)
    labels = compare_methods(ctx)
    export_final_model(ctx, labels, best, lag)
