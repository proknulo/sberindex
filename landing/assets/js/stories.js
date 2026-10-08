// Истории изменений за два года.
// Классический скрипт: файлы подключаются в index.html по порядку и делят общие глобальные имена.
const ind = clusterOf(/Индустри/), sib = clusterOf(/Сельская/);
const share = k => D.months.map((_, t) => D.mos.filter(m => m.L[t] === k).length / NMO);
// столбики по месяцам: подсказка у каждого, клик — этот месяц и тип на карте
function barChart(v, color, typeId) {
  const W = 640, H = 220, mx = d3.max(v), bw = W / v.length;
  return `<svg viewBox="0 0 ${W} ${H + 24}" role="img">` + v.map((x, i) => {
    const h = x / mx * (H - 22), edge = i === 0 || i === v.length - 1;
    const n = Math.round(x * NMO), dlt = i ? x - v[i - 1] : 0;
    const tipHtml = `<b>${mlab(D.months[i])}</b><br>${pct1(x)} территорий (${fmt(n)} МО)` + (i ? `<br>${dlt >= 0 ? "+" : "−"}${ru.format(".1f")(Math.abs(dlt) * 100)} п.п. к прошлому месяцу` : "") + `<br><span class='muted'>Нажмите, чтобы открыть на карте</span>`;
    return `<rect class="b" data-t="${i}" data-type="${typeId}" data-tip="${A(tipHtml)}" x="${i * bw + 2}" y="${H - h}" width="${bw - 4}" height="${h}" rx="3" fill="${color}" opacity="${edge ? 1 : 0.55}"></rect>` +
      (edge ? `<text x="${i * bw + bw / 2}" y="${H - h - 6}" text-anchor="middle" font-size="13" fill="var(--ink2)" pointer-events="none">${pct(x)}</text>` : "");
  }).join("") + `<text x="0" y="${H + 18}" font-size="13" fill="var(--ink3)">${mlab(D.months[0])}</text><text x="${W / 2}" y="${H + 18}" font-size="13" text-anchor="middle" fill="var(--ink3)">${mlab(D.months[12])}</text><text x="${W}" y="${H + 18}" font-size="13" text-anchor="end" fill="var(--ink3)">${mlab(D.months[T - 1])}</text></svg>`;
}
// гантели: доля маркетплейсов в начале и в конце; строка подсвечивается, клик — тип на карте
function dumbbell() {
  const rows = CL.map(c => ({c, a: D.traj[c.id].share_marketplaces[0], b: D.traj[c.id].share_marketplaces[T - 1]}));
  const W = 640, rh = 30, L = 170, R = 76, H = rows.length * rh + 10, mx = d3.max(rows, r => r.b) * 1.05;
  const x = v => L + v / mx * (W - L - R);
  return `<svg class="dumb" viewBox="0 0 ${W} ${H}" role="img">` + rows.map((r, i) => { const y = i * rh + 16;
    const tipHtml = `<b>${r.c.name}</b><br>${mlab(D.months[0])}: ${pct1(r.a)}<br>${mlab(D.months[T - 1])}: ${pct1(r.b)}<br>Рост: +${ru.format(".1f")((r.b - r.a) * 100)} п.п., в ${ru.format(".1f")(r.b / r.a)} раза<br><span class='muted'>Нажмите, чтобы показать тип на карте</span>`;
    return `<g class="row" data-type="${r.c.id}" data-tip="${A(tipHtml)}">
      <rect x="0" y="${y - rh / 2}" width="${W}" height="${rh}" fill="transparent"></rect>
      <text x="0" y="${y + 4}" font-size="13" fill="var(--ink2)">${r.c.short || r.c.name}</text>
      <line x1="${x(r.a)}" x2="${x(r.b)}" y1="${y}" y2="${y}" stroke="${PAL[r.c.id]}" stroke-width="2" opacity=".5"></line>
      <circle cx="${x(r.a)}" cy="${y}" r="5" fill="var(--panel)" stroke="${PAL[r.c.id]}" stroke-width="2"></circle>
      <circle cx="${x(r.b)}" cy="${y}" r="5.5" fill="${PAL[r.c.id]}"></circle>
      <text x="${W}" y="${y + 4}" font-size="13" text-anchor="end" fill="var(--ink3)">${pct(r.a)} → ${pct(r.b)}</text></g>`; }).join("") + `</svg>`;
}
// потоки между типами: наведение на узел подсвечивает все его потоки, клик — тип и квартал на карте
let SK = null;
function sankey() {
  const W = 900, H = 460, nodes = [], idx = new Map(), key = (t, c) => t + ":" + c;
  D.flows.forEach(([a, i, b, j]) => { [[a, i], [b, j]].forEach(([t, c]) => { if (!idx.has(key(t, c))) { idx.set(key(t, c), nodes.length); nodes.push({t, c}); } }); });
  const links = D.flows.map(([a, i, b, j, v]) => ({source: idx.get(key(a, i)), target: idx.get(key(b, j)), value: v, c: i}));
  const G = SK = d3.sankey().nodeWidth(12).nodePadding(4).nodeSort((x, y) => x.c - y.c).extent([[4, 24], [W - 4, H - 4]])({nodes: nodes.map(d => ({...d})), links: links.map(d => ({...d}))});
  const qs = [...new Set(G.nodes.map(d => d.t))];
  return `<svg id="sankey" viewBox="0 0 ${W} ${H}" role="img">` +
    G.links.map((d, k) => {
      const same = d.source.c === d.target.c;
      const tipHtml = same
        ? `<b>${CL[d.source.c].name}</b><br>Остались в типе: ${fmt(d.value)} МО<br>${mlab(D.months[d.source.t])} → ${mlab(D.months[d.target.t])}`
        : `<b>${CL[d.source.c].short || CL[d.source.c].name} → ${CL[d.target.c].short || CL[d.target.c].name}</b><br>${fmt(d.value)} МО сменили тип<br>${mlab(D.months[d.source.t])} → ${mlab(D.months[d.target.t])}`;
      return `<path class="lnk" data-k="${k}" data-s="${d.source.index}" data-tt="${d.target.index}" data-type="${d.target.c}" data-t="${d.target.t}" data-tip="${A(tipHtml)}" d="${d3.sankeyLinkHorizontal()(d)}" stroke="${PAL[d.c]}" stroke-opacity="${same ? .25 : .6}" stroke-width="${Math.max(1, d.width)}" fill="none"></path>`;
    }).join("") +
    G.nodes.map(d => {
      const inn = d3.sum(d.targetLinks.filter(l => l.source.c !== d.c), l => l.value), out = d3.sum(d.sourceLinks.filter(l => l.target.c !== d.c), l => l.value);
      const tipHtml = `<b>${CL[d.c].name}</b><br>${mlab(D.months[d.t])}: ${fmt(d.value)} МО` + (d.targetLinks.length ? `<br>Пришли из других типов: ${fmt(inn)}` : "") + (d.sourceLinks.length ? `<br>Уйдут в другие типы: ${fmt(out)}` : "") + `<br><span class='muted'>Нажмите, чтобы открыть на карте</span>`;
      return `<rect class="nd" data-n="${d.index}" data-type="${d.c}" data-t="${d.t}" data-tip="${A(tipHtml)}" x="${d.x0}" y="${d.y0}" width="${d.x1 - d.x0}" height="${Math.max(1, d.y1 - d.y0)}" fill="${PAL[d.c]}"></rect>`;
    }).join("") +
    qs.map((t, i) => `<text x="${G.nodes.find(n => n.t === t).x0}" y="14" text-anchor="${i === qs.length - 1 ? "end" : i ? "middle" : "start"}">${mlab(D.months[t])}</text>`).join("") + `</svg>`;
}
const indS = share(ind.id), sibS = share(sib.id);
// кто опережает: доля сильных лаговых пар, где МО типа опережает МО других типов; 50% — поровну
function leadChart() {
  const rows = (D.leadlag || []).map(r => ({c: CL[r.type], s: r.lead_share, n: r.leads + r.follows, l: r.leads}))
    .filter(r => r.c).sort((a, b) => b.s - a.s);
  const W = 640, rh = 30, L = 190, R = 60, H = rows.length * rh + 26, x = v => L + v * (W - L - R);
  return `<svg class="dumb" viewBox="0 0 ${W} ${H}" role="img">
    <line x1="${x(.5)}" x2="${x(.5)}" y1="4" y2="${H - 18}" stroke="var(--ink3)" stroke-dasharray="3 3"></line>
    <text x="${x(.5)}" y="${H - 4}" font-size="12" text-anchor="middle" fill="var(--ink3)">поровну</text>
    <text x="${x(.82)}" y="${H - 4}" font-size="12" text-anchor="middle" fill="var(--ink3)">чаще опережает →</text>
    <text x="${x(.2)}" y="${H - 4}" font-size="12" text-anchor="middle" fill="var(--ink3)">← чаще следует</text>` +
    rows.map((r, i) => { const y = i * rh + 16, a = Math.min(x(.5), x(r.s)), w = Math.abs(x(r.s) - x(.5));
      const tipHtml = `<b>${r.c.name}</b><br>Опережает в ${pct(r.s)} сильных лаговых пар с другими типами<br>${fmt(r.l)} из ${fmt(r.n)} пар<br><span class='muted'>Нажмите, чтобы показать тип на карте</span>`;
      return `<g class="row" data-type="${r.c.id}" data-tip="${A(tipHtml)}">
        <rect x="0" y="${y - rh / 2}" width="${W}" height="${rh}" fill="transparent"></rect>
        <text x="0" y="${y + 4}" font-size="13" fill="var(--ink2)">${r.c.short || r.c.name}</text>
        <rect x="${a}" y="${y - 7}" width="${w}" height="14" rx="3" fill="${PAL[r.c.id]}"></rect>
        <text x="${W}" y="${y + 4}" font-size="13" text-anchor="end" fill="var(--ink3)">${pct(r.s)}</text></g>`; }).join("") + `</svg>`;
}
const STORIES = [
  {tab: "Индустриальные города уступают место", head: `Индустриальный тип сжался с ${pct(indS[0])} до ${pct(indS[T - 1])} территорий`,
   body: "116 муниципалитетов, в основном сельские районы Урала и Поволжья, перешли в аграрную глубинку. У них доля обрабатывающих производств в занятости упала с 12% до 7%, а доля маркетплейсов в тратах выросла.",
   method: "Доля — число МО, отнесённых к индустриальному типу в месяце, делённое на 1815. Тип каждого месяца даёт эволюционная спектральная кластеризация с памятью: месяц сравнивается со сглаженной историей, поэтому разовый всплеск трат тип не меняет. Сдвиг совпадает со сменой года в данных Росстата (2023 → 2024): у перешедших МО доля обработки в занятости упала с 11,7% до 7,3%. На двух годах нельзя отличить реальное сокращение промышленной занятости от изменений учёта, поэтому мы называем это наблюдением, а не причиной.",
   cap: "Доля муниципалитетов индустриального типа по месяцам", hint: "Наведите на столбец, чтобы увидеть месяц; нажмите, чтобы открыть его на карте.", chart: () => barChart(indS, PAL[ind.id], ind.id)},
  {tab: "Сельская Сибирь и Север дышат по сезонам", head: `Каждое лето тип «Сельская Сибирь и Север» расширяется — до ${pct(d3.max(sibS))} территорий`,
   body: "Соседние районы с летним пиком трат — дачи, Алтай, Байкал — летом переходят в этот тип и к зиме возвращаются. Эффект повторился в оба года.",
   method: "Доля МО типа «Сельская Сибирь и Север» по месяцам. Признак «летний пик» — насколько траты в июне–августе выше среднего за год; у районов с дачами и туризмом он высокий, и летом их профиль сближается с этим типом. Эффект повторился в 2023 и 2024 годах. Для отдельного МО такой переход сравним с граничным шумом, поэтому правильнее говорить о сезонном смещении границы типа, а не о смене экономики района.",
   cap: "Доля муниципалитетов типа «Сельская Сибирь и Север» по месяцам", hint: "Нажмите на летний столбец, чтобы увидеть на карте, какие районы присоединяются.", chart: () => barChart(sibS, PAL[sib.id], sib.id)},
  {tab: "Маркетплейсы приходят в глубинку", head: "Доля маркетплейсов растёт во всех восьми типах",
   body: "Быстрее всего — там, где мало офлайн-магазинов. На удалённом Северо-Востоке она остаётся самой низкой: доставка всё ещё ограничивает спрос.",
   method: "Медиана доли маркетплейсов в тратах по МО каждого типа при фиксированном составе типа (каждый МО отнесён к своему основному типу за два года), чтобы видеть изменение экономики, а не состава. Сравниваются январь 2023 и декабрь 2024. Декабрь — пик онлайн-покупок, поэтому по среднегодовым значениям рост скромнее: +34–45% в большинстве типов и +84% на Северо-Востоке (отчёт, §7.3).",
   cap: `Доля маркетплейсов в тратах, ${mlab(D.months[0])} → ${mlab(D.months[T - 1])}`, hint: "Наведите на строку, чтобы сравнить; нажмите, чтобы показать тип на карте.", chart: dumbbell},
  {tab: "Кто опережает", head: "Сезонный пик трат на Севере наступает раньше, чем в центре",
   body: "Лаговая корреляция ищет для каждой пары муниципалитетов сдвиг до трёх месяцев, при котором их ряды трат совпадают лучше всего. В сильно связанных парах Северо-Восток и сельская Сибирь чаще оказываются впереди, а пригороды и индустриальные города — позади: навигация, северный завоз и отпуска сдвигают сезон на Севере вперёд.",
   method: "Для каждой пары МО найден лаг ℓ ∈ [−3, 3] мес., максимизирующий корреляцию рядов относительных трат (отклонение от медианного МО в том же месяце). Учитываются сильные пары: максимальная корреляция выше 0,7 и ненулевой лаг. Для пар МО разных основных типов считается, какой тип впереди; на графике — доля таких пар, где тип опережает. Это правило «лаговая корреляция» из сравнения правил рёбер: для поиска типов оно не подходит (отрицательный силуэт), но показывает распространение сезонных сигналов (отчёт, §4.1, §7.4).",
   cap: "Доля сильных лаговых пар, где муниципалитеты типа опережают другие типы", hint: "Наведите на строку, чтобы увидеть число пар; нажмите, чтобы показать тип на карте.", chart: leadChart},
  {tab: "Все переходы между типами", head: `${pct(D.temporal.never_switch_share)} муниципалитетов ни разу не сменили тип`,
   body: `Потоки между типами по кварталам: толщина равна числу муниципалитетов. ${pct(D.adj)} переходов идут между двумя ближайшими типами — это территории на границе, а не случайные скачки.`,
   method: "Узел — тип в начале квартала, поток — число МО, перешедших из типа в тип за квартал. Петли внутри типа — те, кто тип сохранил. «Ближайшие типы» — два типа с ближайшими центрами в пространстве признаков; в них идут 91% переходов. События слияния и разделения типов отслеживаются по доле пересечения состава соседних месяцев (порог 0,3).",
   cap: "Потоки муниципалитетов между типами по кварталам", hint: "Наведите на узел, чтобы подсветить его потоки; нажмите — откроется этот тип и квартал на карте.", chart: sankey}
];
let story = 0;
function renderStory() {
  $("storyTabs").innerHTML = STORIES.map((s, i) => `<button class="story" data-s="${i}" aria-pressed="${i === story}">${s.tab}</button>`).join("");
  $("storyTabs").querySelectorAll(".story").forEach(b => b.onclick = () => { story = +b.dataset.s; renderStory(); });
  const s = STORIES[story];
  $("sHead").textContent = s.head; $("sBody").textContent = s.body; $("sCap").textContent = s.cap;
  $("sChart").innerHTML = s.chart() + `<p class="hint">${s.hint}</p>`;
  $("sMethod").innerHTML = `<p>${s.method}</p>`;
  const box = $("sChart");
  box.querySelectorAll("rect.b").forEach(el => el.onclick = () => goMap({type: +el.dataset.type, t: +el.dataset.t}));
  box.querySelectorAll("g.row").forEach(el => el.onclick = () => goMap({type: +el.dataset.type}));
  const sk = box.querySelector("#sankey");
  if (sk) {
    const nodeOn = n => { sk.classList.add("focus"); sk.querySelectorAll(".lnk").forEach(l => l.classList.toggle("on", l.dataset.s === n || l.dataset.tt === n)); };
    sk.querySelectorAll("rect.nd").forEach(el => {
      el.onmouseenter = () => nodeOn(el.dataset.n);
      el.onmouseleave = () => sk.classList.remove("focus");
      el.onclick = () => goMap({type: +el.dataset.type, t: +el.dataset.t});
    });
    sk.querySelectorAll(".lnk").forEach(el => el.onclick = () => goMap({type: +el.dataset.type, t: +el.dataset.t}));
  }
}
renderStory();
