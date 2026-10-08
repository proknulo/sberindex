"""Сертификаты НУЦ Минцифры для запросов к серверам Сбера и Росстата.

Корневой и промежуточные сертификаты скачиваются с gu-st.ru / nuc-cdp.digital.gov.ru и
склеиваются с набором certifi в certs/bundle.pem. Файл используется только для этих запросов,
системное хранилище сертификатов не меняется.
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

import certifi

CERT_URLS = {
    "ru_root.crt": "https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt",
    "ru_sub.crt": "https://gu-st.ru/content/lending/russian_trusted_sub_ca_pem.crt",
    "subca_2024.pem": "http://nuc-cdp.digital.gov.ru/cdp/subca_ssl_rsa2024.crt",
}


def ca_bundle(certs_dir: Path) -> str:
    """Скачать недостающие сертификаты и собрать certs/bundle.pem; вернуть путь к нему."""
    certs_dir.mkdir(exist_ok=True)
    for name, url in CERT_URLS.items():
        p = certs_dir / name
        if not p.exists():
            p.write_bytes(urllib.request.urlopen(url, timeout=60).read())
    out = certs_dir / "bundle.pem"
    parts = [Path(certifi.where()).read_text(encoding="utf-8")] + \
            [(certs_dir / n).read_text(encoding="utf-8").replace("\r", "") for n in CERT_URLS]
    out.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return str(out)
