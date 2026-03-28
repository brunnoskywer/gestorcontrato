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
  var TABS_SESSION_KEY = 'gestorContrato-admin-tabs-v1';

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

  function saveTabsState() {
    try {
      if (!tabs.length) {
        sessionStorage.removeItem(TABS_SESSION_KEY);
        return;
      }
      sessionStorage.setItem(
        TABS_SESSION_KEY,
        JSON.stringify({
          tabs: tabs.map(function (t) {
            return { id: t.id, path: t.path, title: t.title };
          }),
          activeTabId: activeTabId,
        })
      );
    } catch (e) {}
  }

  function setActiveTab(id) {
    activeTabId = id;
    var list = document.getElementById(TAB_LIST_ID);
    if (!list) return;
    list.querySelectorAll('.nav-link').forEach(function (el) {
      el.classList.toggle('active', el.getAttribute('data-tab-id') === id);
    });
    saveTabsState();
  }

  function setTabPath(tabId, path) {
    if (!tabId || !path) return;
    var normalized = normalizePath(path);
    var tab = tabs.find(function (t) { return t.id === tabId; });
    if (!tab) return;
    tab.path = normalized;
    var link = document.querySelector('[data-tab-id="' + tabId + '"]');
    if (link) link.setAttribute('data-path', normalized);
    saveTabsState();
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
    saveTabsState();
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

  function attachTabListeners(li, tab) {
    var id = tab.id;
    var link = li.querySelector('.nav-link');
    if (!link) return;
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
          saveTabsState();
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
  }

  function createTabListItem(tab) {
    var li = document.createElement('li');
    li.className = 'nav-item admin-tab-item';
    var a = document.createElement('a');
    a.className = 'nav-link d-flex align-items-center';
    a.href = '#';
    a.setAttribute('data-tab-id', tab.id);
    a.setAttribute('data-path', tab.path);
    var spanTitle = document.createElement('span');
    spanTitle.className = 'admin-tab-title';
    spanTitle.textContent = tab.title || tab.path;
    var spanClose = document.createElement('span');
    spanClose.className = 'admin-tab-close ms-2';
    spanClose.setAttribute('data-tab-id', tab.id);
    spanClose.setAttribute('aria-label', 'Fechar aba');
    spanClose.setAttribute('title', 'Fechar aba');
    spanClose.textContent = '\u00d7';
    a.appendChild(spanTitle);
    a.appendChild(spanClose);
    li.appendChild(a);
    attachTabListeners(li, tab);
    return li;
  }

  function restoreTabsFromSession() {
    try {
      var raw = sessionStorage.getItem(TABS_SESSION_KEY);
      if (!raw) return false;
      var data = JSON.parse(raw);
      if (!data || !Array.isArray(data.tabs) || data.tabs.length === 0) return false;

      var list = document.getElementById(TAB_LIST_ID);
      if (!list) return false;

      tabs = [];
      list.innerHTML = '';

      data.tabs.forEach(function (t) {
        if (!t || !t.id || !t.path) return;
        var tab = { id: t.id, path: t.path, title: t.title || t.path };
        tabs.push(tab);
        list.appendChild(createTabListItem(tab));
      });

      if (!tabs.length) return false;

      ensureTabBar();
      var aid = data.activeTabId;
      if (!tabs.some(function (x) { return x.id === aid; })) aid = tabs[0].id;
      activeTabId = aid;
      list.querySelectorAll('.nav-link').forEach(function (el) {
        el.classList.toggle('active', el.getAttribute('data-tab-id') === aid);
      });
      saveTabsState();
      return true;
    } catch (e) {
      return false;
    }
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

    list.appendChild(createTabListItem(tab));

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

  /** Se o Turbo/substituição de página esvaziar a lista mas o estado em memória existir, recria as abas. */
  function syncTabBarDomIfEmpty() {
    var list = document.getElementById(TAB_LIST_ID);
    if (!list || !tabs.length) return;
    if (list.children.length > 0) return;
    tabs.forEach(function (tab) {
      list.appendChild(createTabListItem(tab));
    });
    var aid = activeTabId && tabs.some(function (t) { return t.id === activeTabId; }) ? activeTabId : tabs[0].id;
    activeTabId = aid;
    list.querySelectorAll('.nav-link').forEach(function (el) {
      el.classList.toggle('active', el.getAttribute('data-tab-id') === aid);
    });
    ensureTabBar();
    saveTabsState();
  }

  function init() {
    if (!getFrame()) return;
    if (!initialTabsReady) {
      if (!restoreTabsFromSession()) {
        initInitialTab();
      } else {
        var bar = document.getElementById(TAB_BAR_ID);
        if (bar) bar.style.display = 'block';
      }
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
  document.addEventListener('turbo:load', function () {
    init();
    syncTabBarDomIfEmpty();
  });
})();
