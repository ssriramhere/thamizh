// Recitation: a listen bar for one couplet, and "Play all" for a chapter.
(function () {
  const VOICES = [['male', '♂ Male'], ['female', '♀ Female']];
  const voice = () => (Th.store.get('th.voice', 'male') === 'female' ? 'female' : 'male');
  const url = (n, v) => '/audio/kural/' + (v || voice()) + '/' + n + '.mp3';
  const PLAY = '<svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M7 5l12 7-12 7z"/></svg>';
  const PAUSE = '<svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>';
  const mmss = (s) => (isFinite(s) ? Math.floor(s / 60) + ':' + String(Math.floor(s % 60)).padStart(2, '0') : '0:00');

  function voiceSwitch(onChange) {
    const box = document.createElement('div');
    box.className = 'voice';
    box.innerHTML = '<span id="voice-l">Voice</span><div role="radiogroup" aria-labelledby="voice-l">' +
      VOICES.map(([k, label]) => '<button type="button" role="radio" data-v="' + k + '" aria-checked="' + (k === voice()) + '">' + label + '</button>').join('') + '</div>';
    box.addEventListener('click', (e) => {
      const b = e.target.closest('button[data-v]');
      if (!b) return;
      Th.store.set('th.voice', b.dataset.v);
      box.querySelectorAll('button').forEach((x) => x.setAttribute('aria-checked', String(x === b)));
      onChange(b.dataset.v);
    });
    return box;
  }

  // Printed words wrapped for highlighting while the recitation plays.
  function wrap(lines) {
    let i = 0;
    return lines.map((l) => l.split(' ').map((w) => '<span class="rw" data-wi="' + (i++) + '">' + Th.esc(w) + '</span>').join(' ')).join('<br>');
  }
  function paint(box, timing, t, v) {
    const tm = timing && timing[v || voice()];
    const spans = box ? box.querySelectorAll('.rw') : [];
    if (!tm || t == null) { spans.forEach((s) => s.classList.remove('on', 'done')); return; }
    let cur = -1;
    tm.forEach((x, i) => { if (t >= x[0]) cur = i; });
    if (cur >= 0 && t > tm[cur][1] + 0.4) cur = -1;
    spans.forEach((s, i) => { s.classList.toggle('on', i === cur); s.classList.toggle('done', i < cur || (cur < 0 && t > tm[i][1])); });
  }
  function ticker(audio, fn) {
    const loop = () => { fn(audio.currentTime); if (!audio.paused) requestAnimationFrame(loop); };
    audio.addEventListener('play', loop);
    audio.addEventListener('seeked', () => fn(audio.currentTime));
    audio.addEventListener('ended', () => fn(null));
  }

  // The listen bar under a couplet. onTime(t) is called while it plays (null when it ends).
  function bar(el, n, onTime) {
    const audio = new Audio();
    audio.preload = 'none';
    audio.src = url(n);
    el.innerHTML = '<div class="listen"><button type="button" class="play" aria-label="Play recitation">' + PLAY + '</button>' +
      '<div class="bar" aria-hidden="true"><i></i></div><span class="time">0:00</span></div>' +
      '<p class="small" style="color:#BDBDB8;margin-top:8px">AI recitation (Google Chirp 3 HD). Your choice of voice is remembered.</p>';
    const row = el.querySelector('.listen'), btn = el.querySelector('.play'), fill = el.querySelector('.bar i'), time = el.querySelector('.time');
    row.appendChild(voiceSwitch(() => { const was = !audio.paused; audio.src = url(n); if (was) audio.play(); }));
    btn.addEventListener('click', () => (audio.paused ? audio.play() : audio.pause()));
    audio.addEventListener('play', () => { btn.innerHTML = PAUSE; btn.setAttribute('aria-label', 'Pause recitation'); });
    audio.addEventListener('pause', () => { btn.innerHTML = PLAY; btn.setAttribute('aria-label', 'Play recitation'); });
    audio.addEventListener('timeupdate', () => {
      fill.style.width = (audio.duration ? (100 * audio.currentTime) / audio.duration : 0) + '%';
      time.textContent = mmss(audio.currentTime) + ' / ' + mmss(audio.duration);
    });
    audio.addEventListener('ended', () => { fill.style.width = '100%'; });
    if (onTime) ticker(audio, onTime);
  }

  // "Play all" for a list of couplets; mark(n) highlights the one playing.
  function playAll(el, ns, mark, onTime) {
    const audio = new Audio();
    let i = -1;
    el.classList.add('light');
    el.style.cssText = 'display:flex;flex-wrap:wrap;gap:12px 20px;align-items:center';
    el.innerHTML = '<button type="button" class="btn" id="playall">' + PLAY + ' <span>Play all ' + ns.length + '</span></button>';
    const btn = el.querySelector('#playall');
    el.appendChild(voiceSwitch(() => { if (i >= 0 && !audio.paused) { audio.src = url(ns[i]); audio.play(); } }));
    const go = (k) => {
      i = k;
      if (i >= ns.length) { i = -1; mark(null); btn.lastChild.textContent = 'Play all ' + ns.length; btn.firstChild.outerHTML = PLAY; return; }
      audio.src = url(ns[i]);
      audio.play();
      mark(ns[i]);
    };
    btn.addEventListener('click', () => {
      if (i < 0) go(0);
      else if (audio.paused) audio.play();
      else audio.pause();
    });
    audio.addEventListener('play', () => { btn.querySelector('svg').outerHTML = PAUSE; btn.lastChild.textContent = 'Pause'; });
    audio.addEventListener('pause', () => { if (i >= 0) { btn.querySelector('svg').outerHTML = PLAY; btn.lastChild.textContent = 'Resume'; } });
    audio.addEventListener('ended', () => setTimeout(() => go(i + 1), 700));
    if (onTime) ticker(audio, (t) => onTime(i >= 0 ? ns[i] : null, t));
  }

  window.ThListen = { bar, playAll, wrap, paint, voice, voiceSwitch };
})();
