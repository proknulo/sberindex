"""Единая точка запуска проекта — одинаково в Windows, macOS и Linux.

    python run.py setup        виртуальное окружение .venv и зависимости
    python run.py data         данные СберИндекса, справочник МО, выгрузка БДПМО Росстата (~30 мин, кэшируется)
    python run.py pipeline     признаки → графы → сравнение методов → итоговая модель (~10 мин)
    python run.py robustness   проверки надёжности (~5 мин)
    python run.py intracity    внутригородская структура Москвы и Санкт-Петербурга
    python run.py figures      рисунки для отчёта (results/figures)
    python run.py landing      данные для лендинга (landing/data.js, landing/geo.js)
    python run.py test         тесты индексов качества
    python run.py serve        открыть лендинг: http://localhost:8000
    python run.py all          data → pipeline → robustness → intracity → figures → landing → test

Все шаги после setup выполняются интерпретатором из .venv, если он есть.
"""
from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
VPY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
CFG = ["--config", "configs/default.yaml"]

STEPS = {
    "data": [["scripts/get_data.py"], ["scripts/download_rosstat.py"]],
    "pipeline": [["-m", "sbx.pipeline", *CFG]],
    "robustness": [["-m", "sbx.robustness", *CFG]],
    "intracity": [["-m", "sbx.intracity", *CFG]],
    "figures": [["-m", "sbx.figures", *CFG]],
    "landing": [["-m", "sbx.landing", *CFG]],
    "test": [["-m", "pytest", "-q", "tests"]],
}
ALL = ["data", "pipeline", "robustness", "intracity", "figures", "landing", "test"]


def python() -> str:
    return str(VPY) if VPY.exists() else sys.executable


def env() -> dict:
    # UTF-8 для вывода кириллицы в консоль Windows и для файлов без явной кодировки
    return {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(ROOT / "src")}


def call(args: list[str]) -> None:
    print(">", " ".join(args), flush=True)
    subprocess.run([python(), *args], cwd=ROOT, env=env(), check=True)


def setup() -> None:
    if not VPY.exists():
        print("> создаю .venv", flush=True)
        venv.create(VENV, with_pip=True)
    subprocess.run([str(VPY), "-m", "pip", "install", "-q", "--upgrade", "pip"], cwd=ROOT, check=True)
    subprocess.run([str(VPY), "-m", "pip", "install", "-q", "-r", "requirements.txt", "pytest"], cwd=ROOT, check=True)
    subprocess.run([str(VPY), "-m", "pip", "install", "-q", "-e", "."], cwd=ROOT, check=True)
    print("готово: окружение .venv")


def serve(port: int = 8000) -> None:
    import functools
    import http.server
    import webbrowser
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "landing"))
    url = f"http://localhost:{port}"
    print(f"лендинг: {url}  (Ctrl+C — остановить)")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    http.server.ThreadingHTTPServer(("", port), handler).serve_forever()


def main() -> None:
    # консоль Windows по умолчанию в cp1251/cp866: переключаем вывод на UTF-8, чтобы кириллица не падала
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "setup":
        setup()
    elif cmd == "serve":
        serve(int(sys.argv[2]) if len(sys.argv) > 2 else 8000)
    elif cmd == "all":
        for step in ALL:
            for args in STEPS[step]:
                call(args)
    elif cmd in STEPS:
        for args in STEPS[cmd]:
            call(args)
    else:
        print(__doc__)
        sys.exit(0 if cmd in ("help", "-h", "--help") else 1)


if __name__ == "__main__":
    main()
