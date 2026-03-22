/**
 * Painel de abas: cada link do menu abre em uma aba; se já existir, apenas foca nela.
 * Usa navegação nativa do turbo-frame (src / reload) para o Turbo executar scripts,
 * cancelar requisições antigas e evitar race conditions do fetch+innerHTML.
 */
(function () {
  'use strict';

  var TAB_BAR_ID = 'admin-tab-bar';
  var TAB_BAR_WRAP_ID = 'admin-tab-bar-wrap';
  var TAB_LIST_ID = 'admin-tab-list';
  var FRAME_ID = 'main-content';
  var tabs = [];
  var activeTabId = null;
  var lastFrameLoadUrl = null;
  var listenersBound = false;
  var filterFormsBound = false;
  /** Evita initInitialTab duplicado (DOMContentLoaded + turbo:load na primeira carga). */
  var initialTabsReady = false;
  var pendingLoadCallback = null;

  function normalizePath(href) {
    if (!href) return '';
    try {
      var a = document.createElement('a');
      a.href = href;
      return a.pathname || href;
    } catch (e) {
      return href;
    }
  }

  function resolveFrameUrl(url) {
    if (!url) return '';
    try {
      return new URL(url, window.location.origin).href;
    } catch (e) {
      return url;
    }
  }

  function findTabByPath(path) {
    return tabs.find(function (t) {
      return t.path === path;
    });
  }

  function getFrame() {
    return document.getElementById(FRAME_ID);
  }

  function setActiveTab(id) {
    activeTabId = id;
    var list = document.getElementById(TAB_LIST_ID);
    if (!list) return;
    list.querySelectorAll('.nav-link').forEach(function (el) {
      var tabId = el.getAttribute('data-tab-id');
      el.classList.toggle('active', tabId === id);
    });
  }

  function updateTabTitleFromFrame(tab) {
    if (!tab) return;
    var frame = getFrame();
    if (!frame) return;
    var h =
      frame.querySelector('h1.h3') ||
      frame.querySelector('h1.h4') ||
      frame.querySelector('.h3') ||
      frame.querySelector('.h4') ||
      frame.querySelector('h1');
    if (h && h.textContent.trim()) {
      tab.title = h.textContent.trim();
      var tabLink = document.querySelector('[data-tab-id="' + tab.id + '"] .admin-tab-title');
      if (tabLink) tabLink.textContent = tab.title;
    }
  }

  /**
   * Carrega URL no frame principal via Turbo (executa scripts, cancela loads anteriores).
   */
  function loadUrlInFrame(url, callback) {
    var frame = getFrame();
    if (!frame) {
      if (callback) callback(null);
      return;
    }
    var absolute = resolveFrameUrl(url);
    if (!absolute) {
      if (callback) callback(null);
      return;
    }

    pendingLoadCallback = callback || null;

    var currentAttr = frame.getAttribute('src');
    var sameDestination =
      currentAttr && resolveFrameUrl(currentAttr) === absolute;

    if (sameDestination && typeof frame.reload === 'function') {
      frame.reload().catch(function () {
        frame.classList.remove('main-content-loading');
        pendingLoadCallback = null;
        if (callback) callback(null);
      });
      return;
    }

    frame.src = absolute;
  }

  function loadTabContent(tab, callback) {
    if (!tab || !tab.path) return;
    lastFrameLoadUrl = tab.path;
    loadUrlInFrame(tab.path, function (ok) {
      if (ok && tab) {
        updateTabTitleFromFrame(tab);
      }
      if (callback) callback();
    });
  }

  function ensureTabBar() {
    var bar = document.getElementById(TAB_BAR_ID);
    if (bar) {
      bar.style.display = bar.style.display === 'none' ? 'block' : bar.style.display;
      return bar;
    }
    return null;
  }

  function addTab(path, title, focus) {
    var norm = normalizePath(path);
    if (!norm) return;
    var existing = findTabByPath(norm);
    if (existing) {
      setActiveTab(existing.id);
      if (focus !== false) loadTabContent(existing, function () {});
      return existing;
    }
    ensureTabBar();
    var id = 'tab-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8);
    var tab = { id: id, path: norm, title: title || norm };
    tabs.push(tab);

    var list = document.getElementById(TAB_LIST_ID);
    if (!list) return tab;
    var li = document.createElement('li');
    li.className = 'nav-item admin-tab-item';
    li.innerHTML =
      '<a class="nav-link d-flex align-items-center" href="#" data-tab-id="' +
      id +
      '" data-path="' +
      norm.replace(/"/g, '&quot;') +
      '">' +
      '<span class="admin-tab-title">' +
      (title || norm) +
      '</span>' +
      '<span class="admin-tab-close ms-2" data-tab-id="' +
      id +
      '" aria-label="Fechar" title="Fechar aba">&times;</span>' +
      '</a>';
    list.appendChild(li);

    var link = li.querySelector('.nav-link');
    link.addEventListener('click', function (e) {
      e.preventDefault();
      if (e.target.closest('.admin-tab-close')) {
        var idx = tabs.findIndex(function (t) {
          return t.id === id;
        });
        if (idx === -1) return;
        tabs.splice(idx, 1);
        li.remove();
        if (activeTabId === id && tabs.length > 0) {
          var next = tabs[idx] || tabs[idx - 1] || tabs[0];
          setActiveTab(next.id);
          loadTabContent(next, function () {});
        } else if (tabs.length === 0) {
          activeTabId = null;
          var bar = document.getElementById(TAB_BAR_ID);
          if (bar) bar.style.display = 'none';
          var wrap = document.getElementById(TAB_BAR_WRAP_ID);
          var homeUrl = wrap && wrap.getAttribute('data-home-url');
          if (homeUrl) loadUrlInFrame(homeUrl, function () {});
        }
        return;
      }
      setActiveTab(id);
      loadTabContent(tab, function () {});
    });

    setActiveTab(id);
    if (focus !== false) loadTabContent(tab, function () {});
    return tab;
  }

  function initInitialTab() {
    var path = window.location.pathname || '/';
    var rawTitle = document.title || path;
    var parts = rawTitle.split(' - ');
    var title = parts[parts.length - 1].trim();
    if (!getFrame()) return;
    var bar = document.getElementById(TAB_BAR_ID);
    if (bar) bar.style.display = 'block';
    addTab(path, title, false);
  }

  function interceptFilterForms() {
    if (filterFormsBound) return;
    filterFormsBound = true;
    document.addEventListener(
      'submit',
      function (e) {
        var form = e.target && e.target.tagName === 'FORM' ? e.target : null;
        if (!form || form.method.toLowerCase() !== 'get') return;
        var frame = getFrame();
        if (!frame || !form.closest('#' + FRAME_ID)) return;
        e.preventDefault();
        var action = (form.getAttribute('action') || window.location.href).trim();
        if (!action) return;
        var params = new URLSearchParams(new FormData(form));
        var sep = action.indexOf('?') !== -1 ? '&' : '?';
        var url = params.toString() ? action + sep + params.toString() : action.replace(/\?.*$/, '');
        loadUrlInFrame(url, function (ok) {
          if (!ok) return;
          try {
            window.history.replaceState(null, '', url);
          } catch (err) {}
        });
      },
      true
    );
  }

  function interceptNavLinks() {
    if (listenersBound) return;
    listenersBound = true;
    document.addEventListener('click', function (e) {
      var link = e.target.closest('a[data-turbo-frame="' + FRAME_ID + '"]');
      if (!link || link.getAttribute('href') === '#' || link.getAttribute('href') === '') return;
      var href = link.getAttribute('href');
      if (!href || href.indexOf('javascript:') === 0) return;
      if (link.closest('#admin-tab-bar')) return;
      e.preventDefault();
      var title = (link.textContent || '').trim();
      addTab(href, title || undefined, true);
    });
  }

  function updateActiveTabOnFrameNavigate() {
    document.addEventListener('turbo:before-fetch-request', function (e) {
      var target = e.target;
      if (
        target.id === FRAME_ID ||
        (target.getAttribute && target.getAttribute('data-turbo-frame') === FRAME_ID)
      ) {
        try {
          var u = new URL(e.detail.url.toString(), window.location.origin);
          lastFrameLoadUrl = u.pathname;
        } catch (err) {
          lastFrameLoadUrl = e.detail.url;
        }
      }
    });
    document.addEventListener('turbo:frame-render', function (e) {
      if (e.target.id !== FRAME_ID || !activeTabId || !lastFrameLoadUrl) return;
      var tab = tabs.find(function (t) {
        return t.id === activeTabId;
      });
      if (tab) {
        tab.path = lastFrameLoadUrl;
        var tabLink = document.querySelector('[data-tab-id="' + activeTabId + '"]');
        if (tabLink) tabLink.setAttribute('data-path', lastFrameLoadUrl);
      }
      lastFrameLoadUrl = null;
    });
  }

  /** Um único handler: dispara admin:frame-updated e o callback da navegação que acabou de concluir. */
  function wireFrameLoadPipeline() {
    document.addEventListener('turbo:frame-load', function (e) {
      if (e.target.id !== FRAME_ID) return;
      var frame = e.target;
      frame.classList.remove('main-content-loading');
      try {
        document.dispatchEvent(new CustomEvent('admin:frame-updated', { detail: { frame: frame } }));
      } catch (err) {}
      var cb = pendingLoadCallback;
      pendingLoadCallback = null;
      if (cb) cb(true);
    });

    document.addEventListener('turbo:before-fetch-request', function (e) {
      if (e.target && e.target.id === FRAME_ID) {
        e.target.classList.add('main-content-loading');
      }
    });

    document.addEventListener('turbo:fetch-request-error', function () {
      var frame = getFrame();
      if (!frame || !frame.classList.contains('main-content-loading')) return;
      frame.classList.remove('main-content-loading');
      pendingLoadCallback = null;
    });
  }

  function init() {
    if (!document.getElementById(FRAME_ID)) return;
    if (!initialTabsReady) {
      initInitialTab();
      initialTabsReady = true;
    }
    interceptFilterForms();
    interceptNavLinks();
    updateActiveTabOnFrameNavigate();
  }

  wireFrameLoadPipeline();

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
  document.addEventListener('turbo:load', init);
})();
