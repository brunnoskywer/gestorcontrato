/**
 * Formulário de movimentação de fardamentos (modal).
 */
(function () {
  function initUniformMovementForm(container) {
    if (!container || !container.querySelector) return;
    var form = container.querySelector("#uniform-movement-form");
    if (!form || form.dataset.uniformMovementBound === "1") return;

    var entrySubtypes;
    var exitSubtypes;
    try {
      entrySubtypes = JSON.parse(form.getAttribute("data-entry-subtypes") || "{}");
      exitSubtypes = JSON.parse(form.getAttribute("data-exit-subtypes") || "{}");
    } catch (e) {
      return;
    }

    var directionEl = form.querySelector("#uniform_movement_direction");
    var subtypeEl = form.querySelector("#uniform_movement_subtype");
    var motoboyWrap = form.querySelector("#uniform_movement_motoboy_wrap");
    var motoboyLabel = form.querySelector("#uniform_movement_motoboy_label");
    var payableWrap = form.querySelector("#uniform_movement_payable_wrap");
    if (!directionEl || !subtypeEl) return;

    form.dataset.uniformMovementBound = "1";

    function clearMotoboy() {
      var hid = form.querySelector("#uniform_movement_motoboy_id");
      var inp = form.querySelector("#uniform_movement_motoboy_input");
      if (hid) hid.value = "";
      if (inp) {
        inp.value = "";
        delete inp.dataset.entityPickLabel;
      }
    }

    function clearPayable() {
      var hid = form.querySelector("#uniform_movement_payable_id");
      var inp = form.querySelector("#uniform_movement_payable_input");
      if (hid) hid.value = "";
      if (inp) {
        inp.value = "";
        delete inp.dataset.entityPickLabel;
      }
    }

    function fillSubtypes(map) {
      subtypeEl.innerHTML = '<option value="">Selecione</option>';
      Object.keys(map).forEach(function (key) {
        var opt = document.createElement("option");
        opt.value = key;
        opt.textContent = map[key];
        subtypeEl.appendChild(opt);
      });
      subtypeEl.disabled = false;
      subtypeEl.removeAttribute("disabled");
    }

    function syncConditionalFields() {
      var direction = directionEl.value;
      var subtype = subtypeEl.value;
      if (motoboyWrap) motoboyWrap.style.display = "none";
      if (payableWrap) payableWrap.style.display = "none";
      if (motoboyLabel) motoboyLabel.textContent = "Motoboy";

      if (direction === "entry" && subtype === "purchase") {
        if (payableWrap) payableWrap.style.display = "";
      } else {
        clearPayable();
      }

      if (direction === "entry" && subtype === "return") {
        if (motoboyWrap) motoboyWrap.style.display = "";
        if (motoboyLabel) motoboyLabel.textContent = "Motoboy (retorno) *";
      } else if (direction === "exit" && subtype === "shipment") {
        if (motoboyWrap) motoboyWrap.style.display = "";
        if (motoboyLabel) motoboyLabel.textContent = "Motoboy (envio) *";
      } else {
        clearMotoboy();
      }
    }

    function onDirectionChange() {
      var direction = directionEl.value;
      clearMotoboy();
      clearPayable();
      if (!direction) {
        subtypeEl.innerHTML =
          '<option value="">Selecione o movimento primeiro</option>';
        subtypeEl.disabled = true;
        subtypeEl.setAttribute("disabled", "disabled");
        syncConditionalFields();
        return;
      }
      if (direction === "entry") {
        fillSubtypes(entrySubtypes);
      } else {
        fillSubtypes(exitSubtypes);
      }
      syncConditionalFields();
    }

    directionEl.addEventListener("change", onDirectionChange);
    subtypeEl.addEventListener("change", syncConditionalFields);

    form.addEventListener("submit", function () {
      if (subtypeEl.disabled) {
        subtypeEl.disabled = false;
      }
    });
  }

  window.initUniformMovementForm = initUniformMovementForm;

  document.addEventListener("DOMContentLoaded", function () {
    initUniformMovementForm(document);
  });
})();
