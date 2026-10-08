// Сеть экономической близости: паутина и UMAP.
// Классический скрипт: файлы подключаются в index.html по порядку и делят общие глобальные имена.
// Раскладка «паутина»: сектор = тип; у края сектора — ядро типа (почти все соседи по сходству того же
// типа), ближе к центру — переходные МО, связанные с другими типами; внутри сектора похожие МО лежат
// рядом (порядок по главной оси UMAP). Нити — рёбра kNN-графа
// июня 2024: провисают к центру, как в паутине. Альтернатива — исходная раскладка UMAP.
// Уровень детализации: при отдалении видны только крупнейшие МО, при приближении — все.
(function () {
  if (!D.emb) return;
  const cv = $("net"), ctx = cv.getContext("2d"), ntip = $("ntip");
  const E = D.emb, N = E.xy.length, MO = E.ids.map(id => byId.get(id));
  const nbr = Array.from({length: N}, () => []);
  E.edges.forEach(([a, b]) => { nbr[a].push(b); nbr[b].push(a); });
  const sameShare = E.edges.filter(([a, b]) => E.lab[a] === E.lab[b]).length / E.edges.length;
  $("xNet").textContent = `${pct(sameShare)} нитей соединяют муниципалитеты одного типа`;
  const byPop = d3.range(N).sort((a, b) => MO[b].pop - MO[a].pop);
  const popRank = new Int32Array(N); byPop.forEach((i, r) => popRank[i] = r);
  const maxPop = d3.max(MO, m => m.pop);
  // порядок появления при приближении: внутри типа — по населению, между типами — пропорционально
  // √(размер типа), чтобы даже при сильном отдалении в каждом секторе были узлы и нити
  const typeSize = d3.rollup(d3.range(N), v => v.length, i => E.lab[i]);
  const inType = new Map(); [...byPop].forEach(i => { const c = E.lab[i]; inType.set(i, (inType.get(c + "#") ?? 0)); inType.set(c + "#", (inType.get(c + "#") ?? 0) + 1); });
  const lodOrder = d3.range(N).sort((a, b) => inType.get(a) / Math.sqrt(typeSize.get(E.lab[a])) - inType.get(b) / Math.sqrt(typeSize.get(E.lab[b])));
  const shortName = n => n.replace(/^(городской округ|муниципальный округ|муниципальный район)\s+(город-курорт|город-герой|город|город-порт|закрытое административно-территориальное образование)?\s*/, "")
    .replace(" муниципальный район", " р-н").replace(" муниципальный округ", " м.о.").replace(" городской округ", " г.о.").trim();

  // --- раскладка «паутина»
  const SEC = 2 * Math.PI / K, ang0 = c => -Math.PI / 2 + c * SEC;
  // «типичность»: доля соседей своего типа и доля месяцев в основном типе
  const core = d3.range(N).map(i => nbr[i].length ? nbr[i].filter(j => E.lab[j] === E.lab[i]).length / nbr[i].length : 1);
  const score = d3.range(N).map(i => core[i] + 0.3 * (MO[i].conf ?? 1) + 1e-6 * popRank[i]);
  const R0 = 0.16, RINGS = [0.4, 0.7, 1.0];
  const web = new Array(N);
  CL.forEach(c => {
    const idx = d3.range(N).filter(i => E.lab[i] === c.id); if (!idx.length) return;
    const mx = d3.mean(idx, i => E.xy[i][0]), my = d3.mean(idx, i => E.xy[i][1]);
    let sxx = 0, syy = 0, sxy = 0;
    idx.forEach(i => { const dx = E.xy[i][0] - mx, dy = E.xy[i][1] - my; sxx += dx * dx; syy += dy * dy; sxy += dx * dy; });
    const th = 0.5 * Math.atan2(2 * sxy, sxx - syy), vx = Math.cos(th), vy = Math.sin(th);   // главная ось типа
    const rr0 = new Map([...idx].sort((a, b) => score[a] - score[b]).map((i, r) => [i, idx.length > 1 ? r / (idx.length - 1) : 1]));
    idx.sort((a, b) => (E.xy[a][0] * vx + E.xy[a][1] * vy) - (E.xy[b][0] * vx + E.xy[b][1] * vy))
      .forEach((i, r) => {
        const u = idx.length > 1 ? r / (idx.length - 1) : .5, h = Math.sin(i * 12.9898) * 43758.5453 % 1;
        const a = ang0(c.id) + (u - .5) * SEC * .84, rr = Math.min(1, R0 + (1 - R0) * Math.pow(rr0.get(i), 0.8) + h * .01);
        web[i] = [Math.cos(a) * rr, Math.sin(a) * rr];
      });
  });
  // --- раскладка UMAP, нормированная в тот же квадрат
  const ex = d3.extent(E.xy, p => p[0]), ey = d3.extent(E.xy, p => p[1]);
  const us = 2 / Math.max(ex[1] - ex[0], ey[1] - ey[0]);
  const umap = E.xy.map(p => [(p[0] - (ex[0] + ex[1]) / 2) * us, -(p[1] - (ey[0] + ey[1]) / 2) * us]);

  let mode = "web", pos = web.map(p => [...p]), netType = -1, hover = null, tr = d3.zoomIdentity, W, H, dpr, S;
  const img = BADGE.map(src => Object.assign(new Image(), {src}));
  img.forEach(im => im.onload = () => draw());
  const css = v => getComputedStyle(root).getPropertyValue(v).trim();
  const P = i => [tr.applyX(W / 2 + pos[i][0] * S), tr.applyY(H / 2 + pos[i][1] * S)];
  const W2S = (x, y) => [tr.applyX(W / 2 + x * S), tr.applyY(H / 2 + y * S)];

  function resize() {
    dpr = devicePixelRatio || 1; W = cv.clientWidth; H = cv.clientHeight;
    cv.width = W * dpr; cv.height = H * dpr; S = Math.min(W, H) / 2 / 1.22;
    zoom.extent([[0, 0], [W, H]]).translateExtent([[-W * .25, -H * .25], [W * 1.25, H * 1.25]]);
    draw();
  }
  let visible = [], quad = null;
  function draw() {
    if (!W) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
    const k = tr.k, ink = css("--ink"), ink3 = css("--ink3"), bg = css("--panel");
    // фон паутины: спицы по границам секторов и провисающие кольца уровней трат
    if (mode === "web") {
      ctx.globalAlpha = .55; ctx.strokeStyle = css("--line2"); ctx.lineWidth = 1;
      for (let c = 0; c < K; c++) { const a = ang0(c) - SEC / 2, [x0, y0] = W2S(0, 0), [x1, y1] = W2S(Math.cos(a) * 1.06, Math.sin(a) * 1.06);
        ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke(); }
      RINGS.forEach(r => {
        ctx.beginPath();
        for (let c = 0; c <= K; c++) { const a1 = ang0(c) - SEC / 2, am = a1 - SEC / 2;
          const [x1, y1] = W2S(Math.cos(a1) * r, Math.sin(a1) * r), [cx, cy] = W2S(Math.cos(am) * r * .9, Math.sin(am) * r * .9);
          if (c === 0) ctx.moveTo(x1, y1); else ctx.quadraticCurveTo(cx, cy, x1, y1); }
        ctx.stroke(); });
      ctx.globalAlpha = .9; ctx.fillStyle = ink3; ctx.font = "11px Onest, sans-serif";
      const lab = (r, t) => { const a = -Math.PI / 2 + SEC / 2, [lx, ly] = W2S(Math.cos(a) * r * .95, Math.sin(a) * r * .95); ctx.fillText(t, lx + 4, ly - 4); };
      lab(RINGS[0] * .7, "переходные"); lab(1, "ядро типа");
      ctx.globalAlpha = 1;
    }
    // уровень детализации: сколько МО показывать при текущем приближении
    const nVis = Math.min(N, Math.round(150 * Math.pow(k, 1.75)));
    const vis = new Uint8Array(N);
    for (let r = 0; r < nVis; r++) vis[lodOrder[r]] = 1;
    if (netType >= 0) for (let i = 0; i < N; i++) if (E.lab[i] === netType) vis[i] = 1;
    if (hover != null) { vis[hover] = 1; nbr[hover].forEach(j => vis[j] = 1); }
    const XY = new Array(N);
    visible = [];
    for (let i = 0; i < N; i++) if (vis[i]) { const p = XY[i] = P(i); if (p[0] > -40 && p[0] < W + 40 && p[1] > -40 && p[1] < H + 40) visible.push(i); }
    // нити
    const [cx0, cy0] = W2S(0, 0);
    ctx.lineWidth = Math.min(1.4, .5 + k * .08);
    E.edges.forEach(([a, b]) => {
      if (!vis[a] || !vis[b]) return;
      const same = E.lab[a] === E.lab[b], foc = netType < 0 || E.lab[a] === netType || E.lab[b] === netType;
      ctx.globalAlpha = (same ? .22 : .16) * (foc ? 1 : .25);
      ctx.strokeStyle = same ? PAL[E.lab[a]] : ink;
      const [x1, y1] = XY[a], [x2, y2] = XY[b];
      ctx.beginPath(); ctx.moveTo(x1, y1);
      if (mode === "web") { const mx = (x1 + x2) / 2, my = (y1 + y2) / 2; ctx.quadraticCurveTo(mx + (cx0 - mx) * .18, my + (cy0 - my) * .18, x2, y2); }
      else ctx.lineTo(x2, y2);
      ctx.stroke();
    });
    // выделенные нити наведённого МО
    if (hover != null) {
      ctx.globalAlpha = .9; ctx.strokeStyle = ink; ctx.lineWidth = 1.4;
      nbr[hover].forEach(j => { const [x1, y1] = XY[hover], [x2, y2] = XY[j]; ctx.beginPath(); ctx.moveTo(x1, y1);
        if (mode === "web") { const mx = (x1 + x2) / 2, my = (y1 + y2) / 2; ctx.quadraticCurveTo(mx + (cx0 - mx) * .18, my + (cy0 - my) * .18, x2, y2); } else ctx.lineTo(x2, y2);
        ctx.stroke(); });
    }
    // узлы: точки, при сильном приближении — значки типов
    const asIcon = k >= 3.2;
    visible.sort((a, b) => popRank[b] - popRank[a]).forEach(i => {
      const [x, y] = XY[i], foc = netType < 0 || E.lab[i] === netType || i === hover;
      const r0 = 1.8 + 3.2 * Math.sqrt(MO[i].pop / maxPop), r = r0 * Math.min(2.2, Math.sqrt(k));
      ctx.globalAlpha = foc ? 1 : .15;
      if (asIcon && img[E.lab[i]].complete) { const s = Math.max(18, r * 4); ctx.drawImage(img[E.lab[i]], x - s / 2, y - s / 2, s, s); }
      else { ctx.fillStyle = PAL[E.lab[i]]; ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill(); }
    });
    if (hover != null) { const [x, y] = XY[hover]; ctx.globalAlpha = 1; ctx.strokeStyle = ink; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(x, y, 9, 0, 7); ctx.stroke(); }
    // подписи крупных МО без наложений
    const placed = [], maxLabels = Math.round(10 + 16 * k);
    ctx.font = "500 11.5px Onest, sans-serif"; ctx.textBaseline = "middle"; ctx.lineJoin = "round";
    const cands = [...visible].sort((a, b) => popRank[a] - popRank[b]);
    if (hover != null) cands.unshift(hover);
    for (const i of cands) {
      if (placed.length >= maxLabels) break;
      if (netType >= 0 && E.lab[i] !== netType && i !== hover) continue;
      const t = shortName(MO[i].n), [x, y] = XY[i], w = ctx.measureText(t).width, bx = x + 7, by = y - 8;
      if (bx + w > W || bx < 0 || by < 0 || by + 16 > H) continue;
      if (placed.some(b => bx < b[0] + b[2] && bx + w > b[0] && by < b[1] + b[3] && by + 16 > b[1])) continue;
      placed.push([bx, by, w, 16]);
      ctx.globalAlpha = 1; ctx.strokeStyle = bg; ctx.lineWidth = 3.5; ctx.strokeText(t, bx, y); ctx.fillStyle = ink; ctx.fillText(t, bx, y);
    }
    // подписи секторов
    if (mode === "web") {
      ctx.font = "600 12.5px Onest, sans-serif";
      CL.forEach(c => { const a = ang0(c.id), [x, y] = W2S(Math.cos(a) * 1.13, Math.sin(a) * 1.13);
        const t = c.short || c.name, w = ctx.measureText(t).width, s = 30;
        const left = Math.cos(a) < -0.2, cen = Math.abs(Math.cos(a)) <= 0.2;
        const x0 = cen ? x - (w + s + 6) / 2 : left ? x - w - s - 6 : x;
        ctx.globalAlpha = netType < 0 || netType === c.id ? 1 : .35;
        if (img[c.id].complete) ctx.drawImage(img[c.id], x0, y - s / 2, s, s);
        ctx.strokeStyle = bg; ctx.lineWidth = 4; ctx.strokeText(t, x0 + s + 6, y); ctx.fillStyle = ink; ctx.fillText(t, x0 + s + 6, y); });
    }
    ctx.globalAlpha = 1;
    quad = d3.quadtree().x(i => XY[i][0]).y(i => XY[i][1]).addAll(visible);
    $("netCount").textContent = `Показано ${fmt(visible.length)} из ${fmt(N)} муниципалитетов`;
  }
  let raf = 0; const redraw = () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; draw(); }); };

  // приближение: колесо, щипок, кнопки; одним пальцем на телефоне страница прокручивается как обычно
  const zoom = d3.zoom().scaleExtent([1, 18])
    .filter(e => e.type === "wheel" ? true : e.touches ? e.touches.length > 1 : !e.button)
    .on("zoom", e => { tr = e.transform; hover = null; ntip.style.display = "none"; redraw(); });
  const sel = d3.select(cv).call(zoom);
  cv.style.touchAction = "pan-y";
  $("netIn").onclick = () => sel.transition().duration(300).call(zoom.scaleBy, 1.8);
  $("netOut").onclick = () => sel.transition().duration(300).call(zoom.scaleBy, 1 / 1.8);
  $("netReset").onclick = () => sel.transition().duration(400).call(zoom.transform, d3.zoomIdentity);

  // смена раскладки с плавным переходом
  document.querySelectorAll("#netMode button").forEach(b => b.onclick = () => {
    if (b.dataset.m === mode) return;
    mode = b.dataset.m; document.querySelectorAll("#netMode button").forEach(x => x.setAttribute("aria-pressed", x === b));
    const from = pos.map(p => [...p]), to = mode === "web" ? web : umap, t0 = performance.now();
    const step = now => { const u = Math.min(1, (now - t0) / 700), e = d3.easeCubicInOut(u);
      pos = from.map((p, i) => [p[0] + (to[i][0] - p[0]) * e, p[1] + (to[i][1] - p[1]) * e]); draw(); if (u < 1) requestAnimationFrame(step); };
    REDUCED ? (pos = to.map(p => [...p]), draw()) : requestAnimationFrame(step);
    $("netNote").textContent = mode === "web" ? WEB_NOTE : UMAP_NOTE;
  });

  // наведение и клик
  const at = e => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  cv.addEventListener("mousemove", e => {
    const [x, y] = at(e), i = quad ? quad.find(x, y, 14) : undefined;
    if ((i ?? null) !== hover) { hover = i ?? null; redraw(); }
    if (i == null) { ntip.style.display = "none"; return; }
    const m = MO[i], same = nbr[i].filter(j => E.lab[j] === E.lab[i]).length;
    ntip.innerHTML = `<b>${m.n}</b><br><span class="muted">${m.r}</span><br>${CL[E.lab[i]].name}<br>Траты: ${fmt(m.cons)} ₽ в месяц<br>Соседей по сходству: ${nbr[i].length}, своего типа: ${same}<br><span class="muted">Нажмите, чтобы открыть карточку</span>`;
    ntip.style.display = "block"; ntip.style.left = Math.max(0, Math.min(x + 14, W - 270)) + "px"; ntip.style.top = (cv.offsetTop + Math.min(y + 10, H - 130)) + "px";
  });
  cv.addEventListener("mouseleave", () => { ntip.style.display = "none"; if (hover != null) { hover = null; redraw(); } });
  cv.addEventListener("click", e => { const [x, y] = at(e), i = quad ? quad.find(x, y, 16) : undefined; if (i != null) goMap({mo: E.ids[i]}); });

  // кнопки типов под сетью
  const leg = document.createElement("div"); leg.className = "netlegend"; cv.parentNode.appendChild(leg);
  function renderNetLegend() {
    leg.innerHTML = `<button class="chip" data-i="-1" aria-pressed="${netType < 0}">Все типы</button>` +
      CL.map(c => `<button class="chip" data-i="${c.id}" aria-pressed="${netType === c.id}">${badgeImg(c.id, 28)}${c.short || c.name}</button>`).join("");
    leg.querySelectorAll(".chip").forEach(b => b.onclick = () => { netType = +b.dataset.i; renderNetLegend(); draw(); });
  }
  const WEB_NOTE = "Сектор — тип экономики. У края сектора — ядро типа: почти все похожие на них муниципалитеты того же типа. Ближе к центру — переходные территории: их нити тянутся в соседние сектора.";
  const UMAP_NOTE = "Раскладка UMAP по тем же признакам: похожие муниципалитеты лежат рядом, типы образуют облака, мосты между ними — переходные территории.";
  $("netNote").textContent = WEB_NOTE;
  renderNetLegend();
  addEventListener("resize", resize);
  new MutationObserver(draw).observe(root, {attributes: true, attributeFilter: ["data-theme"]});
  resize();
})();
