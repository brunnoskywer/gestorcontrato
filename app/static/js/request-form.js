(function () {
  var CONTRACT_TYPES = ["distrato", "relocation", "absence"];

  function getTypeSelect(form) {
    return form ? form.querySelector("#sr_request_type") : null;
  }

  function currentType(form) {
    if (!form) return "";
    var hidden = form.querySelector('input[type="hidden"][name="request_type"]');
    if (hidden) return hidden.value || "";
    var sel = getTypeSelect(form);
    return sel ? sel.value || "" : form.getAttribute("data-initial-type") || "";
  }

  function panelVisible(panel, type) {
    var dt = panel.getAttribute("data-type");
    if (dt) return dt === type;
    var dts = panel.getAttribute("data-types");
    if (dts) {
      return dts.split(",").map(function (s) {
        return s.trim();
      }).indexOf(type) >= 0;
    }
    return false;
  }

  function togglePanels(form, type) {
    form.querySelectorAll(".sr-type-panel").forEach(function (panel) {
      var show = panelVisible(panel, type);
      panel.classList.toggle("d-none", !show);
    });
  }

  function formatBr(num) {
    var n = Number(num);
    if (isNaN(n)) return "";
    var fixed = n.toFixed(2).split(".");
    var intPart = fixed[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return intPart + "," + fixed[1];
  }

  function fillContractSelect(form, contracts, selectedId) {
    var sel = form.querySelector("#sr_motoboy_contract_id");
    if (!sel) return;
    sel.innerHTML = "";
    var opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = contracts.length ? "Selecione o contrato..." : "Nenhum contrato vigente nesta locação";
    sel.appendChild(opt0);
    contracts.forEach(function (c) {
      var opt = document.createElement("option");
      opt.value = String(c.id);
      opt.textContent = c.label;
      if (selectedId && String(selectedId) === String(c.id)) opt.selected = true;
      sel.appendChild(opt);
    });
  }

  function updateContractInfo(form, data) {
    var box = form.querySelector("#sr-contract-info");
    var text = form.querySelector("#sr-contract-info-text");
    if (!box || !text) return;
    if (!data || !data.id) {
      box.classList.add("d-none");
      text.textContent = "";
      return;
    }
    var parts = [];
    if (data.motoboy_name) parts.push("Motoboy: " + data.motoboy_name);
    if (data.client_label) parts.push("Cliente: " + data.client_label);
    if (data.missing_value != null) parts.push("Valor falta: R$ " + formatBr(data.missing_value));
    text.textContent = parts.join(" · ");
    box.classList.remove("d-none");
  }

  function contractDetailUrl(form, contractId) {
    var tpl = form.getAttribute("data-contract-detail-url") || "";
    return tpl.replace("/0", "/" + contractId);
  }

  function loadContracts(form, location, selectedId) {
    var url = form.getAttribute("data-contracts-url");
    if (!url) return Promise.resolve();
    var q = location ? "?location=" + encodeURIComponent(location) : "";
    return fetch(url + q, { headers: { Accept: "application/json" } })
      .then(function (r) {
        return r.json();
      })
      .then(function (list) {
        fillContractSelect(form, list || [], selectedId);
        return list;
      })
      .catch(function () {
        fillContractSelect(form, [], selectedId);
      });
  }

  function loadContractDetail(form, contractId) {
    if (!contractId) {
      updateContractInfo(form, null);
      return Promise.resolve(null);
    }
    var url = contractDetailUrl(form, contractId);
    return fetch(url, { headers: { Accept: "application/json" } })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        updateContractInfo(form, data);
        if (currentType(form) === "absence") syncAbsenceAmount(form, data);
        return data;
      })
      .catch(function () {
        updateContractInfo(form, null);
        return null;
      });
  }

  function syncAbsenceAmount(form, data) {
    var sub = form.querySelector("#sr_substitute_id");
    var amt = form.querySelector("#sr_substitute_amount");
    if (!sub || !amt || !sub.value) return;
    if (amt.value && String(amt.value).trim()) return;
    if (data && data.missing_value != null) {
      amt.value = formatBr(data.missing_value);
    }
  }

  function bindAbsenceDiarist(form) {
    var sub = form.querySelector("#sr_substitute_id");
    var nat = form.querySelector("#sr_financial_nature_id");
    var amt = form.querySelector("#sr_substitute_amount");
    if (!sub || !nat || !amt) return;
    function sync() {
      var has = !!sub.value;
      nat.required = has;
      amt.required = has;
      if (!has) amt.value = "";
    }
    sub.addEventListener("change", sync);
    sync();
  }

  function initRequestForm(root) {
    var scope = root && root.querySelector ? root : document;
    var form = scope.querySelector
      ? scope.querySelector("#request-form")
      : document.getElementById("request-form");
    if (!form || form.getAttribute("data-request-form-init") === "1") return;
    form.setAttribute("data-request-form-init", "1");

    var payloadEl = form.querySelector("#request-payload-json");
    var payload = {};
    if (payloadEl) {
      try {
        payload = JSON.parse(payloadEl.textContent || "{}") || {};
      } catch (e) {
        payload = {};
      }
    }
    var typeSel = getTypeSelect(form);
    var initialType = currentType(form) || form.getAttribute("data-initial-type") || "";

    function onTypeChange() {
      togglePanels(form, currentType(form));
    }

    if (typeSel) {
      typeSel.addEventListener("change", onTypeChange);
    }
    onTypeChange();

    var locSel = form.querySelector("#sr_location");
    var contractSel = form.querySelector("#sr_motoboy_contract_id");

    if (locSel) {
      locSel.addEventListener("change", function () {
        var loc = locSel.value || "";
        loadContracts(form, loc, null);
        updateContractInfo(form, null);
      });
    }

    if (contractSel) {
      contractSel.addEventListener("change", function () {
        loadContractDetail(form, contractSel.value);
      });
    }

    bindAbsenceDiarist(form);

    if (CONTRACT_TYPES.indexOf(initialType) >= 0 && locSel) {
      var loc = payload.location || locSel.value || "";
      var cid = payload.motoboy_contract_id || "";
      if (loc) {
        loadContracts(form, loc, cid).then(function () {
          if (cid) loadContractDetail(form, cid);
        });
      }
    }
  }

  window.initRequestForm = initRequestForm;

  document.addEventListener("DOMContentLoaded", function () {
    initRequestForm(document);
  });
  document.addEventListener("turbo:load", function () {
    initRequestForm(document);
  });
})();
