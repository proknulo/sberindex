// Карта: подложка MapLibre, слои, фишки на карте, время, поиск, кнопки типов.
// Классический скрипт: файлы подключаются в index.html по порядку и делят общие глобальные имена.
const isDark = () => root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
const styleUrl = () => `https://tiles.openfreemap.org/styles/${isDark() ? "dark" : "positron"}`;
const RU_BOUNDS = [[19, 41], [190, 78]];
const GQ = GEO.q;
const decRing = r => { const out = []; let x = 0, y = 0; for (let i = 0; i < r.length; i += 2) { x += r[i]; y += r[i + 1]; out.push([x / GQ, y / GQ]); } return out; };
const decPoly = g => g.map(poly => poly.map(decRing));
const moFC = {type: "FeatureCollection", features: D.mos.filter(m => GEO.mo[m.id]).map(m => ({type: "Feature", id: m.id, properties: {}, geometry: {type: "MultiPolygon", coordinates: decPoly(GEO.mo[m.id])}}))};
const intraFC = {type: "FeatureCollection", features: INTRA.mos.filter(m => GEO.intra && GEO.intra[m.id]).map(m => ({type: "Feature", id: m.id, properties: {}, geometry: {type: "MultiPolygon", coordinates: decPoly(GEO.intra[m.id])}}))};
const otherFC = {type: "FeatureCollection", features: GEO.other.map((o, i) => ({type: "Feature", id: i, properties: {n: o.n, r: o.r || ""}, geometry: {type: "MultiPolygon", coordinates: decPoly(o.g)}}))};
const shortReg = n => n.replace(/^Республика\s+/, "Респ. ").replace(" автономный округ", " АО").replace(" автономная область", " АО").replace(" область", " обл.").replace(/\s+—.*$/, "").replace(/ - .*$/, "");
const regFC = {type: "FeatureCollection", features: GEO.regions.map(r => ({type: "Feature", properties: {}, geometry: {type: "MultiLineString", coordinates: r.b.map(decRing)}}))};
const regLabFC = {type: "FeatureCollection", features: GEO.regions.map(r => ({type: "Feature", properties: {n: shortReg(r.n), a: r.a}, geometry: {type: "Point", coordinates: [r.c[1], r.c[0]]}}))};
// маска «всё, кроме России» и контур страны (см. sbx/geo.py)
const maskFC = {type: "FeatureCollection", features: [{type: "Feature", properties: {}, geometry: {type: "MultiPolygon", coordinates: decPoly(GEO.russia.mask)}}]};
const outlineFC = {type: "FeatureCollection", features: [{type: "Feature", properties: {}, geometry: {type: "MultiLineString", coordinates: GEO.russia.outline.map(decRing)}}]};
const bboxOf = id => { let b = [Infinity, Infinity, -Infinity, -Infinity];
  (GEO.mo[id] || GEO.intra[id]).forEach(p => decRing(p[0]).forEach(([x, y]) => { b = [Math.min(b[0], x), Math.min(b[1], y), Math.max(b[2], x), Math.max(b[3], y)]; })); return [[b[0], b[1]], [b[2], b[3]]]; };

const cityBounds = city => { let b = [Infinity, Infinity, -Infinity, -Infinity];
  INTRA.mos.filter(m => m.r === city && GEO.intra[m.id]).forEach(m => GEO.intra[m.id].forEach(p => decRing(p[0]).forEach(([x, y]) => {
    b = [Math.min(b[0], x), Math.min(b[1], y), Math.max(b[2], x), Math.max(b[3], y)]; })));
  return [[b[0], b[1]], [b[2], b[3]]]; };

// ---------- значки типов на карте: крупные МО видны всегда, мелкие появляются при приближении
let iconsOn = true;
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const iconsFC = (t, skip) => ({type: "FeatureCollection", features: D.mos.filter(m => GEO.pt && GEO.pt[m.id] && !(skip && skip.has(m.id)))
  .map(m => ({type: "Feature", properties: {id: m.id, c: m.L[t], pop: m.pop}, geometry: {type: "Point", coordinates: GEO.pt[m.id]}}))});
