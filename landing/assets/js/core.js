// Общее: данные, палитра типов, форматирование чисел, подсказки, фишки типов.
// Классический скрипт: файлы подключаются в index.html по порядку и делят общие глобальные имена.
const D = window.DATA;
// смысловая палитра: цвет типа следует пиктограмме его фишки — черепица дома, лёд, нефть, огни города,
// море, кирпич завода, хвоя, спелый колос; у ресурсных центров — цвет сырой нефти (порядок типов — по убыванию трат, см. configs/cluster_names.yaml)
const PAL = ["#E07B39","#7CC6EE","#7A5230","#7B4FC9","#14808F","#C2452D","#2E8B57","#E0B12E"];
const onColor = hex => { const n = parseInt(hex.slice(1), 16), l = (0.299 * (n >> 16) + 0.587 * (n >> 8 & 255) + 0.114 * (n & 255)) / 255; return l > 0.62 ? "#1d1f23" : "#fff"; };
const SEQ = ["#dce8f7","#a9c6ec","#6f9fdb","#3d74c2","#1f4c8f"];
const K = D.clusters.length, T = D.months.length, CL = D.clusters, NMO = D.mos.length;
const byId = new Map(D.mos.map(m => [m.id, m]));
// районы Москвы и Петербурга: своя внутригородская типология (5 типов, только траты; см. отчёт §7.5)
const INTRA = D.intra || {clusters: [], mos: []};
const ICL = INTRA.clusters, IK = ICL.length, byIdI = new Map(INTRA.mos.map(m => [m.id, m]));
// оттенки «винного» ряда: темнее — выше траты (типы упорядочены по убыванию трат)
const IPAL = ["#6B0D38", "#A12B62", "#CF5A90", "#E28AB2", "#EDB5CF"];
const plural = (n, one, few, many) => { const a = n % 10, b = n % 100; return a === 1 && b !== 11 ? one : a >= 2 && a <= 4 && (b < 12 || b > 14) ? few : many; };
const ru = d3.formatLocale({decimal: ",", thousands: " ", grouping: [3], currency: ["", " ₽"]});
const fmt = ru.format(",.0f"), pct = ru.format(".0%"), pct1 = ru.format(".1%"), f2 = ru.format(".2f"), f3 = ru.format(".3f");
const MONTH_RU = ["янв","фев","мар","апр","май","июн","июл","авг","сен","окт","ноя","дек"];
const mlab = s => { const [y, m] = s.split("-"); return MONTH_RU[+m - 1] + " " + y; };
const FEAT_RU = D.meta.feature_ru || {}, EMP_RU = D.meta.sector_ru || {};
const SH_RU = {food: "Продукты", health: "Здоровье", catering: "Общепит", transport: "Транспорт", marketplaces: "Маркетплейсы", other: "Прочее"};
const root = document.documentElement;
const $ = id => document.getElementById(id);
const chev = d => `<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="${d}"></path></svg>`;
const clusterOf = re => CL.find(c => re.test(c.short || c.name));
const A = s => String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

// ---------- общая подсказка: любой элемент с data-tip (наведение мышью или касание)
const gtip = Object.assign(document.createElement("div"), {className: "gtip"});
gtip.setAttribute("role", "tooltip");
document.body.appendChild(gtip);
function showTip(e, html) {
  gtip.innerHTML = html; gtip.style.display = "block";
  const w = gtip.offsetWidth, h = gtip.offsetHeight;
  let x = e.clientX + 14, y = e.clientY + 14;
  if (x + w > innerWidth - 8) x = e.clientX - w - 14;
  if (y + h > innerHeight - 8) y = e.clientY - h - 14;
  gtip.style.left = Math.max(8, x) + "px"; gtip.style.top = Math.max(8, y) + "px";
}
const hideTip = () => gtip.style.display = "none";
document.addEventListener("mousemove", e => { const t = e.target.closest?.("[data-tip]"); t ? showTip(e, t.dataset.tip) : hideTip(); });
document.addEventListener("pointerdown", e => { if (e.pointerType !== "mouse") { const t = e.target.closest?.("[data-tip]"); t ? showTip(e, t.dataset.tip) : hideTip(); } });
addEventListener("scroll", hideTip, {passive: true});

