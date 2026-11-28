// Caṅkam anthologies: shared facts about the tiṇais, and the list, poem and tiṇai pages.
(function () {
  const AKAM = [
    { id: 'kuṟiñci', ta: 'குறிஞ்சி', en: 'Kuṟiñci', land: 'Mountains', mood: 'Union', moodTa: 'புணர்தல்', time: 'Midnight',
      season: 'The cool season and early dew', god: 'Cēyōṉ (Murukaṉ)', flower: 'The kuṟiñci flower', color: 'var(--kurinci)', soft: '#E6E3F5' },
    { id: 'mullai', ta: 'முல்லை', en: 'Mullai', land: 'Forest and pasture', mood: 'Patient waiting', moodTa: 'இருத்தல்', time: 'Evening',
      season: 'The rainy season', god: 'Māyōṉ', flower: 'Jasmine (mullai)', color: 'var(--mullai)', soft: '#DDEFE0' },
    { id: 'marutam', ta: 'மருதம்', en: 'Marutam', land: 'Farmland', mood: 'Lovers’ quarrel', moodTa: 'ஊடல்', time: 'Dawn',
      season: 'All seasons', god: 'Vēntaṉ', flower: 'The marutam tree', color: 'var(--marutam)', soft: '#F4E8CF' },
    { id: 'neytal', ta: 'நெய்தல்', en: 'Neytal', land: 'Seashore', mood: 'Pining', moodTa: 'இரங்கல்', time: 'Sunset',
      season: 'All seasons', god: 'Varuṇaṉ', flower: 'The water lily (neytal)', color: 'var(--neytal)', soft: '#DCEAF4' },
    { id: 'pālai', ta: 'பாலை', en: 'Pālai', land: 'Parched land', mood: 'Separation', moodTa: 'பிரிதல்', time: 'Midday',
      season: 'Summer and the late dew', god: 'Koṟṟavai', flower: 'The pālai tree', color: 'var(--palai)', soft: '#F6DAD5' },
  ];
  const TEXTS = {
    kuruntokai: { title: 'Kuṟuntokai', ta: 'குறுந்தொகை', kind: 'akam',
      about: 'Short poems of love, four to eight lines each. Every poem is set in one of five landscapes, its tiṇai, and the colophon says who is speaking.' },
    purananuru: { title: 'Puṟanāṉūṟu', ta: 'புறநானூறு', kind: 'puram',
      about: 'Four hundred poems of the outer world: kings and patrons, war and its cost, giving, grief and conduct. The colophon gives each poem its tiṇai and its theme (tuṟai).' },
  };
  const tinai = (id) => AKAM.find((t) => t.id === id);
  // Credit as Project Madurai asks; the full header pages are on /sources.
  const CREDIT = {
    kuruntokai: 'Tamil text: Project Madurai etext of Kuṟuntokai (pm0110). Etext preparation: Dr. K. Kalyanasundaram, Lausanne, Switzerland. Proofreading: Ms. Sarala Sandirasegarane, Kanpur, India. © Project Madurai.',
    purananuru: 'Tamil text: Project Madurai etext of Puṟanāṉūṟu (pm0057). Etext preparation: staff and students of K.A.P. Viswanatham Higher Secondary School, Tiruchirappalli. Web version: Dr. K. Kalyanasundaram. © Project Madurai.',
  };
  const credit = (slug, p) => (p && p.source)
    ? '<p class="pm-credit">' + Th.esc(p.source.note) + ' <a href="/sources#' + p.source.code + '">Full credits</a></p>'
    : '<p class="pm-credit">' + CREDIT[slug] + ' <a href="/sources#' + (slug === 'kuruntokai' ? 'pm0110' : 'pm0057') + '">Full credits</a></p>';
  const esc = (s) => Th.esc(s == null ? '' : String(s));

  function chip(id, taName) {
    const t = tinai(id);
    if (t) return '<span class="tchip" style="background:' + t.soft + ';color:' + t.color + '">' + t.en + '</span>';
    return id ? '<span class="tchip">' + esc(id[0].toUpperCase() + id.slice(1)) + '</span>' : '<span class="muted small">not given</span>';
  }

  // ---- list page: /anthology?t=kuruntokai
  async function list() {
    const q = new URLSearchParams(location.search), slug = TEXTS[q.get('t')] ? q.get('t') : 'kuruntokai', T = TEXTS[slug];
    document.title = T.title + ' · Thamizh.ai';
    Th.meta(T.title + ': all its poems with tiṇai, poet and speaker, translations and recitation.');
    Th.crumbs('<a href="/library">Library</a> › <strong>' + T.title + '</strong>');
    const head = document.getElementById('head');
    head.innerHTML = '<div style="flex:1 1 480px"><h1 lang="ta" style="font-size:clamp(34px,5vw,48px)">' + T.ta + '</h1>' +
      '<p style="font-size:20px;font-weight:600;margin-top:4px">' + T.title + '</p><p class="lead" style="margin-top:10px">' + T.about + '</p></div>' +
      (T.kind === 'akam' ? '<a class="btn ghost" href="/tinai">What is a tiṇai?</a>' : '') + '<div style="flex:1 1 100%">' + credit(slug) + '</div>';
    const idx = await Th.json('/data/' + slug + '/index.json');
    let cur = q.get('tinai') || 'all';
    const counts = {};
    idx.poems.forEach((p) => { counts[p.tinai || ''] = (counts[p.tinai || ''] || 0) + 1; });
    const ids = T.kind === 'akam' ? AKAM.map((t) => t.id)
      : Object.keys(counts).filter((k) => k && counts[k] >= 3).sort((a, b) => counts[b] - counts[a]);
    const filters = document.getElementById('filters');
    const label = (id) => (tinai(id) ? '<span lang="ta">' + tinai(id).ta + '</span> ' + tinai(id).en : esc(id[0].toUpperCase() + id.slice(1)));
    const draw = () => {
      filters.innerHTML = ['all'].concat(ids).map((id) => '<button type="button" class="filter" data-id="' + esc(id) + '" aria-pressed="' + (id === cur) + '"' +
        (tinai(id) ? ' style="--c:' + tinai(id).color + '"' : '') + '>' + (id === 'all' ? 'All ' + idx.count : label(id) + ' <span class="muted">' + counts[id] + '</span>') + '</button>').join('');
      const rows = idx.poems.filter((p) => cur === 'all' || p.tinai === cur);
      document.getElementById('rows').innerHTML =
        '<div class="prow hd" aria-hidden="true"><span>Poem</span><span>First line</span><span>Poet</span><span>Tiṇai</span><span>' + (T.kind === 'akam' ? 'Speaker' : 'Theme (tuṟai)') + '</span></div>' +
        rows.map((p) => '<a class="prow" href="/poem?t=' + slug + '&n=' + p.n + '"><span class="num">' + p.n + '</span><span lang="ta" class="first">' + esc(p.first) + '</span>' +
          '<span class="muted">' + esc(p.poet) + '</span><span>' + chip(p.tinai) + '</span><span class="muted">' + esc(T.kind === 'akam' ? p.speaker : p.turai) + '</span></a>').join('');
    };
    filters.addEventListener('click', (e) => {
      const b = e.target.closest('button[data-id]');
      if (!b) return;
      cur = b.dataset.id;
      const u = new URL(location.href);
      if (cur === 'all') u.searchParams.delete('tinai'); else u.searchParams.set('tinai', cur);
      history.replaceState(null, '', u);
      draw();
    });
    draw();
  }

  // ---- poem page: /poem?t=kuruntokai&n=3
  async function poem() {
    const q = new URLSearchParams(location.search), slug = TEXTS[q.get('t')] ? q.get('t') : 'kuruntokai', T = TEXTS[slug];
    const n = parseInt(q.get('n') || '1', 10);
    Th.crumbs('<a href="/library">Library</a> › <a href="/anthology?t=' + slug + '">' + T.title + '</a> › <strong>' + n + '</strong>');
    document.title = T.title + ' ' + n + ' · Thamizh.ai';
    let p;
    try { p = await Th.json('/data/' + slug + '/' + n + '.json'); } catch (e) {
      document.getElementById('poem').innerHTML = '<p class="pending">There is no poem ' + n + ' in ' + T.title + ' here.</p>'; return;
    }
    const idx = await Th.json('/data/' + slug + '/index.json');
    const pos = idx.poems.findIndex((x) => x.n === n);
    const prev = idx.poems[pos - 1], next = idx.poems[pos + 1];
    const c = p.colophon, ai = p.ai || {};
    Th.meta(T.title + ' ' + n + (c.poet_tr ? ', by ' + c.poet_tr : '') + ': ' + p.lines.slice(0, 2).join(' ') + ' … Word by word, with translation and recitation.');
    document.getElementById('poem').innerHTML =
      '<section class="layer dark"><div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center">' +
      '<p class="eyebrow">' + T.title + ' ' + n + (c.poet_tr ? ' · ' + esc(c.poet_tr) : '') + '</p>' +
      '<div class="pager">' + (prev ? '<a href="/poem?t=' + slug + '&n=' + prev.n + '" aria-label="Previous poem, ' + prev.n + '">‹</a>' : '') +
      (next ? '<a href="/poem?t=' + slug + '&n=' + next.n + '" aria-label="Next poem, ' + next.n + '">›</a>' : '') + '</div></div>' +
      '<div lang="ta" id="recited" style="font-family:var(--ta);font-size:clamp(20px,2.4vw,25px);line-height:1.75;font-weight:600">' + (window.ThListen ? ThListen.wrap(p.lines) : p.lines.map(esc).join('<br>')) + '</div>' +
      (p.timing ? '<div id="listen"></div>' : '') +
      (p.sync ? '<div class="nowword" id="nowword" aria-live="off"><span class="muted">Press play: each word\'s meaning shows here as it is read.</span></div>' : '') +
      '<p style="color:#BDBDB8;font-style:italic;font-size:15px">' + p.tr.map(esc).join('<br>') + '</p>' +
      (ai.translation ? '<p class="meaning" style="font-size:20px;font-weight:500">' + esc(ai.translation) + '</p><p class="small" style="color:var(--gold)">AI translation</p>'
        : '<p class="pending">The AI translation is being prepared.</p>') + '</section>' +
      '<div role="tablist" class="tabs" aria-label="More on this poem">' +
      ['Words', 'Meter · āciriyappā', 'In today\'s Tamil', 'Explanation'].map((l, i) => '<button type="button" role="tab" id="tab' + i + '" aria-controls="pane' + i + '" aria-selected="' + (i === 0) + '">' + l + '</button>').join('') + '</div>' +
      '<div class="layer">' + [words(p), meter(p), modern(p), explain(p)].map((h, i) => '<div role="tabpanel" id="pane' + i + '" aria-labelledby="tab' + i + '"' + (i ? ' hidden' : '') + '>' + h + '</div>').join('') + '</div>';
    document.querySelector('.tabs').addEventListener('click', (e) => {
      const b = e.target.closest('[role=tab]');
      if (!b) return;
      document.querySelectorAll('.tabs [role=tab]').forEach((x) => x.setAttribute('aria-selected', String(x === b)));
      document.querySelectorAll('[role=tabpanel]').forEach((x) => { x.hidden = x.id !== b.getAttribute('aria-controls'); });
    });
    document.getElementById('side').innerHTML = side(slug, T, p);
    if (p.timing && window.ThListen) {
      const box = document.getElementById('recited');
      const now = document.getElementById('nowword');
      let last = -2;
      ThListen.bar(document.getElementById('listen'), n, (t) => {
        const cur = ThListen.paint(box, p.timing, t);
        if (!now || cur === last) return;
        last = cur;
        const g = cur >= 0 && p.sync ? p.sync[cur] : null;
        if (g && g.length) now.innerHTML = g.map((x) => '<span class="nw"><b lang="ta">' + esc(x[0]) + '</b> ' + esc(x[1] || '') + '</span>').join('');
      }, '/audio/' + slug + '/');
    }
  }

  function words(p) {
    const ai = p.ai;
    if (!ai || !ai.lines) return '<p class="pending">Word splits and glosses are being prepared.</p>';
    return ai.lines.map((ln, i) => '<div style="margin-bottom:14px"><p class="small muted" style="font-weight:600;margin-bottom:6px">Line ' + (i + 1) +
      (ln.as_printed ? ' · kept as printed; the word separation did not check out' : '') + '</p><div class="words">' +
      ln.words.map((w) => '<div class="word"><span class="ta" lang="ta">' + esc(w.surface) + '</span>' +
        (w.parts && w.parts.length > 1 ? '<span class="small muted" lang="ta" style="font-family:var(--ta-ui)">' + w.parts.map((x) => esc(x.text)).join(' + ') + '</span>' : '') +
        '<span>' + (w.gloss ? esc(w.gloss) : '<span class="muted">—</span>') + '</span></div>').join('') + '</div></div>').join('') +
      '<p class="small muted">Words separated and glossed by AI (' + esc(ai.model) + '). A split is shown only where its parts join back to the word by the joining rules.</p>';
  }

  function meter(p) {
    const s = p.scan;
    return '<p style="font-size:18px;font-weight:700">' + esc(s.meter[0].toUpperCase() + s.meter.slice(1)) + '</p>' +
      '<ul class="checks">' + s.checks.map((c) => '<li><span aria-hidden="true">' + (c.ok ? '✓' : '·') + '</span> <b>' + esc(c.name) + ':</b> ' + esc(c.detail) + '</li>').join('') + '</ul>' +
      '<div style="display:flex;flex-direction:column;gap:8px;margin-top:10px">' + s.lines.map((ln, i) => '<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:baseline"><span class="small muted" style="width:52px">Line ' + (i + 1) + '</span>' +
        ln.map((f) => '<span class="foot"><span lang="ta">' + esc(f.text) + '</span><span class="small muted">' + esc(f.foot) + '</span></span>').join('') + '</div>').join('') + '</div>' +
      (p.text === 'purananuru' ? '<p class="small muted" style="margin-top:12px">This text is printed word by word, so the division into feet is the scanner\'s best fit.</p>' : '');
  }

  const modern = (p) => (p.ai && p.ai.modern ? '<p lang="ta" style="font-family:var(--ta-ui);font-size:19px;line-height:1.7">' + esc(p.ai.modern) + '</p><p class="small muted">AI rendering in today\'s Tamil</p>'
    : '<p class="pending">Being prepared.</p>') + (p.ai && p.ai.literal ? '<p class="small muted" style="font-weight:600;margin-top:16px">Word for word</p><p>' + esc(p.ai.literal) + '</p>' : '');
  const explain = (p) => (p.ai && p.ai.explanation ? '<p style="font-size:17px;line-height:1.7">' + esc(p.ai.explanation) + '</p><p class="small muted">AI explanation</p>' : '<p class="pending">Being prepared.</p>');

  function side(slug, T, p) {
    const c = p.colophon, t = tinai(c.tinai);
    const rows = [];
    if (c.speaker_ta) rows.push(['Who speaks', (c.speaker_en ? esc(c.speaker_en[0].toUpperCase() + c.speaker_en.slice(1)) + '<br>' : '') + '<span lang="ta" class="small">' + esc(c.speaker_ta) + '</span>']);
    if (c.turai_ta) rows.push(['Theme (tuṟai)', '<span lang="ta">' + esc(c.turai_ta) + '</span>']);
    if (c.addressed_ta) rows.push(['Addressed to', '<span lang="ta">' + esc(c.addressed_ta) + '</span>']);
    if (c.poet_ta) rows.push(['Poet', esc(c.poet_tr) + '<br><span lang="ta" class="small">' + esc(c.poet_ta) + '</span>']);
    return '<section class="card tinai-card"' + (t ? ' style="border-top:6px solid ' + t.color + '"' : '') + '>' +
      '<p class="eyebrow">Tiṇai</p><p lang="ta" style="font-size:28px;font-weight:700;' + (t ? 'color:' + t.color : '') + '">' + esc(c.tinai_ta || '—') + '</p>' +
      '<p class="muted">' + (t ? t.en + ' · ' + t.land.toLowerCase() + ' · ' + t.mood.toLowerCase() : esc(c.tinai ? c.tinai[0].toUpperCase() + c.tinai.slice(1) : 'Not given in the colophon')) + '</p>' +
      '<dl class="facts">' + rows.map(([k, v]) => '<div><dt>' + k + '</dt><dd>' + v + '</dd></div>').join('') + '</dl>' +
      '<p class="small muted">From the anthology\'s colophon.</p>' + credit(slug, p) +
      '<div style="display:flex;flex-direction:column;gap:6px;margin-top:6px">' +
      (t ? '<a href="/tinai?t=' + encodeURIComponent(t.id) + '">About ' + t.en + ' →</a>' : '') +
      (c.tinai ? '<a href="/anthology?t=' + slug + '&tinai=' + encodeURIComponent(c.tinai) + '">More ' + (t ? t.en : esc(c.tinai[0].toUpperCase() + c.tinai.slice(1))) + ' poems in ' + T.title + ' →</a>' : '') +
      '</div></section>';
  }

  // ---- tiṇai explorer: /tinai
  async function explorer() {
    const q = new URLSearchParams(location.search);
    Th.crumbs('<a href="/library">Library</a> › <strong>Tiṇai</strong>');
    let cur = tinai(q.get('t')) ? q.get('t') : 'kuṟiñci';
    const idx = await Th.json('/data/kuruntokai/index.json');
    const pick = document.getElementById('pick'), panel = document.getElementById('panel');
    const draw = () => {
      pick.innerHTML = AKAM.map((t) => '<button type="button" class="land" data-id="' + t.id + '" aria-pressed="' + (t.id === cur) + '" style="--c:' + t.color + '">' +
        '<span lang="ta" style="font-size:22px;font-weight:700">' + t.ta + '</span><span style="font-weight:600">' + t.en + '</span><span class="small">' + t.land + '</span></button>').join('');
      const t = tinai(cur), ps = idx.poems.filter((p) => p.tinai === cur);
      const feat = ps.find((p) => p.ai) || ps[0];
      panel.style.borderTopColor = t.color;
      panel.innerHTML = '<div style="display:flex;gap:12px;align-items:baseline;flex-wrap:wrap"><h2 lang="ta" style="font-size:32px;color:' + t.color + '">' + t.ta + '</h2><span class="muted">' + t.en + ' · ' + t.land + '</span></div>' +
        '<dl class="facts">' + [['Mood (uripporuḷ)', t.mood + ' · <span lang="ta">' + t.moodTa + '</span>'], ['Time of day', t.time], ['Season', t.season], ['Deity', t.god], ['Flower or tree', t.flower],
          ['Poems set here', '<a href="/anthology?t=kuruntokai&tinai=' + encodeURIComponent(t.id) + '">' + ps.length + ' in Kuṟuntokai</a>']].map(([k, v]) => '<div><dt>' + k + '</dt><dd>' + v + '</dd></div>').join('') + '</dl>' +
        (feat ? '<div style="border-top:1px solid var(--rule);padding-top:14px"><p class="eyebrow">A poem from here</p><p lang="ta" style="font-size:20px;line-height:1.6;margin-top:6px">' + esc(feat.first) + '…</p>' +
          '<a href="/poem?t=kuruntokai&n=' + feat.n + '">Kuṟuntokai ' + feat.n + ' · ' + esc(feat.poet) + ' →</a></div>' : '');
    };
    pick.addEventListener('click', (e) => { const b = e.target.closest('button[data-id]'); if (b) { cur = b.dataset.id; history.replaceState(null, '', '?t=' + encodeURIComponent(cur)); draw(); } });
    draw();
    quiz(idx);
  }

  // Test yourself: who is speaking? The answer key is the colophon.
  function quiz(idx) {
    const box = document.getElementById('quiz');
    const pool = idx.poems.filter((p) => /heroine|friend|hero \(|foster/.test(p.speaker));
    const opts = ['the heroine (talaivi)', 'her friend (tōḻi)', 'the hero (talaivaṉ)', 'the foster-mother (cevili)'];
    const ask = () => {
      const p = pool[Math.floor(Math.random() * pool.length)];
      box.innerHTML = '<p class="eyebrow">Test yourself</p><h2 style="font-size:22px">Kuṟuntokai ' + p.n + ': who is speaking?</h2>' +
        '<p lang="ta" style="font-size:19px;line-height:1.6">' + esc(p.first) + '…</p><a class="small" href="/poem?t=kuruntokai&n=' + p.n + '">Read the whole poem first</a>' +
        '<div class="opts" role="group" aria-label="Choose the speaker">' + opts.map((o) => '<button type="button" data-o="' + esc(o) + '">' + esc(o[0].toUpperCase() + o.slice(1)) + '</button>').join('') + '</div><p class="verdict" role="status"></p>';
      box.querySelector('.opts').onclick = (e) => {
        const b = e.target.closest('button[data-o]');
        if (!b) return;
        const right = b.dataset.o === p.speaker;
        box.querySelectorAll('.opts button').forEach((x) => { x.disabled = true; if (x.dataset.o === p.speaker) x.classList.add('right'); });
        if (!right) b.classList.add('wrong');
        box.querySelector('.verdict').innerHTML = (right ? '<b>Right.</b> ' : '<b>Not this time.</b> ') + 'The colophon says ' + esc(p.speaker) + ' is speaking. <button type="button" class="linkbtn" id="again">Try another poem</button>';
        box.querySelector('#again').onclick = ask;
      };
    };
    ask();
  }

  window.ThSangam = { list, poem, explorer, AKAM, TEXTS };
})();
