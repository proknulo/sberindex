// Методы: шаги модели, таблицы сравнений, профили типов.
// Классический скрипт: файлы подключаются в index.html по порядку и делят общие глобальные имена.
$("steps").innerHTML = (D.meta.method_cards || []).map((c, i) =>
  `<details${i === 0 ? " open" : ""}><summary><span>${i + 1}</span>${c.title}</summary><p>${c.text}</p>${c.formula ? `<div class="formula">${c.formula}</div>` : ""}</details>`).join("");
const RULE_RU = D.meta.rule_ru || {}, METHOD_RU = D.meta.method_ru || {};
const num = (k, v) => v == null || Number.isNaN(v) ? "—" : k === "CH" ? fmt(v) : f3(v);
// пояснения к столбцам: показываются при наведении на заголовок
const COL_TIP = {
  SW: "<b>Силуэт (SW)</b><br>Насколько муниципалитет ближе к своему типу, чем к соседнему. От −1 до 1, больше — лучше.",
  CH: "<b>Калински–Харабаш (CH)</b><br>Отношение разброса между типами к разбросу внутри них. Больше — лучше.",
  S_Dbw: "<b>S_Dbw</b><br>Рассеяние внутри типов плюс плотность точек между ними. Меньше — лучше.",
  AVI: "<b>Изолированность (AVI)</b><br>Доля веса рёбер сети, которая остаётся внутри типа. Больше — лучше.",
  AVU: "<b>Объединяемость (AVU)</b><br>Насколько пары типов связаны рёбрами друг с другом. Меньше — лучше.",
  MQ: "<b>Качество модуляризации (MQ)</b><br>Плотность связей внутри типов минус плотность между ними. Больше — лучше.",
  ARI_consecutive: "<b>Стабильность</b><br>ARI между разбиениями соседних месяцев: насколько типы сохраняются во времени.",
  bootstrap_ARI: "<b>Устойчивость</b><br>ARI при повторной кластеризации на случайных 80% муниципалитетов (30 повторов).",
  stability: "<b>Устойчивость</b><br>ARI на подвыборках 80%. Правило выбора k: наибольшее k с устойчивостью не ниже 0,8.",
  share_same_region: "<b>Рёбер в регионе</b><br>Доля рёбер, соединяющих муниципалитеты одного субъекта. Высокая доля — сеть повторяет карту.",
  median_edge_km: "<b>Медиана ребра</b><br>Типичное расстояние по дороге между связанными муниципалитетами.",
  transitivity: "<b>Транзитивность</b><br>Насколько часто соседи соседа тоже соседи. Низкая — сообщества в сети размыты.",
  ARI_ref_month: "<b>ARI, июнь 2024</b><br>Совпадение с базовой моделью в контрольном месяце. 1 — разбиение не изменилось.",
  ARI_panel: "<b>ARI, вся панель</b><br>Совпадение с базовой моделью по всем 24 месяцам сразу.",
  switch_rate: "<b>Переходов в месяц</b><br>Средняя доля муниципалитетов, сменивших тип за месяц."
};
const LOWER_BETTER = new Set(["S_Dbw", "AVU"]);
let sortState = {};
function table(id, cols, rows, first, isBest) {
  const s = sortState[id];
  if (s) rows = [...rows].sort((a, b) => (s.dir) * ((a[s.k] ?? -Infinity) - (b[s.k] ?? -Infinity)));
  // лучшее значение в каждом столбце ICVI — в подсказке строки
  return `<table class="t" data-table="${id}"><thead><tr><th>${first}</th>${cols.map(([k, l]) =>
      `<th data-k="${k}" ${COL_TIP[k] ? `data-tip="${A(COL_TIP[k] + "<br><span class='muted'>Нажмите, чтобы отсортировать</span>")}"` : ""}>${l}<span class="ar">${s && s.k === k ? (s.dir > 0 ? "↑" : "↓") : ""}</span></th>`).join("")}</tr></thead><tbody>` +
    rows.map(r => `<tr class="${isBest(r) ? "best" : ""}"><td>${r._name}</td>${cols.map(([k, l, f]) => `<td data-label="${l}">${(f || (v => num(k, v)))(r[k])}</td>`).join("")}</tr>`).join("") + `</tbody></table>`;
}
// график выбора k: устойчивость и силуэт по k, порог 0,8; точка — подсказка, клик — подсветка строки
function kChart(rows) {
  const W = 640, H = 200, m = {l: 36, r: 16, t: 14, b: 26};
  const x = d3.scalePoint().domain(rows.map(r => r.k)).range([m.l, W - m.r]);
  const y = d3.scaleLinear().domain([0, 1]).range([H - m.b, m.t]);
  const line = key => d3.line().x(r => x(r.k)).y(r => y(r[key]))(rows);
  return `<svg class="kchart" viewBox="0 0 ${W} ${H}" role="img">
    ${[0, .5, 1].map(v => `<text x="${m.l - 8}" y="${y(v) + 4}" font-size="12" text-anchor="end" fill="var(--ink3)">${ru.format(".1f")(v)}</text>`).join("")}
    <line x1="${m.l}" x2="${W - m.r}" y1="${y(.8)}" y2="${y(.8)}" stroke="var(--ink3)" stroke-dasharray="4 4"></line>
    <text x="${W - m.r}" y="${y(.8) - 6}" font-size="12" text-anchor="end" fill="var(--ink3)">порог устойчивости 0,8</text>
    <path d="${line("stability")}" fill="none" stroke="var(--ink)" stroke-width="2"></path>
    <path d="${line("SW")}" fill="none" stroke="var(--ink3)" stroke-width="1.5" stroke-dasharray="2 3"></path>
    ${rows.map(r => `<text x="${x(r.k)}" y="${H - 6}" font-size="12" text-anchor="middle" fill="${r.k === K ? "var(--ink)" : "var(--ink3)"}" font-weight="${r.k === K ? 600 : 400}">${r.k}</text>
      <circle data-k="${r.k}" cx="${x(r.k)}" cy="${y(r.stability)}" r="${r.k === K ? 6 : 4.5}" fill="${r.k === K ? "var(--ink)" : "var(--panel)"}" stroke="var(--ink)" stroke-width="2"
        data-tip="${A(`<b>k = ${r.k}</b>${r.k === K ? " (выбрано)" : ""}<br>Устойчивость: ${f2(r.stability)}<br>Силуэт: ${f3(r.SW)} · MQ: ${f3(r.MQ)}`)}"></circle>`).join("")}
  </svg><div class="dnalegend" style="margin-top:0"><span>сплошная — устойчивость</span><span>пунктир — силуэт (SW)</span></div>`;
}
const ICVI = [["SW", "SW ↑"], ["CH", "CH ↑"], ["S_Dbw", "S_Dbw ↓"], ["AVI", "AVI ↑"], ["AVU", "AVU ↓"], ["MQ", "MQ ↑"]];
const kMethod = D.ksel.some(r => r.method === "spectral") ? "spectral" : D.ksel[0].method;
const BLOCK_RU = {consumption_level: "Уровень трат", consumption_structure: "Структура трат", seasonality: "Сезонность", industry: "Отрасли", labour: "Рынок труда", geography: "География"};
const TABS = {
  methods: () => [table("methods", [...ICVI, ["ARI_consecutive", "Стабильность"], ["bootstrap_ARI", "Устойчивость"]],
      D.methods.map(r => ({...r, _name: METHOD_RU[r.method] || r.method})), "Метод", r => r.method === D.meta.final_method),
    "Средние по 24 месяцам, k = 8. Точкой отмечена итоговая модель: лучший средний ранг по шести индексам и лучшая стабильность. Наведите на заголовок, чтобы узнать, что значит индекс; нажмите, чтобы отсортировать."],
  edges: () => [table("edges", [["share_same_region", "Рёбер в регионе", pct], ["median_edge_km", "Медиана ребра, км", fmt], ["transitivity", "Транзитивность", f2], ...ICVI],
      D.edges.filter(r => r.method === "spectral").map(r => ({...r, _name: RULE_RU[r.rule] || r.rule})), "Правило рёбер", r => r.rule === D.meta.main_rule),
    "Июнь 2024, спектральная кластеризация на графе каждого правила. SW, CH и S_Dbw посчитаны в общем пространстве признаков, AVI, AVU и MQ — на собственном графе правила."],
  k: () => { const rows = D.ksel.filter(r => r.method === kMethod);
    return [kChart(rows) + table("k", [...ICVI, ["stability", "Устойчивость"]], rows.map(r => ({...r, _name: "k = " + r.k})), "Число типов", r => r.k === K),
    `Индексы почти монотонны по k, поэтому k выбрано по устойчивости: наибольшее k, при котором ARI на подвыборках не ниже 0,8. При k = ${K + 1} устойчивость обрывается. Нажмите на точку графика, чтобы найти строку в таблице.`]; },
  rob: () => [table("rob", [["ARI_ref_month", "ARI, июнь 2024", f2], ["ARI_panel", "ARI, вся панель", f2], ["switch_rate", "Переходов в месяц", pct1]],
      (D.rob || []).map(r => ({...r, _name: r.variant.replace(/^(\w+) ×/, (m, b) => (BLOCK_RU[b] || b) + ": вес ×").replace("×0.0", "×0 (блок исключён)").replace("×0.5", "×0,5").replace("×1.5", "×1,5")})), "Вариант", () => false),
    (D.meta.robust_text || "") + (D.spat ? ` Соседи по дороге совпадают по типу в ${pct(D.spat.observed_same_cluster_share)} случаев, при случайных метках — в ${pct(D.spat.null_mean)} (z = ${ru.format(".0f")(D.spat.z)}).` : "")],
  dna: () => {
    const feats = D.meta.dna_features || D.meta.signature_features;
    const col = d3.scaleDiverging(t => d3.interpolateRdBu(1 - t)).domain([-1.5, 0, 1.5]).clamp(true);
    return [`<table class="dna"><thead><tr><th></th>${CL.map(c => `<th class="c" data-type="${c.id}" data-tip="${A(`<b>${c.name}</b><br><span class='muted'>Нажмите, чтобы открыть тип на карте</span>`)}"><i style="background:${PAL[c.id]};color:${onColor(PAL[c.id])}">${c.id + 1}</i></th>`).join("")}</tr></thead><tbody>` +
      feats.map((f, fi) => `<tr><th>${FEAT_RU[f] || f}</th>${CL.map(c => { const v = c.z[f];
        const tipHtml = `<b>${c.name}</b><br>${FEAT_RU[f] || f}: ${featVal(f, c.prof)}<br>${v > 0 ? "Выше" : "Ниже"} среднего на ${ru.format(".1f")(Math.abs(v))} ст. откл.`;
        return `<td data-type="${c.id}" data-f="${fi}" data-tip="${A(tipHtml)}" style="background:${col(v)};color:${Math.abs(v) > 0.9 ? "#fff" : "#222"}">${v > 0 ? "+" : ""}${ru.format(".1f")(v)}</td>`; }).join("")}</tr>`).join("") +
      `</tbody></table><div class="dnalegend">${CL.map(c => `<span>${c.id + 1} — ${c.short || c.name}</span>`).join("")}</div>`,
      "Среднее z-отклонение признака внутри типа: красное — выше среднего по всем муниципалитетам, синее — ниже. Наведите на клетку, чтобы увидеть значение; нажмите на номер типа, чтобы открыть его на карте."];
  }
};
let curTab = "methods";
function renderTab(t) {
  curTab = t;
  document.querySelectorAll("#mtabs button").forEach(b => b.setAttribute("aria-pressed", b.dataset.t === t));
  const [html, note] = TABS[t](); $("tbox").innerHTML = html; $("tnote").textContent = note;
  const box = $("tbox");
  box.querySelectorAll("th[data-k]").forEach(th => th.onclick = () => {
    const id = th.closest("table").dataset.table, k = th.dataset.k, s = sortState[id];
    const dir0 = LOWER_BETTER.has(k) ? 1 : -1;   // сначала лучшие
    sortState[id] = s && s.k === k ? (s.dir === dir0 ? {k, dir: -dir0} : null) : {k, dir: dir0};
    if (!sortState[id]) delete sortState[id];
    renderTab(curTab);
  });
  box.querySelectorAll(".kchart circle").forEach(c => c.onclick = () => {
    const tr = [...box.querySelectorAll("table.t tbody tr")].find(r => r.cells[0].textContent === "k = " + c.dataset.k);
    box.querySelectorAll("table.t tbody tr").forEach(r => r.style.outline = "");
    if (tr) { tr.style.outline = "2px solid var(--ink)"; tr.scrollIntoView({block: "nearest"}); }
  });
  const dna = box.querySelector(".dna");
  if (dna) {
    dna.querySelectorAll("td").forEach(td => {
      td.onmouseenter = () => { dna.classList.add("focus"); dna.querySelectorAll("td").forEach(x => x.classList.toggle("on", x.dataset.type === td.dataset.type || x.dataset.f === td.dataset.f)); };
      td.onclick = () => goMap({type: +td.dataset.type});
    });
    dna.onmouseleave = () => dna.classList.remove("focus");
    dna.querySelectorAll("th.c").forEach(th => th.onclick = () => goMap({type: +th.dataset.type}));
  }
}
document.querySelectorAll("#mtabs button").forEach(b => b.onclick = () => renderTab(b.dataset.t));
renderTab("methods");
