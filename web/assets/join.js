// Joining rules for checking a suggested word split in the browser.
// A port of rejoin() in engine/yappu.py: keep the two in step.
(function (root) {
  const VOWELS = { 'அ': 'k', 'ஆ': 'n', 'இ': 'k', 'ஈ': 'n', 'உ': 'k', 'ஊ': 'n', 'எ': 'k', 'ஏ': 'n', 'ஐ': 'n', 'ஒ': 'k', 'ஓ': 'n', 'ஔ': 'n' };
  const SIGNS = { 'ா': 'ஆ', 'ி': 'இ', 'ீ': 'ஈ', 'ு': 'உ', 'ூ': 'ஊ', 'ெ': 'எ', 'ே': 'ஏ', 'ை': 'ஐ', 'ொ': 'ஒ', 'ோ': 'ஓ', 'ௌ': 'ஔ' };
  const SIGN_OF = { 'அ': '' };
  Object.keys(SIGNS).forEach((s) => { SIGN_OF[SIGNS[s]] = s; });
  const CONS = new Set('கஙசஞடணதநபமயரலவழளறனஜஷஸஹ');
  const HARD = new Set('கசடதபற');
  const PULLI = '்';

  function letters(w) {
    const out = [];
    for (let i = 0; i < w.length;) {
      const ch = w[i];
      if (VOWELS[ch]) { out.push({ text: ch, kind: VOWELS[ch], c: '', v: ch }); i += 1; }
      else if (ch === 'ஃ') { out.push({ text: ch, kind: 'a', c: '', v: '' }); i += 1; }
      else if (CONS.has(ch)) {
        const nx = w[i + 1] || '';
        if (nx === PULLI) { out.push({ text: ch + PULLI, kind: 'o', c: ch, v: '' }); i += 2; }
        else if (SIGNS[nx]) { const v = SIGNS[nx]; out.push({ text: ch + nx, kind: VOWELS[v], c: ch, v: v }); i += 2; }
        else { out.push({ text: ch, kind: 'k', c: ch, v: 'அ' }); i += 1; }
      } else i += 1;
    }
    return out;
  }
  const str = (ls) => ls.map((x) => x.text).join('');
  const merge = (c, L) => c + SIGN_OF[L.v];
  function kurriyalukaram(A) {
    if (A.length < 2) return false;
    const L = A[A.length - 1];
    if (!(L.kind === 'k' && L.v === 'உ' && HARD.has(L.c))) return false;
    return !(A.length === 2 && A[0].kind === 'k');
  }

  function rejoin(parts) {
    let results = new Set(['']);
    for (const part of parts) {
      const B = letters(part);
      const nxt = new Set();
      for (const acc of results) {
        const A = letters(acc);
        nxt.add(acc + part);
        if (!A.length || !B.length) continue;
        const first = B[0], last = A[A.length - 1], restB = str(B.slice(1)), headA = str(A.slice(0, -1));
        if (!first.c && (first.kind === 'k' || first.kind === 'n')) {
          if (last.kind === 'k' && last.v === 'உ' && last.c && A.length > 1) nxt.add(headA + merge(last.c, first) + restB);
          if (kurriyalukaram(A)) nxt.add(headA + merge(last.c, first) + restB);
          if (last.kind === 'o') {
            const joined = merge(last.c, first) + restB;
            nxt.add(headA + joined);
            nxt.add(acc + joined);
          }
          if ((last.kind === 'k' || last.kind === 'n') && last.v) ['ய', 'வ'].forEach((g) => nxt.add(acc + merge(g, first) + restB));
        } else if (HARD.has(first.c)) {
          nxt.add(acc + first.c + PULLI + part);
        }
        if (last.kind === 'o' && last.c === 'ம' && first.c) {
          const nasal = { 'க': 'ங', 'ச': 'ஞ', 'த': 'ந', 'ப': 'ம', 'ட': 'ண', 'ற': 'ன' }[first.c];
          if (nasal) nxt.add(acc.slice(0, -2) + nasal + PULLI + part);
        }
        if (last.kind === 'o' && 'லளனண'.includes(last.c) && HARD.has(first.c)) {
          nxt.add(acc.slice(0, -2) + { 'ல': 'ற', 'ன': 'ற', 'ள': 'ட', 'ண': 'ட' }[last.c] + PULLI + part);
        }
        if (last.kind === 'o' && 'லளனண'.includes(last.c) && first.c === 'த') {
          const [pre, t] = { 'ல': ['ற', 'ற'], 'ன': ['ன', 'ற'], 'ள': ['ட', 'ட'], 'ண': ['ண', 'ட'] }[last.c];
          nxt.add(acc.slice(0, -2) + pre + PULLI + first.text.replace('த', t) + restB);
        }
        if (last.kind === 'o' && last.c === 'ம' && first.c && !HARD.has(first.c)) nxt.add(acc.slice(0, -2) + part);
        if (last.kind === 'o' && 'னணலள'.includes(last.c) && first.c === 'ந') {
          const nas = { 'ன': 'ன', 'ல': 'ன', 'ண': 'ண', 'ள': 'ண' }[last.c];
          nxt.add(acc.slice(0, -2) + nas + PULLI + nas + part.slice(1));
          if ('னண'.includes(last.c)) nxt.add(acc.slice(0, -2) + nas + part.slice(1));
        }
        if (A.length > 1 && last.text === 'மை') {
          // a quality noun drops மை: கருமை + கோல் -> கருங்கோல்
          nxt.add(headA + part);
          if (HARD.has(first.c)) {
            nxt.add(headA + { 'க': 'ங', 'ச': 'ஞ', 'த': 'ந', 'ப': 'ம', 'ட': 'ண', 'ற': 'ன' }[first.c] + PULLI + part);
            nxt.add(headA + first.c + PULLI + part);
          }
        }
      }
      results = nxt;
    }
    return results;
  }

  const api = { letters, rejoin, joins: (parts, word) => rejoin(parts.map((p) => p.normalize('NFC'))).has(word.normalize('NFC')) };
  if (typeof module !== 'undefined') module.exports = api;
  else root.ThJoin = api;
})(this);
