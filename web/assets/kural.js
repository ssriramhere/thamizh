// The layered Kuṟaḷ reader.
(function () {
  const esc = Th.esc;
  const q = new URLSearchParams(location.search);
  const COUNT = 1330;

  function todayN() {
    const d = new Date();
    const days = Math.floor(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / 86400000);
    return (days % COUNT) + 1;
  }
  const isToday = q.has('today');
  const n = isToday ? todayN() : Math.min(COUNT, Math.max(1, parseInt(q.get('n'), 10) || 1));

  const LAYERS = ['Meaning', 'English letters', 'Tamil letters', 'Words', 'Meter', 'Explanation'];
  const PRESETS = [
    ['New to Tamil', 2], ['I speak it, but can’t read', 3], ['I read Tamil', 4], ['I study classical Tamil', 6],
  ];
  let layer = parseInt(q.get('level'), 10) || Th.store.get('th.layer', 3);
  layer = Math.min(6, Math.max(1, layer));

  const KIND = {
    k: 'Short letter (kuṟil) · 1 beat',
    n: 'Long letter (neṭil) · 2 beats',
    o: 'Consonant alone (oṟṟu) · ½ beat',
    a: 'Āytam · ½ beat',
  };
  const SOUND = {
    'ழ': 'ழ (ḻ) is the sound only Tamil has: the tongue curls back without touching the roof of the mouth.',
    'ள': 'ள (ḷ) is an l made with the tongue curled back.',
    'ற': 'ற (ṟ) is a trilled or hard r; doubled (ற்ற) it sounds close to "tr".',
    'ண': 'ண (ṇ) is an n made with the tongue curled back.',
    'ன': 'ன (ṉ) is an n made just behind the teeth, at the gum ridge.',
    'ந': 'ந (n) is an n made with the tongue on the teeth; it mostly starts words.',
    'ஃ': 'ஃ (āytam) is a soft breath between sounds, counted as half a beat.',
  };

  function renderLayers() {
    document.getElementById('layers').innerHTML = LAYERS.map((label, i) => {
      const k = i + 1;
      return '<button type="button" data-k="' + k + '" class="' + (k <= layer ? 'on' : '') + '"' + (k === layer ? ' aria-current="step"' : '') + '>' +
        '<span class="dot">' + k + '</span>' + label + '</button>';
    }).join('');
    document.getElementById('presets').innerHTML = PRESETS.map(([label, k]) =>
      '<button type="button" data-k="' + k + '" aria-pressed="' + (k === layer) + '">' + esc(label) + '</button>'
    ).join('');
    document.querySelectorAll('[data-layer]').forEach((s) => {
      s.classList.toggle('hidden', parseInt(s.getAttribute('data-layer'), 10) > layer);
    });
  }
  function setLayer(k) {
    layer = k;
    Th.store.set('th.layer', k);
    renderLayers();
  }
  document.getElementById('layers').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-k]');
    if (b) setLayer(parseInt(b.getAttribute('data-k'), 10));
  });
  document.getElementById('presets').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-k]');
    if (b) setLayer(parseInt(b.getAttribute('data-k'), 10));
  });

  function pending(text) {
    return '<p class="pending">' + esc(text) + '</p>';
  }

  let selected = null;
  let letterIndex = {};

  function renderInfo(k) {
    const L = letterIndex[selected];
    const el = document.getElementById('info');
    if (!L) { el.innerHTML = '<p class="muted">Tap a letter.</p>'; return; }
    let parts = L.kind === 'o' ? 'Consonant ' + L.c + ' with no vowel'
      : L.kind === 'a' ? 'Āytam'
      : L.c ? L.c + '் + ' + L.v : 'Vowel ' + L.v;
    const notes = [];
    if (SOUND[L.c]) notes.push(SOUND[L.c]);
    if (L.g === 'ஃ') notes.push(SOUND['ஃ']);
    if (L.lastU) notes.push('At the end of the couplet this u is shortened to half a beat (kuṟṟiyalukaram). It decides the shape of the last foot.');
    el.innerHTML =
      '<span class="big" lang="ta">' + esc(L.g) + '</span>' +
      '<span class="tr">' + esc(L.tr) + '</span>' +
      '<span class="kind">' + esc(KIND[L.kind] || '') + '</span>' +
      '<span class="small">' + esc(parts) + '</span>' +
      notes.map((t) => '<span class="note">' + esc(t) + '</span>').join('');
  }

  function renderLetters(k) {
    letterIndex = {};
    const lastLine = k.words.length - 1;
    const lastWord = k.words[lastLine].length - 1;
    const finalU = k.scan.lines.length && k.scan.lines[k.scan.lines.length - 1].slice(-1)[0].final_u;
    let first = null;
    document.getElementById('letters').innerHTML = k.words.map((line, li) =>
      '<div class="letters-line">' + line.map((w, wi) =>
        '<div class="lw">' + w.letters.map((L, ci) => {
          const id = li + '-' + wi + '-' + ci;
          const isLast = li === lastLine && wi === lastWord && ci === w.letters.length - 1;
          letterIndex[id] = Object.assign({}, L, { lastU: finalU && isLast && L.v === 'உ' });
          if (!first) first = id;
          if (L.c === 'ழ' && selected == null) selected = id;
          return '<button type="button" class="lt ' + L.kind + '" data-id="' + id + '" aria-label="' + esc(L.tr + ', ' + (KIND[L.kind] || '')) + '" aria-pressed="false">' + esc(L.g) + '</button>';
        }).join('') + '</div>'
      ).join('') + '</div>'
    ).join('');
    if (selected == null) selected = first;
    markSelected();
  }
  function markSelected() {
    document.querySelectorAll('.lt').forEach((b) => b.setAttribute('aria-pressed', String(b.getAttribute('data-id') === selected)));
    renderInfo();
  }
  document.getElementById('letters').addEventListener('click', (e) => {
    const b = e.target.closest('.lt');
    if (!b) return;
    selected = b.getAttribute('data-id');
    markSelected();
  });

  function renderWords(k) {
    const ai = k.ai || {};
    const glosses = {};
    (ai.words || []).forEach((w) => { glosses[w.surface] = w; });
    document.getElementById('words').innerHTML = k.words.flat().map((w) => {
      const g = glosses[w.ta];
      let parts = '';
      if (g && g.parts && g.parts.length > 1) {
        parts = '<span class="small muted" lang="ta" style="font-family:var(--ta-ui)">' + g.parts.map((p) => esc(p.text)).join(' + ') + '</span>';
      }
      return '<div class="word"><span class="ta" lang="ta">' + esc(w.ta) + '</span><span class="tr">' + esc(w.tr) + '</span>' + parts +
        '<span>' + (g ? esc(g.gloss) : '<span class="pending">Gloss being prepared</span>') + '</span></div>';
    }).join('');
    document.getElementById('modern').innerHTML = ai.modern
      ? '<div style="border-top:1px solid var(--rule);padding-top:14px;display:flex;flex-direction:column;gap:6px"><p class="small muted" style="font-weight:600">In today\'s Tamil (AI rendering)</p><p class="ta-ui" lang="ta" style="font-size:18px;line-height:1.6">' + esc(ai.modern) + '</p></div>'
      : '';
  }

  function renderMeter(k) {
    const s = k.scan;
    document.getElementById('metrical').innerHTML = s.lines.map((l) => l.map((f) => esc(f.text)).join(' ')).join('<br>');
    document.getElementById('feet').innerHTML = s.lines.map((line, li) => {
      return '<div class="feet-line">' + line.map((f, fi) => {
        const globalIdx = s.lines.slice(0, li).reduce((a, l) => a + l.length, 0) + fi;
        const link = globalIdx > 0 ? s.links[globalIdx - 1] : null;
        const linkHtml = link ? '<span class="link' + (link.name === 'veṇṭaḷai' ? '' : ' bad') + '" title="linkage">' + esc(link.name) + (link.name === 'veṇṭaḷai' ? ' ✓' : '') + '</span>' : '';
        return linkHtml + '<div class="foot"><span class="ta" lang="ta">' + esc(f.text) + '</span><span class="tr">' + esc(f.tr) + '</span>' +
          '<div class="acai">' + f.acai.map((a) => '<span class="' + (a.kind === 'nēr' ? 'ner' : 'nirai') + '" title="' + esc(a.kind) + '">' + esc(a.tr) + '</span>').join('') + '</div>' +
          '<span class="name">' + esc(f.foot) + '</span>' +
          '<span class="small muted">' + esc(f.acai.map((a) => a.kind).join(' + ')) + (f.final_u ? ' (+ shortened u)' : '') + '</span></div>';
      }).join('') + '</div>';
    }).join('');
    document.getElementById('verdict').textContent = s.ok ? 'Kuṟaḷ veṇpā' : 'Does not scan as a regular kuṟaḷ veṇpā';
    document.getElementById('checks').innerHTML = s.checks.map((c) =>
      '<li><span class="' + (c.ok ? 'ok' : 'no') + '">' + (c.ok ? '✓' : '✗') + '</span><span>' + esc(c.text) + '</span></li>'
    ).join('');
    const words = k.words;
    const parts = [];
    (s.monai || []).forEach((m) => {
      const ws = m.words.map((i) => words[m.line][i] && words[m.line][i].ta).filter(Boolean);
      parts.push('<b>Mōṉai</b> (initial rhyme) in line ' + (m.line + 1) + ': <span lang="ta" style="font-family:var(--ta-ui)">' + ws.map(esc).join(' · ') + '</span>');
    });
    if (s.etukai) parts.push('<b>Etukai</b> (second-letter rhyme): both lines open on a word whose second letter is <span lang="ta" style="font-family:var(--ta-ui)">' + esc(s.etukai.letter) + '</span>');
    document.getElementById('toTai').innerHTML = parts.join('<br>');
    const notes = [];
    if (s.joins && s.joins.length) notes.push('<b>How the words join in verse:</b> ' + s.joins.map((j) => '<span lang="ta" style="font-family:var(--ta-ui)">' + esc(j) + '</span>').join('; '));
    if (s.moved) notes.push('The meter places ' + s.moved + ' foot boundar' + (s.moved === 1 ? 'y' : 'ies') + ' differently from the printed word breaks.');
    if (k.source && k.source.chosen_by && k.source.chosen_by !== 'majority') {
      notes.push(k.source.chosen_by.indexOf('correction') === 0
        ? 'The digital sources share a typo in this couplet; the reading shown is a correction that scans, pending a check against a printed edition.'
        : 'The digital sources disagree on this couplet; the reading shown is the one that scans.');
    }
    document.getElementById('joins').innerHTML = notes.join('<br>');
  }

  function render(k, ch) {
    document.title = 'Kuṟaḷ ' + k.n + ' · Tirukkuṟaḷ · Thamizh.ai';
    document.getElementById('kicker').textContent = (isToday ? 'Kuṟaḷ for today · ' : '') + 'Tirukkuṟaḷ ' + k.n;
    document.getElementById('chname').innerHTML = 'Chapter ' + ch.n + ' · <span lang="ta" style="font-family:var(--ta)">' + esc(ch.ta) + '</span> · ' + esc(ch.tr);
    const cc = document.getElementById('crumb-ch');
    cc.textContent = 'Chapter ' + ch.n; cc.href = '/chapter?c=' + ch.n;
    document.getElementById('crumb-n').textContent = 'Kuṟaḷ ' + k.n;
    const prev = document.getElementById('prev'), next = document.getElementById('next');
    if (k.n > 1) prev.href = '/kural?n=' + (k.n - 1); else prev.setAttribute('aria-disabled', 'true');
    if (k.n < COUNT) next.href = '/kural?n=' + (k.n + 1); else next.setAttribute('aria-disabled', 'true');

    const ai = k.ai || {};
    document.getElementById('meaning').innerHTML =
      '<p lang="ta" style="font-family:var(--ta);font-size:26px;line-height:1.6;font-weight:600;margin-bottom:12px">' + k.lines.map(esc).join('<br>') + '</p>' +
      (ai.translation
        ? '<p class="meaning">' + esc(ai.translation) + '</p><p class="small" style="color:var(--gold);margin-top:8px">AI translation</p>'
        : pending('The AI translation is being prepared.'));
    document.getElementById('roman').innerHTML = k.tr.map(esc).join('<br>');
    renderLetters(k);
    renderWords(k);
    renderMeter(k);
    document.getElementById('explain').innerHTML = ai.explanation
      ? '<p style="font-size:16px;line-height:1.7">' + esc(ai.explanation) + '</p><p class="small muted">AI explanation</p>'
      : pending('The AI explanation is being prepared.');
  }

  (async function () {
    renderLayers();
    try {
      const idx = await Th.json('/data/kural/index.json');
      const c = idx.chapter_of[String(n)];
      const data = await Th.json('/data/kural/' + c + '.json');
      const k = data.kurals.find((x) => x.n === n);
      let ch;
      idx.books.forEach((b) => b.chapters.forEach((x) => { if (x.n === c) ch = x; }));
      render(k, ch);
    } catch (e) {
      document.getElementById('reader').insertAdjacentHTML('afterbegin', '<p class="pending">Could not load this couplet.</p>');
    }
  })();
})();
