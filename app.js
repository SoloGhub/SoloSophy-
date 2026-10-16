/* SoloSophy Insights — static web app (no login, no keys). Data: docs/data/*.json written by scheduled tasks. */
(function () {
  'use strict';
  const $ = (s, el) => (el || document).querySelector(s);
  const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const DEC = { GC: 1, SI: 3, HG: 4, CL: 2, SOXL: 2 };
  const ICON = { GC: 'gc', SI: 'si', HG: 'hg', CL: 'cl', SOXL: 'soxl' };
  const FAM_SHORT = { GC: 'GCZ6', SI: 'SIZ6', HG: 'HGZ6', CL: 'CLZ6', SOXL: 'SOXL' };
  const fmt = (v, a, d) => (v == null || isNaN(v)) ? '—' : Number(v).toLocaleString('en-US', { minimumFractionDigits: d != null ? d : DEC[a] || 2, maximumFractionDigits: d != null ? d : DEC[a] || 2 });
  const pc = (v) => (v == null ? '—' : (v > 0 ? '+' : '') + Number(v).toFixed(2) + '%');
  const pcs = (v) => `<span class="num">${pc(v)}</span>`;
  const nc = (s) => /[\u0600-\u06FF]/.test(String(s)) ? '' : 'n';
  const chip = (v, suffix) => v == null ? '' : `<span class="chip ${v > 0.05 ? 'up' : v < -0.05 ? 'dn' : 'fl'}">${pc(v)}${suffix ? ' ' + esc(suffix) : ''}</span>`;
  const S = { index: null, report: null, engine: null, alerts: null, live: null, config: {}, asset: 'GC', view: 'report', engTf: 'daily', engAsset: 'GC' };

  async function getJSON(path, optional) {
    try {
      const r = await fetch(path + (path.includes('?') ? '&' : '?') + 't=' + Math.floor(Date.now() / 60000), { cache: 'no-store' });
      if (!r.ok) throw new Error(r.status + ' ' + path);
      return await r.json();
    } catch (e) { if (optional) return null; throw e; }
  }
  function toast(msg) { const t = document.createElement('div'); t.className = 'toast'; t.textContent = msg; document.body.appendChild(t); setTimeout(() => t.remove(), 2600); }
  const plaque = (a, small, sel) => `<span class="plaque${sel ? ' sel' : ''}" data-family="${ICON[a.code || a]}" data-asset="${esc(a.code || a)}"><img src="assets/icons/${ICON[a.code || a]}.svg" alt=""><span><b>${esc(FAM_SHORT[a.code || a])}</b><small>${esc(small || (a.name || ''))}</small></span></span>`;
  const secH = (icon, title, sub, fill, end) => `<div class="sec-h ${fill || ''}"><img src="assets/icons/${icon}.svg" alt=""><div><h2>${title}</h2>${sub ? `<p>${sub}</p>` : ''}</div>${end ? `<div class="end">${end}</div>` : ''}</div>`;

  /* ------------------------------------------------------------ boot */
  async function boot() {
    $('#printBtn').addEventListener('click', () => window.print());
    $$('.tab[data-view]').forEach((b) => b.addEventListener('click', () => go(b.dataset.view)));
    window.addEventListener('hashchange', route);
    try {
      [S.index, S.config, S.alerts, S.live] = await Promise.all([
        getJSON('data/index.json'), getJSON('data/config.json', true), getJSON('data/alerts.json', true), getJSON('data/live.json', true)]);
      S.config = S.config || {};
    } catch (e) {
      $('#view-report').innerHTML = `<div class="err">تعذّر تحميل فهرس التقارير (${esc(e.message)}).</div>`; return;
    }
    route();
  }
  function go(view, id) { location.hash = view + (id ? '/' + id : ''); }
  async function route() {
    const [view, id] = (location.hash.replace('#', '') || 'report').split('/');
    S.view = ['report', 'alerts', 'engine', 'archive', 'listen', 'generate'].includes(view) ? view : 'report';
    $$('.tab[data-view]').forEach((b) => b.setAttribute('aria-selected', b.dataset.view === S.view ? 'true' : 'false'));
    $$('.view').forEach((v) => v.classList.toggle('hide', v.id !== 'view-' + S.view));
    const want = id ? S.index.reports.find((r) => r.id === id) : null;
    const path = want ? want.path : S.index.latest;
    if (!S.report || S.report._path !== path) {
      try { S.report = await getJSON('data/' + path.replace(/^data\//, '')); S.report._path = path; S.engine = null; }
      catch (e) { $('#view-report').innerHTML = `<div class="err">تعذّر تحميل التقرير (${esc(e.message)}).</div>`; return; }
      renderChrome(S.report); renderReport(S.report);
    }
    if (S.view === 'engine') renderEngine();
    if (S.view === 'alerts') renderAlerts();
    if (S.view === 'archive') renderArchive();
    if (S.view === 'listen') renderListen();
    if (S.view === 'generate') renderGenerate();
    window.scrollTo({ top: 0 });
  }

  /* ------------------------------------------------------------ chrome */
  function renderChrome(r) {
    $('#edition').textContent = r.edition || 'Market Vision Edition';
    if (r.slogan) $('#slogan').textContent = r.slogan;
    $('#hdrMeta').innerHTML = `<span><b>${esc(r.type_ar)}</b> · ${esc(r.subtitle || '')}</span><span>الإصدار: <b>${esc(r.issued_label)}</b></span><span>${esc(r.data_cutoff)}</span>`;
    $('#tickerRun').innerHTML = (r.what_changed || []).map((w) => `<span>${esc(w.text)}</span>`).join('');
    $('#ticker').classList.toggle('hide', !(r.what_changed || []).length);
    $('#disclaimer').textContent = r.disclaimer || '';
    document.title = `SoloSophy Insights — ${r.type_ar} — ${r.issued_label}`;
  }

  /* ------------------------------------------------------------ charts */
  function spark(data, color) {
    if (!data || data.length < 2) return '';
    const c = data.map((d) => d.c), w = 300, h = 46, mn = Math.min(...c), mx = Math.max(...c), k = (mx - mn) || 1;
    const pts = c.map((v, i) => `${(i / (c.length - 1) * w).toFixed(1)},${(h - 3 - (v - mn) / k * (h - 6)).toFixed(1)}`).join(' ');
    return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline fill="none" stroke="${color}" stroke-width="2" points="${pts}"/><polyline fill="${color}" fill-opacity=".08" stroke="none" points="0,${h} ${pts} ${w},${h}"/></svg>`;
  }
  const parseLvl = (s) => String(s).replace(/,/g, '').split(/[–-]/).map((x) => parseFloat(x)).filter((x) => !isNaN(x));
  function candleChart(a) {
    const d = (a.spark || []).slice(-70); if (!d.length) return '';
    const W = 920, H = 380, padL = 8, padR = 74, padT = 14, padB = 26;
    const lo = Math.min(...d.map((x) => x.l)), hi = Math.max(...d.map((x) => x.h));
    const lv = [];
    const add = (arr, kind) => (arr || []).forEach(([v, n]) => { const p = parseLvl(v); if (p.length) lv.push({ v: p[0], v2: p[1], n, kind }); });
    add(a.control.resist, 'r'); add(a.control.support, 's'); if (a.control.pivot) add([a.control.pivot], 'p');
    let ymin = lo, ymax = hi; const span = hi - lo;
    lv.forEach((l) => { if (l.v > lo - span * 0.35 && l.v < hi + span * 0.35) { ymin = Math.min(ymin, l.v); ymax = Math.max(ymax, l.v2 || l.v); } });
    if (a.ntz) { ymin = Math.min(ymin, a.ntz[0]); ymax = Math.max(ymax, a.ntz[1]); }
    const pad = (ymax - ymin) * 0.04; ymin -= pad; ymax += pad;
    const y = (v) => padT + (ymax - v) / (ymax - ymin) * (H - padT - padB);
    const cw = (W - padL - padR) / d.length;
    let g = '';
    for (let i = 0; i <= 4; i++) { const v = ymin + (ymax - ymin) * i / 4; g += `<line x1="${padL}" x2="${W - padR}" y1="${y(v)}" y2="${y(v)}" stroke="#000" stroke-opacity=".05"/>`; }
    if (a.ntz) g += `<rect x="${padL}" width="${W - padL - padR}" y="${y(a.ntz[1])}" height="${y(a.ntz[0]) - y(a.ntz[1])}" fill="#987230" fill-opacity=".10"/><text x="${W - padR - 8}" y="${y(a.ntz[1]) - 4}" font-size="11" font-weight="700" fill="#725b33" font-family="Noto Naskh Arabic" direction="rtl" text-anchor="start">منطقة اللاتداول</text>`;
    let c = '';
    d.forEach((x, i) => {
      const cx = padL + i * cw + cw / 2, up = x.c >= x.o, col = up ? '#205e43' : '#882f40';
      c += `<line x1="${cx}" x2="${cx}" y1="${y(x.h)}" y2="${y(x.l)}" stroke="${col}" stroke-width="1"/>`;
      const top = y(Math.max(x.o, x.c)), bh = Math.max(1, Math.abs(y(x.o) - y(x.c)));
      c += `<rect x="${cx - cw * 0.34}" y="${top}" width="${cw * 0.68}" height="${bh}" fill="${up ? '#2d7a57' : '#a64a5b'}" rx="1"/>`;
    });
    let L = '';
    const COL = { r: '#882f40', s: '#205e43', p: '#987230' };
    const labels = [];
    lv.forEach((l) => {
      if (l.v < ymin || l.v > ymax) return;
      if (l.v2 && l.v2 <= ymax) L += `<rect x="${padL}" width="${W - padL - padR}" y="${y(l.v2)}" height="${Math.max(1, y(l.v) - y(l.v2))}" fill="${COL[l.kind]}" fill-opacity=".07"/>`;
      L += `<line x1="${padL}" x2="${W - padR}" y1="${y(l.v)}" y2="${y(l.v)}" stroke="${COL[l.kind]}" stroke-width="${l.kind === 'p' ? 1.6 : 1}" stroke-dasharray="${l.kind === 'p' ? '6 4' : '3 4'}" opacity=".85"/>`;
      labels.push({ y: y(l.v), t: fmt(l.v, a.code), col: COL[l.kind], last: false });
    });
    const last = d[d.length - 1].c;
    L += `<line x1="${padL}" x2="${W - padR}" y1="${y(last)}" y2="${y(last)}" stroke="#101c2b" stroke-width="1.2"/>`;
    labels.push({ y: y(last), t: fmt(last, a.code), col: '#101c2b', last: true });
    // collision avoidance: keep the close label fixed, spread the others at >= 14px
    labels.sort((p, q) => p.y - q.y);
    const gap = 14;
    for (let pass = 0; pass < 6; pass++) {
      for (let i = 1; i < labels.length; i++) {
        const A0 = labels[i - 1], B0 = labels[i];
        if (B0.y - A0.y < gap) {
          const need = gap - (B0.y - A0.y);
          if (A0.last) B0.y += need; else if (B0.last) A0.y -= need; else { A0.y -= need / 2; B0.y += need / 2; }
        }
      }
    }
    labels.forEach((l) => {
      const yy = Math.max(padT, Math.min(H - padB, l.y));
      if (l.last) L += `<rect x="${W - padR + 1}" y="${yy - 9}" width="${padR - 2}" height="18" rx="4" fill="#101c2b"/><text x="${W - padR + 5}" y="${yy + 4}" font-size="11.5" fill="#f3e6bf" font-weight="700" font-family="Avenir Next,Segoe UI,Arial">${l.t}</text>`;
      else L += `<text x="${W - padR + 5}" y="${yy + 4}" font-size="11" fill="${l.col}" font-family="Avenir Next,Segoe UI,Arial">${l.t}</text>`;
    });
    let X = '';
    [0, Math.floor(d.length / 3), Math.floor(2 * d.length / 3), d.length - 1].forEach((i) => { X += `<text x="${padL + i * cw + cw / 2}" y="${H - 8}" font-size="10.5" fill="#676961" text-anchor="middle" font-family="Avenir Next,Segoe UI,Arial">${esc(d[i].t.slice(5))}</text>`; });
    return `<svg class="chart" viewBox="0 0 ${W} ${H}" direction="ltr" style="direction:ltr" role="img" aria-label="شموع يومية مع مستويات الدعم والمقاومة">${g}${L}${c}${X}</svg>
      <div class="legend"><span><i style="background:#882f40"></i>مقاومة</span><span><i style="background:#205e43"></i>دعم</span><span><i style="background:#987230"></i>محور</span><span><i style="background:#987230;opacity:.35;height:8px"></i>منطقة اللاتداول</span><span><i style="background:#101c2b"></i>الإغلاق</span><span>شموع يومية · IBKR Last · تاريخ الجلسة</span></div>`;
  }

  /* ------------------------------------------------------------ report */
  function renderReport(r) {
    const A = r.assets || [];
    if (!A.find((x) => x.code === S.asset) && A.length) S.asset = A[0].code;
    const html = [];
    // hero
    html.push(`<section class="sec"><div class="hero"><div class="txt"><div class="kicker">MARKET VISION · ${esc(r.type)}</div><h1>رؤية الأسواق</h1><div class="headline">${esc(r.headline)}</div><div class="plaques">${A.map((a) => plaque(a, a.tag_ar)).join('')}</div></div><div class="imgwrap" role="img" aria-label="تصور رمزي للمعادن والطاقة"></div></div></section>`);
    // price board
    html.push(`<section class="sec">${secH('monitor', 'لوحة الأسعار', 'IBKR · سعر Last عند الإغلاق — العقد النشط ديسمبر 2026', 'f-green')}<div class="sec-b"><div class="grid g5">${A.map((a) => `
      <div class="pcard" data-asset="${a.code}"><div class="top">${plaque(a, a.name)}</div>
      <div class="px">${fmt(a.price.last, a.code)}</div>
      <div class="chips">${chip(a.price.day, 'يوم')}${chip(a.price.week, 'أسبوع')}${a.price.month != null ? chip(a.price.month, 'شهر') : ''}</div>
      ${spark(a.spark, a.price.week >= 0 ? '#205e43' : '#882f40')}
      <span class="tag ${a.tag}"><img src="assets/icons/${a.tag === 'bullish' ? 'bull' : a.tag === 'bearish' ? 'bear' : 'scale'}.svg" alt="">${esc(a.tag_ar)}</span>
      ${a.price.front ? `<div class="small muted">نوفمبر ${esc(a.price.front.contract)}: <span class="num">${fmt(a.price.front.last, 'CL')}</span> (${pcs(a.price.front.week)} أسبوعياً) — ينتهي ${esc(a.price.front.last_trade)}</div>` : ''}
      </div>`).join('')}</div></div></section>`);
    // sessions
    if ((r.sessions || []).length) html.push(`<section class="sec">${secH('clock', 'رادار الجلسات', 'المواعيد بتوقيت دبي — العدّ التنازلي محسوب من جهازك', 'f-teal')}<div class="sec-b"><div class="grid g3">${r.sessions.map((s) => {
      const ic = /آسيا/.test(s.region) ? 'asia' : /أوروبا/.test(s.region) ? 'europe' : /أمريكا/.test(s.region) ? 'us' : 'clock';
      return `<div class="sess"><div class="h"><img src="assets/icons/${ic}.svg" alt=""><div><b>${esc(s.region)} · ${esc(s.city)}</b><div class="t">${esc(s.open_dubai)}</div></div></div><div class="small muted">${esc(s.note)}</div><div class="cd" data-at="${esc(s.open_dubai)}"></div></div>`;
    }).join('')}</div></div></section>`);
    // asset deep dive
    html.push(`<section class="sec" id="deep">${secH('levels', 'تحليل الأصول', 'إحنا فين · نقاط التحكم · المحرّكات · المؤشرات · السيناريوهات · التوصية', 'f-gold')}<div class="sec-b"><div class="asset-tabs">${A.map((a) => plaque(a, a.name, a.code === S.asset)).join('')}</div><div id="assetBody"></div></div></section>`);
    // macro
    if (r.macro) html.push(`<section class="sec">${secH('usd', 'الاقتصاد الكلي والفيدرالي', 'البيانات الصادرة هذا الأسبوع ومسار الفائدة', 'f-steel')}<div class="sec-b">
      <div class="tblwrap"><table class="tbl"><thead><tr><th>البيان</th><th>الفعلي</th><th>المتوقع</th><th>السابق</th><th>التوقيت (دبي)</th><th>القراءة</th></tr></thead><tbody>${r.macro.data.map((m) => `<tr><td>${esc(m.name)}</td><td class="${nc(m.actual)}"><b>${esc(m.actual)}</b></td><td class="${nc(m.consensus)}">${esc(m.consensus)}</td><td class="${nc(m.prior)}">${esc(m.prior)}</td><td>${esc(m.date)}</td><td>${esc(m.read)}</td></tr>`).join('')}</tbody></table></div>
      <div class="grid g2" style="margin-top:14px"><div class="card"><h3>الفيدرالي</h3><ul>${r.macro.fed.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div>
      <div class="card"><h3>العوائد والدولار والأسهم</h3><table class="tbl"><tbody>${r.macro.rates.map((x) => `<tr><td>${esc(x.name)}</td><td class="${nc(x.value)}"><b>${esc(x.value)}</b></td><td class="${nc(x.week)}">${esc(x.week)}</td></tr>`).join('')}</tbody></table><h3 style="margin-top:12px">الصين</h3><ul>${r.macro.china.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div></div></div></section>`);
    // geopolitics
    if (r.geopolitics) html.push(`<section class="sec">${secH('globe', 'الجيوسياسة', 'المؤكد فقط (مصدران مستقلان أو مصدر رسمي) — وغير المؤكد في قائمة منفصلة', 'f-burg')}<div class="sec-b"><div class="grid g2">${r.geopolitics.confirmed.map((g) => `<div class="geo"><h4>${esc(g.title)}${g.single ? '<span class="single">مصدر واحد</span>' : ''}</h4><div>${esc(g.detail)}</div><div class="src">المصادر: ${esc(g.sources.join(' · '))} — <span class="impact">${esc(g.impact)}</span></div></div>`).join('')}</div>
      <div class="card" style="margin-top:14px"><h3>غير مؤكد / ادعاءات طرف واحد</h3><ul>${r.geopolitics.unconfirmed.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div></div></section>`);
    // events
    if ((r.events || []).length) html.push(`<section class="sec">${secH('clock', 'أجندة الأسبوع القادم', 'بتوقيت دبي · 🔔 = تنبيه مجدول قبل الحدث بـ30 دقيقة وبعده مباشرة', 'f-teal')}<div class="sec-b"><div class="tblwrap"><table class="tbl"><thead><tr><th>اليوم</th><th>الوقت</th><th>الحدث</th><th>الدولة</th><th>المتوقع</th><th>السابق</th><th>الأهمية</th><th>الأصول</th></tr></thead><tbody>${r.events.map((e) => `<tr><td>${esc(e.day)}</td><td class="${nc(e.time)}">${esc(e.time)}</td><td>${e.alert ? '<span class="bell">🔔</span> ' : ''}${esc(e.event)}</td><td>${esc(e.country)}</td><td class="${nc(e.consensus)}">${esc(e.consensus)}</td><td class="${nc(e.prior)}">${esc(e.prior)}</td><td><span class="imp ${/حرج/.test(e.imp) ? 'crit' : /مرتفع/.test(e.imp) ? 'high' : 'med'}">${esc(e.imp)}</span></td><td>${esc(e.assets)}</td></tr>`).join('')}</tbody></table></div>
      ${(r.events_after || []).length ? `<div class="card" style="margin-top:12px"><h3>ما بعد الأسبوع</h3><ul>${r.events_after.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div>` : ''}</div></section>`);
    // market makers
    const mm = r.market_makers;
    if (mm) html.push(`<section class="sec">${secH('handshake', 'صُنّاع السوق والمراكز', esc(mm.cot_note || ''), 'f-plum')}<div class="sec-b">
      <div class="tblwrap"><table class="tbl"><thead><tr><th>الأصل</th><th>المضاربون (MM) شراء</th><th>MM بيع</th><th>صافي MM</th><th>التغير</th><th>تجّار المقايضة (صافي)</th><th>المنتجون (صافي)</th><th>الاتجاه</th></tr></thead><tbody>${mm.cot.map((c) => `<tr><td>${plaque(c.asset)}</td><td class="n">${fmt(c.mm_long, 0, 0)}</td><td class="n">${fmt(c.mm_short, 0, 0)}</td><td class="n"><b>${fmt(c.mm_net, 0, 0)}</b></td><td class="n">${c.chg > 0 ? '+' : ''}${fmt(c.chg, 0, 0)}</td><td class="n">${fmt(c.swap_net, 0, 0)}</td><td class="n">${fmt(c.pm_net, 0, 0)}</td><td>${esc(c.trend)}</td></tr>`).join('')}</tbody></table></div>
      <div class="grid g2" style="margin-top:14px"><div class="card"><h3>صناديق الذهب المتداولة</h3><ul>${mm.etf.map((x) => `<li>${esc(x)}</li>`).join('')}</ul><h3>البنوك المركزية</h3><ul>${mm.central_banks.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div>
      <div class="card"><h3>الخيارات (IBKR)</h3><table class="tbl"><thead><tr><th>الأصل</th><th>IV</th><th>المئين</th><th>القراءة</th></tr></thead><tbody>${mm.options.map((o) => `<tr><td>${esc(o.asset)}</td><td class="n">${esc(o.iv)}</td><td class="n">${esc(o.ivp)}</td><td>${esc(o.read)}</td></tr>`).join('')}</tbody></table><p class="small muted">${esc(mm.options_note)}</p></div></div>
      <div class="card" style="margin-top:14px"><h3>أسواق التوقعات</h3><table class="tbl"><tbody>${mm.prediction.map((p) => `<tr><td>${esc(p.market)}</td><td class="${nc(p.value)}"><b>${esc(p.value)}</b></td><td class="small muted">${esc(p.src)}</td></tr>`).join('')}</tbody></table><p class="small muted">${esc(mm.prediction_note)}</p></div></div></section>`);
    // conflicts
    if ((r.conflicts || []).length) html.push(`<section class="sec">${secH('escalation', 'التعارضات وما لم يُتحقق منه', 'كل رقم متعارض يُعرض مع طريقة حسمه — لا شيء مخفي', 'f-brown')}<div class="sec-b"><div class="tblwrap"><table class="tbl"><thead><tr><th>الموضوع</th><th>التعارض</th><th>الحسم</th></tr></thead><tbody>${r.conflicts.map((c) => `<tr><td><b>${esc(c.topic)}</b></td><td>${esc(c.detail)}</td><td>${esc(c.resolution)}</td></tr>`).join('')}</tbody></table></div></div></section>`);
    // methodology
    if ((r.methodology || []).length) html.push(`<section class="sec">${secH('shield', 'المنهجية وقواعد البيانات', 'كيف بُنيت الأرقام والنسب والمستويات', 'f-steel')}<div class="sec-b"><ul>${r.methodology.map((x) => `<li>${esc(x)}</li>`).join('')}</ul><p class="small">نتائج المحرك الكمي (CME Engine) معروضة كاملة في تبويب <a href="#engine">مختبر المحرك</a>.</p></div></section>`);
    // solo vision (FIXED position: before footer)
    if ((r.solo_vision || []).length) html.push(`<section class="sec sv"><div class="sec-h"><span class="sv-plaque"><b><i>Solo</i> Vision</b></span></div><div class="sec-b">${r.solo_vision.map((p) => `<p>${p}</p>`).join('')}<div class="wisdom">${esc(r.solo_vision_wisdom || '')}</div></div></section>`);
    // sources
    if ((r.sources || []).length) html.push(`<section class="sec">${secH('news', 'المصادر', 'A = رسمي/أولي · B = وسيلة موثوقة — كل رقم في التقرير يعود لأحدها', 'f-brown')}<div class="sec-b"><ol class="small">${r.sources.map((s) => `<li><span class="pill">${esc(s.tier)}</span> ${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title)}</a>` : `${esc(s.title)} — ${esc(s.note || '')}`}</li>`).join('')}</ol></div></section>`);
    $('#view-report').innerHTML = html.join('');
    $$('#view-report .plaque[data-asset], #view-report .pcard[data-asset]').forEach((el) => el.addEventListener('click', () => { S.asset = el.dataset.asset; renderAsset(); $('#deep').scrollIntoView({ behavior: 'smooth' }); }));
    renderAsset(); tickSessions();
  }

  function renderAsset() {
    const r = S.report, a = (r.assets || []).find((x) => x.code === S.asset); if (!a) return;
    $$('#deep .asset-tabs .plaque').forEach((p) => p.classList.toggle('sel', p.dataset.asset === S.asset));
    const p = a.price, L = a.ladder;
    const lvRow = (cls, k, v, n, w) => `<div class="lvl ${cls}"><span class="k">${k}</span><div><div class="v">${esc(v)}</div><div class="small muted">${esc(n)}</div></div><div class="bar" style="width:${w}%"></div></div>`;
    const res = a.control.resist.slice().reverse().map(([v, n], i, arr) => lvRow('r', 'مقاومة ' + (arr.length - i), v, n, 40 + (arr.length - i) * 12)).join('');
    const sup = a.control.support.map(([v, n], i) => lvRow('s', 'دعم ' + (i + 1), v, n, 40 + (i + 1) * 12)).join('');
    const piv = a.control.pivot ? lvRow('p', 'المحور', a.control.pivot[0], a.control.pivot[1], 60) : '';
    const now = lvRow('now', 'الإغلاق', fmt(p.last, a.code), 'IBKR Last', 50);
    const setup = (s) => `<div class="setup ${s.side}"><div class="hd"><b>${esc(s.label)}</b><span class="action ${s.side === 'long' ? 'buy' : 'sell'}">${s.side === 'long' ? 'BUY' : 'SELL'}</span></div>
      <span class="grade ${s.grade}">${esc(s.grade_ar)}</span>
      <div class="lv"><div><small>الدخول</small><b>${fmt(s.entry, a.code)}</b></div><div><small>وقف الخسارة</small><b>${fmt(s.stop, a.code)}</b></div><div><small>الهدف 1</small><b>${fmt(s.targets[0], a.code)}</b></div><div><small>الهدف 2</small><b>${fmt(s.targets[1], a.code)}</b></div></div>
      <div class="cond">الشرط: ${esc(s.condition)}</div><div class="small muted">المخاطرة <span class="num">${fmt(s.risk, a.code)}</span> · العائد/المخاطرة: الهدف 1 <span class="num">${s.rr[0].toFixed(2)}</span> · الهدف 2 <span class="num">${s.rr[1].toFixed(2)}</span> · إزاحة <span class="num">${fmt(s.raw.offset, a.code, DEC[a.code] + 1)}</span> (10% ATR)</div>${s.note ? `<div class="note">${esc(s.note)}</div>` : ''}</div>`;
    const an = a.analog || {};
    const pos = a.positioning;
    $('#assetBody').innerHTML = `
      <div class="subh"><img src="assets/icons/compass.svg" alt=""><h3>إحنا فين — ${esc(a.name)} <span class="small muted">${esc(a.contract)}</span></h3><span class="tag ${a.tag}" style="margin-inline-start:auto">${esc(a.tag_ar)}</span></div>
      <p class="lead">${esc(a.where)}</p>
      <div class="facts"><div class="fact"><small>الإغلاق (Last)</small><b>${fmt(p.last, a.code)}</b></div><div class="fact"><small>اليوم · الأسبوع</small><b style="direction:rtl">${pcs(p.day)} · ${pcs(p.week)}</b></div><div class="fact"><small>نطاق الأسبوع</small><b>${fmt(p.week_low, a.code)} – ${fmt(p.week_high, a.code)}</b></div><div class="fact"><small>إغلاق الأسبوع السابق</small><b>${fmt(p.prev_week_close, a.code)}</b></div>
      <div class="fact"><small>التقلّب الضمني / التاريخي 30ي</small><b>${p.iv}% / ${p.hv != null ? p.hv + '%' : '—'}</b></div><div class="fact"><small>ATR (14)</small><b>${fmt(a.atr, a.code)}</b></div><div class="fact"><small>${a.code === 'SOXL' ? 'الحجم' : 'المراكز المفتوحة'}</small><b>${a.code === 'SOXL' ? fmt(p.volume, 0, 0) : fmt(p.oi, 0, 0)}</b></div><div class="fact"><small>آخر 21 جلسة</small><b>${pc(p.month)}</b></div></div>
      ${candleChart(a)}
      <div class="subh"><img src="assets/icons/levels.svg" alt=""><h3>نقاط التحكم</h3></div>
      <div class="grid g2"><div>${res}${piv}${now}${sup}</div><div class="card"><h3>المحرّكات</h3>${a.drivers.map(([s, t, d]) => `<div class="drv"><span class="s ${s === '+' ? 'p' : s === '−' ? 'm' : 'n'}">${s === '+' ? '+' : s === '−' ? '−' : '±'}</span><b>${esc(t)}</b><span class="t">${esc(d)}</span></div>`).join('')}</div></div>
      <div class="subh"><img src="assets/icons/monitor.svg" alt=""><h3>المؤشرات — القيمة ومعناها</h3></div>
      <div class="tblwrap"><table class="tbl"><thead><tr><th>المؤشر</th><th>القيمة</th><th>المعنى</th></tr></thead><tbody>${a.indicators.map(([n, v, m]) => `<tr><td>${esc(n)}</td><td class="n"><b>${esc(v)}</b></td><td>${esc(m)}</td></tr>`).join('')}</tbody></table></div>
      <div class="subh"><img src="assets/icons/scenarios.svg" alt=""><h3>السيناريوهات — ${esc(L.horizon)}</h3></div>
      <div class="ladder">${L.items.map((it) => `<div class="rung ${it.key}"><div class="nm"><img src="assets/icons/${it.key.includes('up') ? 'bull' : it.key.includes('down') ? 'bear' : 'scale'}.svg" alt="">${esc(it.name)}</div><div><div class="rg">${esc(it.range)}</div><div class="why">${esc(it.why)}</div></div><div class="w">${it.weight}%<div class="tilt">${it.tilt >= 0 ? '+' : ''}${it.tilt} عن الأساس</div></div><div class="bar"><i style="width:${it.weight * 2.5}%"></i></div></div>`).join('')}</div>
      <div class="totals"><div class="total u">إجمالي الصعود<b>${L.up_total}%</b></div><div class="total r">عرضي<b>${L.range_total}%</b></div><div class="total d">إجمالي الهبوط<b>${L.down_total}%</b></div></div>
      <details class="method"><summary>المنهجية — ترجيح تحليلي وليس احتمالاً محسوباً</summary><p>σ أسبوعية = ${fmt(p.last, a.code)} × IV ${L.iv}% × √(5/252) = <b class="num">${fmt(L.sigma, a.code, DEC[a.code] + 1)}</b>. نطاق 1σ: <span class="num">${fmt(L.one_sigma[0], a.code)} – ${fmt(L.one_sigma[1], a.code)}</span> · نطاق 2σ: <span class="num">${fmt(L.two_sigma[0], a.code)} – ${fmt(L.two_sigma[1], a.code)}</span>. الأساس الطبيعي ${L.items.map((i) => i.base).join('/')} ثم تعديل تحليلي ≤ ±8 نقاط لكل خانة وفق المحرّكات أعلاه. النتيجة مجموعها 100%.</p></details>
      <div class="subh"><img src="assets/icons/scale.svg" alt=""><h3>التوصية التنفيذية</h3></div>
      <div class="ntz"><span class="lbl">منطقة اللاتداول أولاً</span><b class="v">${fmt(a.ntz[0], a.code)} – ${fmt(a.ntz[1], a.code)}</b><span class="small">لا تنفيذ داخل هذه المنطقة — الدخول فقط عند المستويات أدناه.</span></div>
      <div class="setups">${a.setups.map(setup).join('')}</div>
      <div class="stance">الخلاصة: ${esc(a.stance)}</div>
      <div class="subh"><img src="assets/icons/chat.svg" alt=""><h3>آراء المحللين (متعددة الدول)</h3></div>
      <div class="tblwrap"><table class="tbl"><thead><tr><th>الجهة</th><th>الدولة</th><th>التاريخ</th><th>الرأي والمستويات</th></tr></thead><tbody>${a.analysts.map((x) => `<tr><td>${x.url ? `<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.source)}</a>` : esc(x.source)}</td><td>${esc(x.country)}</td><td>${esc(x.date)}</td><td>${esc(x.view)}</td></tr>`).join('')}</tbody></table></div>
      <div class="grid g2" style="margin-top:14px">
        <div class="card"><h3>المراكز (CFTC)</h3>${pos ? `<p>صافي شراء المضاربين: <b class="num">${fmt(pos.mm_net, 0, 0)}</b> (<span class="num">${pos.chg > 0 ? '+' : ''}${fmt(pos.chg, 0, 0)}</span> أسبوعياً) — ${esc(pos.trend)}.</p><p class="small muted">تجّار المقايضة: <span class="num">${fmt(pos.swap_net, 0, 0)}</span> · المنتجون: <span class="num">${fmt(pos.pm_net, 0, 0)}</span></p>` : '<p class="muted">لا يوجد تقرير CFTC لهذا الأصل (صندوق متداول).</p>'}</div>
        <div class="card"><h3>سوابق تاريخية (وصفية)</h3><p>${esc(an.label || '')} — عدد الحالات: <b>${an.n || 0}</b> · الفترة <span class="num">${esc(an.period || '')}</span>.</p>${an.n ? `<p>الأسبوع التالي: صعد في <b>${an.next_up_share}%</b> من الحالات · الوسيط <b>${pcs(an.next_median)}</b> · المدى من ${pcs(an.next_min)} إلى ${pcs(an.next_max)}.</p><p class="small muted">عيّنة صغيرة من شموع IBKR نفسها — للسياق فقط، لا تُستخدم كاحتمال.</p>` : ''}</div>
      </div>`;
  }

  function nextOpen(hhmm) {
    const m = String(hhmm).match(/(\d{1,2}):(\d{2})/); if (!m) return null;
    const now = new Date(), H = +m[1], M = +m[2];
    for (let i = 0; i < 8; i++) {
      const t = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + i, H - 4, M));
      const dubaiDow = new Date(t.getTime() + 4 * 3600e3).getUTCDay();
      if (t > now && dubaiDow >= 1 && dubaiDow <= 5) return t;
    }
    return null;
  }
  function tickSessions() {
    $$('.sess .cd').forEach((el) => {
      const at = el.dataset.at; if (/–/.test(at)) { el.textContent = ''; return; }
      const t = nextOpen(at); if (!t) return;
      const ms = t - new Date(), h = Math.floor(ms / 3600e3), mi = Math.floor(ms % 3600e3 / 60e3);
      el.textContent = 'يفتح بعد ' + (h >= 24 ? Math.floor(h / 24) + ' ي ' + (h % 24) + ' س ' : h + ' س ') + mi + ' د';
    });
  }
  setInterval(tickSessions, 30000);

  /* ------------------------------------------------------------ engine lab */
  async function renderEngine() {
    const v = $('#view-engine');
    if (!S.engine) {
      v.innerHTML = '<div class="empty">جارِ تحميل نتائج المحرك…</div>';
      try { S.engine = await getJSON('data/' + S.report.engine_ref.replace(/^data\//, '')); } catch (e) { v.innerHTML = `<div class="err">لا توجد نتائج محرك مرتبطة بهذا التقرير (${esc(e.message)}).</div>`; return; }
    }
    const E = S.engine, assets = Object.keys(E.assets);
    if (!assets.includes(S.engAsset)) S.engAsset = assets[0];
    const A = E.assets[S.engAsset];
    const tfs = Object.keys(A.timeframes);
    if (!A.rules[S.engTf]) S.engTf = Object.keys(A.rules)[0] || tfs[0];
    const pctv = (x) => x == null ? '—' : (100 * x).toFixed(1) + '%';
    const OBS_AR = { close: 'الإغلاق', ema_12: 'EMA 12', ema_26: 'EMA 26', sma_50: 'SMA 50', sma_200: 'SMA 200', rsi_14: 'RSI 14', adx_14: 'ADX 14', plus_di_14: '+DI', minus_di_14: '−DI', atr_14: 'ATR 14', support_20: 'دعم 20', resistance_20: 'مقاومة 20', zscore_20: 'Z-Score 20' };
    const hitbar = (b) => b && b.hit != null ? `<div class="hitbar" title="فاصل ثقة ويلسون ${pctv(b.lo)} – ${pctv(b.hi)}"><i style="left:${100 * b.lo}%;width:${100 * (b.hi - b.lo)}%"></i><em style="left:calc(${100 * b.hit}% - 1px)"></em></div>` : '';
    const R = A.rules[S.engTf] || { rules: [], walk_forward: { folds: [] } };
    v.innerHTML = `<section class="sec">${secH('levels', 'مختبر المحرك — CME Engine v0.3', 'كل مخرجات المحرك كما هي: الحالات، المؤشرات، اختبارات القواعد، التحقق المتدرج، المناطق والسيناريوهات', 'f-gold')}<div class="sec-b">
      <div class="banner"><b>نتائج بحثية غير معايرة — تُعرض كاملة بطلبك.</b> حالة التشغيل: <span class="num">${esc(E.run_status)}</span> · الاحتمالات محجوبة داخل المحرك (<span class="num">probabilities_withheld=${E.probabilities_withheld}</span>) لأن القواعد لم تنجح بعد في اختبار خارج العيّنة. "نسبة الإصابة" أدناه هي تكرار تاريخي وليست احتمالاً مستقبلياً. الخط الأحمر المتقطع = 50% (عشوائي).</div>
      <p class="small muted">آخر تشغيل: <span class="num">${esc(E.generated_at_utc)}</span> UTC · بصمة المدخلات <span class="num">${esc(E.input_fingerprint.slice(0, 12))}</span> · نسخة القواعد ${esc(E.ruleset_version)}</p>
      <div class="asset-tabs">${assets.map((a) => plaque(a, 'محرك', a === S.engAsset)).join('')}</div>
      <div class="grid g3">${tfs.map((tf) => { const t = A.timeframes[tf]; return `<div class="card state"><span class="pill">${esc(t.tf_ar)}</span><span class="st">${esc(t.state_ar)}</span><span class="small muted">${esc(t.volatility_ar || '')}</span><span class="small">حتى: <span class="num">${esc((t.data_cutoff_utc || '').replace('+00:00', 'Z'))}</span> · الجودة: ${esc(t.quality)}</span>${Object.keys(t.observations || {}).length ? `<div class="obs">${Object.entries(t.observations).map(([k, val]) => `<span>${esc(OBS_AR[k] || k)} <b>${val == null ? '—' : Number(val).toLocaleString('en-US', { maximumFractionDigits: 3 })}</b></span>`).join('')}</div>` : `<div class="small muted">${esc((t.live_blocking || []).join(' · '))}</div>`}</div>`; }).join('')}</div>
      ${A.consensus ? `<div class="card" style="margin-top:12px"><h3>توافق الأطر الزمنية: ${esc(A.consensus.ar)}</h3><div class="chips">${Object.entries(A.consensus.dirs).map(([k, d]) => `<span class="pill">${esc(A.timeframes[k] ? A.timeframes[k].tf_ar : k)}: ${esc(d.ar)}</span>`).join(' ')}</div><p class="small muted">الإجراء التشغيلي: ${esc((A.action || {}).action)} — ${esc((A.action || {}).reason)}</p></div>` : ''}
      <div class="subh"><img src="assets/icons/monitor.svg" alt=""><h3>اختبار القواعد المرشّحة</h3><span class="seg" style="margin-inline-start:auto">${Object.keys(A.rules).map((tf) => `<button data-tf="${tf}" class="${tf === S.engTf ? 'on' : ''}">${esc(A.timeframes[tf] ? A.timeframes[tf].tf_ar : tf)}</button>`).join('')}</span></div>
      <div class="tblwrap"><table class="tbl"><thead><tr><th>القاعدة</th><th>الأفق (شموع)</th><th>التطوير: إشارات · إصابة</th><th>الاختبار: إشارات · إصابة</th><th>فاصل الثقة</th><th>متوسط العائد (اختبار)</th><th>الحكم</th></tr></thead><tbody>${R.rules.map((x) => `<tr><td>${esc(x.rule_ar)}</td><td class="n">${x.horizon}</td><td class="n">${x.dev ? x.dev.signals : '—'} · ${pctv(x.dev && x.dev.hit)}</td><td class="n">${x.holdout ? x.holdout.signals : '—'} · <b>${pctv(x.holdout && x.holdout.hit)}</b></td><td>${hitbar(x.holdout)}</td><td class="n">${x.holdout && x.holdout.avg_ret != null ? (100 * x.holdout.avg_ret).toFixed(3) + '%' : '—'}</td><td>${esc(x.holdout ? x.holdout.edge_ar : '')}</td></tr>`).join('')}</tbody></table></div>
      <p class="small muted">القواعد الناجية للمعايرة: ${R.survivors && R.survivors.length ? esc(R.survivors.join('، ')) : 'لا توجد'} · عوائق المعايرة: ${esc((R.walk_forward.blockers || []).join(' · '))}</p>
      <div class="subh"><img src="assets/icons/clock.svg" alt=""><h3>التحقق المتدرج (Walk-Forward) — القاعدة المشروطة بالنظام</h3></div>
      <div class="tblwrap"><table class="tbl"><thead><tr><th>الأفق</th><th>الطيّة</th><th>فترة الاختبار</th><th>إشارات</th><th>إصابة</th><th>فاصل الثقة</th><th>متوسط العائد</th><th>الحكم</th></tr></thead><tbody>${(R.walk_forward.folds || []).map((f) => `<tr><td class="n">${f.horizon}</td><td class="n">${f.fold}</td><td class="n">${esc(f.test_start)} → ${esc(f.test_end)}</td><td class="n">${f.signals}</td><td class="n"><b>${pctv(f.hit)}</b></td><td>${hitbar(f)}</td><td class="n">${f.avg_ret != null ? (100 * f.avg_ret).toFixed(3) + '%' : '—'}</td><td>${esc(f.edge_ar)}</td></tr>`).join('')}</tbody></table></div>
      <div class="grid g2" style="margin-top:14px">
        <div class="card"><h3>مناطق المستويات (${esc(A.timeframes[S.engTf] ? A.timeframes[S.engTf].tf_ar : S.engTf)})</h3><table class="tbl"><thead><tr><th>المنطقة</th><th>المركز</th><th>الأدلة</th></tr></thead><tbody>${(A.zones[S.engTf] || []).map((z) => `<tr><td class="n">${fmt(z.low, S.engAsset)} – ${fmt(z.high, S.engAsset)}</td><td class="n"><b>${fmt(z.centre, S.engAsset)}</b></td><td class="small">${esc(z.evidence.join(', '))}</td></tr>`).join('') || '<tr><td colspan="3" class="muted">لا توجد</td></tr>'}</tbody></table></div>
        <div class="card"><h3>سيناريوهات المحرك (شرطية)</h3>${(A.scenarios[S.engTf] || []).map((s) => `<p><span class="pill">${esc(s.scenario.includes('upward') ? 'اختراق صاعد' : s.scenario.includes('downward') ? 'كسر هابط' : s.scenario)}</span> الشرط: <span class="num">${esc(s.trigger.condition)} @ ${fmt(s.trigger.level, S.engAsset)}</span> · الإلغاء: <span class="num">${esc(s.invalidation.condition)}</span> · الاحتمال: ${s.probability == null ? 'محجوب' : s.probability}</p>`).join('') || '<p class="muted">لا توجد</p>'}</div>
      </div>
      <div class="card" style="margin-top:14px"><h3>نمط الساعات (UTC) — متوسط العائد لكل ساعة</h3>${hourBars((A.time_profiles[S.engTf === 'daily' ? 'hourly' : S.engTf] || {}).by_hour || [])}</div>
      <div class="subh"><img src="assets/icons/shield.svg" alt=""><h3>جودة البيانات وتغطيتها</h3></div>
      <div class="tblwrap"><table class="tbl"><thead><tr><th>مجموعة البيانات</th><th>القرار</th><th>العوائق</th><th>التحذيرات</th></tr></thead><tbody>${E.coverage.map((c) => `<tr><td class="n">${esc(c.dataset)}</td><td>${esc(c.decision)}</td><td class="small">${esc(c.blocking.join(', ') || '—')}</td><td class="small">${esc(c.warnings.join(', '))}</td></tr>`).join('')}</tbody></table></div>
      <p class="small muted">طبقة الأحداث: ${esc(E.layers.event)} · طبقة التنفيذ: ${esc(E.layers.execution)} · سجل الإشارات: ${E.journal ? (E.journal.valid ? 'سليم' : 'غير سليم') + ' (' + E.journal.record_count + ' سجل)' : '—'} · نتائج بانتظار التقييم: ${esc((E.outcome_scoring || {}).pending)}</p>
    </div></section>`;
    $$('#view-engine .plaque[data-asset]').forEach((el) => el.addEventListener('click', () => { S.engAsset = el.dataset.asset; renderEngine(); }));
    $$('#view-engine .seg button').forEach((b) => b.addEventListener('click', () => { S.engTf = b.dataset.tf; renderEngine(); }));
  }
  function hourBars(rows) {
    if (!rows.length) return '<p class="muted">غير متاح</p>';
    const mx = Math.max(...rows.map((r) => Math.abs(r.mean))) || 1, W = 720, H = 120, bw = W / 24;
    let s = `<svg viewBox="0 0 ${W} ${H + 18}" style="width:100%;height:auto"><line x1="0" x2="${W}" y1="${H / 2}" y2="${H / 2}" stroke="#000" stroke-opacity=".2"/>`;
    rows.forEach((r) => { const h = Math.abs(r.mean) / mx * (H / 2 - 4), x = r.h * bw + 3; s += `<rect x="${x}" y="${r.mean >= 0 ? H / 2 - h : H / 2}" width="${bw - 6}" height="${h}" fill="${r.mean >= 0 ? '#2d7a57' : '#a64a5b'}" rx="2"><title>${r.h}:00 UTC · n=${r.n} · ${(100 * r.mean).toFixed(4)}%</title></rect><text x="${x + (bw - 6) / 2}" y="${H + 14}" font-size="9" text-anchor="middle" fill="#676961">${r.h}</text>`; });
    return s + '</svg><p class="small muted">وصفي فقط — ليس توقعاً. مرّر المؤشر فوق العمود لرؤية العيّنة.</p>';
  }

  /* ------------------------------------------------------------ alerts */
  function renderAlerts() {
    const v = $('#view-alerts'), al = S.alerts || { tasks: [], events: [] }, lv = S.live;
    v.innerHTML = `<section class="sec">${secH('clock', 'المراقبة الحيّة', lv ? 'آخر فحص: ' + esc(lv.checked_label || lv.checked_utc) : 'لم يبدأ أول فحص بعد', 'f-green')}<div class="sec-b">${lv ? `<div class="grid g5">${(lv.assets || []).map((x) => `<div class="pcard">${plaque(x.code, x.status_ar || '')}<div class="px">${fmt(x.last, x.code)}</div><div class="chips">${chip(x.chg_pct, 'منذ الإغلاق')}</div><div class="small muted">العتبة ±${x.threshold}% · ${esc(x.ts_label || '')}</div>${x.breach ? '<span class="tag bearish">تجاوز العتبة — صدر تنبيه</span>' : ''}</div>`).join('')}</div><p class="small muted">${esc(lv.note || '')}</p>` : '<p class="muted">ستظهر هنا قراءة كل ساعة (10:00–02:00 دبي، أيام التداول).</p>'}</div></section>
      <section class="sec">${secH('news', 'التنبيهات المجدولة للأحداث', 'قبل الحدث بـ30 دقيقة (T-30) وبعد صدوره مباشرة (T+1)', 'f-plum')}<div class="sec-b"><div class="tblwrap"><table class="tbl"><thead><tr><th>الحدث</th><th>التوقيت (دبي)</th><th>T-30</th><th>T+1</th><th>الأصول</th><th>الحالة</th></tr></thead><tbody>${(al.events || []).map((e) => `<tr><td><b>${esc(e.event)}</b></td><td>${esc(e.when)}</td><td class="n">${esc(e.t30 || '—')}</td><td class="n">${esc(e.t1 || '—')}</td><td>${esc(e.assets)}</td><td>${esc(e.status || 'مجدول')}</td></tr>`).join('')}</tbody></table></div></div></section>
      <section class="sec">${secH('monitor', 'جدول التقارير الآلية', 'المهام المجدولة في السحابة — تعمل والجهاز مغلق', 'f-teal')}<div class="sec-b"><div class="tblwrap"><table class="tbl"><thead><tr><th>المهمة</th><th>الموعد (دبي)</th><th>المحتوى</th></tr></thead><tbody>${(al.tasks || []).map((t) => `<tr><td><b>${esc(t.name)}</b></td><td>${esc(t.when)}</td><td>${esc(t.what)}</td></tr>`).join('')}</tbody></table></div></div></section>`;
  }

  /* ------------------------------------------------------------ archive */
  function renderArchive() {
    const v = $('#view-archive');
    v.innerHTML = `<section class="sec">${secH('news', 'أرشيف التقارير', (S.index.reports || []).length + ' تقرير', 'f-brown')}<div class="sec-b">${(S.index.reports || []).map((r) => `<div class="arch" data-id="${esc(r.id)}"><span class="d">${esc(r.date)}</span><span class="pill">${esc(r.type_ar)}</span><div><b>${esc(r.title)}</b><div class="small muted">${esc(r.headline || '')}</div></div></div>`).join('') || '<div class="empty">لا توجد تقارير بعد</div>'}</div></section>`;
    $$('#view-archive .arch').forEach((el) => el.addEventListener('click', () => go('report', el.dataset.id)));
  }

  /* ------------------------------------------------------------ listen (browser Arabic voice) */
  let speaking = false, chapIdx = 0;
  function voices() { return (window.speechSynthesis ? speechSynthesis.getVoices() : []).filter((v) => /^ar/i.test(v.lang)); }
  function renderListen() {
    const v = $('#view-listen'), ch = S.report.voice || [];
    const ok = 'speechSynthesis' in window;
    v.innerHTML = `<section class="sec">${secH('chat', 'استمع للتقرير', 'قراءة بصوت عربي من جهازك — ملف صوتي MP3 احترافي (Piper) ضمن المرحلة القادمة', 'f-burg')}<div class="sec-b">
      ${ok ? '' : '<div class="err">المتصفح لا يدعم القراءة الصوتية.</div>'}
      <div class="player"><button class="btn" id="vPlay">▶ تشغيل</button><button class="btn light" id="vPause">⏸ إيقاف مؤقت</button><button class="btn light" id="vStop">■ إيقاف</button>
      <label style="margin:0">السرعة <input type="range" id="vRate" min="0.7" max="1.3" step="0.05" value="0.95"></label>
      <select id="vVoice" style="max-width:260px"></select></div>
      <p class="small muted" id="vNote"></p>
      <div style="margin-top:12px">${ch.map((c, i) => `<div class="chap" data-i="${i}"><span class="no">${i + 1}</span><div><b>${esc(c.title)}</b><div class="small muted">${esc(c.text.slice(0, 110))}…</div></div></div>`).join('')}</div></div></section>`;
    const fill = () => { const vs = voices(); $('#vVoice').innerHTML = vs.map((x, i) => `<option value="${i}">${esc(x.name)} (${esc(x.lang)})</option>`).join('') || '<option>لا يوجد صوت عربي — سيُستخدم الافتراضي</option>'; $('#vNote').textContent = vs.length ? '' : 'لم يُعثر على صوت عربي في هذا الجهاز؛ على آيفون/ماك: الإعدادات ← تسهيلات الاستخدام ← المحتوى المنطوق ← الأصوات ← العربية.'; };
    if (ok) { fill(); speechSynthesis.onvoiceschanged = fill; }
    $('#vPlay').onclick = () => { if (!ok) return; if (speechSynthesis.paused) { speechSynthesis.resume(); return; } speaking = true; speakFrom(chapIdx); };
    $('#vPause').onclick = () => ok && speechSynthesis.pause();
    $('#vStop').onclick = () => { speaking = false; ok && speechSynthesis.cancel(); chapIdx = 0; mark(-1); };
    $$('#view-listen .chap').forEach((el) => el.addEventListener('click', () => { if (!ok) return; speaking = true; speechSynthesis.cancel(); speakFrom(+el.dataset.i); }));
  }
  function mark(i) { $$('#view-listen .chap').forEach((el) => el.classList.toggle('on', +el.dataset.i === i)); }
  function speakFrom(i) {
    const ch = S.report.voice || []; if (i >= ch.length || !speaking) { speaking = false; mark(-1); chapIdx = 0; return; }
    chapIdx = i; mark(i);
    const u = new SpeechSynthesisUtterance(ch[i].title + '. ' + ch[i].text); u.lang = 'ar-SA'; u.rate = +($('#vRate') || { value: 0.95 }).value;
    const vs = voices(), sel = $('#vVoice'); if (vs.length && sel) u.voice = vs[+sel.value] || vs[0];
    u.onend = () => { if (speaking) speakFrom(i + 1); };
    speechSynthesis.speak(u);
  }

  /* ------------------------------------------------------------ generate on demand */
  function renderGenerate() {
    const v = $('#view-generate'), c = S.config || {};
    const types = [
      ['snapshot', 'لقطة سريعة', 'إحنا فين + المستويات + السيناريوهات المختصرة (~10 دقائق)'],
      ['full', 'تقرير كامل', 'كل الأقسام 0–14 مثل التقرير الأسبوعي (~25 دقيقة)'],
      ['asset', 'أصل واحد بالتفصيل', 'تحليل عميق لأصل واحد تختاره'],
      ['event', 'تقرير حدث', 'قبل/بعد حدث محدد (بيان، قرار، نتائج شركة)'],
    ];
    v.innerHTML = `<section class="sec">${secH('monitor', 'اطلب تقرير الآن', 'التطبيق ليس للمهام المجدولة فقط — أصدر تقريراً في أي لحظة', 'f-burg')}<div class="sec-b">
      <div class="opts" id="gTypes">${types.map(([k, t, d], i) => `<div class="opt${i === 0 ? ' on' : ''}" data-k="${k}"><b>${t}</b><small>${d}</small></div>`).join('')}</div>
      <label for="gAsset">الأصول</label><select id="gAsset"><option value="ALL">كل الأصول (ذهب، فضة، نحاس، نفط، SOXL)</option><option>GC</option><option>SI</option><option>HG</option><option>CL</option><option>SOXL</option></select>
      <label for="gNote">ملاحظة أو حدث محدد (اختياري)</label><input type="text" id="gNote" placeholder="مثال: بعد قرار الفيدرالي / التركيز على النفط وهرمز">
      <div class="player" style="margin-top:16px">
        <button class="btn alt" id="gNow">⚡ تشغيل فوري عبر Claude</button>
        <button class="btn" id="gQueue">⏱ إضافة للطابور (GitHub)</button>
        <button class="btn light" id="gCopy">نسخ نص الطلب</button>
      </div>
      <div class="card" style="margin-top:14px"><h3>كيف يعمل</h3><ol>
        <li><b>تشغيل فوري:</b> يُنسخ نص الطلب وتُفتح صفحة المهمة "SoloSophy — تقرير عند الطلب" في Claude. اضغط <b>Run now</b> والصق النص في خانة النص — يصدر التقرير ويظهر هنا تلقائياً خلال ~10–25 دقيقة.</li>
        <li><b>الطابور:</b> يفتح طلباً جاهزاً على GitHub (يحتاج تسجيل دخول GitHub مرة واحدة). مهمة المراقبة كل ساعة تلتقطه وتنفّذه في أول دورة (10:00–02:00 دبي أيام التداول).</li>
        <li>كل تقرير يُحفظ في الأرشيف ويُبنى بنفس الدستور والمصادر (IBKR + مصدران للخبر).</li></ol>
        <p class="small muted">${c.ondemand_name ? 'اسم المهمة: ' + esc(c.ondemand_name) : ''}</p></div>
    </div></section>`;
    let kind = 'snapshot';
    $$('#gTypes .opt').forEach((o) => o.addEventListener('click', () => { $$('#gTypes .opt').forEach((x) => x.classList.remove('on')); o.classList.add('on'); kind = o.dataset.k; }));
    const text = () => `SOLOSOPHY_REQUEST type=${kind} assets=${$('#gAsset').value} requested_at=${new Date().toISOString()}${$('#gNote').value ? ' note=' + $('#gNote').value.replace(/\s+/g, ' ') : ''}`;
    const copy = async () => { try { await navigator.clipboard.writeText(text()); toast('تم نسخ نص الطلب'); } catch (e) { prompt('انسخ النص:', text()); } };
    $('#gCopy').onclick = copy;
    $('#gNow').onclick = async () => { await copy(); window.open(c.ondemand_url || 'https://claude.ai/code/routines', '_blank', 'noopener'); };
    $('#gQueue').onclick = () => {
      const repo = c.repo || 'SoloGhub/SoloSophy-';
      const u = `https://github.com/${repo}/issues/new?labels=report-request&title=${encodeURIComponent('طلب تقرير: ' + kind + ' — ' + $('#gAsset').value)}&body=${encodeURIComponent(text() + '\n\n(أُنشئ من تطبيق SoloSophy — ستلتقطه مهمة المراقبة التالية)')}`;
      window.open(u, '_blank', 'noopener');
    };
  }

  boot();
})();
