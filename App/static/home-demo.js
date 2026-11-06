/* Home page: a round of ReCode, replayed on a loop.
   Type a solution -> tests ripple then flip green -> score tiles fill -> "You" lands on the board. */
(function () {
  const demo = document.getElementById("demo");
  if (!demo) return;

  const ROUNDS = [
    {
      file: "two_sum.py",
      code: "def two_sum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        if target - n in seen:\n            return [seen[target - n], i]\n        seen[n] = i",
      score: [60, 20, 10, 6.4],
    },
    {
      file: "climb_stairs.py",
      code: "def climb_stairs(n):\n    a, b = 1, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a",
      score: [60, 15, 10, 9.6],
    },
  ];

  const codeEl = document.getElementById("demo-code");
  const fileEl = document.getElementById("demo-file");
  const chips = [...document.querySelectorAll("#demo-tests .case-chip")];
  const tiles = [...document.querySelectorAll("#demo-score .score-tile")];
  const you = demo.querySelector(".demo-you");
  const totalEl = document.getElementById("demo-total");
  const pushedRank = document.getElementById("demo-pushed-rank");
  const esc = (s) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

  // Tiny Python highlighter: enough for the two snippets above.
  function highlight(src) {
    return esc(src)
      .replace(/\b(def|for|in|if|return|while|else)\b/g, "<span class='tk-k'>$1</span>")
      .replace(/\b(enumerate|range|len)\b/g, "<span class='tk-b'>$1</span>")
      .replace(/(<span class='tk-k'>def<\/span> )(\w+)/g, "$1<span class='tk-f'>$2</span>")
      .replace(/\b(\d+)\b/g, "<span class='tk-n'>$1</span>");
  }

  // ---- pausing: only play while visible on screen and the tab is in front
  let onScreen = true;
  if ("IntersectionObserver" in window) {
    new IntersectionObserver((e) => { onScreen = e[0].isIntersecting; }, { threshold: 0.2 }).observe(demo);
  }
  const running = () => onScreen && document.visibilityState === "visible";
  // Waits `ms` of visible time (the clock stops while the demo is off screen or the tab is hidden).
  const sleep = (ms) => new Promise((resolve) => {
    let left = ms, last = performance.now();
    (function tick() {
      const now = performance.now();
      if (running()) left -= now - last;
      last = now;
      left <= 0 ? resolve() : setTimeout(tick, Math.min(left, 50));
    })();
  });

  function setTile(tile, value) {
    const max = Number(tile.dataset.max), pct = Math.round((value / max) * 100);
    tile.style.setProperty("--fill", pct + "%");
    tile.classList.toggle("full", pct >= 99);
    tile.classList.toggle("partial", pct > 0 && pct < 99);
    tile.querySelector(".value").firstChild.textContent = (Math.round(value * 10) / 10).toString();
  }

  function countTo(update, target, ms) {
    return new Promise((resolve) => {
      const start = performance.now();
      (function step(now) {
        const t = Math.min(1, (now - start) / ms), eased = 1 - Math.pow(1 - t, 3);
        update(target * eased);
        t < 1 ? requestAnimationFrame(step) : resolve();
      })(start);
    });
  }

  function reset(round) {
    fileEl.textContent = round.file;
    codeEl.innerHTML = "<span class='demo-caret'></span>";
    chips.forEach((c) => (c.className = "case-chip"));
    tiles.forEach((t) => setTile(t, 0));
    you.classList.remove("is-in");
    pushedRank.textContent = "2";
    totalEl.textContent = "0.0";
    demo.classList.remove("is-fading");
  }

  function finalFrame(round) {
    fileEl.textContent = round.file;
    codeEl.innerHTML = highlight(round.code);
    chips.forEach((c, i) => { c.className = "case-chip pass"; c.style.setProperty("--i", i); });
    tiles.forEach((t, i) => setTile(t, round.score[i]));
    you.classList.add("is-in");
    pushedRank.textContent = "3";
    totalEl.textContent = round.score.reduce((a, b) => a + b, 0).toFixed(1);
  }

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    finalFrame(ROUNDS[0]);
    return;
  }

  async function play(round) {
    reset(round);
    await sleep(500);
    // 1. type it out
    let typed = "";
    for (const ch of round.code) {
      typed += ch;
      codeEl.innerHTML = highlight(typed) + "<span class='demo-caret'></span>";
      await sleep(ch === "\n" ? 110 : 14 + Math.random() * 22);
    }
    await sleep(450);
    // 2. run the tests: ripple, then flip green one by one
    chips.forEach((c, i) => { c.style.setProperty("--i", i); c.className = "case-chip pending"; });
    await sleep(900);
    chips.forEach((c) => (c.className = "case-chip reveal pass"));
    await sleep(chips.length * 70 + 500);
    // 3. score fills
    await Promise.all(tiles.map((t, i) => countTo((v) => setTile(t, v), round.score[i], 800)));
    await sleep(250);
    // 4. you hit the board and push Dato down a place
    you.classList.add("is-in");
    setTimeout(() => (pushedRank.textContent = "3"), 200);
    await countTo((v) => (totalEl.textContent = v.toFixed(1)), round.score.reduce((a, b) => a + b, 0), 700);
    await sleep(2800);
    demo.classList.add("is-fading");
    await sleep(350);
  }

  (async function loop() {
    for (let i = 0; ; i = (i + 1) % ROUNDS.length) await play(ROUNDS[i]);
  })();
})();
