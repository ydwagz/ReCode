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
  function tickCountdowns() {
    document.querySelectorAll("[data-countdown]").forEach((el) => {
      const left = Math.floor((new Date(el.dataset.countdown) - new Date()) / 1000);
      if (left <= 0) { el.textContent = el.dataset.doneText || "closed"; return; }
      const h = Math.floor(left / 3600), m = Math.floor((left % 3600) / 60), s = left % 60;
      el.textContent = String(h).padStart(2, "0") + ":" + String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
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

  window.ReCode = { getCookie, postJSON, getJSON, fmtDuration, escapeHTML };
})();
