// Карточка под картой: вступление, портрет типа, карточка муниципалитета.
// Классический скрипт: файлы подключаются в index.html по порядку и делят общие глобальные имена.
const detail = $("detail");
function renderIntro() {
  detail.innerHTML = `<div class="intro">
    <p><b>Сеть сходства.</b> Каждый месяц муниципалитет связан с 15 самыми похожими по тратам, занятости, зарплатам и доступу к рынкам.</p>
    <p><b>${K} типов.</b> Группы, которые держатся в сети все ${T} месяца: от пригородов мегаполисов до аграрной глубинки.</p>
    <p><b>${pct(D.temporal.never_switch_share)} стабильны.</b> Остальные переходят между соседними типами — по сезонам или вслед за структурой занятости.</p></div>`;
}
const pager = () => `<div class="pager">
  <button class="btn" data-go="-1">${chev("M10 3L5 8l5 5")}Предыдущий</button>
  <button class="btn" data-go="1">Следующий${chev("M6 3l5 5-5 5")}</button></div>`;
function renderPortrait(i) {
  const c = CL[i], p = c.prof;
  const sig = (D.meta.signature_features || []).filter(f => c.z[f] != null).sort((a, b) => Math.abs(c.z[b]) - Math.abs(c.z[a])).slice(0, 5);
  detail.innerHTML = `<div class="portrait">
    <div><div class="bar6" style="background:${PAL[i]}"></div><h2>${c.name}</h2><p class="desc">${c.desc || ""}</p></div>
    <div><dl class="facts">
      <div><dt>Муниципалитетов</dt><dd>${fmt(c.size)}</dd></div>
      <div><dt>Доля всех МО</dt><dd>${pct1(c.size / NMO)}</dd></div>
      <div><dt>Траты жителя в месяц</dt><dd>${fmt(p.cons_total_rub)} ₽</dd></div>
      <div><dt>Маркетплейсы в тратах</dt><dd>${pct1(p.share_marketplaces)}</dd></div></dl></div>
    <div><h4 style="margin-top:0">Чем выделяется</h4>
      <div class="diff">${sig.map(f => { const z = Math.max(-2.5, Math.min(2.5, c.z[f])), w = Math.abs(z) / 2.5 * 50;
        const tipHtml = `<b>${FEAT_RU[f] || f}</b><br>У типа: ${featVal(f, p)}<br>${c.z[f] > 0 ? "Выше" : "Ниже"} среднего по всем МО на ${ru.format(".1f")(Math.abs(c.z[f]))} ст. откл.`;
        return `<div class="row" data-tip="${A(tipHtml)}"><div class="track"><i style="${z >= 0 ? "left:50%" : "right:50%"};width:${w}%;background:${z >= 0 ? "var(--pos)" : "var(--neg)"}"></i></div><span>${FEAT_RU[f] || f}</span></div>`; }).join("")}</div>
      <p class="muted" style="font-size:13px;margin:10px 0 0">Вправо — выше среднего по всем МО, влево — ниже.</p>
      <p class="muted" style="margin:16px 0 0;font-size:14.5px;line-height:1.55">Например: ${c.examples.slice(0, 5).join(", ")}</p>
      ${pager()}</div></div>`;
  detail.querySelectorAll("[data-go]").forEach(b => b.onclick = () => selectType((i + K + +b.dataset.go) % K));
}
// полоски структуры МО; в подсказке — сравнение с медианой его типа
function bars(obj, labels, ref, typeVal, typeName) {
  return `<div class="bars">` + Object.entries(obj).filter(([, v]) => v != null).sort((a, b) => b[1] - a[1]).map(([k, v]) => {
    const tv = typeVal ? typeVal(k) : null;
    const tipHtml = `<b>${labels[k] || k}</b>: ${pct1(v)}` + (tv != null ? `<br>Медиана типа «${typeName}»: ${pct1(tv)}<br>${v > tv ? "Выше" : "Ниже"} на ${ru.format(".1f")(Math.abs(v - tv) * 100)} п.п.` : "");
    return `<div class="row" data-tip="${A(tipHtml)}"><span>${labels[k] || k}</span><span class="bar"><i style="width:${Math.min(100, v * 100 / (ref || 1))}%"></i></span><span class="muted" style="text-align:right">${pct(v)}</span></div>`;
  }).join("") + `</div>`;
}
function highlight(id) { ["mo-sel", "intra-sel"].forEach(l => { if (map.getLayer(l)) map.setFilter(l, ["==", ["id"], id ?? -1]); }); }
// карточка района Москвы или Петербурга: внутригородской тип по месяцам и структура трат
function selectIntra(id, zoomTo) {
  const m = byIdI.get(id); if (!m) return;
  selected = id; highlight(id);
  const counts = d3.rollup(m.L, v => v.length, x => x), main = [...counts].sort((a, b) => b[1] - a[1])[0][0], c = ICL[main];
  detail.innerHTML = `<div class="mocard">
    <div>
      <h2 style="font-size:clamp(24px,2.8vw,32px)">${m.n}</h2>
      <p class="muted" style="margin:8px 0 0;font-size:15px">${m.r}, внутригородская территория</p>
      <div class="strip">${m.L.map((l, i) => `<div data-t="${i}" class="${i === month ? "cur" : ""}" data-tip="${A(`<b>${mlab(D.months[i])}</b><br>${ICL[l].name}<br><span class='muted'>Нажмите, чтобы показать этот месяц на карте</span>`)}" style="background:${IPAL[l]}"></div>`).join("")}</div>
      <p class="muted" style="margin:0;font-size:13px">Внутригородской тип по месяцам, янв 2023 — дек 2024. Смен типа: ${m.sw}.</p>
      <p style="margin:16px 0 0;font-size:16px"><i style="display:inline-block;width:10px;height:10px;border-radius:5px;background:${IPAL[main]}"></i> Основной тип: <b>${c.name}</b></p>
      <p class="muted" style="margin:6px 0 0;font-size:14px;line-height:1.5">${c.desc || ""}</p>
      <div class="kv">
        <span>Траты жителя в месяц, дек 2024</span><span>${fmt(m.cons)} ₽</span>
        <span>Медиана типа</span><span>${fmt(c.prof.cons_total_rub)} ₽</span>
        <span>Сезонная амплитуда трат</span><span>${f2(m.sa)}</span>
      </div>
      <p class="muted" style="font-size:13px;line-height:1.5">Районы столиц типизированы отдельно и только по тратам: данных Росстата о занятости и зарплатах по ним нет.</p>
    </div>
    <div>
      <h4 style="margin-top:4px">Структура трат</h4>${bars(m.sh, SH_RU, 0.6, k => c.prof["share_" + k], c.short || c.name)}
      <div style="margin-top:24px"><button class="btn" id="backBtn">${chev("M10 3L5 8l5 5")}К районам Москвы и Петербурга</button></div>
    </div></div>`;
  detail.querySelectorAll(".strip [data-t]").forEach(el => el.onclick = () => {
    if (layer !== "type") setLayer("type");
    setMonth(+el.dataset.t);
    detail.querySelectorAll(".strip [data-t]").forEach(x => x.classList.toggle("cur", x === el));
  });
  $("backBtn").onclick = () => { selected = null; highlight(null); if (!capFocus) { capFocus = true; renderChips(); restyle(); } renderCapitals(); };
  if (zoomTo) { zoomToMo(id); $("map-s").scrollIntoView({block: "start"}); }
}
function selectMo(id, zoomTo) {
  if (byIdI.has(id)) return selectIntra(id, zoomTo);
  const m = byId.get(id); if (!m) return;
  selected = id; highlight(id);
  const counts = d3.rollup(m.L, v => v.length, x => x), main = [...counts].sort((a, b) => b[1] - a[1])[0][0];
  const emp = Object.fromEntries(Object.entries(m.emp).sort((a, b) => b[1] - a[1]).slice(0, 6));
  const shortEmp = Object.fromEntries(Object.entries(EMP_RU).map(([k, v]) => [k, v.replace(/\s*\(.*\)$/, "")]));
  detail.innerHTML = `<div class="mocard">
    <div>
      <h2 style="font-size:clamp(24px,2.8vw,32px)">${m.n}</h2>
      <p class="muted" style="margin:8px 0 0;font-size:15px">${m.r}, ${m.t}</p>
      <div class="strip">${m.L.map((l, i) => `<div data-t="${i}" class="${i === month ? "cur" : ""}" data-tip="${A(`<b>${mlab(D.months[i])}</b><br>${CL[l].name}<br><span class='muted'>Нажмите, чтобы показать этот месяц на карте</span>`)}" style="background:${PAL[l]}"></div>`).join("")}</div>
      <p class="muted" style="margin:0;font-size:13px">Тип по месяцам, янв 2023 — дек 2024. Смен типа: ${m.sw}. Нажмите на месяц, чтобы открыть его на карте.</p>
      <p style="margin:16px 0 0;font-size:16px"><i style="display:inline-block;width:10px;height:10px;border-radius:5px;background:${PAL[main]}"></i> Основной тип: <b>${CL[main].name}</b></p>
      <div class="kv">
        <span>Траты жителя в месяц, дек 2024</span><span>${fmt(m.cons)} ₽</span>
        <span>Медиана типа</span><span>${fmt(CL[main].prof.cons_total_rub)} ₽</span>
        <span>Население</span><span>${fmt(m.pop)}</span>
        <span>Зарплата к медиане МО</span><span>${m.wage != null ? f2(m.wage) + "×" : "нет данных"}</span>
        <span>Сезонная амплитуда трат</span><span>${f2(m.sa)}</span>
      </div>
      <h4>Экономические двойники из других регионов</h4>
      <div class="twins">${m.tw.map(t => { const x = byId.get(t); return x ? `<button data-id="${t}">${x.n} <span class="muted">· ${x.r}</span></button>` : ""; }).join("")}</div>
    </div>
    <div>
      <h4 style="margin-top:4px">Структура трат</h4>${bars(m.sh, SH_RU, 0.6, k => CL[main].prof["share_" + k], CL[main].short || CL[main].name)}
      <h4>Структура занятости${m.imp > 0 ? ' <span class="muted" style="font-weight:400">(частично восстановлена)</span>' : ""}</h4>${bars(emp, shortEmp, 0.6, k => CL[main].prof["emp_share_" + k], CL[main].short || CL[main].name)}
      <div style="margin-top:24px"><button class="btn" id="backBtn">${chev("M10 3L5 8l5 5")}${typeSel >= 0 ? "К типу" : "Ко всем типам"}</button></div>
    </div></div>`;
  detail.querySelectorAll(".twins button").forEach(b => b.onclick = () => selectMo(+b.dataset.id, true));
  detail.querySelectorAll(".strip [data-t]").forEach(el => el.onclick = () => {
    if (layer !== "type") setLayer("type");
    setMonth(+el.dataset.t);
    detail.querySelectorAll(".strip [data-t]").forEach(x => x.classList.toggle("cur", x === el));
  });
  $("backBtn").onclick = () => { selected = null; highlight(null); typeSel >= 0 ? renderPortrait(typeSel) : renderIntro(); };
  if (zoomTo) { zoomToMo(id); $("map-s").scrollIntoView({block: "start"}); }
}

renderChips(); renderLegend(); renderIntro(); setMonth(month);
