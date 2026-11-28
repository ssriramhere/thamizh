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
        where: 'Tirukkuṟaḷ ' + n + (chap ? ' · ' + cap(chap.tr) : ''), href: '/kural?n=' + n, timing: k.timing, sync: k.sync, audio: !!k.timing, base: '/audio/kural/' };
    }
    const idx = await Th.json('/data/' + id + '/index.json');
    const ready = idx.poems.filter((p) => p.ai);
    const pick = ready[day() % ready.length];
    const p = await Th.json('/data/' + id + '/' + pick.n + '.json');
    const c = p.colophon;
    return { id, n: p.n, lines: p.lines, tr: p.tr, translation: p.ai && p.ai.translation,
      feet: (p.scan.lines[0] || []).map((f) => ({ tr: f.tr, foot: f.foot })),
      where: TEXTS.find((t) => t.id === id).title + ' ' + p.n + (c.poet_tr ? ' · ' + c.poet_tr : ''),
      label: TINAI[c.tinai] || (c.tinai ? cap(c.tinai) : ''), href: '/poem?t=' + id + '&n=' + p.n,
      timing: p.timing, sync: p.sync, audio: !!p.timing, base: '/audio/' + id + '/' };
  }

  function card(v, compact) {
    const cut = compact && v.lines.length > 4 ? 4 : v.lines.length;
    const html = (v.audio ? ThListen.wrap(v.lines) : v.lines.map(esc).join('<br>')).split('<br>');
    const lines = v.lines.slice(0, cut);
    const hidden = html.length - cut;
    const more = hidden > 0 ? '<button type="button" class="linkbtn vmore" style="color:#C8C8C8;align-self:flex-start">Show all ' + v.lines.length + ' lines</button>' : '';
    return '<blockquote lang="ta" class="vlines' + (v.lines.length > 2 ? ' poem' : '') + '" id="vl-' + v.id + '">' + html.slice(0, cut).join('<br>') +
      (hidden > 0 ? '<span class="vrest" hidden><br>' + html.slice(cut).join('<br>') + '</span>' : '') + '</blockquote>' + more +
      '<p style="font-size:16px;color:#C8C8C8;font-style:italic">' + (compact ? v.tr.slice(0, lines.length) : v.tr).map(esc).join('<br>') + '</p>' +
      (v.translation ? '<p class="' + (compact ? 'clamp' : '') + '" style="font-size:18px">' + esc(v.translation) + '</p>' : '') +
      (v.audio ? '<div id="vlisten-' + v.id + '"></div>' : '') +
      (v.audio && v.sync ? '<div class="nowword" id="vnow-' + v.id + '"' + (compact ? ' hidden' : '') + '><span class="muted">Press play: each word\'s meaning shows here as it is read.</span></div>' : '') +
      (compact ? '' : '<div class="chips">' + v.feet.map((f) => '<span>' + esc(f.tr) + ' · ' + esc(f.foot) + '</span>').join('') + '</div>') +
      '<figcaption style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap"><span>' + esc(v.where) + (v.label ? ' · ' + esc(v.label) : '') + '</span>' +
      '<a href="' + v.href + '" style="color:var(--gold);font-weight:600">Read it →</a></figcaption>';
  }
  function wire(v) {
    if (!v.audio) { const b = document.querySelector('#vl-' + v.id + ' ~ .vmore'); if (b) b.remove(); return; }
    const box = document.getElementById('vl-' + v.id), now = document.getElementById('vnow-' + v.id);
    const showAll = () => { const r = box.querySelector('.vrest'); if (r) r.hidden = false; const b = box.parentElement.querySelector('.vmore'); if (b) b.remove(); };
    const mb = box.parentElement.querySelector('.vmore'); if (mb) mb.onclick = showAll;
    let last = -2;
    ThListen.bar(document.getElementById('vlisten-' + v.id), v.n, (t) => {
      const cur = ThListen.paint(box, v.timing, t);
      if (t != null && t > 0) { showAll(); if (now) now.hidden = false; }   // the whole poem is read, so show all of it
      if (!now || cur === last) return;
      last = cur;
      const g = cur >= 0 && v.sync ? v.sync[cur] : null;
      if (g && g.length) now.innerHTML = g.map((x) => '<span class="nw"><b lang="ta">' + esc(x[0]) + '</b> ' + esc(x[1] || '') + '</span>').join('');
    }, v.base);
  }

  // The home page card: one tab per live text.
  async function tabs(el) {
    const date = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long' });
    el.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap"><p class="eyebrow">Today\'s verses · ' + date + '</p>' +
      '<span style="display:flex;gap:16px;align-items:baseline"><a href="/today#reel" style="color:#E8C26A;font-size:14px;font-weight:600" title="Today\'s reel">▶ Reel</a><a href="/today" style="color:#C8C8C8;font-size:14px">All of today\'s →</a></span></div>' +
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

  // Today's reel on /today: one reel a day, in the voice the reader has chosen.
  async function reel(el) {
    let r;
    try { r = (await Th.json('/data/reels.json')).days[String(day())]; } catch (e) { return; }
    if (!r) return;
    const href = r.text === 'kural' ? '/kural?n=' + r.n : '/poem?t=' + r.text + '&n=' + r.n;
    const file = (v) => '/reels/' + r.text + '-' + r.n + '-' + v + '.mp4';
    const tags = { kural: '#Thirukkural #திருக்குறள்', kuruntokai: '#Kurunthogai #குறுந்தொகை #SangamLiterature',
      purananuru: '#Purananuru #புறநானூறு #SangamLiterature' }[r.text] || '';
    const caption = () => [r.ref + ' · Today\'s verse on Thamizh.ai', r.hook, '', 'Read it word by word: https://thamizh.ai' + href, '', tags + ' #Tamil #செந்தமிழ்'].join('\n');
    el.innerHTML = '<div class="reelbox">' +
      '<video id="reelv" controls playsinline preload="none"></video>' +
      '<div class="reelside"><p class="eyebrow">Today\'s reel</p><h2>' + esc(r.ref) + '</h2>' +
      '<p class="muted">' + esc(r.hook) + '</p>' +
      '<p class="muted small">A short video: the verse recited with each word lit and its meaning, then the translation and one word to remember.</p>' +
      '<div class="reelbtns"><button class="btn primary" id="reelshare" type="button"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 12v7a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7"/><path d="M16 6l-4-4-4 4"/><path d="M12 2v13"/></svg>Share reel</button>' +
      '<a class="btn ghost" id="reeldl" download>Download</a><button class="btn ghost" id="reelcopy" type="button">Copy caption</button></div>' +
      '<div id="reelvoice" class="light"></div><p class="small muted" id="reelmsg" role="status"></p></div></div>';
    el.hidden = false;
    const vid = el.querySelector('#reelv'), dl = el.querySelector('#reeldl'), msg = el.querySelector('#reelmsg');
    const set = () => { const f = file(ThListen.voice()); vid.poster = f.replace(/\.mp4$/, '.jpg'); vid.src = f; dl.href = f; dl.setAttribute('download', 'thamizh-' + r.text + '-' + r.n + '.mp4'); };
    set();
    el.querySelector('#reelvoice').appendChild(ThListen.voiceSwitch(set));
    const count = (how) => { try { navigator.sendBeacon('/api/share', JSON.stringify({ voice: ThListen.voice(), text: r.text, n: r.n, how })); } catch (e) {} };
    el.querySelector('#reelcopy').addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(caption()); msg.textContent = 'Caption copied.'; } catch (e) { msg.textContent = 'Could not copy.'; }
    });
    dl.addEventListener('click', () => count('download'));
    el.querySelector('#reelshare').addEventListener('click', async () => {
      msg.textContent = '';
      try {
        const blob = await (await fetch(file(ThListen.voice()))).blob();
        const f = new File([blob], 'thamizh-' + r.text + '-' + r.n + '.mp4', { type: 'video/mp4' });
        if (navigator.canShare && navigator.canShare({ files: [f] })) {
          await navigator.share({ files: [f], text: caption() });
          count('share');
          return;
        }
        if (navigator.share) { await navigator.share({ title: r.ref, text: caption(), url: 'https://thamizh.ai/today' }); count('link'); return; }
        await navigator.clipboard.writeText(caption());
        msg.textContent = 'This browser can\'t share video. The caption is copied; use Download to get the video.';
        count('copy');
      } catch (e) { if (e && e.name !== 'AbortError') msg.textContent = 'Could not share. Try Download.'; }
    });
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

  window.ThToday = { tabs, all, reel, TEXTS };
})();
