/**
 * Painel de abas: cada link do menu abre em uma aba; se já existir, apenas foca nela.
 * Implementação sem depender do lifecycle do Turbo para troca de conteúdo.
 *
 * O elemento #admin-tab-bar-wrap no base.html usa data-turbo-permanent para que,
 * após navegações Turbo (redirect pós-formulário em modal, etc.), a barra de abas
 * não seja substituída pelo template vazio do servidor.
 */
(function () {
  'use strict';

  var TAB_BAR_ID = 'admin-tab-bar';
  var TAB_BAR_WRAP_ID = 'admin-tab-bar-wrap';
  var TAB_LIST_ID = 'admin-tab-list';
  var FRAME_ID = 'main-content';

  var tabs = [];
  var activeTabId = null;
  var listenersBound = false;
  var filterFormsBound = false;
  var initialTabsReady = false;
  var currentRequestController = null;
  var requestCounter = 0;

  function normalizePath(href) {
    if (!href) return '';
    try {
      var a = document.createElement('a');
      a.href = href;
      return (a.pathname || '') + (a.search || '');
    } catch (e) {
      return href;
    }
  }

  function toAbsoluteUrl(url) {
    try {
      return new URL(url, window.location.origin).toString();
    } catch (e) {
      return url;
    }
  }

  function getFrame() {
    return document.getElementById(FRAME_ID);
  }

  function findTabByPath(path) {
    return tabs.find(function (t) { return t.path === path; });
  }

  function setActiveTab(id) {
    activeTabId = id;
    var list = document.getElementById(TAB_LIST_ID);
    if (!list) return;
    list.querySelectorAll('.nav-link').forEach(function (el) {
      el.classList.toggle('active', el.getAttribute('data-tab-id') === id);
    });
  }

  function setTabPath(tabId, path) {
    if (!tabId || !path) return;
    var normalized = normalizePath(path);
    var tab = tabs.find(function (t) { return t.id === tabId; });
    if (!tab) return;
    tab.path = normalized;
    var link = document.querySelector('[data-tab-id="' + tabId + '"]');
    if (link) link.setAttribute('data-path', normalized);
  }

  function updateTabTitleFromFrame(tab) {
    if (!tab) return;
    var frame = getFrame();
    if (!frame) return;
    var titleEl =
      frame.querySelector('h1.h3') ||
      frame.querySelector('h1.h4') ||
      frame.querySelector('h1') ||
      frame.querySelector('.h3') ||
      frame.querySelector('.h4');
    if (!titleEl || !titleEl.textContent.trim()) return;
    tab.title = titleEl.textContent.trim();
    var textEl = document.querySelector('[data-tab-id="' + tab.id + '"] .admin-tab-title');
    if (textEl) textEl.textContent = tab.title;
  }

  function executeScriptsSequentially(container, done) {
    var scripts = Array.prototype.slice.call(container.querySelectorAll('script'));
    if (!scripts.length) {
      if (done) done();
      return;
    }

    var i = 0;
    function runNext() {
      if (i >= scripts.length) {
        if (done) done();
        return;
      }
      var oldScript = scripts[i++];
      var newScript = document.createElement('script');
      Array.prototype.forEach.call(oldScript.attributes, function (attr) {
        newScript.setAttribute(attr.name, attr.value);
      });
      if (!oldScript.src) newScript.textContent = oldScript.textContent;
      newScript.async = false;

      if (oldScript.src) {
        newScript.onload = runNext;
        newScript.onerror = runNext;
      }

      oldScript.parentNode.replaceChild(newScript, oldScript);
      if (!oldScript.src) runNext();
    }

    runNext();
  }

  function loadUrlInFrame(url, callback) {
    var frame = getFrame();
    if (!frame) {
      if (callback) callback(null);
      return;
    }

    var absolute = toAbsoluteUrl(url);
    if (!absolute) {
      if (callback) callback(null);
      return;
    }

    if (currentRequestController) currentRequestController.abort();
    currentRequestController = new AbortController();
    requestCounter += 1;
    var reqId = requestCounter;

    frame.classList.add('main-content-loading');

    fetch(absolute, {
      headers: {
        Accept: 'text/html',
        'Turbo-Frame': FRAME_ID,
        'X-Requested-With': 'XMLHttpRequest',
      },
      signal: currentRequestController.signal,
    })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        if (reqId !== requestCounter) return;
        var parser = new DOMParser();
        var doc = parser.parseFromString(html, 'text/html');
        var newFrame = doc.querySelector('turbo-frame#' + FRAME_ID);
        frame.innerHTML = newFrame ? newFrame.innerHTML : html;

        executeScriptsSequentially(frame, function () {
          if (reqId !== requestCounter) return;
          frame.classList.remove('main-content-loading');
          try {
            document.dispatchEvent(new CustomEvent('admin:frame-updated', { detail: { frame: frame } }));
          } catch (e) {}
          if (callback) callback(true);
        });
      })
      .catch(function (err) {
        if (err && err.name === 'AbortError') return;
        if (reqId !== requestCounter) return;
        frame.classList.remove('main-content-loading');
        if (callback) callback(null);
      });
  }

  function loadTabContent(tab, callback) {
    if (!tab || !tab.path) return;
    loadUrlInFrame(tab.path, function (ok) {
      if (ok) updateTabTitleFromFrame(tab);
      if (callback) callback();
    });
  }

  function ensureTabBar() {
    var bar = document.getElementById(TAB_BAR_ID);
    if (!bar) return null;
    if (bar.style.display === 'none') bar.style.display = 'block';
    return bar;
  }

  function addTab(path, title, focus) {
    var norm = normalizePath(path);
    if (!norm) return null;

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
      '<a class="nav-link d-flex align-items-center" href="#" data-tab-id="' + id + '" data-path="' + norm.replace(/"/g, '&quot;') + '">' +
      '<span class="admin-tab-title">' + (title || norm) + '</span>' +
      '<span class="admin-tab-close ms-2" data-tab-id="' + id + '" aria-label="Close tab" title="Close tab">&times;</span>' +
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
    if (!getFrame()) return;
    var path = (window.location.pathname || '/') + (window.location.search || '');
    var rawTitle = document.title || path;
    var parts = rawTitle.split(' - ');
    var title = parts[parts.length - 1].trim();
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

      setTabPath(activeTabId, url);
      loadUrlInFrame(url, function (ok) {
        if (!ok) return;
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
      if (!link) return;
      if (link.closest('#admin-tab-bar')) return;

      var href = link.getAttribute('href');
      if (!href || href === '#' || href.indexOf('javascript:') === 0) return;

      e.preventDefault();
      var title = (link.textContent || '').trim();
      addTab(href, title || undefined, true);
    });
  }

  function init() {
    if (!getFrame()) return;
    if (!initialTabsReady) {
      initInitialTab();
      initialTabsReady = true;
    }
    interceptFilterForms();
    interceptNavLinks();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
  document.addEventListener('turbo:load', init);
})();
