"""Выгрузка показателей из Базы данных показателей муниципальных образований (БДПМО) Росстата.

БДПМО разбита на региональные базы munst{код ОКАТО региона}. Для каждого показателя
скрипт открывает форму запроса, берёт из её JS коды всех значений измерений
(муниципалитеты, ОКВЭД, годы) и отправляет запрос на построение таблицы, как это
делает кнопка «Показать таблицу». HTML-ответы кэшируются в data/raw/rosstat/html.

Показатели:
  8423005 — среднесписочная численность работников организаций (без МСП), по разделам ОКВЭД2
  8423007 — среднемесячная заработная плата работников организаций (без МСП), по разделам ОКВЭД2
  8112027 — оценка численности населения на 1 января

Запуск: python scripts/download_rosstat.py
"""
import io
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data/raw/rosstat/html"
OUT = ROOT / "data/raw/rosstat"
HOST = "https://rosstat.gov.ru"
INDICATORS = {"8423005": "employees", "8423007": "wage", "8112027": "population"}
YEARS = ["2021", "2022", "2023", "2024"]
PERIOD_FULL_YEAR = "79"  # «январь-декабрь»
MO_DIMS = ("munr", "tippos", "oktmo")

S = requests.Session()
S.verify = str(ROOT / "certs/bundle.pem")
S.headers["User-Agent"] = "Mozilla/5.0"


def post(url, data, cache_file):
    if cache_file.exists():
        return cache_file.read_text()
    failed = cache_file.with_suffix(".failed")
    if failed.exists():
        raise RuntimeError(f"ранее не удалось: {url} {data.get('pl')}")
    for attempt in range(4):
        try:
            r = S.post(url, data=data, timeout=180)
            r.encoding = "cp1251"
            if r.status_code == 200:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(r.text)
                return r.text
        except requests.RequestException as e:
            print("  retry", attempt, e, file=sys.stderr)
        time.sleep(3 * (attempt + 1))
    failed.parent.mkdir(parents=True, exist_ok=True)
    failed.write_text("")
    raise RuntimeError(f"failed {url} {data.get('pl')}")


def region_codes():
    html = S.get(f"{HOST}/storage/mediabank/Munst.htm", timeout=60)
    html.encoding = html.apparent_encoding
    return sorted(set(re.findall(r"munst(\d+)/DBInet\.cgi", html.text)), key=int)


def parse_form(html):
    """Измерения формы: имя -> (коды, подписи)."""
    dims = {}
    for name in re.findall(r'<SELECT NAME="(\w+)"', html):
        codes = re.findall(r'p_%s\[\d+\]="([^"]*)"' % name, html)
        block = re.search(r'<SELECT NAME="%s".*?</SELECT>' % name, html, re.S).group(0)
        labels = [re.sub(r"\s+", " ", x).replace("</SELECT>", "").strip()
                  for x in re.split(r"<OPTION[^>]*>", block)[1:]]
        dims[name] = (codes, labels)
    return dims


def build_query(dims):
    sel, z, s, b = {}, ["Pokazateli"], [], []
    for name, (codes, _) in dims.items():
        if name == "Pokazateli":
            sel[name] = codes
        elif name == "god":
            sel[name] = [y for y in codes if y in YEARS]
            s.insert(0, name)
        elif name == "period":
            sel[name] = [PERIOD_FULL_YEAR] if PERIOD_FULL_YEAR in codes else codes[-1:]
            z.append(name)
        elif name == "oktmo":
            sel[name] = [c for c in codes if re.fullmatch(r"\d{2}[5-7]\d{2}000", c.zfill(8))]  # у регионов 01–09 ведущий 0 опущен
            b.append(name)
        elif name in MO_DIMS:
            sel[name] = codes
            b.append(name)
        else:
            sel[name] = codes
            (z if len(codes) == 1 else s).append(name)
    qry = "".join(f"{k}:{','.join(v)};" for k, v in sel.items())

    def gm(names, suffix):
        return "".join(f"{n}_{suffix}:{i + 1 if len(names) > 1 else 1};" for i, n in enumerate(names))

    b.sort(key=MO_DIMS.index)
    return qry, gm(z, "z") + gm(s, "s") + gm(b, "b"), sel, s, len(b)


def _num(cell):
    txt = re.sub(r"<[^>]+>|&nbsp;|\s", "", cell).replace(",", ".")
    try:
        return float(txt)
    except ValueError:
        return None


