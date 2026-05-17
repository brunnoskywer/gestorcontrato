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
      panel.querySelectorAll("input, select, textarea").forEach(function (el) {
        el.removeAttribute("required");
        el.required = false;
      });
    });
  }

  function formatBr(num) {
    var n = Number(num);
    if (isNaN(n)) return "";
    var fixed = n.toFixed(2).split(".");
    var intPart = fixed[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return intPart + "," + fixed[1];
  }

  function resetFormFieldsExceptType(form) {
    form.querySelectorAll("input, textarea, select").forEach(function (el) {
      if (el.id === "sr_request_type") return;
      if (el.name === "request_type" && el.type === "hidden") return;

      el.removeAttribute("required");
      el.required = false;
      if (el.type === "checkbox") {
        el.checked = false;
        return;
      }
      if (el.tagName === "SELECT") {
        el.selectedIndex = 0;
        return;
      }
      if (el.type === "hidden") {
        el.value = "";
        return;
      }
      el.value = "";
    });
    form.removeAttribute("data-contract-missing");
    fillDiaristSelect(form, [], null);
    fillContractSelect(form, [], null);
  }

  function fillContractSelect(form, contracts, selectedId) {
    var sel = form.querySelector("#sr_motoboy_contract_id");
    if (!sel) return;
    sel.innerHTML = "";
    var opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = contracts.length
      ? "Selecione o contrato..."
      : "Nenhum contrato vigente nesta locação";
    sel.appendChild(opt0);
    contracts.forEach(function (c) {
      var opt = document.createElement("option");
      opt.value = String(c.id);
      opt.textContent = c.label;
      if (selectedId && String(selectedId) === String(c.id)) opt.selected = true;
      sel.appendChild(opt);
    });
  }

  function fillDiaristSelect(form, motoboys, selectedId) {
    var sel = form.querySelector("#sr_substitute_id");
    if (!sel) return;
    sel.innerHTML = "";
    var opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = "Nenhum — só registro de falta";
    sel.appendChild(opt0);
    motoboys.forEach(function (m) {
      var opt = document.createElement("option");
      opt.value = String(m.id);
      opt.textContent = m.label;
      if (selectedId && String(selectedId) === String(m.id)) opt.selected = true;
      sel.appendChild(opt);
    });
  }

  function setContractMissing(form, data) {
    if (data && data.missing_value != null && !isNaN(Number(data.missing_value))) {
      form.setAttribute("data-contract-missing", String(data.missing_value));
    } else {
      form.removeAttribute("data-contract-missing");
    }
  }

  function contractDetailUrl(form, contractId) {
    var tpl = form.getAttribute("data-contract-detail-url") || "";
    return tpl.replace("/0", "/" + contractId);
  }

  function diaristsUrl(form, contractId) {
    var base = form.getAttribute("data-diarists-url") || "";
    return base + "?contract_id=" + encodeURIComponent(contractId);
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

  function loadDiarists(form, contractId, selectedId) {
    if (!contractId) {
      fillDiaristSelect(form, [], null);
      return Promise.resolve([]);
    }
    return fetch(diaristsUrl(form, contractId), { headers: { Accept: "application/json" } })
      .then(function (r) {
        return r.json();
      })
      .then(function (list) {
        fillDiaristSelect(form, list || [], selectedId);
        return list;
      })
      .catch(function () {
        fillDiaristSelect(form, [], selectedId);
      });
  }

  function loadContractDetail(form, contractId) {
    if (!contractId) {
      setContractMissing(form, null);
      return Promise.resolve(null);
    }
    var url = contractDetailUrl(form, contractId);
    return fetch(url, { headers: { Accept: "application/json" } })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        setContractMissing(form, data);
        return data;
      })
      .catch(function () {
        setContractMissing(form, null);
        return null;
      });
  }

  function applyDiaristAmount(form) {
    var sub = form.querySelector("#sr_substitute_id");
    var amt = form.querySelector("#sr_substitute_amount");
    if (!sub || !amt) return;
    if (!sub.value) {
      amt.value = "";
      return;
    }
    var missing = form.getAttribute("data-contract-missing");
    if (missing != null && missing !== "") {
      amt.value = formatBr(Number(missing));
    }
  }

  function bindAbsenceDiarist(form) {
    var sub = form.querySelector("#sr_substitute_id");
    if (!sub) return;
    sub.addEventListener("change", function () {
      applyDiaristAmount(form);
    });
  }

  function onContractChange(form) {
    var contractSel = form.querySelector("#sr_motoboy_contract_id");
    if (!contractSel) return;
    var contractId = contractSel.value;
    var type = currentType(form);

    loadContractDetail(form, contractId);
    if (type === "absence") {
      var payloadEl = form.querySelector("#request-payload-json");
      var selectedDiarist = null;
      if (payloadEl) {
        try {
          var p = JSON.parse(payloadEl.textContent || "{}");
          selectedDiarist = p.substitute_supplier_id || null;
        } catch (e) {}
      }
      loadDiarists(form, contractId, selectedDiarist);
      var amt = form.querySelector("#sr_substitute_amount");
      if (amt) amt.value = "";
    }
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
    var isEdit = !!form.querySelector('input[type="hidden"][name="request_type"]');

    function onTypeChange() {
      if (!isEdit) {
        resetFormFieldsExceptType(form);
      }
      togglePanels(form, currentType(form));
    }

    if (typeSel && !isEdit) {
      typeSel.addEventListener("change", onTypeChange);
    }
    onTypeChange();

    var locSel = form.querySelector("#sr_location");
    var contractSel = form.querySelector("#sr_motoboy_contract_id");

    if (locSel) {
      locSel.addEventListener("change", function () {
        var loc = locSel.value || "";
        loadContracts(form, loc, null);
        setContractMissing(form, null);
        fillDiaristSelect(form, [], null);
        var amt = form.querySelector("#sr_substitute_amount");
        if (amt) amt.value = "";
      });
    }

    if (contractSel) {
      contractSel.addEventListener("change", function () {
        onContractChange(form);
      });
    }

    bindAbsenceDiarist(form);

    if (CONTRACT_TYPES.indexOf(initialType) >= 0 && locSel) {
      var loc = payload.location || locSel.value || "";
      var cid = payload.motoboy_contract_id || "";
      if (loc) {
        loadContracts(form, loc, cid).then(function () {
          if (cid) {
            loadContractDetail(form, cid).then(function () {
              if (initialType === "absence") {
                loadDiarists(form, cid, payload.substitute_supplier_id || null).then(
                  function () {
                    applyDiaristAmount(form);
                  }
                );
              }
            });
          }
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
