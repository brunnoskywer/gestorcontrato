/**
 * Modais reutilizáveis do admin: confirmação (excluir), formulário (criar/editar) e mensagens (flash).
 * Máscaras CPF e CNPJ. Compatível com Turbo Drive.
 */
(function () {
  'use strict';

  function maskCpf(value) {
    var d = (value || '').replace(/\D/g, '').slice(0, 11);
    if (d.length <= 3) return d;
    if (d.length <= 6) return d.replace(/(\d{3})(\d+)/, '$1.$2');
    if (d.length <= 9) return d.replace(/(\d{3})(\d{3})(\d+)/, '$1.$2.$3');
    return d.replace(/(\d{3})(\d{3})(\d{3})(\d+)/, '$1.$2.$3-$4');
  }

  function maskCnpj(value) {
    var d = (value || '').replace(/\D/g, '').slice(0, 14);
    if (d.length <= 2) return d;
    if (d.length <= 5) return d.replace(/(\d{2})(\d+)/, '$1.$2');
    if (d.length <= 8) return d.replace(/(\d{2})(\d{3})(\d+)/, '$1.$2.$3');
    if (d.length <= 12) return d.replace(/(\d{2})(\d{3})(\d{3})(\d+)/, '$1.$2.$3/$4');
    return d.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d+)/, '$1.$2.$3/$4-$5');
  }

  function applyMasks(container) {
    if (!container || !container.querySelector) return;
    var cpfInputs = container.querySelectorAll('[data-mask="cpf"]');
    var cnpjInputs = container.querySelectorAll('[data-mask="cnpj"]');

    cpfInputs.forEach(function (input) {
      if (input.dataset.maskApplied) return;
      input.dataset.maskApplied = '1';
      input.value = maskCpf(input.value);
      input.addEventListener('input', function () {
        input.value = maskCpf(input.value);
      });
    });

    cnpjInputs.forEach(function (input) {
      if (input.dataset.maskApplied) return;
      input.dataset.maskApplied = '1';
      input.value = maskCnpj(input.value);
      input.addEventListener('input', function () {
        input.value = maskCnpj(input.value);
      });
    });

    var form = container.tagName === 'FORM' ? container : container.querySelector('form');
    if (form && (cpfInputs.length || cnpjInputs.length)) {
      form.addEventListener('submit', function stripMasksOnce() {
        form.querySelectorAll('[data-mask="cpf"]').forEach(function (el) {
          el.value = (el.value || '').replace(/\D/g, '');
        });
        form.querySelectorAll('[data-mask="cnpj"]').forEach(function (el) {
          el.value = (el.value || '').replace(/\D/g, '');
        });
      }, { capture: true, once: true });
    }
  }

  function initConfirmModal() {
    var modal = document.getElementById('adminConfirmModal');
    if (!modal) return;
    modal.addEventListener('show.bs.modal', function (e) {
      var trigger = e.relatedTarget;
      if (!trigger) return;
      var action = trigger.getAttribute('data-confirm-action');
      var message = trigger.getAttribute('data-confirm-message');
      var form = document.getElementById('adminConfirmForm');
      var msgEl = document.getElementById('adminConfirmMessage');
      if (form && action) form.setAttribute('action', action);
      if (msgEl && message) msgEl.textContent = message;
    });
  }

  function runScriptsInElement(container) {
    if (!container || !container.querySelectorAll) return;
    container.querySelectorAll('script').forEach(function (oldScript) {
      if (oldScript.src) return;
      var script = document.createElement('script');
      script.textContent = oldScript.textContent;
      (oldScript.parentNode || document.body).appendChild(script);
      script.remove();
    });
  }

  function openFormModal(url, title) {
    var modalEl = document.getElementById('adminFormModal');
    var bodyEl = document.getElementById('adminFormModalBody');
    var titleEl = document.getElementById('adminFormModalLabel');
    if (!modalEl || !bodyEl) return;
    bodyEl.innerHTML = '<p class="text-muted text-center py-3">Carregando...</p>';
    if (titleEl) titleEl.textContent = title || 'Formulário';
    var modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
    fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'text/html' } })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        bodyEl.innerHTML = html;
        runScriptsInElement(bodyEl);
        applyMasks(bodyEl);
        initSearchInputs(bodyEl);
      })
      .catch(function () {
        bodyEl.innerHTML = '<p class="text-danger text-center py-3">Erro ao carregar o formulário.</p>';
      });
  }
  window.openFormModal = openFormModal;

  function showMessageModal(message, title) {
    var modalEl = document.getElementById('adminMessageModal');
    var bodyEl = document.getElementById('adminMessageModalBody');
    var titleEl = document.getElementById('adminMessageModalLabel');
    if (!modalEl || !bodyEl) return;
    bodyEl.textContent = message || '';
    if (titleEl) titleEl.textContent = title || 'Atenção';
    var modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }
  window.showMessageModal = showMessageModal;

  var pendingConfirmCallback = null;
  function showConfirmModal(message, title, confirmLabel, onConfirm) {
    var modalEl = document.getElementById('adminConfirmActionModal');
    var bodyEl = document.getElementById('adminConfirmActionMessage');
    var titleEl = document.getElementById('adminConfirmActionModalLabel');
    var btnEl = document.getElementById('adminConfirmActionBtn');
    if (!modalEl || !bodyEl || !btnEl) return;
    bodyEl.textContent = message || '';
    if (titleEl) titleEl.textContent = title || 'Confirmar';
    btnEl.textContent = confirmLabel || 'Confirmar';
    pendingConfirmCallback = typeof onConfirm === 'function' ? onConfirm : null;
    var modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }
  window.showConfirmModal = showConfirmModal;

  function initConfirmActionModal() {
    var modalEl = document.getElementById('adminConfirmActionModal');
    var btnEl = document.getElementById('adminConfirmActionBtn');
    if (!modalEl || !btnEl) return;
    btnEl.addEventListener('click', function () {
      if (pendingConfirmCallback) {
        pendingConfirmCallback();
        pendingConfirmCallback = null;
      }
      var modal = window.bootstrap.Modal.getInstance(modalEl);
      if (modal) modal.hide();
    });
  }

  function initFormModal() {
    var modalEl = document.getElementById('adminFormModal');
    var bodyEl = document.getElementById('adminFormModalBody');
    var titleEl = document.getElementById('adminFormModalLabel');
    if (!modalEl || !bodyEl) return;

    bodyEl.addEventListener('click', function (e) {
      var link = e.target.closest('a.admin-calendar-month-nav[data-replace-modal-body]');
      if (link && link.href) {
        e.preventDefault();
        bodyEl.innerHTML = '<p class="text-muted text-center py-3">Carregando...</p>';
        fetch(link.href, { headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'text/html' } })
          .then(function (r) { return r.text(); })
          .then(function (html) {
            bodyEl.innerHTML = html;
            runScriptsInElement(bodyEl);
          })
          .catch(function () {
            bodyEl.innerHTML = '<p class="text-danger text-center py-3">Erro ao carregar o calendário.</p>';
          });
      }
    });

    document.addEventListener('click', function (e) {
      var trigger = e.target.closest('[data-form-url]');
      if (!trigger) return;
      e.preventDefault();
      var url = trigger.getAttribute('data-form-url');
      var title = trigger.getAttribute('data-form-title') || 'Form';
      if (!url) return;
      openFormModal(url, title);
    });
  }

  function syncSelectAllState(table) {
    var selectAll = table.querySelector('thead .select-all');
    if (!selectAll) return;
    var all = table.querySelectorAll('tbody .row-select');
    var checked = table.querySelectorAll('tbody .row-select:checked');
    selectAll.checked = all.length > 0 && all.length === checked.length;
  }

  function initTableListRowClick(container) {
    var root = container || document;
    root.querySelectorAll('table.table-list').forEach(function (table) {
      if (!container && table.getAttribute('data-row-click-inited') === '1') return;
      if (!container) table.setAttribute('data-row-click-inited', '1');
      table.querySelectorAll('tbody tr').forEach(function (tr) {
        var cb = tr.querySelector('.row-select');
        if (!cb) return;
        tr.style.cursor = 'pointer';
        tr.addEventListener('click', function (e) {
          if (e.target.closest('a, button, .btn') || e.target === cb || e.target.closest('input[type="checkbox"]')) return;
          e.preventDefault();
          cb.checked = !cb.checked;
          if (cb.checked) tr.classList.add('table-active'); else tr.classList.remove('table-active');
          syncSelectAllState(table);
        });
      });
      table.querySelectorAll('tbody .row-select').forEach(function (cb) {
        cb.addEventListener('change', function () {
          var tr = cb.closest('tr');
          if (tr) {
            if (cb.checked) tr.classList.add('table-active'); else tr.classList.remove('table-active');
          }
          syncSelectAllState(table);
        });
        var tr = cb.closest('tr');
        if (cb.checked && tr) tr.classList.add('table-active');
      });
      var selectAll = table.querySelector('thead .select-all');
      if (selectAll) {
        selectAll.addEventListener('change', function () {
          table.querySelectorAll('tbody tr').forEach(function (tr) {
            var cb = tr.querySelector('.row-select');
            if (cb) {
              if (selectAll.checked) tr.classList.add('table-active'); else tr.classList.remove('table-active');
            }
          });
        });
      }
    });
  }

  function initToolbar() {
    document.querySelectorAll('.admin-toolbar').forEach(function (toolbar) {
      var tableId = toolbar.getAttribute('data-table-id');
      var table = document.getElementById(tableId);
      if (!table) return;

      function getSelectedIds() {
        var ids = [];
        table.querySelectorAll('tbody .row-select:checked').forEach(function (cb) {
          if (cb.value) ids.push(cb.value);
        });
        return ids;
      }

      function getFirstSelectedRow() {
        var row = table.querySelector('tbody .row-select:checked');
        return row ? row.closest('tr') : null;
      }

      toolbar.querySelector('.admin-toolbar-select-all')?.addEventListener('click', function () {
        table.querySelectorAll('tbody .row-select').forEach(function (cb) {
          cb.checked = true;
        });
        var selectAll = table.querySelector('thead .select-all');
        if (selectAll) selectAll.checked = true;
      });

      toolbar.querySelector('.admin-toolbar-deselect')?.addEventListener('click', function () {
        table.querySelectorAll('.row-select').forEach(function (cb) {
          cb.checked = false;
        });
        var selectAll = table.querySelector('thead .select-all');
        if (selectAll) selectAll.checked = false;
      });

      var insertUrl = toolbar.getAttribute('data-insert-url');
      var insertTitle = toolbar.getAttribute('data-insert-title');
      toolbar.querySelector('.admin-toolbar-insert')?.addEventListener('click', function () {
        if (!insertUrl) return;
        openFormModal(insertUrl, insertTitle || 'Inserir');
      });

      var editTpl = toolbar.getAttribute('data-edit-url-template');
      toolbar.querySelector('.admin-toolbar-edit')?.addEventListener('click', function () {
        if (!editTpl) return;
        var ids = getSelectedIds();
        if (ids.length === 0) {
          showMessageModal('Selecione um registro para editar.', 'Atenção');
          return;
        }
        if (ids.length > 1) {
          showMessageModal('Selecione apenas um registro para editar.', 'Atenção');
          return;
        }
        openFormModal(editTpl.replace('{id}', ids[0]), 'Editar');
      });

      var deleteUrl = toolbar.getAttribute('data-delete-bulk-url');
      toolbar.querySelector('.admin-toolbar-delete')?.addEventListener('click', function () {
        if (!deleteUrl) return;
        var ids = getSelectedIds();
        if (ids.length === 0) {
          showMessageModal('Selecione um ou mais registros para excluir.', 'Atenção');
          return;
        }
        var count = ids.length;
        showConfirmModal(
          'Excluir ' + count + ' registro(s) selecionado(s)?',
          'Confirmar',
          'Excluir',
          function () {
            var form = document.createElement('form');
            form.method = 'POST';
            form.action = deleteUrl;
            form.setAttribute('data-turbo-frame', 'main-content');
            ids.forEach(function (id) {
              var input = document.createElement('input');
              input.type = 'hidden';
              input.name = 'ids';
              input.value = id;
              form.appendChild(input);
            });
            document.body.appendChild(form);
            form.submit();
          }
        );
      });

      var faltaTpl = toolbar.getAttribute('data-falta-url-template');
      var faltaTitle = toolbar.getAttribute('data-falta-title') || 'Registrar falta';
      toolbar.querySelector('.admin-toolbar-falta')?.addEventListener('click', function () {
        if (!faltaTpl) return;
        var ids = getSelectedIds();
        if (ids.length === 0) {
          showMessageModal('Selecione um contrato para registrar falta.', 'Atenção');
          return;
        }
        if (ids.length > 1) {
          showMessageModal('Selecione apenas um contrato para registrar falta.', 'Atenção');
          return;
        }
        openFormModal(faltaTpl.replace('{id}', ids[0]), faltaTitle);
      });

      var calendarTpl = toolbar.getAttribute('data-calendar-url-template');
      var calendarTitle = toolbar.getAttribute('data-calendar-title') || 'Calendário de faltas';
      toolbar.querySelector('.admin-toolbar-calendar')?.addEventListener('click', function () {
        if (!calendarTpl) return;
        var ids = getSelectedIds();
        if (ids.length === 0) {
          showMessageModal('Selecione um contrato para ver o calendário de faltas.', 'Atenção');
          return;
        }
        if (ids.length > 1) {
          showMessageModal('Selecione apenas um contrato para ver o calendário de faltas.', 'Atenção');
          return;
        }
        openFormModal(calendarTpl.replace('{id}', ids[0]), calendarTitle);
      });

      if (toolbar.getAttribute('data-finance-actions') === '1') {
        var transferUrl = toolbar.getAttribute('data-transfer-url');
        toolbar.querySelector('.admin-toolbar-transfer')?.addEventListener('click', function () {
          if (transferUrl) openFormModal(transferUrl, 'Transferência entre contas');
        });

        var approveTpl = toolbar.getAttribute('data-approve-url-template');
        toolbar.querySelector('.admin-toolbar-approve')?.addEventListener('click', function () {
          if (!approveTpl) return;
          var cb = table.querySelector('tbody tr[data-settled="0"] .row-select:checked');
          if (!cb) {
            showMessageModal('Selecione um lançamento pendente para aprovar.', 'Atenção');
            return;
          }
          var id = cb.closest('tr').getAttribute('data-id');
          openFormModal(approveTpl.replace('{id}', id), 'Aprovar lançamento');
        });

        var reopenUrl = toolbar.getAttribute('data-reopen-bulk-url');
        toolbar.querySelector('.admin-toolbar-reopen')?.addEventListener('click', function () {
          if (!reopenUrl) return;
          var rows = table.querySelectorAll('tbody tr[data-settled="1"]');
          var ids = [];
          rows.forEach(function (tr) {
            var cb = tr.querySelector('.row-select:checked');
            if (cb && cb.value) ids.push(cb.value);
          });
          if (ids.length === 0) {
showMessageModal('Selecione um ou mais lançamentos quitados para reabrir.', 'Atenção');
          return;
          }
          var reopenCount = ids.length;
          showConfirmModal(
            'Reabrir ' + reopenCount + ' lançamento(s) selecionado(s)?',
            'Confirmar',
            'Reabrir',
            function () {
              var formData = new FormData();
              ids.forEach(function (id) {
                formData.append('ids', id);
              });
              fetch(reopenUrl, {
                method: 'POST',
                body: formData,
                headers: {
                  'Accept': 'text/html',
                  'X-Requested-With': 'XMLHttpRequest'
                },
                redirect: 'follow'
              })
                .then(function (r) { return r.text(); })
                .then(function (html) {
                  var frame = document.getElementById('main-content');
                  if (!frame) return;
                  var parser = new DOMParser();
                  var doc = parser.parseFromString(html, 'text/html');
                  var newFrame = doc.querySelector('turbo-frame#main-content');
                  if (newFrame) {
                    frame.innerHTML = newFrame.innerHTML;
                    runScriptsInElement(frame);
                    setTimeout(function () {
                      initToolbar();
                      initTableListRowClick(frame);
                      initSearchInputs(frame);
                      if (typeof window.dispatchEvent === 'function') {
                        window.dispatchEvent(new CustomEvent('admin:frame-updated', { detail: { frame: frame } }));
                      }
                    }, 0);
                  }
                })
                .catch(function () {
                  showMessageModal('Erro ao reabrir lançamento(s). Tente novamente.', 'Erro');
                });
            }
          );
        });
      }
    });
  }

  function initSearchInputs(container) {
    if (!container || !container.querySelectorAll) return;

    var inputs = container.querySelectorAll('.search-entity-input');
    if (!inputs.length) return;

    inputs.forEach(function (input) {
      if (input.dataset.searchBound) return;
      input.dataset.searchBound = '1';

      var dropdown = input.parentElement.querySelector('.search-entity-dropdown');
      var hiddenId = input.parentElement.querySelector('input[type="hidden"][name="' + input.dataset.targetHidden + '"]');
      var searchUrl = input.getAttribute('data-search-url');
      var debounceTimer = null;

      function hideDropdown() {
        if (dropdown) {
          dropdown.style.display = 'none';
          dropdown.innerHTML = '';
        }
      }

      function performSearch(term) {
        if (!searchUrl || term.length < 3) {
          hideDropdown();
          return;
        }
        var url = searchUrl + '?q=' + encodeURIComponent(term);
        var typeSource = input.getAttribute('data-supplier-type-source');
        if (typeSource) {
          var typeSelect = document.getElementById(typeSource);
          if (typeSelect && typeSelect.value) {
            url += '&type=' + encodeURIComponent(typeSelect.value);
          }
        }
        fetch(url, {
          headers: { 'Accept': 'application/json' }
        })
          .then(function (r) { return r.json(); })
          .then(function (items) {
            if (!Array.isArray(items) || !items.length) {
              hideDropdown();
              return;
            }
            dropdown.innerHTML = '';
            items.forEach(function (item) {
              var btn = document.createElement('button');
              btn.type = 'button';
              btn.className = 'list-group-item list-group-item-action py-1';
              btn.textContent = item.label + (item.secondary ? ' · ' + item.secondary : '');
              btn.addEventListener('click', function () {
                input.value = item.label;
                if (hiddenId) hiddenId.value = item.id;
                hideDropdown();
              });
              dropdown.appendChild(btn);
            });
            dropdown.style.display = 'block';
          })
          .catch(hideDropdown);
      }

      input.addEventListener('input', function () {
        if (hiddenId && input.value.trim() === '') {
          hiddenId.value = '';
        }
        var term = input.value.trim();
        if (debounceTimer) clearTimeout(debounceTimer);
        debounceTimer = setTimeout(function () {
          performSearch(term);
        }, 300);
      });

      input.addEventListener('focus', function () {
        var term = input.value.trim();
        if (term.length >= 3) {
          performSearch(term);
        }
      });

      document.addEventListener('click', function (e) {
        if (!dropdown.contains(e.target) && e.target !== input) {
          hideDropdown();
        }
      });
    });
  }

  function showFlashModalIfNeeded() {
    var wrap = document.getElementById('adminFlashModalWrap');
    if (!wrap || !wrap.querySelector('.modal-body').innerText.trim()) return;
    var modal = window.bootstrap.Modal.getOrCreateInstance(wrap);
    modal.show();
    // Fecha ao clicar em qualquer lugar (conteúdo ou backdrop)
    var content = wrap.querySelector('.modal-content');
    if (content) {
      content.addEventListener('click', function closeFlash() {
        modal.hide();
        content.removeEventListener('click', closeFlash);
      });
    }
  }

  function initConfirmSubmitForms() {
    document.addEventListener('submit', function (e) {
      var form = e.target && e.target.closest && e.target.closest('form.admin-confirm-submit');
      if (!form) return;
      e.preventDefault();
      var message = form.getAttribute('data-confirm-message') || 'Confirmar ação?';
      var title = form.getAttribute('data-confirm-title') || 'Confirmar';
      var confirmLabel = form.getAttribute('data-confirm-label') || 'Confirmar';
      showConfirmModal(message, title, confirmLabel, function () {
        form.submit();
      });
    }, true);
  }

  function init() {
    initConfirmModal();
    initConfirmActionModal();
    initFormModal();
    initConfirmSubmitForms();
    initToolbar();
    initTableListRowClick();
    initSearchInputs(document);
    showFlashModalIfNeeded();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  document.addEventListener('turbo:load', init);

  document.addEventListener('admin:frame-updated', function (e) {
    var container = (e.detail && e.detail.frame) || document;
    initToolbar();
    initTableListRowClick(container);
    initSearchInputs(container);
    runScriptsInElement(container);
  });

  document.addEventListener('turbo:frame-render', function (e) {
    if (e.target.id === 'main-content') {
      initToolbar();
      initTableListRowClick();
      runScriptsInElement(e.target);
      var modalEl = document.getElementById('adminFormModal');
      if (modalEl) {
        var modal = window.bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }
    }
  });
})();
