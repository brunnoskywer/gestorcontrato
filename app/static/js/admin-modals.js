/**
 * Modais reutilizáveis do admin: confirmação (excluir), formulário (criar/editar) e mensagens (flash).
 * Máscaras CPF e CNPJ. Compatível com Turbo Drive.
 * Após carregar um formulário no modal, injeta hidden `next` (path+query do contexto ativo) em todo POST.
 * Com abas admin, o path vem de getAdminActiveContentPath() — a URL do browser nem sempre é a da aba.
 */
(function () {
  'use strict';

  function listReturnNextPath() {
    if (typeof window.getAdminActiveContentPath === 'function') {
      try {
        var p = window.getAdminActiveContentPath();
        if (p && typeof p === 'string' && p.charAt(0) === '/') return p;
      } catch (err) {}
    }
    return (window.location.pathname || '/') + (window.location.search || '');
  }

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

  function maskCep(value) {
    var d = (value || '').replace(/\D/g, '').slice(0, 8);
    if (d.length <= 5) return d;
    return d.replace(/(\d{5})(\d+)/, '$1-$2');
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

  /** Parse BR currency field for blur normalization (milhares com ponto, decimais com vírgula). */
  function parseBrazilianCurrencyInput(raw) {
    if (!raw || !String(raw).trim()) return NaN;
    var t = String(raw).trim().replace(/\./g, '').replace(',', '.');
    if (t.endsWith('.')) t = t.slice(0, -1);
    if (t === '' || t === '-') return NaN;
    return parseFloat(t);
  }

  /** Formata número como moeda BR (1.234,56), sempre com dois decimais. */
  function formatCurrencyBR(num) {
    if (typeof num !== 'number' || isNaN(num)) return '';
    var cents = Math.round(num * 100);
    var negative = cents < 0;
    cents = Math.abs(cents);
    var intPart = Math.floor(cents / 100);
    var decPart = cents % 100;
    var intStr = intPart.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    var decStr = decPart.toString().padStart(2, '0');
    return (negative ? '-' : '') + intStr + ',' + decStr;
  }

  function normalizeCurrencyOnBlur(input) {
    var raw = (input.value || '').trim();
    if (!raw) return;
    var n = parseBrazilianCurrencyInput(raw);
    if (isNaN(n)) return;
    input.value = formatCurrencyBR(n);
  }

  function applyMasks(container) {
    if (!container || !container.querySelector) return;
    var cpfInputs = container.querySelectorAll('[data-mask="cpf"]');
    var cnpjInputs = container.querySelectorAll('[data-mask="cnpj"]');
    var cepInputs = container.querySelectorAll('[data-mask="cep"]');
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

    cepInputs.forEach(function (input) {
      if (input.dataset.maskApplied) return;
      input.dataset.maskApplied = '1';
      input.value = maskCep(input.value);
      input.addEventListener('input', function () {
        input.value = maskCep(input.value);
      });
    });

    currencyInputs.forEach(function (input) {
      if (input.dataset.maskApplied) return;
      input.dataset.maskApplied = '1';
      // Não formatamos durante a digitação para não mexer no cursor.
      // Valor inicial: normaliza para ,00 quando vier só parte inteira.
      if (input.value) {
        normalizeCurrencyOnBlur(input);
      }
      input.addEventListener('blur', function () {
        normalizeCurrencyOnBlur(input);
      });
    });

    var form = container.tagName === 'FORM' ? container : container.querySelector('form');
    if (form && (cpfInputs.length || cnpjInputs.length || cepInputs.length || currencyInputs.length)) {
      form.addEventListener('submit', function stripMasksOnce() {
        form.querySelectorAll('[data-mask="cpf"]').forEach(function (el) {
          el.value = (el.value || '').replace(/\D/g, '');
        });
        form.querySelectorAll('[data-mask="cnpj"]').forEach(function (el) {
          el.value = (el.value || '').replace(/\D/g, '');
        });
        form.querySelectorAll('[data-mask="cep"]').forEach(function (el) {
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

  function showLookupMessage(message, title) {
    if (typeof window.showMessageModal === 'function') {
      window.showMessageModal(message, title || 'Atenção');
      return;
    }
    window.alert(message);
  }

  function initCepLookup(container) {
    if (!container || !container.querySelectorAll) return;
    container.querySelectorAll('[data-cep-consult-btn]').forEach(function (btn) {
      if (btn.dataset.cepLookupBound) return;
      btn.dataset.cepLookupBound = '1';

      btn.addEventListener('click', function () {
        var form = btn.closest('form');
        if (!form) return;
        var cepInput = form.querySelector('input[name="cep"]');
        if (!cepInput) return;

        var cep = (cepInput.value || '').replace(/\D/g, '');
        if (cep.length !== 8) {
          showLookupMessage('Informe um CEP válido com 8 dígitos.', 'Consulta de CEP');
          return;
        }

        var streetInput = form.querySelector('input[name="street"]');
        var neighborhoodInput = form.querySelector('input[name="neighborhood"]');
        var cityInput = form.querySelector('input[name="city"]');
        var stateInput = form.querySelector('select[name="state"], input[name="state"]');
        var complementInput = form.querySelector('input[name="address"]');

        var originalLabel = btn.textContent;
        btn.disabled = true;
        btn.textContent = 'Consultando...';

        fetch('/admin/address/cep-lookup?cep=' + encodeURIComponent(cep), {
          headers: { Accept: 'application/json' }
        })
          .then(function (response) {
            return response.json();
          })
          .then(function (payload) {
            if (!payload || payload.ok !== true || !payload.data) {
              showLookupMessage((payload && payload.message) || 'Não foi possível consultar este CEP.', 'Consulta de CEP');
              return;
            }
            var data = payload.data;
            if (data.cep) cepInput.value = maskCep(data.cep);
            if (streetInput && data.street) streetInput.value = data.street;
            if (neighborhoodInput && data.neighborhood) neighborhoodInput.value = data.neighborhood;
            if (cityInput && data.city) cityInput.value = data.city;
            if (stateInput && data.state) stateInput.value = String(data.state).toUpperCase();
            if (complementInput && data.complement && !complementInput.value) {
              complementInput.value = data.complement;
            }
          })
          .catch(function () {
            showLookupMessage('Falha ao consultar CEP. Tente novamente em instantes.', 'Consulta de CEP');
          })
          .finally(function () {
            btn.disabled = false;
            btn.textContent = originalLabel;
          });
      });
    });
  }

  function initCnpjLookup(container) {
    if (!container || !container.querySelectorAll) return;
    container.querySelectorAll('[data-cnpj-consult-btn]').forEach(function (btn) {
      if (btn.dataset.cnpjLookupBound) return;
      btn.dataset.cnpjLookupBound = '1';

      btn.addEventListener('click', function () {
        var form = btn.closest('form');
        if (!form) return;

        var cnpjInput =
          form.querySelector('input[name="cnpj"]') ||
          form.querySelector('input[name="document"]') ||
          form.querySelector('input[name="document_secondary"]');
        if (!cnpjInput) return;

        var cnpj = (cnpjInput.value || '').replace(/\D/g, '');
        if (cnpj.length !== 14) {
          showLookupMessage('Informe um CNPJ válido com 14 dígitos.', 'Consulta de CNPJ');
          return;
        }

        var legalNameInput = form.querySelector('input[name="legal_name"]');
        var tradeNameInput = form.querySelector('input[name="trade_name"]');
        var fullNameInput = form.querySelector('input[name="full_name"]');
        var supplierNameInput = form.querySelector('input[name="name"]');
        var emailInput = form.querySelector('input[name="email"]');
        var contactPhoneInput = form.querySelector('input[name="contact_phone"]');
        var cepInput = form.querySelector('input[name="cep"]');
        var streetInput = form.querySelector('input[name="street"]');
        var neighborhoodInput = form.querySelector('input[name="neighborhood"]');
        var cityInput = form.querySelector('input[name="city"]');
        var stateInput = form.querySelector('select[name="state"], input[name="state"]');
        var complementInput = form.querySelector('input[name="address"]');

        var originalLabel = btn.textContent;
        btn.disabled = true;
        btn.textContent = 'Buscando...';

        fetch('/admin/address/cnpj-lookup?cnpj=' + encodeURIComponent(cnpj), {
          headers: { Accept: 'application/json' }
        })
          .then(function (response) {
            return response.json();
          })
          .then(function (payload) {
            if (!payload || payload.ok !== true || !payload.data) {
              showLookupMessage((payload && payload.message) || 'Não foi possível consultar este CNPJ.', 'Consulta de CNPJ');
              return;
            }
            var data = payload.data;
            if (data.cnpj) cnpjInput.value = maskCnpj(data.cnpj);
            if (legalNameInput && data.legal_name) legalNameInput.value = data.legal_name;
            if (tradeNameInput && data.trade_name) tradeNameInput.value = data.trade_name;
            if (fullNameInput) {
              var motoboyName = data.legal_name || data.trade_name;
              if (motoboyName) fullNameInput.value = motoboyName;
            }
            if (supplierNameInput) {
              var supplierName = data.trade_name || data.legal_name;
              if (supplierName) supplierNameInput.value = supplierName;
            }
            if (emailInput && data.email) emailInput.value = data.email;
            if (contactPhoneInput && data.phone) contactPhoneInput.value = data.phone;
            if (cepInput && data.cep) cepInput.value = maskCep(data.cep);
            if (streetInput && data.street) streetInput.value = data.street;
            if (neighborhoodInput && data.neighborhood) neighborhoodInput.value = data.neighborhood;
            if (cityInput && data.city) cityInput.value = data.city;
            if (stateInput && data.state) stateInput.value = String(data.state).toUpperCase();
            if (complementInput && data.complement) complementInput.value = data.complement;
          })
          .catch(function () {
            showLookupMessage('Falha ao consultar CNPJ. Tente novamente em instantes.', 'Consulta de CNPJ');
          })
          .finally(function () {
            btn.disabled = false;
            btn.textContent = originalLabel;
          });
      });
    });
  }

  function initWhatsappDataRequest(container) {
    if (!container || !container.querySelectorAll) return;
    container.querySelectorAll('[data-whatsapp-request-btn]').forEach(function (btn) {
      if (btn.dataset.whatsappRequestBound) return;
      btn.dataset.whatsappRequestBound = '1';

      btn.addEventListener('click', function () {
        var form = btn.closest('form');
        if (!form) return;
        var phoneInput = form.querySelector('input[name="contact_phone"]');
        var phone = (phoneInput && phoneInput.value ? phoneInput.value : '').replace(/\D/g, '');
        if (!phone) {
          showLookupMessage('Informe o telefone de contato para abrir o WhatsApp.', 'Solicitação de dados');
          return;
        }

        var messageLines = [
          'Olá! Para concluir seu cadastro de motoboy, envie por favor:',
          '',
          '*Nome Completo*',
          '*CPF*',
          '*CNPJ*',
          '*CEP*',
          '*LOGRADOURO/NUMERO*',
          '*PIX*',
          '*BAIRRO*',
          '*EMAIL*',
          '*PLACA*',
          '',
          'Obrigado!'
        ];
        var text = messageLines.join('\n');
        var url = 'https://web.whatsapp.com/send/?phone=' +
          encodeURIComponent(phone) +
          '&text=' +
          encodeURIComponent(text);
        window.open(url, '_blank', 'noopener');
      });
    });
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
        nextInput.value = listReturnNextPath();
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

  /** Atualiza só o turbo-frame principal a partir do HTML da resposta (mantém abas e URL com filtros). */
  function mergeTurboMainContentFromHtml(html) {
    var frame = document.getElementById('main-content');
    if (!frame) return;
    var parser = new DOMParser();
    var doc = parser.parseFromString(html, 'text/html');
    var newFrame = doc.querySelector('turbo-frame#main-content');
    if (!newFrame) return;
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

  /**
   * Garante campo hidden `next` em formulários POST do modal, com a URL da lista atual
   * (path + query), para o backend redirecionar mantendo filtros após inserir/editar.
   */
  function injectListReturnNextOnPostForms(container) {
    if (!container || !container.querySelectorAll) return;
    var path = listReturnNextPath();
    if (!path || path.charAt(0) !== '/') return;
    container.querySelectorAll('form').forEach(function (form) {
      var method = (form.getAttribute('method') || 'get').toLowerCase();
      if (method !== 'post') return;
      var nextInput = form.querySelector('input[name="next"]');
      if (!nextInput) {
        nextInput = document.createElement('input');
        nextInput.type = 'hidden';
        nextInput.name = 'next';
        form.insertBefore(nextInput, form.firstChild);
      }
      nextInput.value = path;
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
      dialogEl.classList.remove('modal-sm', 'modal-md', 'modal-lg', 'modal-xl');
      if (size === 'sm') dialogEl.classList.add('modal-sm');
      else if (size === 'md') dialogEl.classList.add('modal-md');
      else if (size === 'xl') dialogEl.classList.add('modal-xl');
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
        initCepLookup(bodyEl);
        initCnpjLookup(bodyEl);
        initWhatsappDataRequest(bodyEl);
        injectListReturnNextOnPostForms(bodyEl);
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
          initCepLookup(bodyEl);
          initCnpjLookup(bodyEl);
          initWhatsappDataRequest(bodyEl);
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

  function setRowSelected(table, cb, checked) {
    if (!cb) return;
    cb.checked = !!checked;
    var tr = cb.closest('tr');
    if (tr) tr.classList.toggle('table-active', !!checked);
    if (table) syncSelectAllState(table);
  }

  function setAllRowsSelected(table, checked) {
    if (!table) return;
    table.querySelectorAll('tbody .row-select').forEach(function (cb) {
      setRowSelected(table, cb, checked);
    });
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
        if (th.getAttribute('data-sort-skip') === '1') return;
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
          setRowSelected(table, cb, !cb.checked);
        });
      });
      table.querySelectorAll('tbody .row-select').forEach(function (cb) {
        cb.addEventListener('change', function () {
          setRowSelected(table, cb, cb.checked);
        });
        setRowSelected(table, cb, cb.checked);
      });
      var selectAll = table.querySelector('thead .select-all');
      if (selectAll) {
        selectAll.addEventListener('change', function () {
          setAllRowsSelected(table, selectAll.checked);
        });
      }
    });
  }

  function initToolbar() {
    document.querySelectorAll('.admin-toolbar').forEach(function (toolbar) {
      var tableId = toolbar.getAttribute('data-table-id');
      var table = document.getElementById(tableId);
      if (!table) return;

      var toolbarModalSize = toolbar.getAttribute('data-modal-size') || '';
      var financeModalSize =
        toolbar.getAttribute('data-finance-actions') === '1' ? 'md' : toolbarModalSize;

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
        setAllRowsSelected(table, true);
      });

      toolbar.querySelector('.admin-toolbar-deselect')?.addEventListener('click', function () {
        setAllRowsSelected(table, false);
      });

      var insertUrl = toolbar.getAttribute('data-insert-url');
      var insertTitle = toolbar.getAttribute('data-insert-title');
      toolbar.querySelector('.admin-toolbar-insert')?.addEventListener('click', function () {
        if (!insertUrl) return;
        openFormModal(insertUrl, insertTitle || 'Inserir', financeModalSize || undefined);
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
        var url = editTpl.replace('{id}', ids[0]);
        if (toolbar.getAttribute('data-finance-actions') === '1') {
          var row = getFirstSelectedRow();
          if (row && row.getAttribute('data-settled') === '1') {
            showMessageModal('Não é possível editar lançamento quitado. Reabra-o antes.', 'Atenção');
            return;
          }
        }
        openFormModal(url, 'Editar', financeModalSize || undefined);
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
            nextInput.value = listReturnNextPath();
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

      function postSingleRowAction(actionTpl, confirmMsg, confirmBtnLabel) {
        if (!actionTpl) return;
        var ids = getSelectedIds();
        if (ids.length === 0) {
          showMessageModal('Selecione um registro.', 'Atenção');
          return;
        }
        if (ids.length > 1) {
          showMessageModal('Selecione apenas um registro.', 'Atenção');
          return;
        }
        showConfirmModal(confirmMsg, 'Confirmar', confirmBtnLabel || 'Confirmar', function () {
          var url = actionTpl.replace('{id}', ids[0]);
          var formData = new FormData();
          formData.append('next', listReturnNextPath());
          fetch(url, {
            method: 'POST',
            body: formData,
            headers: {
              Accept: 'text/html',
              'X-Requested-With': 'XMLHttpRequest'
            },
            redirect: 'follow'
          })
            .then(function (r) {
              return r.text();
            })
            .then(function (html) {
              mergeTurboMainContentFromHtml(html);
            })
            .catch(function () {
              showMessageModal('Erro ao executar a ação. Tente novamente.', 'Erro');
            });
        });
      }

      var mbCloseTpl = toolbar.getAttribute('data-motoboy-close-url-template');
      toolbar.querySelector('.admin-toolbar-motoboy-close')?.addEventListener('click', function () {
        postSingleRowAction(
          mbCloseTpl,
          'Encerrar o motoboy selecionado? Ele deixa de aparecer em contratos, faltas e financeiro.',
          'Encerrar'
        );
      });
      var mbActTpl = toolbar.getAttribute('data-motoboy-activate-url-template');
      toolbar.querySelector('.admin-toolbar-motoboy-activate')?.addEventListener('click', function () {
        postSingleRowAction(mbActTpl, 'Reativar o motoboy selecionado?', 'Ativar');
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

      var distratoTpl = toolbar.getAttribute('data-distrato-url-template');
      var distratoTitle = toolbar.getAttribute('data-distrato-title') || 'Gerar distrato';
      toolbar.querySelector('.admin-toolbar-distrato')?.addEventListener('click', function () {
        if (!distratoTpl) return;
        var ids = getSelectedIds();
        if (ids.length === 0) {
          showMessageModal('Selecione um contrato para gerar o distrato.', 'Atenção');
          return;
        }
        if (ids.length > 1) {
          showMessageModal('Selecione apenas um contrato para gerar o distrato.', 'Atenção');
          return;
        }
        var row = getFirstSelectedRow();
        var d = row && row.getAttribute('data-distrato-date');
        if (!d || !String(d).trim()) {
          showMessageModal(
            'Cadastre a data de distrato no contrato antes de gerar o lançamento.',
            'Atenção'
          );
          return;
        }
        openFormModal(distratoTpl.replace('{id}', ids[0]), distratoTitle, 'md');
      });

      var contractPrintTpl = toolbar.getAttribute('data-contract-print-url-template');
      var contractPrintTitle = toolbar.getAttribute('data-contract-print-title') || 'Gerar contrato (PDF)';
      toolbar.querySelector('.admin-toolbar-contract-print')?.addEventListener('click', function () {
        if (!contractPrintTpl) return;
        var ids = getSelectedIds();
        if (ids.length === 0) {
          showMessageModal('Selecione um contrato vigente para gerar o contrato em PDF.', 'Atenção');
          return;
        }
        if (ids.length > 1) {
          showMessageModal('Selecione apenas um contrato para gerar o PDF.', 'Atenção');
          return;
        }
        var row = getFirstSelectedRow();
        var distratoDate = row && row.getAttribute('data-distrato-date');
        if (distratoDate && String(distratoDate).trim()) {
          showMessageModal('A geração do contrato só é permitida para contrato vigente (sem data de distrato).', 'Atenção');
          return;
        }
        openFormModal(contractPrintTpl.replace('{id}', ids[0]), contractPrintTitle, 'md');
      });

      var attachmentsTpl = toolbar.getAttribute('data-attachments-url-template');
      var attachmentsTitle =
        toolbar.getAttribute('data-attachments-title') || 'Anexos do contrato';
      toolbar.querySelector('.admin-toolbar-attachments')?.addEventListener('click', function () {
        if (!attachmentsTpl) return;
        var ids = getSelectedIds();
        if (ids.length === 0) {
          showMessageModal('Selecione um registro para ver ou enviar anexo.', 'Atenção');
          return;
        }
        if (ids.length > 1) {
          showMessageModal('Selecione apenas um registro para anexar arquivo.', 'Atenção');
          return;
        }
        openFormModal(attachmentsTpl.replace('{id}', ids[0]), attachmentsTitle, 'lg');
      });

      var distratoPrintTpl = toolbar.getAttribute('data-distrato-print-url-template');
      var distratoPrintTitle =
        toolbar.getAttribute('data-distrato-print-title') || 'Distrato (PDF)';
      toolbar.querySelector('.admin-toolbar-distrato-print')?.addEventListener('click', function () {
        if (!distratoPrintTpl) return;
        var ids = getSelectedIds();
        if (ids.length === 0) {
          showMessageModal(
            'Selecione um contrato com data de distrato para gerar o distrato em PDF.',
            'Atenção'
          );
          return;
        }
        if (ids.length > 1) {
          showMessageModal('Selecione apenas um contrato para gerar o distrato em PDF.', 'Atenção');
          return;
        }
        var row = getFirstSelectedRow();
        var distratoDate = row && row.getAttribute('data-distrato-date');
        if (!distratoDate || !String(distratoDate).trim()) {
          showMessageModal(
            'A impressão do distrato só é permitida quando a data de distrato estiver preenchida no contrato.',
            'Atenção'
          );
          return;
        }
        openFormModal(distratoPrintTpl.replace('{id}', ids[0]), distratoPrintTitle, 'md');
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
        /* Hub “Processar” (filtros + tabela): largura ampla; formulários dos botões usam data-modal-size no próprio gatilho. */
        if (revenueBatchesUrl) openFormModal(revenueBatchesUrl, revenueBatchesTitle, 'xl');
      });

      if (toolbar.getAttribute('data-finance-actions') === '1') {
        var transferUrl = toolbar.getAttribute('data-transfer-url');
        var bulkUpdateUrl = toolbar.getAttribute('data-bulk-update-url');
        toolbar.querySelector('.admin-toolbar-transfer')?.addEventListener('click', function () {
          if (transferUrl) openFormModal(transferUrl, 'Transferência entre contas', 'md');
        });
        toolbar.querySelector('.admin-toolbar-bulk-update')?.addEventListener('click', function () {
          if (!bulkUpdateUrl) return;
          var selectedRows = [];
          table.querySelectorAll('tbody .row-select:checked').forEach(function (cb) {
            var tr = cb.closest('tr');
            if (tr) selectedRows.push(tr);
          });
          if (!selectedRows.length) {
            showMessageModal('Selecione um ou mais lançamentos para alterar em massa.', 'Atenção');
            return;
          }
          var hasSettled = selectedRows.some(function (tr) {
            return tr.getAttribute('data-settled') === '1';
          });
          if (hasSettled) {
            showMessageModal('A alteração em massa só pode ser aplicada quando todos os selecionados estiverem pendentes.', 'Atenção');
            return;
          }
          var ids = selectedRows
            .map(function (tr) { return tr.getAttribute('data-id'); })
            .filter(function (id) { return !!id; });
          if (!ids.length) {
            showMessageModal('Nenhum lançamento válido selecionado para alterar.', 'Atenção');
            return;
          }
          var next = listReturnNextPath();
          var params = ids.map(function (id) {
            return 'ids=' + encodeURIComponent(id);
          }).join('&');
          var url = bulkUpdateUrl + '?' + params + '&next=' + encodeURIComponent(next);
          openFormModal(url, 'Alterar lançamentos em massa', 'md');
        });

        var approveTpl = toolbar.getAttribute('data-approve-url-template');
        var approveBulkUrl = toolbar.getAttribute('data-approve-bulk-url');
        toolbar.querySelector('.admin-toolbar-approve')?.addEventListener('click', function () {
          if (!approveTpl && !approveBulkUrl) return;
          var selectedRows = [];
          table.querySelectorAll('tbody .row-select:checked').forEach(function (cb) {
            var tr = cb.closest('tr');
            if (tr) selectedRows.push(tr);
          });
          if (!selectedRows.length) {
            showMessageModal('Selecione um ou mais lançamentos pendentes para aprovar.', 'Atenção');
            return;
          }
          var hasSettled = selectedRows.some(function (tr) {
            return tr.getAttribute('data-settled') === '1';
          });
          if (hasSettled) {
            showMessageModal('Para baixa em lote, todos os selecionados devem estar pendentes.', 'Atenção');
            return;
          }
          var ids = selectedRows
            .map(function (tr) { return tr.getAttribute('data-id'); })
            .filter(function (id) { return !!id; });
          if (!ids.length) {
            showMessageModal('Nenhum lançamento válido selecionado para aprovar.', 'Atenção');
            return;
          }
          var next = listReturnNextPath();
          var url;
          if (ids.length === 1 && approveTpl) {
            url = approveTpl.replace('{id}', ids[0]) + '?next=' + encodeURIComponent(next);
          } else if (approveBulkUrl) {
            var params = ids.map(function (id) {
              return 'ids=' + encodeURIComponent(id);
            }).join('&');
            url = approveBulkUrl + '?' + params + '&next=' + encodeURIComponent(next);
          } else {
            showMessageModal('Aprovação em lote indisponível.', 'Atenção');
            return;
          }
          openFormModal(url, 'Aprovar lançamento', 'md');
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
              formData.append('next', listReturnNextPath());
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
                .then(function (r) {
                  return r.text();
                })
                .then(function (html) {
                  mergeTurboMainContentFromHtml(html);
                })
                .catch(function () {
                  showMessageModal('Erro ao reabrir lançamento(s). Tente novamente.', 'Erro');
                });
            }
          );
        });

        var residualPdfTpl = toolbar.getAttribute('data-residual-detail-pdf-url-template');
        var residualPdfTitle =
          toolbar.getAttribute('data-residual-detail-pdf-title') || 'Detalhamento residual (PDF)';
        toolbar.querySelector('.admin-toolbar-residual-detail-pdf')?.addEventListener('click', function () {
          if (!residualPdfTpl) return;
          var ids = getSelectedIds();
          if (ids.length === 0) {
            showMessageModal(
              'Selecione um lançamento gerado pelo processamento residual para abrir o PDF.',
              'Atenção'
            );
            return;
          }
          if (ids.length > 1) {
            showMessageModal(
              'Selecione apenas um lançamento para o detalhamento residual em PDF.',
              'Atenção'
            );
            return;
          }
          var row = getFirstSelectedRow();
          if (!row || row.getAttribute('data-residual-detail') !== '1') {
            showMessageModal(
              'O PDF de detalhamento residual só está disponível para lançamentos gerados pelo processamento residual.',
              'Atenção'
            );
            return;
          }
          openFormModal(residualPdfTpl.replace('{id}', ids[0]), residualPdfTitle, 'md');
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
                input.dataset.entityPickLabel = item.label;
                hideDropdown();
              });
              dropdown.appendChild(btn);
            });
            dropdown.style.display = 'block';
          })
          .catch(hideDropdown);
      }

      input.addEventListener('input', function () {
        if (hiddenId) {
          var v = input.value.trim();
          if (v === '') {
            hiddenId.value = '';
            delete input.dataset.entityPickLabel;
          } else if (
            hiddenId.value &&
            input.dataset.entityPickLabel &&
            v !== input.dataset.entityPickLabel
          ) {
            hiddenId.value = '';
            delete input.dataset.entityPickLabel;
          }
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
      nextInput.value = listReturnNextPath();
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
    applyMasks(document);
    initCepLookup(document);
    initCnpjLookup(document);
    initWhatsappDataRequest(document);
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
    applyMasks(container);
    initCepLookup(container);
    initCnpjLookup(container);
    initWhatsappDataRequest(container);
    initSearchInputs(container);
    runScriptsInElement(container);
  });

  document.addEventListener('turbo:frame-render', function (e) {
    if (e.target.id === 'main-content') {
      initToolbar();
      initTableListRowClick();
      applyMasks(e.target);
      initCepLookup(e.target);
      initCnpjLookup(e.target);
      initWhatsappDataRequest(e.target);
      runScriptsInElement(e.target);
      var modalEl = document.getElementById('adminFormModal');
      if (modalEl) {
        var modal = window.bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }
    }
  });
})();
