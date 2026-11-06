// Pure helpers: file names, problem text, result formatting. No VS Code imports.

const LANGUAGES = { python: { ext: "py", comment: "#" }, javascript: { ext: "js", comment: "//" } };

function languageForFile(fileName) {
  if (/\.(py)$/i.test(fileName)) return "python";
  if (/\.(m?js|cjs)$/i.test(fileName)) return "javascript";
  return null;
}

function solutionFileName(language) {
  return `solution.${(LANGUAGES[language] || LANGUAGES.python).ext}`;
}

function callExample(fn, args) {
  return `${fn}(${args.map((a) => JSON.stringify(a)).join(", ")})`;
}

/** A short comment block for the top of the solution file. */
function solutionHeader(ch, language) {
  const c = (LANGUAGES[language] || LANGUAGES.python).comment;
  const fn = ch.function[language] || ch.function.python;
  const lines = [
    `${ch.title} (${ch.difficulty})`,
    `Problem: PROBLEM.md. Run examples: Ctrl+Alt+R. Submit: Ctrl+Alt+Enter.`,
    "",
    "Examples:",
    ...ch.examples.map((e) => `  ${callExample(fn, e.args)} -> ${JSON.stringify(e.expected)}`),
  ];
  return lines.map((l) => (l ? `${c} ${l}` : c)).join("\n") + "\n\n";
}

/** PROBLEM.md, opened as a Markdown preview next to the code. */
function problemMarkdown(ch, language) {
  const fn = ch.function[language] || ch.function.python;
  const parts = [
    `# ${ch.title}`,
    "",
    `**${capitalize(ch.difficulty)}** · ${ch.release_date} · closes ${new Date(ch.closes_at).toUTCString()}`,
    "",
    ch.description,
    "",
    "## Signature",
    "",
    "```",
    `${fn}(${ch.params.join(", ")})`,
    "```",
    "",
    "## Examples",
    "",
    ...ch.examples.flatMap((e) => ["```", `${callExample(fn, e.args)}`, `→ ${JSON.stringify(e.expected)}`, "```", ""]),
  ];
  if (ch.constraints) parts.push("## Constraints", "", "```", ch.constraints, "```", "");
  parts.push("Submitting also runs hidden tests, including a large input for the efficiency score.", "");
  return parts.join("\n");
}

function meta(ch) {
  return { challenge: ch.slug, title: ch.title, function: ch.function, params: ch.params, examples: ch.examples, url: ch.url };
}

function capitalize(s) { return s ? s[0].toUpperCase() + s.slice(1) : s; }

function formatDuration(totalSeconds) {
  if (totalSeconds == null) return "—";
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  if (h) return `${h}h ${String(m).padStart(2, "0")}m`;
  if (m) return `${m}m ${String(sec).padStart(2, "0")}s`;
  return `${sec}s`;
}

/** "3h 12m" until closesAt, or "closed". */
function timeLeft(closesAt, now = Date.now()) {
  const left = (new Date(closesAt).getTime() - now) / 1000;
  if (left <= 0) return "closed";
  const h = Math.floor(left / 3600), m = Math.floor((left % 3600) / 60);
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${Math.max(1, m)}m`;
}

const STATUS = {
  accepted: "All tests passed",
  wrong: "Some tests failed",
  error: "Your code raised an error",
  timeout: "Too slow: time limit exceeded",
};

/** Turn a run/submit response into lines for the output panel and a one-line summary. */
function formatResult(response, action) {
  const r = response.result;
  const entry = response.entry;
  const lines = [];
  const headline = STATUS[r.status] || r.status;
  lines.push(`${action}: ${headline}${r.total ? ` (${r.passed}/${r.total} tests, ${r.runtime_ms} ms)` : ""}`);
  if (r.error) lines.push("", ...String(r.error).split("\n").map((l) => "  " + l));
  (r.cases || []).forEach((c, i) => {
    const n = `Test ${i + 1}`;
    if (c.passed) lines.push(`  ✓ ${n}`);
    else if (c.expected === null && c.got === null) lines.push(`  ✗ ${n} (hidden)${c.error ? `: ${c.error}` : ""}`);
    else if (c.error) lines.push(`  ✗ ${n}: ${c.error}`);
    else lines.push(`  ✗ ${n}: returned ${JSON.stringify(c.got)}, expected ${JSON.stringify(c.expected)}`);
    if (c.stdout) lines.push(...String(c.stdout).trimEnd().split("\n").map((l) => `      ${l}`));
  });
  if (r.stdout) lines.push("", "Output:", ...String(r.stdout).trimEnd().split("\n").map((l) => "  " + l));
  let summary = `${headline}${r.total ? ` (${r.passed}/${r.total})` : ""}`;
  const solved = Boolean(entry && entry.solved);
  if (solved) {
    const b = entry.breakdown;
    const parts = `correct ${b.correctness}, attempts ${b.attempts}, speed ${b.speed}, efficiency ${b.efficiency}` + (b.hint_penalty ? `, hints -${b.hint_penalty}` : "");
    lines.push("", `Solved${entry.practice ? " (practice)" : ""}: ${entry.score}/100 in ${formatDuration(entry.solve_seconds)}`, `  ${parts}`);
    summary = `Solved: ${entry.score}/100${entry.practice ? " (practice)" : ""}`;
  } else if (entry) {
    lines.push("", `Failed attempts so far: ${entry.failed_attempts}`);
  }
  return { ok: r.status === "accepted", solved, summary, lines };
}

module.exports = {
  LANGUAGES, languageForFile, solutionFileName, solutionHeader, problemMarkdown, meta,
  formatDuration, timeLeft, formatResult, capitalize,
};
