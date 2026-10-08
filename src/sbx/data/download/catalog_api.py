"""Клиент публичного API СберИндекса (sberindex.ru/api).

Часть маршрутов (например, /dataset/v1/list) доступна только через прокси
/api/sowa, который принимает маршрут и тело в base64-обёртке. Запросы идут
через системный curl: он умеет достраивать цепочку сертификатов сайта.

Каталог наборов СберИндекса сохраняется в data/sberindex_api/list.json: python -m sbx catalog.
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
import uuid
from pathlib import Path

BASE = "https://sberindex.ru/api"


def _curl(args: list[str]) -> bytes:
    out = subprocess.run(["curl", "-sS", "--max-time", "120", *args], capture_output=True, check=True)
    return out.stdout


def _decode(v):
    """Развернуть типизированную обёртку ответа прокси /api/sowa в обычные значения Python."""
    if isinstance(v, list):
        return [_decode(x) for x in v]
    if isinstance(v, dict) and v.get("type") == "object":
        res = {}
        for item in v["value"]:
            if item["type"] == "longstring":
                return "".join(_decode(item["value"]))
            res[item["key"]] = _decode(item["value"])
        return res
    m = re.match(r"^__([a-z0-9]*)__(.*)", str(v), re.S)
    if not m:
        return v
    t, val = m.groups()
    if t == "null":
        return None
    if t == "number":
        return float(val)
    if t == "boolean":
        return val == "true"
    if t == "string":
        return base64.b64decode(val).decode("utf-8")
    return val


def sowa_get(route: str):
    """GET-запрос к маршруту API через прокси /api/sowa."""
    body = {"SOWA": {"method": "GET", "route": base64.b64encode(route.encode()).decode(),
                     "data": {"type": "object", "value": []}}}
    raw = _curl(["-X", "POST", "-H", "Content-Type: application/json",
                 "-H", f"RqUID: {uuid.uuid4().hex}", "--data", json.dumps(body), f"{BASE}/sowa"])
    return _decode(json.loads(raw)["SOWA"]["data"])


def get(route: str):
    """Прямой GET-запрос к открытому маршруту API."""
    raw = _curl(["-H", f"RqUID: {uuid.uuid4().hex}", BASE + route])
    return json.loads(raw)


def save_catalog(path: Path) -> int:
    """Сохранить каталог наборов данных СберИндекса (/dataset/v1/list) в JSON; вернуть число наборов."""
    data = sowa_get("/dataset/v1/list")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(data)
