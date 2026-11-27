// Shared header and footer, and small helpers.
(function () {
  const here = location.pathname.replace(/\/index(\.html)?$/, '/').replace(/\.html$/, '');

  function header() {
    const el = document.querySelector('[data-site-header]');
    if (!el) return;
    const crumbs = el.getAttribute('data-crumbs') || '';
    const links = [
      ['/learn', 'Learn'],
      ['/library', 'Library'],
      ['/today', 'Today\'s verses'],
    ];
    el.innerHTML =
      '<div class="band" aria-hidden="true"><span class="k"></span><span class="m"></span><span class="r"></span><span class="n"></span><span class="p"></span></div>' +
      '<header class="site-header"><nav aria-label="Main" class="wrap">' +
      '<a class="brand" href="/"><span class="mark" aria-hidden="true">ழ</span><span class="name">Thamizh.ai</span></a>' +
      '<p class="crumbs">' + crumbs + '</p>' +
      '<div class="navlinks">' +
      links.map(([href, label]) => {
        const cur = href.split('?')[0] === here ? ' aria-current="page"' : '';
        return '<a href="' + href + '"' + cur + '>' + label + '</a>';
      }).join('') +
      '</div></nav></header>';
  }

  function footer() {
    const el = document.querySelector('[data-site-footer]');
    if (!el) return;
    el.innerHTML =
      '<footer class="site-footer"><div class="wrap">' +
      '<span>Built by Sriram Subramanian using AI · <a class="contact" href="#">Contact</a> · <a href="https://github.com/ssriramhere/thamizh">Source on GitHub</a></span>' +
      '<span>Translations and explanations are AI-generated.</span>' +
      '</div></footer>';
    const c = el.querySelector('.contact');
    c.addEventListener('click', (e) => {
      e.preventDefault();
      location.href = 'mailto:' + ['sriram', 'sriramhere.com'].join('@');
    });
  }

  header();
  footer();

  window.Th = {
    esc(s) {
      return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    },
    async json(url) {
      const r = await fetch(url);
      if (!r.ok) throw new Error(url + ' ' + r.status);
      return r.json();
    },
    crumbs(html) { const c = document.querySelector('.site-header .crumbs'); if (c) c.innerHTML = html; },
    store: {
      get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
      set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* ignore */ } },
    },
  };
})();