const ICON_ZOOM = [[2, .46], [4, .54], [6, .66], [8, .78], [11, .92]];
const iconScale = z => { const a = ICON_ZOOM; if (z <= a[0][0]) return a[0][1];
  for (let i = 1; i < a.length; i++) if (z <= a[i][0]) { const [z0, s0] = a[i - 1], [z1, s1] = a[i]; return s0 + (s1 - s0) * (z - z0) / (z1 - z0); }
  return a[a.length - 1][1]; };

// слои-показатели: 5 квантильных классов (смены типа — по числу смен)
function quantClasses(get, fmtv, unit) {
  const v = D.mos.map(get).filter(x => x != null).sort(d3.ascending);
  const br = [0.2, 0.4, 0.6, 0.8].map(p => d3.quantileSorted(v, p));
  const cls = x => x == null ? -1 : br.filter(b => x > b).length;
  const edges = [v[0], ...br, v[v.length - 1]];
  const labels = d3.range(5).map(i => `${fmtv(edges[i])}–${fmtv(edges[i + 1])}${unit}`);
  return {cls, labels};
}
const times = n => n % 10 >= 2 && n % 10 <= 4 && (n < 12 || n > 14) ? "раза" : "раз";
const LAYERS = {
  type: {name: "Типы"},
  cons: {name: "Траты", note: "Безналичные траты жителя в месяц, декабрь 2024", get: m => m.cons, val: m => fmt(m.cons) + " ₽", ...quantClasses(m => m.cons, x => ru.format(",.0f")(Math.round(x / 1000)), " тыс. ₽")},
  mp: {name: "Маркетплейсы", note: "Доля маркетплейсов в тратах, среднее за 2023–2024", get: m => m.sh.marketplaces, val: m => pct1(m.sh.marketplaces), ...quantClasses(m => m.sh.marketplaces, x => ru.format(".0f")(x * 100), "%")},
  sw: {name: "Смены типа", note: "Сколько раз муниципалитет сменил тип за 24 месяца", get: m => m.sw, val: m => m.sw ? `${m.sw} ${times(m.sw)}` : "ни разу",
       cls: x => x == null ? -1 : x >= 5 ? 4 : x >= 3 ? 3 : x, labels: ["ни разу", "1 раз", "2 раза", "3–4 раза", "5 и больше"]}
};

let month = T - 1, layer = "type", typeSel = -1, selected = null, legendSel = -1, capFocus = false, itypeSel = -1;
const map = new maplibregl.Map({container: "map", style: styleUrl(), bounds: RU_BOUNDS, fitBoundsOptions: {padding: 10},
  minZoom: 1.5, maxZoom: 15, maxBounds: [[-25, 20], [235, 86]], attributionControl: {compact: true}, dragRotate: false, pitchWithRotate: false,
  cooperativeGestures: matchMedia("(pointer: coarse)").matches});
map.addControl(new maplibregl.NavigationControl({showCompass: false}), "top-left");
map.touchZoomRotate.disableRotation();

const dimExpr = (on, off) => ["case", ["boolean", ["feature-state", "dim"], false], off, on];
const fillColor = () => layer === "type"
  ? ["match", ["coalesce", ["feature-state", "c"], -1], ...PAL.slice(0, K).flatMap((c, i) => [i, c]), "#999"]
  : ["match", ["coalesce", ["feature-state", "v"], -1], ...SEQ.flatMap((c, i) => [i, c]), "#bbb"];
const intraColor = () => layer === "type"
  ? ["match", ["coalesce", ["feature-state", "c"], -1], ...IPAL.slice(0, IK).flatMap((c, i) => [i, c]), "#999"]
  : ["match", ["coalesce", ["feature-state", "v"], -1], ...SEQ.flatMap((c, i) => [i, c]), "#bbb"];
// районы столиц смотрят на крупном масштабе, поэтому их заливка бледнеет слабее
const intraOpacity = () => ["interpolate", ["linear"], ["zoom"], 5, dimExpr(0.85, 0.08), 12, dimExpr(0.62, 0.05)];
// при приближении заливка бледнеет, чтобы читались улицы, реки и подписи
const fillOpacity = () => ["interpolate", ["linear"], ["zoom"], 5, dimExpr(0.68, 0.06), 10, dimExpr(0.28, 0.03)];

