"""Repair word timings where the alignment bunched words together.

Speech-to-text sometimes cannot place a run of words: they come back with no
duration, and the word after them swallows the whole stretch. A highlighter then
jumps over the run. smooth() finds such words (too short, or far longer than their
letters warrant), widens each run with its neighbours until it has a sensible
span, and shares that span out by the number of letters in each word.
"""
from __future__ import annotations

import unicodedata


def letters(w: str) -> int:
    return max(1, sum(1 for c in w if not unicodedata.category(c).startswith("M")))


def smooth(words: list[str], spans: list, short: float = 0.12, long: float = 2.6) -> list:
    n = len(spans)
    if n < 2 or n != len(words) or any(s is None for s in spans):
        return spans
    sp = [list(s) for s in spans]
    total = sp[-1][1] - sp[0][0]
    per = total / sum(letters(w) for w in words) if total > 0 else 0.1
    exp = [letters(w) * per for w in words]
    bad = [(b - a) < short or (b - a) > long * e for (a, b), e in zip(sp, exp)]
    i = 0
    while i < n:
        if not bad[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and bad[j + 1]:
            j += 1
        lo, hi = i, j
        # widen until the run has at least 60% of the time its letters need
        while (sp[hi][1] - sp[lo][0]) < 0.6 * sum(exp[lo:hi + 1]) and (lo > 0 or hi < n - 1):
            if lo > 0 and (hi == n - 1 or (sp[lo - 1][1] - sp[lo - 1][0]) >= (sp[hi + 1][1] - sp[hi + 1][0])):
                lo -= 1
            else:
                hi += 1
        a, b = sp[lo][0], sp[hi][1]
        w = [letters(x) for x in words[lo:hi + 1]]
        t = a
        for k, lw in zip(range(lo, hi + 1), w):
            d = (b - a) * lw / sum(w)
            sp[k] = [round(t, 2), round(t + d, 2)]
            t += d
        i = hi + 1
    return sp
