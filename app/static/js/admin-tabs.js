/**
 * Painel de abas: cada link do menu abre em uma aba; se já existir, apenas foca nela.
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

  function findTabByPath(path) {
    return tabs.find(function (t) { return t.path === path; });
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

  function loadUrlInFrame(url, callback) {
    var frame = getFrame();
    if (!frame) return;
    fetch(url, {
      headers: {
        'Accept': 'text/html',
        'Turbo-Frame': FRAME_ID,
        'X-Requested-With': 'XMLHttpRequest'
      }
    })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        var parser = new DOMParser();
        var doc = parser.parseFromString(html, 'text/html');
        var frameEl = doc.querySelector('turbo-frame#' + FRAME_ID);
        if (frameEl) {
          frame.innerHTML = frameEl.innerHTML;
          try {
            document.dispatchEvent(new CustomEvent('admin:frame-updated', { detail: { frame: frame } }));
          } catch (err) {}
        }
        if (callback) callback(html);
      })
      .catch(function () {
        if (callback) callback(null);
      });
  }

  function loadTabContent(tab, callback) {
    if (!tab || !tab.path) return;
    lastFrameLoadUrl = tab.path;
    loadUrlInFrame(tab.path, function (html) {
      if (tab && html) {
        var parser = new DOMParser();
        var doc = parser.parseFromString(html, 'text/html');
        var titleEl = doc.querySelector('title');
        if (titleEl && titleEl.textContent) {
          var rawTitle = titleEl.textContent.trim();
          var parts = rawTitle.split(' - ');
          tab.title = parts[parts.length - 1].trim();
          var tabLink = document.querySelector('[data-tab-id="' + tab.id + '"] .admin-tab-title');
          if (tabLink) tabLink.textContent = tab.title;
        }
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
      '<a class="nav-link d-flex align-items-center" href="#" data-tab-id="' + id + '" data-path="' + (norm.replace(/"/g, '&quot;')) + '">' +
      '<span class="admin-tab-title">' + (title || norm) + '</span>' +
      '<span class="admin-tab-close ms-2" data-tab-id="' + id + '" aria-label="Fechar" title="Fechar aba">&times;</span>' +
      '</a>';
    list.appendChild(li);

    var link = li.querySelector('.nav-link');
    link.addEventListener('click', function (e) {
      e.preventDefault();
      if (e.target.closest('.admin-tab-close')) {
        var idx = tabs.findIndex(function (t) { return t.id === id; });
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
    document.addEventListener('submit', function (e) {
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
      loadUrlInFrame(url, function () {
        try {
          window.history.replaceState(null, '', url);
        } catch (err) {}
      });
    }, true);
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
      if (target.id === FRAME_ID || (target.getAttribute && target.getAttribute('data-turbo-frame') === FRAME_ID)) {
        lastFrameLoadUrl = e.detail.url.toString ? new URL(e.detail.url).pathname : e.detail.url;
      }
    });
    document.addEventListener('turbo:frame-render', function (e) {
      if (e.target.id !== FRAME_ID || !activeTabId || !lastFrameLoadUrl) return;
      var tab = tabs.find(function (t) { return t.id === activeTabId; });
      if (tab) {
        tab.path = lastFrameLoadUrl;
        var tabLink = document.querySelector('[data-tab-id="' + activeTabId + '"]');
        if (tabLink) tabLink.setAttribute('data-path', lastFrameLoadUrl);
      }
      lastFrameLoadUrl = null;
    });
  }

  function init() {
    if (!document.getElementById(FRAME_ID)) return;
    initInitialTab();
    interceptFilterForms();
    interceptNavLinks();
    updateActiveTabOnFrameNavigate();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
  document.addEventListener('turbo:load', init);
})();
