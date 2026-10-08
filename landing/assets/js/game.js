// Игра «Угадайте экономику».
// Классический скрипт: файлы подключаются в index.html по порядку и делят общие глобальные имена.
// Раунд — настоящий МО с устойчивым типом (≥ 90% месяцев в одном типе). Подсказки открываются
// по одной: структура трат → занятость → регион и население. Очки: 3 / 2 / 1 за верный ответ.
(function () {
  const ROUNDS = 10;
  const modal = m => { const c = d3.rollup(m.L, v => v.length, x => x); return [...c].sort((a, b) => b[1] - a[1])[0][0]; };
  const pool = d3.group(D.mos.filter(m => (m.conf ?? 0) >= 0.9 && m.pop > 3000), modal);
  const rnd = n => Math.floor(Math.random() * n);
  const shortEmp = Object.fromEntries(Object.entries(EMP_RU).map(([k, v]) => [k, v.replace(/\s*\(.*\)$/, "")]));
  const RANKS = [[26, "Главный экономгеограф"], [19, "Экономгеограф"], [11, "Краевед"], [0, "Турист"]];
  let best = 0; try { best = +localStorage.getItem("sbx-quiz-best") || 0; } catch (e) {}
  let st;

  function newGame() {
    const order = d3.shuffle(CL.map(c => c.id).filter(k => pool.get(k)?.length));
    st = {round: 0, score: 0, streak: 0, order, used: new Set()};
    nextRound();
  }
  function nextRound() {
    if (st.round >= ROUNDS) return finish();
    const k = st.order[st.round % st.order.length];
    const cand = pool.get(k).filter(m => !st.used.has(m.id));
    const m = cand[rnd(cand.length)]; st.used.add(m.id);
    Object.assign(st, {m, answer: k, clues: 1, done: false});
    st.round++;
    render();
  }
  function clueHtml(i) {
    const m = st.m;
    if (i === 0) return `<div class="clue"><h4>Структура трат <span class="pts">подсказка 1</span></h4><p class="muted" style="margin:0 0 8px;font-size:14px">Безналичные траты жителя: <b style="color:var(--ink)">${fmt(m.cons)} ₽</b> в месяц</p>${bars(m.sh, SH_RU, 0.6)}</div>`;
    if (i === 1) return `<div class="clue"><h4>Занятость <span class="pts">подсказка 2</span></h4>${bars(Object.fromEntries(Object.entries(m.emp).sort((a, b) => b[1] - a[1]).slice(0, 5)), shortEmp, 0.6)}<p class="muted" style="margin:8px 0 0;font-size:14px">Зарплата: ${m.wage != null ? `×${f2(m.wage)} к медиане МО` : "нет данных"}</p></div>`;
    return `<div class="clue"><h4>Где это <span class="pts">подсказка 3</span></h4><p style="margin:0;font-size:15px">${m.r}<br><span class="muted">${fmt(m.pop)} жителей, ${m.t}</span></p></div>`;
  }
  function render() {
    $("gRound").textContent = st.round; $("gScore").textContent = st.score; $("gStreak").textContent = st.streak; $("gBest").textContent = best;
    const left = [0, 1, 2].map(i => i < st.clues || st.done ? clueHtml(i)
      : (i === st.clues ? `<div class="clue locked"><span>Ещё ${3 - st.clues} ${3 - st.clues === 1 ? "подсказка" : "подсказки"}. Каждая отнимает одно очко.</span><button class="btn" id="gMore">Открыть</button></div>` : "")).join("");
    $("gClues").innerHTML = left;
    $("gOpts").innerHTML = CL.map(c => `<button class="opt" data-k="${c.id}" ${st.done ? "disabled" : ""}>${badgeImg(c.id, 36)}<span>${c.short || c.name}</span></button>`).join("");
    if (st.done) $("gOpts").querySelectorAll(".opt").forEach(b => { const k = +b.dataset.k;
      b.classList.add(k === st.answer ? "right" : k === st.pick ? "wrong" : "dim"); });
    $("gMore")?.addEventListener("click", () => { st.clues++; render(); });
    $("gOpts").querySelectorAll(".opt:not(:disabled)").forEach(b => b.onclick = () => answer(+b.dataset.k));
    $("gResult").innerHTML = st.done ? verdict() : `<p class="hint">Верный ответ сейчас стоит ${4 - st.clues} ${4 - st.clues === 1 ? "очко" : "очка"}.</p>`;
    $("gNext")?.addEventListener("click", nextRound);
    $("gMap")?.addEventListener("click", () => goMap({mo: st.m.id}));
  }
  function answer(k) {
    st.pick = k; st.done = true;
    const ok = k === st.answer, pts = ok ? 4 - st.clues : 0;
    st.score += pts; st.streak = ok ? st.streak + 1 : 0; st.last = {ok, pts};
    render();
  }
  function verdict() {
    const m = st.m, c = CL[st.answer], ok = st.last.ok;
    const sig = (D.meta.signature_features || []).filter(f => c.z[f] != null).sort((a, b) => Math.abs(c.z[b]) - Math.abs(c.z[a]))[0];
    return `<div class="verdict"><b>${ok ? `Верно! +${st.last.pts}` : "Не угадали."}</b> Это <b>${m.n}</b> (${m.r}) — тип «${c.name}».
      Главная примета типа: ${(FEAT_RU[sig] || sig).toLowerCase()} ${c.z[sig] > 0 ? "выше" : "ниже"} среднего.${st.streak >= 3 ? ` Серия из ${st.streak} верных подряд!` : ""}</div>
      <div class="gameactions"><button class="btn primary" id="gNext">${st.round >= ROUNDS ? "Итоги" : "Следующий муниципалитет"}</button><button class="btn" id="gMap">Показать на карте</button></div>`;
  }
  function finish() {
    const rank = RANKS.find(([s]) => st.score >= s)[1];
    if (st.score > best) { best = st.score; try { localStorage.setItem("sbx-quiz-best", best); } catch (e) {} }
    $("gBest").textContent = best;
    $("gClues").innerHTML = `<div class="clue"><h4>Игра окончена</h4><p style="margin:0;font-size:28px;font-weight:600">${st.score} из ${ROUNDS * 3}</p><p class="muted" style="margin:6px 0 0;font-size:15px">Ваше звание: <b style="color:var(--ink)">${rank}</b></p></div>`;
    $("gOpts").innerHTML = "";
    $("gResult").innerHTML = `<div class="gameactions"><button class="btn primary" id="gAgain">Сыграть ещё раз</button></div>`;
    $("gAgain").onclick = newGame;
  }
  newGame();
})();
