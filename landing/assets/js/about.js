// Почему можно доверять, скачивание CSV, подвал.
// Классический скрипт: файлы подключаются в index.html по порядку и делят общие глобальные имена.
const best = D.methods.find(r => r.method === D.meta.final_method);
$("trust").innerHTML = `
  <div><h3>Метод выбран сравнением</h3><p>Мы не назначили метод заранее, а сравнили ${D.edges.filter(r => r.method === "spectral").length} правил построения сети и ${D.methods.length} методов кластеризации по шести индексам качества (SW, CH, S_Dbw, AVI, AVU, MQ), стабильности во времени и устойчивости к подвыборке. Итоговая модель — лучшая по среднему рангу.</p></div>
  <div><h3>Число типов не на глаз</h3><p>Индексы качества почти монотонны по числу типов, поэтому k выбрано по устойчивости: наибольшее k, при котором разбиение воспроизводится на случайных 80% муниципалитетов с ARI не ниже 0,8. При 8 типах это так, при 9 устойчивость обрывается до 0,53.</p></div>
  <div><h3>Результат устойчив</h3><p>Соседние месяцы совпадают с ARI ${f2(best ? best.ARI_consecutive : D.temporal.ARI_consecutive)}. Смена случайного зерна, масштаба ядра и памяти модели почти не меняет разбиение (ARI 0,93–1,00). Ядро типологии переживает изменение весов признаков; чувствительны только два переходных сибирских типа, и мы так и пишем.</p></div>
  <div><h3>Карта подтверждает</h3><p>Координат в модели нет, но ${D.spat ? `соседи по дороге совпадают по типу в ${pct(D.spat.observed_same_cluster_share)} случаев против ${pct(D.spat.null_mean)} при случайных метках (z = ${ru.format(".0f")(D.spat.z)})` : "типы складываются в связные районы"}. Типы совпадают с известными экономическими районами: нефтегазовые Югра и Ямал, алмазная Якутия, Подмосковье.</p></div>
  <div><h3>Индексы проверены тестами</h3><p>Реализации AVI, AVU, MQ и S_Dbw проверены автотестами на графах с заранее известным ответом. Там же зафиксировано свойство AVU: при двух кластерах он равен 1 для любого разбиения.</p></div>
  <div><h3>Ограничения названы</h3><p>Два года данных, отраслевая структура только по крупным и средним организациям, безналичные траты без наличных, восемь регионов без данных СберИндекса. Все ограничения перечислены в отчёте.</p></div>`;
$("csvBtn").onclick = () => {
  const esc = s => `"${String(s).replace(/"/g, '""')}"`;
  const head = ["territory_id", "name", "region", ...D.months].join(",");
  const rows = D.mos.map(m => [m.id, esc(m.n), esc(m.r), ...m.L.map(l => l + 1)].join(","));
  const legend = CL.map(c => `# ${c.id + 1} = ${c.name}`).join("\n");
  const blob = new Blob(["﻿" + legend + "\n" + head + "\n" + rows.join("\n")], {type: "text/csv;charset=utf-8"});
  const a = Object.assign(document.createElement("a"), {href: URL.createObjectURL(blob), download: "municipal_types_by_month.csv"});
  a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
};
$("csvIntraBtn").onclick = () => {
  const esc = s => `"${String(s).replace(/"/g, '""')}"`;
  const head = ["territory_id", "district", "city", ...D.months].join(",");
  const rows = INTRA.mos.map(m => [m.id, esc(m.n), esc(m.r), ...m.L.map(l => l + 1)].join(","));
  const legend = ICL.map(c => `# ${c.id + 1} = ${c.name}`).join("\n");
  const blob = new Blob(["\ufeff" + legend + "\n" + head + "\n" + rows.join("\n")], {type: "text/csv;charset=utf-8"});
  const a = Object.assign(document.createElement("a"), {href: URL.createObjectURL(blob), download: "moscow_spb_district_types_by_month.csv"});
  a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
};
$("foot").innerHTML = (D.meta.footer || "") + " Подложка карты: © OpenStreetMap, OpenFreeMap.";
