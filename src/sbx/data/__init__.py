"""Данные: загрузка и согласование источников СберИндекса и Росстата по territory_id.

Единица анализа — муниципальное образование в постоянных границах (territory_id
из справочника СберИндекса). Скачивание исходных файлов — подпакет download.
"""
from .catalog import CAT_SHORT, CATEGORIES, OKVED_GROUPS, OKVED_TOTAL, SECTOR_RU, TOTAL
from .dataset import Dataset, load_all, month_range

__all__ = ["CAT_SHORT", "CATEGORIES", "OKVED_GROUPS", "OKVED_TOTAL", "SECTOR_RU", "TOTAL",
           "Dataset", "load_all", "month_range"]
