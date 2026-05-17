/**
 * Sino de solicitações pendentes (admin e membro).
 */
(function () {
  'use strict';

  function updateBadge(count) {
    var badge = document.getElementById('requests-bell-badge');
    var link = document.getElementById('requests-bell');
    if (!badge || !link) return;
    var n = parseInt(count, 10) || 0;
    if (n > 0) {
      badge.textContent = n > 99 ? '99+' : String(n);
      badge.hidden = false;
      link.setAttribute('aria-label', n + ' solicitações pendentes');
    } else {
      badge.hidden = true;
      badge.textContent = '';
      link.setAttribute('aria-label', 'Solicitações pendentes');
    }
  }

  function refreshCount() {
    var link = document.getElementById('requests-bell');
    if (!link) return;
    var url = link.getAttribute('data-count-url');
    if (!url) return;
    fetch(url, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(function (r) {
        return r.ok ? r.json() : { count: 0 };
      })
      .then(function (data) {
        updateBadge(data && data.count);
      })
      .catch(function () {});
  }

  function init() {
    refreshCount();
    if (!window._requestsBellInterval) {
      window._requestsBellInterval = setInterval(refreshCount, 60000);
    }
  }

  document.addEventListener('DOMContentLoaded', init);
  document.addEventListener('turbo:load', init);
})();
