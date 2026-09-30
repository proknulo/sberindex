"""Скачивание файлов с серверов Сбера (сертификаты НУЦ Минцифры)."""
import ssl, sys, urllib.request, pathlib

CERTS = pathlib.Path(__file__).resolve().parent.parent / "certs"
CERT_URLS = {
    "ru_root.crt": "https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt",
    "ru_sub.crt": "https://gu-st.ru/content/lending/russian_trusted_sub_ca_pem.crt",
}

def context():
    CERTS.mkdir(exist_ok=True)
    ctx = ssl.create_default_context()
    for name, url in CERT_URLS.items():
        p = CERTS / name
        if not p.exists():
            p.write_bytes(urllib.request.urlopen(url, timeout=60).read())
        ctx.load_verify_locations(str(p))
    return ctx

def fetch(url, out):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=context(), timeout=600) as r:
        data = r.read()
        pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(out).write_bytes(data)
        print(r.status, r.geturl(), r.headers.get("Content-Type"), len(data), "->", out)

if __name__ == "__main__":
    fetch(sys.argv[1], sys.argv[2])
