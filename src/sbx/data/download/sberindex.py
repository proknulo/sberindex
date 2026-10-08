"""Скачивание открытых данных СберИндекса (CC BY-SA 4.0).

  1. Набор данных конкурса по МО: consumption / market_access / connection (parquet)
     https://sberindex.ru/ru/research/data-sense-opisanie-nabora-dannikh-khakatona-sberindeksa-po-munitsipalnim-dannim
  2. Справочник границ и преобразований МО (territory_id, ОКТМО, полигоны)
     https://sberindex.ru/ru/research/dataset-borders-and-changes-of-municipalities
"""
from __future__ import annotations

import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import requests

from .certs import ca_bundle

DATA = {
    "hackathon.zip": "https://www.sberbank.com/common/img/uploaded/files/pdf/sberindex/hackathonlicence.zip",
    "municipal_dict.rar": "https://s.sber.ru/GthXk7",
}


def rar_tool() -> str:
    """Чем распаковать RAR v5. Нужен bsdtar (libarchive): в macOS и Windows 10+ это системный `tar`,
    в Linux — пакет libarchive-tools (`bsdtar`). GNU tar RAR не читает."""
    cands = [shutil.which("bsdtar"), shutil.which("tar")]
    if os.name == "nt":   # системный tar Windows — это bsdtar; в Git Bash его может заслонять GNU tar
        cands.append(os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "tar.exe"))
    for exe in filter(None, cands):
        try:
            if "bsdtar" in subprocess.run([exe, "--version"], capture_output=True, text=True).stdout:
                return exe
        except OSError:
            continue
    raise SystemExit("Не найден bsdtar для распаковки справочника МО (RAR). "
                     "Linux: sudo apt install libarchive-tools; macOS и Windows 10+: встроенный tar.")


def download(raw: Path, certs_dir: Path) -> None:
    """Скачать набор конкурса и справочник МО в raw и распаковать (уже скачанное не перекачивается)."""
    raw.mkdir(parents=True, exist_ok=True)
    verify = ca_bundle(certs_dir)
    for name, url in DATA.items():
        dst = raw / name
        if not dst.exists():
            r = requests.get(url, verify=verify, timeout=600, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            dst.write_bytes(r.content)
            print("скачан", dst, len(r.content) // 1024, "КБ")
    with zipfile.ZipFile(raw / "hackathon.zip") as z:
        for info in z.infolist():
            if info.filename.endswith(".parquet"):
                z.extract(info, raw)
    (raw / "dict").mkdir(exist_ok=True)
    subprocess.run([rar_tool(), "-xf", str(raw / "municipal_dict.rar"), "-C", str(raw / "dict")], check=True)
    print("готово:", sorted(p.name for p in (raw / "hackathonlicence").glob("*.parquet")))