function addOurLayers() {
  const st = map.getStyle();
  const firstSymbol = st.layers.find(l => l.type === "symbol")?.id;
  const dark = isDark();
  // подписи подложки — по-русски и контрастно поверх цветной заливки
  st.layers.filter(l => l.type === "symbol" && JSON.stringify(l.layout?.["text-field"] || "").includes("name"))
    .forEach(l => map.setLayoutProperty(l.id, "text-field", ["coalesce", ["get", "name:ru"], ["get", "name:nonlatin"], ["get", "name"]]));
  st.layers.filter(l => l.type === "symbol" && /^(label_|place_|water_name|waterway|highway_name|highway-name)/.test(l.id)).forEach(l => {
    map.setPaintProperty(l.id, "text-color", dark ? "#f1f2f4" : "#1b1d22");
    map.setPaintProperty(l.id, "text-halo-color", dark ? "rgba(10,11,14,0.9)" : "rgba(255,255,255,0.92)");
    map.setPaintProperty(l.id, "text-halo-width", 1.6);
  });
  map.addSource("mo", {type: "geojson", data: moFC});
  map.addSource("other", {type: "geojson", data: otherFC});
  map.addSource("reg", {type: "geojson", data: regFC});
  map.addSource("reglab", {type: "geojson", data: regLabFC});
  map.addLayer({id: "other-fill", type: "fill", source: "other", paint: {"fill-color": "#9aa0a8", "fill-opacity": 0.2}}, firstSymbol);
  map.addLayer({id: "mo-fill", type: "fill", source: "mo", paint: {"fill-color": fillColor(), "fill-opacity": fillOpacity()}}, firstSymbol);
  map.addSource("intra", {type: "geojson", data: intraFC});
  map.addLayer({id: "intra-fill", type: "fill", source: "intra", paint: {"fill-color": intraColor(), "fill-opacity": intraOpacity()}}, firstSymbol);
  map.addLayer({id: "intra-line", type: "line", source: "intra", paint: {"line-color": dark ? "#0b0c0f" : "#ffffff",
    "line-width": ["interpolate", ["linear"], ["zoom"], 6, 0.2, 9, 0.8, 12, 1.6], "line-opacity": 0.85}}, firstSymbol);
  map.addLayer({id: "mo-line", type: "line", source: "mo", paint: {"line-color": dark ? "#0b0c0f" : "#ffffff",
    "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.15, 7, 0.7, 11, 1.4], "line-opacity": 0.8}}, firstSymbol);
  map.addLayer({id: "reg-line", type: "line", source: "reg", layout: {"line-join": "round"},
    paint: {"line-color": dark ? "#e6e8ec" : "#2b2f37", "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.7, 8, 1.6], "line-opacity": 0.6}}, firstSymbol);
  map.addLayer({id: "mo-sel", type: "line", source: "mo", filter: ["==", ["id"], selected ?? -1],
    paint: {"line-color": dark ? "#ffffff" : "#1f2328", "line-width": 3}});
  map.addLayer({id: "intra-sel", type: "line", source: "intra", filter: ["==", ["id"], selected ?? -1],
    paint: {"line-color": dark ? "#ffffff" : "#1f2328", "line-width": 3}});
  // всё за пределами России закрыто цветом фона карточки: и суша, и подписи соседних стран
  const bgc = getComputedStyle(root).getPropertyValue("--panel").trim() || (dark ? "#1b1f26" : "#f6f7f9");
  map.addSource("mask", {type: "geojson", data: maskFC});
  map.addSource("outline", {type: "geojson", data: outlineFC});
  map.addLayer({id: "mask", type: "fill", source: "mask", paint: {"fill-color": bgc, "fill-opacity": 1, "fill-antialias": false}}, "mo-sel");
  map.addLayer({id: "outline", type: "line", source: "outline", layout: {"line-join": "round"},
    paint: {"line-color": dark ? "#8e96a3" : "#616975", "line-width": ["interpolate", ["linear"], ["zoom"], 2, 0.8, 8, 1.6]}}, "mo-sel");
  // значки типов: картинки грузятся асинхронно, слой добавляется, когда они готовы
  Promise.all(CL.map(c => new Promise(res => { const img = new Image(112, 112);
    img.onload = () => { if (!map.hasImage("badge-" + c.id)) map.addImage("badge-" + c.id, img, {pixelRatio: 2}); res(); }; img.src = BADGE[c.id]; })))
    .then(() => {
      if (map.getSource("icons")) return;
      map.addSource("icons", {type: "geojson", data: iconsFC(month)});
      map.addLayer({id: "mo-icons", type: "symbol", source: "icons", layout: {
        "icon-image": ["concat", "badge-", ["to-string", ["get", "c"]]],
        "icon-size": ["interpolate", ["linear"], ["zoom"], ...ICON_ZOOM.flat()],
        "icon-anchor": "bottom", "icon-allow-overlap": false, "icon-padding": 2, "symbol-sort-key": ["-", 0, ["get", "pop"]]},
        paint: {"icon-opacity": iconOpacity()}}, "mo-sel");
      syncIcons();
    });
  // свои подписи субъектов на мелком масштабе; крупнее их сменяют подписи подложки
  map.addLayer({id: "reg-label", type: "symbol", source: "reglab", maxzoom: 5,
    layout: {"text-field": ["get", "n"], "text-font": ["Noto Sans Bold"], "text-size": 10.5, "text-transform": "uppercase",
             "text-letter-spacing": 0.04, "symbol-sort-key": ["-", 0, ["get", "a"]], "text-max-width": 9},
    paint: {"text-color": dark ? "#e6e8ec" : "#2b2f37", "text-halo-color": dark ? "#14171c" : "#ffffff", "text-halo-width": 1.4, "text-opacity": 0.85}});
  restyle();
}
map.on("style.load", addOurLayers);
// индикатор загрузки скрывается, когда карта впервые полностью отрисована
const hideMapLoading = () => document.getElementById("mapLoading")?.classList.add("done");
map.once("idle", hideMapLoading);
setTimeout(hideMapLoading, 15000);   // страховка, если подложка не загрузилась
new MutationObserver(() => map.setStyle(styleUrl(), {diff: false})).observe(root, {attributes: true, attributeFilter: ["data-theme"]});

function restyle() {
  if (!map.getSource("mo")) return;
  const L = LAYERS[layer];
  D.mos.forEach(m => {
    const c = m.L[month], v = L.cls ? L.cls(L.get(m)) : -1;
    const dim = capFocus || (typeSel >= 0 && c !== typeSel) || (layer !== "type" && legendSel >= 0 && v !== legendSel);
    map.setFeatureState({source: "mo", id: m.id}, {c, v, dim});
  });
  if (!map.getSource("intra")) return;
  INTRA.mos.forEach(m => {
    const c = m.L[month], v = L.cls ? L.cls(L.get(m)) : -1;
    const dim = typeSel >= 0 || (capFocus && itypeSel >= 0 && c !== itypeSel) || (layer !== "type" && legendSel >= 0 && v !== legendSel);
    map.setFeatureState({source: "intra", id: m.id}, {c, v, dim});
  });
}
// легенда слоя-показателя: класс можно нажать — на карте останутся только его муниципалитеты
function renderLegend() {
  const L = LAYERS[layer];
  if (layer === "type") {
    $("legend").innerHTML = `<span>${typeSel >= 0 ? "Остальные типы приглушены." : "Цвет — тип экономики в выбранном месяце."} Районы Москвы и Петербурга — свои ${IK} внутригородских типов, оттенки винного: кнопка «Москва и Петербург». Серым — территории вне модели.${iconsOn ? " Значки стоят на крупнейших муниципалитетах, при приближении их больше. Нажмите ▶: при смене типа старый значок рушится и строится новый." : ""}</span>`;
  } else {
    const counts = d3.range(5).map(i => D.mos.filter(m => L.cls(L.get(m)) === i).length);
    $("legend").innerHTML = `<span style="color:var(--ink2)">${L.note}:</span>` + L.labels.map((l, i) =>
      `<button data-cls="${i}" aria-pressed="${legendSel === i}" class="${legendSel >= 0 && legendSel !== i ? "off" : ""}" data-tip="${A(`<b>${l}</b><br>${fmt(counts[i])} муниципалитетов<br><span class='muted'>Нажмите, чтобы оставить на карте только их</span>`)}"><i style="background:${SEQ[i]}"></i>${l}</button>`).join("");
    $("legend").querySelectorAll("[data-cls]").forEach(b => b.onclick = () => { legendSel = legendSel === +b.dataset.cls ? -1 : +b.dataset.cls; renderLegend(); restyle(); });
  }
  $("timeline").classList.toggle("off", layer !== "type");
}
function setLayer(l) {
  layer = l; legendSel = -1;
  document.querySelectorAll("#layers button").forEach(x => x.setAttribute("aria-pressed", x.dataset.l === l));
  if (map.getLayer("mo-fill")) map.setPaintProperty("mo-fill", "fill-color", fillColor());
  if (map.getLayer("intra-fill")) map.setPaintProperty("intra-fill", "fill-color", intraColor());
  restyle(); renderLegend(); syncIcons();
}
document.querySelectorAll("#layers button").forEach(b => b.onclick = () => setLayer(b.dataset.l));
// переход к карте из любой визуализации: тип, месяц, муниципалитет
function goMap({type, t, mo} = {}) {
  if (layer !== "type") setLayer("type");
  if (t != null) setMonth(t);
  if (type != null && type !== typeSel) selectType(type);
  if (mo != null) selectMo(mo, true);
  else $("map-s").scrollIntoView({behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start"});
}

// подсказки и выбор на карте
const tip = $("tip");
const placeTip = (e, html) => { tip.innerHTML = html; tip.style.display = "block";
  tip.style.left = Math.max(0, Math.min(e.point.x + 14, $("map").clientWidth - 270)) + "px"; tip.style.top = (e.point.y + 12) + "px"; };
map.on("mousemove", "mo-fill", e => { const m = byId.get(e.features[0].id); if (!m) return; const c = CL[m.L[month]];
  map.getCanvas().style.cursor = "pointer";
  const extra = layer === "type" ? `Траты: ${fmt(m.cons)} ₽ в месяц` : `${LAYERS[layer].name}: ${LAYERS[layer].val(m)}`;
  placeTip(e, `<b>${m.n}</b><br><span class="muted">${m.r}</span><br><i style="display:inline-block;width:9px;height:9px;border-radius:5px;background:${PAL[c.id]}"></i> ${c.name}<br>${extra}`); });
map.on("mousemove", "intra-fill", e => { const m = byIdI.get(e.features[0].id); if (!m) return; const c = ICL[m.L[month]];
  map.getCanvas().style.cursor = "pointer";
  const extra = layer === "type" ? `Траты: ${fmt(m.cons)} ₽ в месяц` : `${LAYERS[layer].name}: ${LAYERS[layer].val(m)}`;
  placeTip(e, `<b>${m.n}</b><br><span class="muted">${m.r}, район</span><br><i style="display:inline-block;width:9px;height:9px;border-radius:5px;background:${IPAL[c.id]}"></i> ${c.name}<br>${extra}`); });
map.on("mousemove", "other-fill", e => { if (map.queryRenderedFeatures(e.point, {layers: ["mo-fill"]}).length) return; const p = e.features[0].properties;
  placeTip(e, `<b>${p.n}</b><br><span class="muted">${p.r}</span><br>Вне модели: нет данных СберИндекса`); });
["mo-fill", "intra-fill", "other-fill"].forEach(l => map.on("mouseleave", l, () => { tip.style.display = "none"; map.getCanvas().style.cursor = ""; }));
map.on("click", "mo-fill", e => selectMo(e.features[0].id));
map.on("click", "intra-fill", e => selectMo(e.features[0].id));
const zoomToMo = id => { if (GEO.mo[id] || GEO.intra[id]) map.fitBounds(bboxOf(id), {maxZoom: GEO.intra[id] ? 12 : 10, padding: 40, duration: 900}); };

// время
const slider = $("slider");
slider.max = T - 1; slider.value = month;
function setMonth(t) { const prev = month; month = t; slider.value = t; $("mlabel").textContent = mlab(D.months[t]); restyle(); updateIcons(prev); }

// значки: прозрачность при выбранном типе, видимость только на слое «Типы»
function iconOpacity() { return capFocus ? 0.18 : typeSel >= 0 ? ["case", ["==", ["get", "c"], typeSel], 1, 0.18] : 1; }
function syncIcons() {
  if (!map.getLayer("mo-icons")) return;
  map.setLayoutProperty("mo-icons", "visibility", iconsOn && layer === "type" ? "visible" : "none");
  map.setPaintProperty("mo-icons", "icon-opacity", iconOpacity());
}
$("iconsBtn").onclick = function () { iconsOn = !iconsOn; this.setAttribute("aria-pressed", iconsOn); syncIcons(); renderLegend(); };
// смена месяца на один шаг: у видимых значков, чей тип поменялся, старый рушится и строится новый
let fxToken = 0;
function updateIcons(prev) {
  const src = map.getSource("icons"); if (!src) return;
  const tok = ++fxToken;
  const canAnim = iconsOn && layer === "type" && !REDUCED && prev != null && Math.abs(month - prev) === 1 && map.getLayer("mo-icons");
  if (!canAnim) { src.setData(iconsFC(month)); return; }
  const seen = new Set();
  const changed = map.queryRenderedFeatures({layers: ["mo-icons"]}).map(f => f.properties.id)
    .filter(id => { if (seen.has(id)) return false; seen.add(id); const m = byId.get(id); return m && m.L[prev] !== m.L[month]; })
    .sort((a, b) => byId.get(b).pop - byId.get(a).pop).slice(0, 30);
  if (!changed.length) { src.setData(iconsFC(month)); return; }
  src.setData(iconsFC(month, new Set(changed)));
  const size = 56 * iconScale(map.getZoom()), box = $("map");
  const els = changed.map(id => spawnFx(box, map.project(GEO.pt[id]), size, byId.get(id).L[prev], byId.get(id).L[month]));
  setTimeout(() => { els.forEach(e => e.remove()); if (tok === fxToken) src.setData(iconsFC(month)); }, 1400);
}
function spawnFx(box, p, size, from, to) {
  const el = document.createElement("div"); el.className = "fx";
  el.style.cssText = `left:${p.x}px;top:${p.y - size / 2}px;width:${size}px;height:${size}px`;
  const SH = [["polygon(0 0,58% 0,46% 48%,0 40%)", "-14px", "10px", "-35deg"], ["polygon(58% 0,100% 0,100% 52%,46% 48%)", "13px", "8px", "40deg"],
              ["polygon(0 40%,46% 48%,40% 100%,0 100%)", "-10px", "22px", "-20deg"], ["polygon(46% 48%,100% 52%,100% 100%,40% 100%)", "11px", "24px", "25deg"]];
  el.innerHTML = `<div class="old">${SH.map(([cp, dx, dy, r]) => `<div class="shard" style="background-image:url('${BADGE[from]}');clip-path:${cp};--dx:${dx};--dy:${dy};--rot:${r}"></div>`).join("")}</div>` +
    [[-12, 6], [12, 4], [0, 10]].map(([dx, dy]) => `<div class="dust" style="--dx:${dx}px;--dy:${dy}px"></div>`).join("") +
    `<div class="scaf"></div><div class="new" style="background-image:url('${BADGE[to]}')"></div><div class="ring" style="border-color:${PAL[to]}"></div>`;
  box.appendChild(el); return el;
}
// если карту сдвинули во время анимации — убрать её и сразу показать итог
map.on("movestart", () => { const fx = document.querySelectorAll("#map .fx"); if (fx.length) { fx.forEach(e => e.remove()); map.getSource("icons")?.setData(iconsFC(month)); } });
slider.oninput = () => setMonth(+slider.value);
let timer = null;
const PLAY = '<path d="M2 2l10 6-10 6z" fill="currentColor"></path>', PAUSE = '<path d="M3 2h3v12H3zM8 2h3v12H8z" fill="currentColor"></path>';
function stopPlay() { clearInterval(timer); timer = null; $("playIcon").innerHTML = PLAY; $("play").setAttribute("aria-label", "Проиграть два года по месяцам"); }
$("play").onclick = () => {
  if (timer) return stopPlay();
  $("playIcon").innerHTML = PAUSE; $("play").setAttribute("aria-label", "Пауза");
  if (month === T - 1) setMonth(0);
  timer = setInterval(() => month >= T - 1 ? stopPlay() : setMonth(month + 1), iconsOn && layer === "type" && !REDUCED ? 1450 : 650);
};

// кнопки типов
function renderChips() {
  $("chips").innerHTML = `<button class="chip" data-i="-1" aria-pressed="${typeSel < 0 && !capFocus}">Все типы</button>` +
    CL.map(c => `<button class="chip" data-i="${c.id}" aria-pressed="${typeSel === c.id}">${badgeImg(c.id, 28)}${c.short || c.name}</button>`).join("") +
    (IK ? `<button class="chip" data-cap="1" aria-pressed="${capFocus}"><span style="display:inline-flex;gap:2px">${IPAL.slice(0, IK).map(c => `<i style="width:7px;height:20px;border-radius:2px;background:${c}"></i>`).join("")}</span>Москва и Петербург</button>` : "");
  $("chips").querySelectorAll(".chip").forEach(b => b.onclick = () => b.dataset.cap ? selectCapitals() : selectType(+b.dataset.i));
}
function selectType(i) {
  typeSel = i; capFocus = false; itypeSel = -1; selected = null; highlight(null);
  renderChips(); renderLegend(); restyle(); syncIcons();
  i < 0 ? renderIntro() : renderPortrait(i);
}

// районы столиц: остальная Россия приглушается, под картой — портрет внутригородской типологии
function selectCapitals(city) {
  typeSel = -1; capFocus = true; selected = null; highlight(null);
  if (layer !== "type") setLayer("type");
  renderChips(); renderLegend(); restyle(); syncIcons(); renderCapitals();
  map.fitBounds(cityBounds(city || "Москва"), {padding: 30, duration: 900});
}
function renderCapitals() {
  const share = c => `${fmt(c.msk)} в Москве, ${fmt(c.spb)} в Петербурге`;
  detail.innerHTML = `<div class="portrait cap">
    <div><div class="bar6" style="background:linear-gradient(90deg,${IPAL.slice(0, IK).join(",")})"></div><h2>Москва и Петербург: ${IK} типов районов</h2>
      <p class="desc">${fmt(INTRA.mos.length)} внутригородских территорий не входят в основную модель: это части единого рынка труда, и данных Росстата по ним нет. Поэтому их типы найдены отдельно, той же схемой (сеть сходства → эволюционная спектральная кластеризация), но только по тратам жителей: уровень, структура, сезонность. Число типов выбрано тем же правилом устойчивости.</p>
      <div class="actions" style="margin-top:14px"><button class="btn" data-city="Москва">Показать Москву</button><button class="btn" data-city="Санкт-Петербург">Показать Петербург</button></div></div>
    <div class="ilist">${ICL.map(c => `<button class="itype" data-it="${c.id}" aria-pressed="${itypeSel === c.id}">
        <i style="background:${IPAL[c.id]}"></i><span><b>${c.name}</b><span class="muted"> · ${fmt(c.size)} ${plural(c.size, "район", "района", "районов")}: ${share(c)} · траты ${fmt(c.prof.cons_total_rub)} ₽</span><br><span class="d">${c.desc || ""}</span></span></button>`).join("")}
      <p class="muted" style="font-size:13px;margin:10px 0 0">Нажмите на тип, чтобы оставить на карте только его районы; ещё раз — показать все.</p></div></div>`;
  detail.querySelectorAll("[data-city]").forEach(b => b.onclick = () => map.fitBounds(cityBounds(b.dataset.city), {padding: 30, duration: 900}));
  detail.querySelectorAll("[data-it]").forEach(b => b.onclick = () => { itypeSel = itypeSel === +b.dataset.it ? -1 : +b.dataset.it; restyle(); renderCapitals(); });
}

// поиск
const search = $("search"), sugg = $("sugg");
search.oninput = () => {
  const q = search.value.trim().toLowerCase();
  if (q.length < 2) { sugg.style.display = "none"; return; }
  const hits = [...D.mos, ...INTRA.mos].filter(m => m.n.toLowerCase().includes(q)).slice(0, 10);
  sugg.innerHTML = hits.map(m => `<button data-id="${m.id}">${m.n} <span class="muted">· ${m.r}</span></button>`).join("") || `<div class="muted" style="padding:10px 14px">Ничего не найдено. Попробуйте часть названия, например «Уфа».</div>`;
  sugg.style.display = "block";
};
sugg.onclick = e => { const b = e.target.closest("[data-id]"); if (b) { selectMo(+b.dataset.id, true); sugg.style.display = "none"; search.value = ""; } };
document.addEventListener("click", e => { if (!e.target.closest(".mapbar")) sugg.style.display = "none"; });
