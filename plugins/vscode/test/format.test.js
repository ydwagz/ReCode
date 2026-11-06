const test = require("node:test");
const assert = require("node:assert");
const fmt = require("../src/format");

const CH = {
  slug: "two-sum-2026-11-01", title: "Two Sum", difficulty: "easy", release_date: "2026-11-01",
  closes_at: "2026-11-02T00:00:00+00:00", description: "Return the indices.", constraints: "2 ≤ n",
  function: { python: "two_sum", javascript: "twoSum" }, params: ["nums", "target"], url: "/challenges/two-sum-2026-11-01/",
  examples: [{ args: [[2, 7, 11, 15], 9], expected: [0, 1] }],
};

test("language detection and file names", () => {
  assert.strictEqual(fmt.languageForFile("a/solution.py"), "python");
  assert.strictEqual(fmt.languageForFile("solution.mjs"), "javascript");
  assert.strictEqual(fmt.languageForFile("notes.md"), null);
  assert.strictEqual(fmt.solutionFileName("javascript"), "solution.js");
});

test("solution header uses the right comment style and function name", () => {
  assert.match(fmt.solutionHeader(CH, "python"), /^# Two Sum \(easy\)/);
  assert.match(fmt.solutionHeader(CH, "python"), /two_sum\(\[2,7,11,15\], 9\) -> \[0,1\]/);
  assert.match(fmt.solutionHeader(CH, "javascript"), /^\/\/ Two Sum/);
  assert.match(fmt.solutionHeader(CH, "javascript"), /twoSum\(/);
});

test("problem markdown has the essentials", () => {
  const md = fmt.problemMarkdown(CH, "python");
  for (const part of ["# Two Sum", "Return the indices.", "two_sum(nums, target)", "## Constraints"]) assert.ok(md.includes(part), part);
});

test("time left and durations", () => {
  const now = Date.parse("2026-11-01T20:30:00Z");
  assert.strictEqual(fmt.timeLeft(CH.closes_at, now), "3h 30m");
  assert.strictEqual(fmt.timeLeft(CH.closes_at, Date.parse("2026-11-02T01:00:00Z")), "closed");
  assert.strictEqual(fmt.formatDuration(95), "1m 35s");
});

test("results: failed, hidden and solved", () => {
  const failed = fmt.formatResult({ result: { status: "wrong", passed: 1, total: 3, runtime_ms: 2, error: "", stdout: "",
    cases: [{ passed: true }, { passed: false, got: 1, expected: 2, error: "" }, { passed: false, got: null, expected: null, error: "" }] },
    entry: { solved: false, failed_attempts: 1 } }, "Submit");
  assert.strictEqual(failed.ok, false);
  assert.ok(failed.lines.some((l) => l.includes("returned 1, expected 2")));
  assert.ok(failed.lines.some((l) => l.includes("Test 3 (hidden)")));
  const solved = fmt.formatResult({ result: { status: "accepted", passed: 3, total: 3, runtime_ms: 1, cases: [] },
    entry: { solved: true, score: 96.4, solve_seconds: 300, practice: false, breakdown: { correctness: 60, attempts: 20, speed: 10, efficiency: 6.4, hint_penalty: 0 } } }, "Submit");
  assert.strictEqual(solved.summary, "Solved: 96.4/100");
});