def _header_keys(trs, dims, col_dims):
    """Ключи колонок из шапки таблицы: сервер выкидывает пустые колонки, поэтому
    порядок выбора использовать нельзя."""
    hdr = [tr for tr in trs if "TblShap" in tr][:len(col_dims)]
    flat = []
    for tr, d in zip(hdr, col_dims):
        codes, labels = dims[d]
        lab2code = {re.sub(r"\s+", " ", lab).strip(): c for c, lab in zip(codes, labels)}
        level = []
        for attrs, txt in re.findall(r"<TD class=TblShap([^>]*)>(.*?)</TD>", tr, re.S | re.I):
            txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>|&nbsp;", " ", txt)).strip()
            if not txt:
                continue
            span = re.search(r"colspan=(\d+)", attrs)
            n = int(span.group(1)) if span and int(span.group(1)) > 0 else 1
            level += [lab2code[txt]] * n
        flat.append(level)
    n_cols = len(flat[-1])
    return [[lvl[i] if len(lvl) == n_cols else lvl[i % len(lvl)] for lvl in flat] for i in range(n_cols)]


def parse_table(html, dims, sel, col_dims, n_row_dims):
    """Строки нижнего уровня (класс bL{n-1}) — это МО; колонки — из шапки таблицы."""
    trs = re.findall(r"<TR>(.*?)</TR>", html, re.S | re.I)
    col_keys = _header_keys(trs, dims, col_dims)
    okt_codes, okt_labels = dims["oktmo"]
    selected = set(sel["oktmo"])
    queue = {}  # подпись -> очередь кодов (подписи бывают неуникальны)
    for c, lab in zip(okt_codes, okt_labels):
        if c in selected:
            queue.setdefault(lab, []).append(c)
    leaf = f"bL{n_row_dims - 1}"
    rows = []
    for tr in trs:
        m = re.search(r"<p\s+class=(bL\d+)[^>]*>(.*?)</p>", tr, re.S)
        if not m or m.group(1) != leaf:
            continue
        lab = re.sub(r"\s+", " ", m.group(2)).strip()
        if not queue.get(lab):
            continue
        code = queue[lab].pop(0)
        cells = re.findall(r"<TD align=right>(.*?)</TD>", tr, re.S | re.I)
        if len(cells) != len(col_keys):
            raise ValueError(f"{lab}: {len(cells)} ячеек, ожидалось {len(col_keys)}")
        for key, cell in zip(col_keys, cells):
            v = _num(cell)
            if v is not None:
                rows.append({"oktmo8": code.zfill(8), "mo_name": lab, **dict(zip(col_dims, key)), "value": v})
    matched = len({r["oktmo8"] for r in rows})
    return rows, matched, len(selected)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    regions = region_codes()
    print("regions:", len(regions))
    for pl, short in INDICATORS.items():
        out_file = OUT / f"{short}.parquet"
        if out_file.exists():
            print("skip", out_file)
            continue
        frames = []
        for reg in regions:
            url = f"{HOST}/dbscripts/munst/munst{reg}/DBInet.cgi"
            try:
                form = post(url, {"pl": pl}, CACHE / f"form_{pl}_{reg}.html")
                dims = parse_form(form)
                if "oktmo" not in dims or not dims["Pokazateli"][0]:
                    print(f"  {reg}: нет показателя {pl}")
                    continue
                qry, gm, sel, col_dims, n_b = build_query(dims)
                years = ";".join(dims["god"][0]) + ";" if "god" in dims else ";"
                html = post(url, {"rdLayoutType": "Au", "Qry": qry, "QryGm": gm, "QryFootNotes": ";",
                                  "YearsList": years, "tbl": "Показать таблицу"},
                            CACHE / f"table_{pl}_{reg}.html")
                rows, matched, total = parse_table(html, dims, sel, col_dims, n_b)
                df = pd.DataFrame(rows)
                df["region_db"] = reg
                frames.append(df)
                print(f"  {pl} {reg}: {matched}/{total} МО, {len(df)} значений")
            except Exception as e:  # регион без данных или со сбоем — фиксируем и идём дальше
                print(f"  {pl} {reg}: ОШИБКА {e}")
        res = pd.concat(frames, ignore_index=True)
        res.to_parquet(out_file)
        print("saved", out_file, res.shape)


if __name__ == "__main__":
    main()