// ---------- значки типов: цветной кружок типа и белая пиктограмма (24×24)
const GLYPHS = [
  [/пригород/i, `<path d="M12 3.5 2.5 11.5H5.5V20h5.2v-5h2.6v5h5.2v-8.5h3z"/>`],                                        // дом
  [/Северо/, `<g fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round"><path d="M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9M9.5 4.6 12 6.2l2.5-1.6M9.5 19.4 12 17.8l2.5 1.6M4.5 10.6l2.6-.1-1.3-2.6M19.5 13.4l-2.6.1 1.3 2.6"/></g>`], // снежинка
  [/Ресурс/, `<g fill="none" stroke="#fff" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 7.4 21M12 3l4.6 18M9 14.5h6M10.1 10h3.8M5.5 21h13M12 3v3"/></g>`], // вышка
  [/Крупн/, `<path d="M3.5 21V11h5v10zM9.8 21V3.5h5.4V21zM16.5 21v-7.5h4V21z"/><path fill-opacity=".45" d="M11.2 6h1v1.2h-1zm1.6 0h1v1.2h-1zM11.2 9h1v1.2h-1zm1.6 0h1v1.2h-1zM11.2 12h1v1.2h-1zm1.6 0h1v1.2h-1z"/>`], // небоскрёбы
  [/Сельская/, `<path d="M12 2.5 6.8 9.6h3L5.2 16h5.3v5.5h3V16h5.3l-4.6-6.4h3z"/>`],                                    // ель
  [/Сибирь/, `<g fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="5" r="1.9"/><path d="M12 7v13.5M8 10.5h8M4.8 13.5a7.2 7.2 0 0 0 14.4 0"/></g>`], // якорь
  [/Индустри/, `<path d="M2.5 21V11.5l5 3v-3l5 3V8.5h2.2V3.5h2.6v5h1.4V3.5h2.6V21z"/>`],                               // завод
  [/Аграр/, `<path d="M12 9c-2.2-1-3.4-3.1-3.4-5.6 2.2 1 3.4 3.1 3.4 5.6zm0 0c2.2-1 3.4-3.1 3.4-5.6-2.2 1-3.4 3.1-3.4 5.6zm0 5c-2.4-1-3.8-3.2-3.8-5.6 2.4 1 3.8 3.2 3.8 5.6zm0 0c2.4-1 3.8-3.2 3.8-5.6-2.4 1-3.8 3.2-3.8 5.6zm0 5c-2.4-1-3.8-3.2-3.8-5.6 2.4 1 3.8 3.2 3.8 5.6zm0 0c2.4-1 3.8-3.2 3.8-5.6-2.4 1-3.8 3.2-3.8 5.6z"/><path d="M11.2 9h1.6v12h-1.6z"/>`] // колос
];
const glyphOf = c => (GLYPHS.find(([re]) => re.test(c.short || c.name)) || [null, `<circle cx="12" cy="12" r="5"/>`])[1];
// фишка «Монополии»: металлическая фигурка на подставке цвета типа (56×56)
const shade = (hex, f) => { const n = parseInt(hex.slice(1), 16), t = f > 0 ? 255 : 0, a = Math.abs(f);
  const c = [n >> 16, n >> 8 & 255, n & 255].map(v => Math.round(v + (t - v) * a)); return "#" + c.map(v => v.toString(16).padStart(2, "0")).join(""); };
const badgeSVG = (k, size = 56) => {
  const g = glyphOf(CL[k]), isStroke = g.includes('fill="none"');
  const metal = isStroke ? g.replace(/stroke="#fff"/g, 'stroke="url(#m)"') : `<g fill="url(#m)" stroke="#3f444b" stroke-width=".55">${g}</g>`;
  const outline = isStroke ? g.replace(/stroke="#fff"/g, 'stroke="#3f444b"').replace(/stroke-width="([\d.]+)"/g, (m, w) => `stroke-width="${+w + 1}"`) : "";
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 56 56">` +
    `<defs><linearGradient id="m" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset=".45" stop-color="#c3c7cd"/><stop offset="1" stop-color="#6d727a"/></linearGradient></defs>` +
    `<ellipse cx="28" cy="49" rx="18" ry="4" fill="#000" opacity=".15"/>` +
    `<ellipse cx="28" cy="47" rx="17" ry="5.5" fill="${shade(PAL[k], -.35)}" stroke="#1d1f23" stroke-width=".8"/>` +
    `<ellipse cx="28" cy="45" rx="17" ry="5.5" fill="${PAL[k]}" stroke="#1d1f23" stroke-width=".8"/>` +
    `<ellipse cx="25" cy="43.6" rx="9" ry="1.6" fill="#fff" opacity=".35"/>` +
    (outline ? `<g transform="translate(9.5 4) scale(1.55)">${outline}</g>` : "") +
    `<g transform="translate(9.5 4) scale(1.55)">${metal}</g></svg>`;
};
const BADGE = CL.map(c => "data:image/svg+xml;charset=utf-8," + encodeURIComponent(badgeSVG(c.id, 112)));
const badgeImg = (k, px = 26) => `<img src="${BADGE[k]}" width="${px}" height="${px}" alt="" style="display:block;flex-shrink:0">`;

// значение признака в понятных единицах (для подсказок к профилям)
function featVal(f, p) {
  const v = p[f]; if (v == null) return "—";
  if (f.startsWith("share_") || f.startsWith("emp_share_")) return pct1(v);
  if (f === "cons_level") return `${fmt(p.cons_total_rub)} ₽ в месяц`;
  if (f === "wage_rel") return `×${f2(Math.exp(v))} к медиане`;
  if (f === "emp_rate") return `${f2(v)} работника на жителя`;
  if (f === "log_ma") return `индекс ${fmt(Math.exp(v))}`;
  if (f === "log_pop") return `${fmt(Math.exp(v))} жителей`;
  if (f === "summer_peak") return (v > 0 ? "+" : "") + pct1(v) + " летом";
  return f3(v);
}

$("lead").textContent = `Каждый из ${fmt(NMO)} муниципалитетов относится к одному из ${K} типов, а ${fmt(INTRA.mos.length)} ${plural(INTRA.mos.length, "район", "района", "районов")} Москвы и Петербурга — к одному из ${IK} внутригородских. Выберите тип, переключите слой или найдите свой город.`;
$("themeBtn").onclick = () => {
  const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  root.dataset.theme = dark ? "light" : "dark";
};
