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

  /** Brazilian currency: display as 1.234,56 (comma as decimal separator). */
  function maskCurrency(value) {
    if (value === null || value === undefined || value === '') return '';
    var str = String(value).trim();
    if (str.indexOf(',') !== -1 || str.indexOf('.') !== -1) {
      var num = parseFloat(str.replace(/\./g, '').replace(',', '.'));
      if (isNaN(num)) return '';
      var intPart = Math.floor(Math.abs(num));
      var decPart = Math.round((Math.abs(num) - intPart) * 100);
      if (decPart >= 100) { decPart = 0; intPart += 1; }
      var sign = num < 0 ? '-' : '';
      var intStr = intPart.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
      var decStr = decPart.toString().padStart(2, '0');
      return sign + intStr + ',' + decStr;
    }
    var digits = str.replace(/\D/g, '');
    if (digits.length === 0) return '';
    var cents = digits.length <= 2 ? digits.padStart(2, '0') : digits.slice(-2);
    var intDigits = digits.length <= 2 ? '0' : digits.slice(0, -2);
    var intPart = intDigits.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return intPart + ',' + cents;
  }

  /** Convert displayed currency to dot-decimal for form submit (e.g. 1.234,56 -> 1234.56). */
  function parseCurrencyForSubmit(value) {
    if (!value || !String(value).trim()) return '';
    var s = String(value).trim().replace(/\./g, '').replace(',', '.');
    var num = parseFloat(s);
    return isNaN(num) ? '' : num.toFixed(2);
  }

  function applyMasks(container) {
    if (!container || !container.querySelector) return;
    var cpfInputs = container.querySelectorAll('[data-mask="cpf"]');
    var cnpjInputs = container.querySelectorAll('[data-mask="cnpj"]');
    var currencyInputs = container.querySelectorAll('[data-mask="currency"]');

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

    currencyInputs.forEach(function (input) {
      if (input.dataset.maskApplied) return;
      input.dataset.maskApplied = '1';
      // Não formatamos durante a digitação para não mexer no cursor.
      // Apenas garantimos que o valor inicial vindo do backend esteja no formato esperado.
      if (input.value) {
        input.value = String(input.value).replace(/[^0-9,]/g, '').replace(/\./g, ',');
      }
    });

    var form = container.tagName === 'FORM' ? container : container.querySelector('form');
    if (form && (cpfInputs.length || cnpjInputs.length || currencyInputs.length)) {
      form.addEventListener('submit', function stripMasksOnce() {
        form.querySelectorAll('[data-mask="cpf"]').forEach(function (el) {
          el.value = (el.value || '').replace(/\D/g, '');
        });
        form.querySelectorAll('[data-mask="cnpj"]').forEach(function (el) {
          el.value = (el.value || '').replace(/\D/g, '');
        });
        // Para currency, só limpamos caracteres inválidos e deixamos o backend interpretar
        // a vírgula como separador decimal (ex.: \"7,00\" -> 7.00).
        form.querySelectorAll('[data-mask=\"currency\"]').forEach(function (el) {
          var raw = (el.value || '').trim();
          if (!raw) return;
          raw = raw.replace(/[^0-9,]/g, '').replace(/\./g, ',');
          var parts = raw.split(',');
          if (parts.length > 2) {
            raw = parts[0] + ',' + parts.slice(1).join('');
          }
          el.value = raw;
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
      if (form) {
        var nextInput = form.querySelector('input[name="next"]');
        if (!nextInput) {
          nextInput = document.createElement('input');
          nextInput.type = 'hidden';
          nextInput.name = 'next';
          form.appendChild(nextInput);
        }
        nextInput.value = window.location.pathname + window.location.search;
      }
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

  function openFormModal(url, title, size) {
    var modalEl = document.getElementById('adminFormModal');
    var bodyEl = document.getElementById('adminFormModalBody');
    var titleEl = document.getElementById('adminFormModalLabel');
    var dialogEl = modalEl ? modalEl.querySelector('.modal-dialog') : null;
    if (!modalEl || !bodyEl) return;
    bodyEl.innerHTML = '<p class="text-muted text-center py-3">Carregando...</p>';
    if (titleEl) titleEl.textContent = title || 'Formulário';
    if (dialogEl) {
      dialogEl.classList.remove('modal-sm', 'modal-md', 'modal-lg');
      if (size === 'sm') dialogEl.classList.add('modal-sm');
      else if (size === 'md') dialogEl.classList.add('modal-md');
      else dialogEl.classList.add('modal-lg');
    }
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

  /**
   * HTMLFormElement.submit() não dispara o evento submit — o Turbo não intercepta e a página recarrega inteira (perde abas).
   * requestSubmit() dispara submit como um clique real no formulário.
   */
  function submitFormForTurbo(form) {
    if (!form) return;
    try {
      if (typeof form.requestSubmit === 'function') {
        form.requestSubmit();
        return;
      }
    } catch (e) {}
    var btn = document.createElement('button');
    btn.type = 'submit';
    btn.hidden = true;
    form.appendChild(btn);
    btn.click();
    form.removeChild(btn);
  }

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

    function replaceModalBodyWithUrl(url) {
      bodyEl.innerHTML = '<p class="text-muted text-center py-3">Carregando...</p>';
      fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'text/html' } })
        .then(function (r) { return r.text(); })
        .then(function (html) {
          bodyEl.innerHTML = html;
          runScriptsInElement(bodyEl);
          applyMasks(bodyEl);
          initSearchInputs(bodyEl);
        })
        .catch(function () {
          bodyEl.innerHTML = '<p class="text-danger text-center py-3">Erro ao carregar.</p>';
        });
    }

    bodyEl.addEventListener('click', function (e) {
      var link = e.target.closest('a.admin-calendar-month-nav[data-replace-modal-body]');
      if (link && link.href) {
        e.preventDefault();
        replaceModalBodyWithUrl(link.href);
      }
      var clearLink = e.target.closest('a.admin-modal-filter-clear');
      if (clearLink && clearLink.href) {
        e.preventDefault();
        replaceModalBodyWithUrl(clearLink.href);
      }
    });

    bodyEl.addEventListener('submit', function (e) {
      var form = e.target.closest('form[data-replace-modal-body]');
      if (!form) return;
      e.preventDefault();
      var action = form.getAttribute('action') || '';
      var formData = new FormData(form);
      var params = new URLSearchParams(formData).toString();
      var url = params ? action + (action.indexOf('?') !== -1 ? '&' : '?') + params : action;
      replaceModalBodyWithUrl(url);
    });

    document.addEventListener('click', function (e) {
      var trigger = e.target.closest('[data-form-url]');
      if (!trigger) return;
      e.preventDefault();
      var url = trigger.getAttribute('data-form-url');
      var title = trigger.getAttribute('data-form-title') || 'Form';
      var size = trigger.getAttribute('data-modal-size') || '';
      if (!url) return;
      openFormModal(url, title, size);
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

      // Sorting by header click (except selection checkbox column)
      var headers = table.querySelectorAll('thead th');
      headers.forEach(function (th, index) {
        var hasSelectAll = th.querySelector('.select-all');
        if (hasSelectAll) return; // skip checkbox column
        th.style.cursor = 'pointer';
        th.addEventListener('click', function () {
          var tbody = table.querySelector('tbody');
          if (!tbody) return;
          var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
          var currentOrder = th.getAttribute('data-sort-order') || 'none';
          var newOrder = currentOrder === 'asc' ? 'desc' : 'asc';
          // reset others
          headers.forEach(function (h) {
            if (h !== th) {
              h.removeAttribute('data-sort-order');
              h.classList.remove('table-sort-asc', 'table-sort-desc');
            }
          });
          th.setAttribute('data-sort-order', newOrder);
          th.classList.remove('table-sort-asc', 'table-sort-desc');
          th.classList.add(newOrder === 'asc' ? 'table-sort-asc' : 'table-sort-desc');

          var isNumeric = th.classList.contains('text-end') || th.getAttribute('data-sort-type') === 'number';

          rows.sort(function (a, b) {
            var aCell = a.children[index];
            var bCell = b.children[index];
            if (!aCell || !bCell) return 0;
            var aText = (aCell.innerText || aCell.textContent || '').trim();
            var bText = (bCell.innerText || bCell.textContent || '').trim();

            if (isNumeric) {
              var aNum = parseFloat(aText.replace(/[^\d,-]/g, '').replace(/\./g, '').replace(',', '.')) || 0;
              var bNum = parseFloat(bText.replace(/[^\d,-]/g, '').replace(/\./g, '').replace(',', '.')) || 0;
              return newOrder === 'asc' ? aNum - bNum : bNum - aNum;
            } else {
              var cmp = aText.localeCompare(bText, 'pt-BR', { sensitivity: 'base' });
              return newOrder === 'asc' ? cmp : -cmp;
            }
          });

          rows.forEach(function (r) {
            tbody.appendChild(r);
          });
        });
      });

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
            // Preserva filtros atuais após a ação
            var nextInput = document.createElement('input');
            nextInput.type = 'hidden';
            nextInput.name = 'next';
            nextInput.value = window.location.pathname + window.location.search;
            form.appendChild(nextInput);
            ids.forEach(function (id) {
              var input = document.createElement('input');
              input.type = 'hidden';
              input.name = 'ids';
              input.value = id;
              form.appendChild(input);
            });
            document.body.appendChild(form);
            submitFormForTurbo(form);
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

      var revenueBatchesUrl = toolbar.getAttribute('data-revenue-batches-url');
      var revenueBatchesTitle = toolbar.getAttribute('data-revenue-batches-title') || 'Processar receitas';
      toolbar.querySelector('.admin-toolbar-revenue-batches')?.addEventListener('click', function () {
        if (revenueBatchesUrl) openFormModal(revenueBatchesUrl, revenueBatchesTitle);
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
          var next = window.location.pathname + window.location.search;
          var url = approveTpl.replace('{id}', id) + '?next=' + encodeURIComponent(next);
          openFormModal(url, 'Aprovar lançamento');
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
              formData.append('next', window.location.pathname + window.location.search);
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
      var nextInput = form.querySelector('input[name="next"]');
      if (!nextInput) {
        nextInput = document.createElement('input');
        nextInput.type = 'hidden';
        nextInput.name = 'next';
        form.appendChild(nextInput);
      }
      nextInput.value = window.location.pathname + window.location.search;
      if (form.getAttribute('data-confirm-bypass') === '1') {
        form.removeAttribute('data-confirm-bypass');
        return;
      }
      e.preventDefault();
      var message = form.getAttribute('data-confirm-message') || 'Confirmar ação?';
      var title = form.getAttribute('data-confirm-title') || 'Confirmar';
      var confirmLabel = form.getAttribute('data-confirm-label') || 'Confirmar';
      showConfirmModal(message, title, confirmLabel, function () {
        form.setAttribute('data-confirm-bypass', '1');
        submitFormForTurbo(form);
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
