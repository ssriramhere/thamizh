// Today's verses: one verse a day from each text that is live, the same for everyone on a given date.
(function () {
  const esc = (s) => Th.esc(s == null ? '' : String(s));
  const day = () => { const d = new Date(); return Math.floor(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / 86400000); };
  const TINAI = { 'kuṟiñci': 'Kuṟiñci · mountains', mullai: 'Mullai · forest', marutam: 'Marutam · farmland', neytal: 'Neytal · seashore', 'pālai': 'Pālai · parched land' };
  const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : '');

  // The texts that are live, in the order they are offered. Tirukkuṟaḷ first.
  const TEXTS = [
    { id: 'kural', title: 'Tirukkuṟaḷ', short: 'Kuṟaḷ', ta: 'திருக்குறள்' },
    { id: 'kuruntokai', title: 'Kuṟuntokai', short: 'Kuṟuntokai', ta: 'குறுந்தொகை' },
    { id: 'purananuru', title: 'Puṟanāṉūṟu', short: 'Puṟanāṉūṟu', ta: 'புறநானூறு' },
  ];

  async function load(id) {
    if (id === 'kural') {
      const n = (day() % 1330) + 1;
      const idx = await Th.json('/data/kural/index.json');
      const ch = await Th.json('/data/kural/' + idx.chapter_of[n] + '.json');
      const k = ch.kurals.find((x) => x.n === n);
      const chap = idx.books.flatMap((b) => b.chapters).find((c) => c.n === idx.chapter_of[n]);
      return { id, n, lines: k.lines, tr: k.tr, translation: k.ai && k.ai.translation, feet: k.scan.lines[0],
        where: 'Tirukkuṟaḷ ' + n + (chap ? ' · ' + cap(chap.tr) : ''), href: '/kural?n=' + n, timing: k.timing, audio: true };
    }
    const idx = await Th.json('/data/' + id + '/index.json');
    const ready = idx.poems.filter((p) => p.ai);
    const pick = ready[day() % ready.length];
    const p = await Th.json('/data/' + id + '/' + pick.n + '.json');
    const c = p.colophon;
    return { id, n: p.n, lines: p.lines, tr: p.tr, translation: p.ai && p.ai.translation,
      feet: (p.scan.lines[0] || []).map((f) => ({ tr: f.tr, foot: f.foot })),
      where: TEXTS.find((t) => t.id === id).title + ' ' + p.n + (c.poet_tr ? ' · ' + c.poet_tr : ''),
      label: TINAI[c.tinai] || (c.tinai ? cap(c.tinai) : ''), href: '/poem?t=' + id + '&n=' + p.n };
  }

  function card(v, compact) {
    const lines = compact && v.lines.length > 4 ? v.lines.slice(0, 4) : v.lines;
    const more = lines.length < v.lines.length ? '<p class="small" style="color:#BDBDB8">… ' + (v.lines.length - lines.length) + ' more lines</p>' : '';
    return '<blockquote lang="ta" class="vlines' + (v.lines.length > 2 ? ' poem' : '') + '" id="vl-' + v.id + '">' + (v.audio ? ThListen.wrap(lines) : lines.map(esc).join('<br>')) + '</blockquote>' + more +
      '<p style="font-size:16px;color:#C8C8C8;font-style:italic">' + (compact ? v.tr.slice(0, lines.length) : v.tr).map(esc).join('<br>') + '</p>' +
      (v.translation ? '<p class="' + (compact ? 'clamp' : '') + '" style="font-size:18px">' + esc(v.translation) + '</p>' : '') +
      (v.audio ? '<div id="vlisten-' + v.id + '"></div>' : '') +
      '<div class="chips">' + v.feet.map((f) => '<span>' + esc(f.tr) + ' · ' + esc(f.foot) + '</span>').join('') + '</div>' +
      '<figcaption style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap"><span>' + esc(v.where) + (v.label ? ' · ' + esc(v.label) : '') + '</span>' +
      '<a href="' + v.href + '" style="color:var(--gold);font-weight:600">Read it →</a></figcaption>';
  }
  function wire(v) {
    if (!v.audio) return;
    const box = document.getElementById('vl-' + v.id);
    ThListen.bar(document.getElementById('vlisten-' + v.id), v.n, (t) => ThListen.paint(box, v.timing, t));
  }

  // The home page card: one tab per live text.
  async function tabs(el) {
    const date = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long' });
    el.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap"><p class="eyebrow">Today\'s verses · ' + date + '</p>' +
      '<a href="/today" style="color:#C8C8C8;font-size:14px">All of today\'s →</a></div>' +
      '<div class="vtabs" role="tablist" aria-label="Choose a text">' + TEXTS.map((t, i) => '<button type="button" role="tab" data-id="' + t.id + '" aria-selected="' + (i === 0) + '">' + t.short + '</button>').join('') + '</div>' +
      '<div id="vbody" role="tabpanel" aria-live="polite" style="display:flex;flex-direction:column;gap:16px"><p class="pending">Loading…</p></div>';
    const body = el.querySelector('#vbody');
    const show = async (id) => {
      el.querySelectorAll('[role=tab]').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.id === id)));
      try { const v = await load(id); body.innerHTML = card(v, true); wire(v); } catch (e) { console.error(e); body.innerHTML = '<p class="pending">Could not load today\'s verse.</p>'; }
    };
    el.querySelector('.vtabs').addEventListener('click', (e) => { const b = e.target.closest('[data-id]'); if (b) show(b.dataset.id); });
    show(TEXTS[0].id);
  }

  // The /today page: every live text, one after another.
  async function all(el) {
    el.innerHTML = TEXTS.map((t) => '<figure class="quote" id="today-' + t.id + '"><p class="eyebrow">' + t.title + '</p><p class="pending">Loading…</p></figure>').join('');
    for (const t of TEXTS) {
      const f = document.getElementById('today-' + t.id);
      try { const v = await load(t.id); f.innerHTML = '<p class="eyebrow">' + t.title + ' · <span lang="ta">' + t.ta + '</span></p>' + card(v, false); wire(v); }
      catch (e) { f.innerHTML = '<p class="pending">Could not load.</p>'; }
    }
  }

  window.ThToday = { tabs, all, TEXTS };
})();
