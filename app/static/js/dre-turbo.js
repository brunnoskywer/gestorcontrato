/**
 * DRE: gráficos e modal de detalhe após navegação Turbo (scripts dentro do frame não rodam).
 */
(function () {
  var CHART_CDN =
    "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js";
  var chartLoadPromise = null;

  function ensureChart() {
    if (typeof Chart !== "undefined") {
      return Promise.resolve();
    }
    if (chartLoadPromise) {
      return chartLoadPromise;
    }
    chartLoadPromise = new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = CHART_CDN;
      s.crossOrigin = "anonymous";
      s.onload = resolve;
      s.onerror = reject;
      document.head.appendChild(s);
    });
    return chartLoadPromise;
  }

  function destroyDreCharts() {
    if (typeof Chart === "undefined") {
      return;
    }
    ["dreReceitasNaturezaChart", "dreDespesasNaturezaChart", "dreEvolucaoPeriodoChart"].forEach(
      function (id) {
        var el = document.getElementById(id);
        if (!el) {
          return;
        }
        var c = Chart.getChart(el);
        if (c) {
          c.destroy();
        }
      }
    );
  }

  function initDreCharts() {
    var dataEl = document.getElementById("dre-chart-data");
    if (!dataEl || typeof Chart === "undefined") {
      return;
    }
    var data;
    try {
      data = JSON.parse(dataEl.textContent);
    } catch (e) {
      return;
    }

    destroyDreCharts();

    var palette = [
      "#0d6efd",
      "#198754",
      "#fd7e14",
      "#6f42c1",
      "#20c997",
      "#dc3545",
      "#ffc107",
      "#6610f2",
      "#0dcaf0",
      "#adb5bd",
    ];

    var recLabels = data.recLabels || [];
    var recValues = data.recValues || [];
    var payLabels = data.payLabels || [];
    var payValues = data.payValues || [];
    var dayLabels = data.dayLabels || [];
    var dayRec = data.dayRec || [];
    var dayPay = data.dayPay || [];
    var dayBalance = data.dayBalance || [];

    var recCtx = document.getElementById("dreReceitasNaturezaChart");
    if (recCtx) {
      new Chart(recCtx, {
        type: "doughnut",
        data: {
          labels: recLabels.length ? recLabels : ["Sem dados"],
          datasets: [
            {
              data: recValues.length ? recValues : [1],
              backgroundColor: recLabels.length ? palette : ["#dee2e6"],
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: "bottom" } },
        },
      });
    }

    var payCtx = document.getElementById("dreDespesasNaturezaChart");
    if (payCtx) {
      new Chart(payCtx, {
        type: "doughnut",
        data: {
          labels: payLabels.length ? payLabels : ["Sem dados"],
          datasets: [
            {
              data: payValues.length ? payValues : [1],
              backgroundColor: payLabels.length ? palette : ["#dee2e6"],
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: "bottom" } },
        },
      });
    }

    var lineCtx = document.getElementById("dreEvolucaoPeriodoChart");
    if (lineCtx) {
      new Chart(lineCtx, {
        type: "line",
        data: {
          labels: dayLabels,
          datasets: [
            {
              label: "Receitas",
              data: dayRec,
              borderColor: "#198754",
              backgroundColor: "rgba(25, 135, 84, 0.15)",
              tension: 0.2,
              fill: false,
            },
            {
              label: "Despesas",
              data: dayPay,
              borderColor: "#dc3545",
              backgroundColor: "rgba(220, 53, 69, 0.15)",
              tension: 0.2,
              fill: false,
            },
            {
              label: "Resultado acumulado",
              data: dayBalance,
              borderColor: "#0d6efd",
              backgroundColor: "rgba(13, 110, 253, 0.15)",
              tension: 0.2,
              fill: true,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: "top" } },
          scales: { y: { beginAtZero: false } },
        },
      });
    }
  }

  function openDreDetail(btn) {
    var root = document.getElementById("dre-page");
    if (!root || typeof bootstrap === "undefined") {
      return;
    }
    var modalEl = document.getElementById("dreDetailModal");
    var bodyEl = document.getElementById("dreDetailModalBody");
    var titleEl = document.getElementById("dreDetailModalLabel");
    if (!modalEl || !bodyEl || !titleEl) {
      return;
    }

    var detailUrl = root.getAttribute("data-detail-url");
    if (!detailUrl) {
      return;
    }

    var kind = btn.getAttribute("data-kind") || "receitas";
    var natureId = btn.getAttribute("data-nature-id") || "";
    var dateFrom = root.getAttribute("data-date-from") || "";
    var dateTo = root.getAttribute("data-date-to") || "";
    var companyId = root.getAttribute("data-company-id") || "";

    titleEl.textContent =
      kind === "despesas" ? "Detalhamento de Despesas" : "Detalhamento de Receitas";
    bodyEl.innerHTML = '<p class="text-muted mb-0">Carregando...</p>';
    var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();

    var url = new URL(detailUrl, window.location.origin);
    url.searchParams.set("kind", kind);
    url.searchParams.set("date_from", dateFrom);
    url.searchParams.set("date_to", dateTo);
    if (natureId) {
      url.searchParams.set("nature_id", natureId);
    }
    if (companyId) {
      url.searchParams.set("company_id", companyId);
    }

    fetch(url.toString(), {
      headers: { "X-Requested-With": "XMLHttpRequest", Accept: "text/html" },
    })
      .then(function (r) {
        return r.text();
      })
      .then(function (html) {
        bodyEl.innerHTML = html;
      })
      .catch(function () {
        bodyEl.innerHTML =
          '<p class="text-danger mb-0">Erro ao carregar detalhamento.</p>';
      });
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".dre-detail-trigger");
    if (btn) {
      if (!document.getElementById("dre-page")) {
        return;
      }
      openDreDetail(btn);
      return;
    }

    var pageLink = e.target.closest("a.dre-detail-pagination");
    if (!pageLink || !pageLink.href) {
      return;
    }
    var bodyEl = document.getElementById("dreDetailModalBody");
    if (!bodyEl || !bodyEl.contains(pageLink)) {
      return;
    }
    e.preventDefault();
    bodyEl.innerHTML = '<p class="text-muted mb-0">Carregando...</p>';
    fetch(pageLink.href, {
      headers: { "X-Requested-With": "XMLHttpRequest", Accept: "text/html" },
    })
      .then(function (r) {
        return r.text();
      })
      .then(function (html) {
        bodyEl.innerHTML = html;
      })
      .catch(function () {
        bodyEl.innerHTML =
          '<p class="text-danger mb-0">Erro ao carregar detalhamento.</p>';
      });
  });

  function initDreTurbo() {
    if (!document.getElementById("dre-page")) {
      return;
    }
    ensureChart()
      .then(initDreCharts)
      .catch(function () {});
  }

  document.addEventListener("DOMContentLoaded", initDreTurbo);
  document.addEventListener("turbo:frame-load", function (e) {
    if (e.target && e.target.id === "main-content") {
      initDreTurbo();
    }
  });
})();
