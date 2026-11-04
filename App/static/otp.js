/* Six-tile code entry: written-in digits, auto submit, animated states. */
(function () {
  const form = document.getElementById("otp-form");
  if (!form) return;
  const input = document.getElementById("otp-input");
  const tiles = [...form.querySelectorAll(".otp-tile")];
  const status = document.getElementById("otp-status");
  const length = Number(form.dataset.length);
  let busy = false;

  form.classList.add("is-enhanced");

  // Status line "writes" itself out, one character at a time.
  let typing;
  function say(text, tone) {
    clearInterval(typing);
    status.dataset.tone = tone || "";
    status.textContent = "";
    if (!text) return;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) { status.textContent = text; return; }
    let i = 0;
    typing = setInterval(() => {
      status.textContent = text.slice(0, ++i);
      if (i >= text.length) clearInterval(typing);
    }, 22);
  }

  function setRow(state) { form.dataset.state = state; }

  function render() {
    const value = input.value;
    tiles.forEach((tile, i) => {
      const glyph = tile.querySelector(".glyph");
      const ch = value[i] || "";
      if (glyph.textContent !== ch) {
        glyph.textContent = ch;
        if (ch) { tile.dataset.state = "filled"; tile.classList.remove("write"); void tile.offsetWidth; tile.classList.add("write"); }
      }
      if (!ch) tile.dataset.state = (i === value.length && document.activeElement === input) ? "active" : "empty";
    });
  }

  async function submit() {
    if (busy) return;
    busy = true;
    input.blur();
    setRow("checking");
    say("Checking…");
    let res;
    try {
      const r = await fetch(form.getAttribute("action") || location.pathname, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": ReCode.getCookie("csrftoken") },
        body: JSON.stringify({ code: input.value }),
      });
      res = await r.json();
    } catch (e) {
      res = { ok: false, state: "error", message: "Couldn't reach the server. Try again." };
    }
    if (res.ok) {
      setRow("verified");
      say("Verified.", "ok");
      setTimeout(() => (location.href = res.next), 1200);
      return;
    }
    setRow(res.state === "wrong" ? "wrong" : "expired");
    say(res.message + (res.state === "wrong" && res.attempts_left ? " " + res.attempts_left + " left." : ""), "bad");
    setTimeout(() => {
      busy = false;
      if (res.state === "wrong" || res.state === "error") {
        input.value = "";
        setRow("");
        render();
        input.focus();
      }
    }, 650);
  }

  input.addEventListener("input", () => {
    if (busy) return;
    input.value = input.value.replace(/\D/g, "").slice(0, length);
    if (form.dataset.state && form.dataset.state !== "checking") setRow("");
    render();
    if (input.value.length === length) submit();  // auto submit on the last digit
  });
  input.addEventListener("focus", render);
  input.addEventListener("blur", render);
  form.addEventListener("submit", (e) => { e.preventDefault(); if (input.value.length === length) submit(); });
  render();

  // Resend cooldown
  const resend = document.getElementById("resend-btn");
  if (!resend) return;
  let wait = Number(resend.dataset.wait);
  function tick() {
    if (wait > 0) { resend.disabled = true; resend.textContent = "Resend in " + wait + "s"; wait--; setTimeout(tick, 1000); }
    else { resend.disabled = false; resend.textContent = "Resend code"; }
  }
  tick();
})();
