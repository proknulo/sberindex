"""Клиент публичного API СберИндекса (sberindex.ru/api).

Часть маршрутов (например, /dataset/v1/list) доступна только через прокси
/api/sowa, который принимает маршрут и тело в base64-обёртке. Запросы идут
через системный curl: он умеет достраивать цепочку сертификатов сайта.
"""
import base64, json, re, subprocess, uuid

BASE = "https://sberindex.ru/api"


def _curl(args):
    out = subprocess.run(["curl", "-sS", "--max-time", "120", *args], capture_output=True, check=True)
    return out.stdout


def _decode(v):
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


def sowa_get(route):
    body = {"SOWA": {"method": "GET", "route": base64.b64encode(route.encode()).decode(),
                     "data": {"type": "object", "value": []}}}
    raw = _curl(["-X", "POST", "-H", "Content-Type: application/json",
                 "-H", f"RqUID: {uuid.uuid4().hex}", "--data", json.dumps(body), f"{BASE}/sowa"])
    return _decode(json.loads(raw)["SOWA"]["data"])


def get(route):
    raw = _curl(["-H", f"RqUID: {uuid.uuid4().hex}", BASE + route])
    return json.loads(raw)
