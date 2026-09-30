"""Скачивание открытых данных СберИндекса (CC BY-SA 4.0).

  1. Набор данных конкурса по МО: consumption / market_access / connection (parquet)
     https://sberindex.ru/ru/research/data-sense-opisanie-nabora-dannikh-khakatona-sberindeksa-po-munitsipalnim-dannim
  2. Справочник границ и преобразований МО (territory_id, ОКТМО, полигоны)
     https://sberindex.ru/ru/research/dataset-borders-and-changes-of-municipalities

Серверы Сбера и Росстата используют сертификаты НУЦ Минцифры: корневой и
промежуточные сертификаты скачиваются с gu-st.ru / nuc-cdp.digital.gov.ru и
добавляются к certifi только для этих запросов (системное хранилище не меняется).
"""
import subprocess
import urllib.request
import zipfile
from pathlib import Path

import certifi
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw"
CERTS = ROOT / "certs"

CERT_URLS = {
    "ru_root.crt": "https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt",
    "ru_sub.crt": "https://gu-st.ru/content/lending/russian_trusted_sub_ca_pem.crt",
    "subca_2024.pem": "http://nuc-cdp.digital.gov.ru/cdp/subca_ssl_rsa2024.crt",
}
DATA = {
    "hackathon.zip": "https://www.sberbank.com/common/img/uploaded/files/pdf/sberindex/hackathonlicence.zip",
    "municipal_dict.rar": "https://s.sber.ru/GthXk7",
}


def bundle() -> str:
    CERTS.mkdir(exist_ok=True)
    for name, url in CERT_URLS.items():
        p = CERTS / name
        if not p.exists():
            p.write_bytes(urllib.request.urlopen(url, timeout=60).read())
    out = CERTS / "bundle.pem"
    parts = [Path(certifi.where()).read_text()] + [(CERTS / n).read_text().replace("\r", "") for n in CERT_URLS]
    out.write_text("\n".join(parts) + "\n")
    return str(out)


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    verify = bundle()
    for name, url in DATA.items():
        dst = RAW / name
        if not dst.exists():
            r = requests.get(url, verify=verify, timeout=600, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            dst.write_bytes(r.content)
            print("скачан", dst, len(r.content) // 1024, "КБ")
    with zipfile.ZipFile(RAW / "hackathon.zip") as z:
        for info in z.infolist():
            if info.filename.endswith(".parquet"):
                z.extract(info, RAW)
    (RAW / "dict").mkdir(exist_ok=True)
    # RAR v5: распаковывает bsdtar (есть в macOS и большинстве Linux)
    subprocess.run(["bsdtar", "-xf", str(RAW / "municipal_dict.rar"), "-C", str(RAW / "dict")], check=True)
    print("готово:", sorted(p.name for p in (RAW / "hackathonlicence").glob("*.parquet")))


if __name__ == "__main__":
    main()
