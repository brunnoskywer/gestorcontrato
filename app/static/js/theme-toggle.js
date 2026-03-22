/**
 * Light / dark theme toggle (Bootstrap 5.3 color modes).
 * Persists preference in localStorage under STORAGE_KEY.
 */
(function () {
  var STORAGE_KEY = "gestorContrato-theme";

  function getStoredTheme() {
    try {
      var t = localStorage.getItem(STORAGE_KEY);
      if (t === "dark" || t === "light") return t;
    } catch (e) {}
    return null;
  }

  function currentTheme() {
    var fromDom = document.documentElement.getAttribute("data-bs-theme");
    if (fromDom === "dark" || fromDom === "light") return fromDom;
    var s = getStoredTheme();
    if (s) return s;
    if (
      window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches
    ) {
      return "dark";
    }
    return "light";
  }

  function applyTheme(theme) {
    if (theme !== "dark" && theme !== "light") theme = "light";
    document.documentElement.setAttribute("data-bs-theme", theme);
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (e) {}
    updateToggleUi(theme);
  }

  function updateToggleUi(theme) {
    var btn = document.getElementById("theme-toggle");
    if (!btn) return;
    var isDark = theme === "dark";
    btn.setAttribute("aria-pressed", isDark ? "true" : "false");
    btn.setAttribute(
      "aria-label",
      isDark ? "Switch to light theme" : "Switch to dark theme",
    );
    btn.title = isDark ? "Light mode" : "Dark mode";
    var moon = btn.querySelector(".theme-icon-moon");
    var sun = btn.querySelector(".theme-icon-sun");
    if (moon && sun) {
      moon.hidden = isDark;
      sun.hidden = !isDark;
    }
  }

  function onToggleClick() {
    var next = currentTheme() === "dark" ? "light" : "dark";
    applyTheme(next);
  }

  function bindToggleOnce() {
    var btn = document.getElementById("theme-toggle");
    if (!btn || btn.dataset.themeBound === "1") return;
    btn.dataset.themeBound = "1";
    btn.addEventListener("click", onToggleClick);
  }

  function init() {
    bindToggleOnce();
    // DOM theme is set by inline script (localStorage or prefers-color-scheme)
    updateToggleUi(currentTheme());
  }

  document.addEventListener("DOMContentLoaded", init);
  document.addEventListener("turbo:load", init);
})();
