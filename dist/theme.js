/* Appearance is a local preference, separate from all project records. */
(() => {
  'use strict';
  const key = 'folio-relay-theme';
  const root = document.documentElement;
  const valid = value => value === 'dark' || value === 'light';
  let cached;
  try { cached = localStorage.getItem(key); } catch (_) {}
  const requested = new URL(location.href).searchParams.get('theme');
  let theme = valid(requested) ? requested : valid(cached) ? cached : 'dark';
  let revision = 0;
  let writes = Promise.resolve();

  function apply(value) {
    theme = value;
    root.dataset.theme = value;
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', value === 'dark' ? '#05070b' : '#f4f8fc');
    const button = document.getElementById('theme-toggle');
    if (!button) return;
    const label = value === 'dark' ? '日间模式' : '夜间模式';
    button.querySelector('.theme-label').textContent = label;
    button.setAttribute('aria-label', '切换到' + label);
    button.setAttribute('title', '切换到' + label);
    button.setAttribute('aria-pressed', String(value === 'dark'));
  }

  function cache(value) {
    try { localStorage.setItem(key, value); } catch (_) {}
  }

  function saveNative(value) {
    const bridge = window.pywebview?.api;
    if (!bridge?.set_theme) return;
    // Keep rapid changes in order; the final click must be the saved choice.
    writes = writes.catch(() => {}).then(() => bridge.set_theme(value));
    writes.catch(() => {
      if (typeof window.toast === 'function') window.toast('外观已切换，但未能记住选择，请稍后重试');
    });
  }

  async function restoreNative() {
    const bridge = window.pywebview?.api;
    if (!bridge?.get_theme) return;
    // A choice made before the bridge connected takes precedence over disk.
    if (revision > 0) { saveNative(theme); return; }
    const before = revision;
    try {
      const saved = await bridge.get_theme();
      if (before === revision && valid(saved)) {
        apply(saved);
        cache(saved);
      }
    } catch (_) { /* The page remains usable if the native bridge is unavailable. */ }
  }

  function bind() {
    apply(theme);
    document.getElementById('theme-toggle').addEventListener('click', () => {
      const chosen = theme === 'dark' ? 'light' : 'dark';
      revision++;
      apply(chosen);
      cache(chosen);
      const url = new URL(location.href);
      url.searchParams.set('theme', chosen);
      history.replaceState(history.state, '', url);
      saveNative(chosen);
    });
    restoreNative();
  }

  // Run in <head> so the first painted frame already uses the chosen palette.
  apply(theme);
  window.addEventListener('pywebviewready', restoreNative);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind, {once:true});
  else bind();
})();
