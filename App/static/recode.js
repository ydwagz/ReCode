/* Shared helpers for every ReCode page. */
(function () {
  function getCookie(name) {
    const match = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[2]) : "";
  }

  async function postJSON(url, data) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
      body: JSON.stringify(data || {}),
      credentials: "same-origin",
    });
    let body;
    try { body = await res.json(); } catch (e) { body = { ok: false, error: "Server error (" + res.status + ")" }; }
    return body;
  }

  async function getJSON(url) {
    const res = await fetch(url, { credentials: "same-origin" });
    return res.json();
  }

  function fmtDuration(totalSeconds) {
    if (totalSeconds == null) return "—";
    totalSeconds = Math.max(0, Math.floor(totalSeconds));
    const h = Math.floor(totalSeconds / 3600), m = Math.floor((totalSeconds % 3600) / 60), s = totalSeconds % 60;
    if (h) return h + "h " + String(m).padStart(2, "0") + "m";
    if (m) return m + "m " + String(s).padStart(2, "0") + "s";
    return s + "s";
  }

  function escapeHTML(str) {
    return String(str == null ? "" : str).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // <span data-countdown="2026-01-01T00:00:00Z">: live "hh:mm:ss" countdown.
  // With class "tile-clock" each digit is drawn as a tile.
  function tickCountdowns() {
    document.querySelectorAll("[data-countdown]").forEach((el) => {
      const left = Math.floor((new Date(el.dataset.countdown) - new Date()) / 1000);
      if (left <= 0) { el.textContent = el.dataset.doneText || "closed"; el.classList.remove("tile-clock"); return; }
      const h = Math.floor(left / 3600), m = Math.floor((left % 3600) / 60), s = left % 60;
      const text = String(h).padStart(2, "0") + ":" + String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
      if (!el.classList.contains("tile-clock")) { el.textContent = text; return; }
      if (el.children.length !== text.length) {
        el.innerHTML = text.split("").map((c) => c === ":" ? "<span class='sep'>:</span>" : "<span class='tile'></span>").join("");
        el.setAttribute("aria-label", "Closes in " + text);
      }
      text.split("").forEach((c, i) => { if (c !== ":" && el.children[i].textContent !== c) el.children[i].textContent = c; });
    });
  }
  tickCountdowns();
  setInterval(tickCountdowns, 1000);

  // Comment votes: <button data-vote="up" data-url="...">
  document.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-vote]");
    if (!btn) return;
    event.preventDefault();
    const res = await postJSON(btn.dataset.url, { value: btn.dataset.vote });
    if (!res.ok) { if (res.error) alert(res.error); return; }
    const box = btn.closest(".vote-box");
    box.querySelector(".vote-score").textContent = res.score;
    box.querySelectorAll("[data-vote]").forEach((b) => b.classList.remove("voted"));
    if (res.mine === 1) box.querySelector('[data-vote="up"]').classList.add("voted");
    if (res.mine === -1) box.querySelector('[data-vote="down"]').classList.add("voted");
  });

  // Copy buttons: <button data-copy="#selector">
  document.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-copy]");
    if (!btn) return;
    const target = document.querySelector(btn.dataset.copy);
    const text = target.value !== undefined ? target.value : target.textContent;
    navigator.clipboard.writeText(text).then(() => {
      const old = btn.textContent;
      btn.textContent = "Copied!";
      setTimeout(() => (btn.textContent = old), 1200);
    });
  });

  const reduceMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const html = document.documentElement;

  // ---------------------------------------------------------------- loading
  // The loader only becomes visible if a page takes longer than ~250ms (CSS delay),
  // so fast navigations never flash it.
  const doneLoading = () => html.classList.remove("is-loading", "is-navigating");
  doneLoading();
  window.addEventListener("pageshow", doneLoading);  // back/forward cache

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[href]");
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.href, location.href);
    if (link.target || link.hasAttribute("download") || url.origin !== location.origin) return;
    if (url.pathname === location.pathname && url.search === location.search && url.hash) return;  // in-page anchor
    if (link.getAttribute("href").startsWith("#") || link.dataset.bsToggle) return;
    html.classList.add("is-navigating");
  });

  // Normal (non-JS) form submits: show the loader and a busy state on the button pressed.
  document.addEventListener("submit", (event) => {
    if (event.defaultPrevented) return;
    const form = event.target;
    if (form.dataset.noLoader !== undefined) return;
    const button = event.submitter;
    if (button) {
      button.classList.add("is-busy");
      setTimeout(() => (button.disabled = true), 0);  // after the browser has read its value
    }
    html.classList.add("is-navigating");
  });

  // ------------------------------------------------------------ count-ups
  // Big numbers count up from zero the first time they scroll into view.
  function countUp(el) {
    const node = [...el.childNodes].find((n) => n.nodeType === 3 && /\d/.test(n.textContent));
    if (!node) return;
    const match = node.textContent.match(/-?\d+(\.\d+)?/);
    if (!match) return;
    const target = parseFloat(match[0]);
    const decimals = match[1] ? match[1].length - 1 : 0;
    const before = node.textContent.slice(0, match.index), after = node.textContent.slice(match.index + match[0].length);
    const start = performance.now(), duration = 900;
    const step = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      node.textContent = before + (target * eased).toFixed(decimals) + after;
      if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }
  if (!reduceMotion() && !html.classList.contains("no-enter") && "IntersectionObserver" in window) {
    const seen = new IntersectionObserver((entries) => entries.forEach((entry) => {
      if (entry.isIntersecting) { countUp(entry.target); seen.unobserve(entry.target); }
    }), { threshold: 0.4 });
    document.querySelectorAll(".score-total, .streak-number, .stat strong, .mini-stats strong, .team-kpis strong, .my-rank strong, .points-table .pts, .score-tile .value")
      .forEach((el) => seen.observe(el));
  }

  // ------------------------------------------------------------ flash messages
  document.querySelectorAll(".flash-success, .flash-info").forEach((flash) => {
    setTimeout(() => { flash.classList.add("is-leaving"); setTimeout(() => flash.remove(), 400); }, 5000);
  });

  // ------------------------------------------------------------ theme
  // Follows the system until the person picks one; the new theme ripples out from the button.
  const toggle = document.getElementById("theme-toggle");
  if (toggle) toggle.addEventListener("click", () => {
    const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const current = html.dataset.theme || (systemDark ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    const apply = () => {
      html.dataset.theme = next;
      try { localStorage.setItem("recode-theme", next); } catch (e) {}
    };
    if (!document.startViewTransition || reduceMotion()) return apply();
    const rect = toggle.getBoundingClientRect();
    html.style.setProperty("--vt-x", rect.left + rect.width / 2 + "px");
    html.style.setProperty("--vt-y", rect.top + rect.height / 2 + "px");
    // While the theme reveal runs, the icons swap instantly and cross-fade in their own layer
    // (style transitions are held during a view transition and would otherwise lag behind).
    html.classList.add("theme-switching");
    document.startViewTransition(apply).finished.finally(() => html.classList.remove("theme-switching"));
  });

  // Score breakdown as four tiles (used by the challenge page after a submit).
  function scoreTiles(b) {
    const parts = [["Correct", b.correctness, 60], ["Attempts", b.attempts, 20], ["Speed", b.speed, 10], ["Efficiency", b.efficiency, 10]];
    return "<div class='score-tiles'>" + parts.map(([label, value, max]) => {
      const pct = Math.round((value / max) * 100);
      const cls = pct >= 99 ? "full" : pct > 0 ? "partial" : "";
      return "<div class='score-tile " + cls + "' style='--fill:" + pct + "%'><span class='value'>" +
        (Math.round(value * 10) / 10) + "<small>/" + max + "</small></span><span class='label'>" + label + "</span></div>";
    }).join("") + "</div>";
  }

  window.ReCode = { getCookie, postJSON, getJSON, fmtDuration, escapeHTML, scoreTiles };
})();
