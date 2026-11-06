// Runs against a live ReCode server. Set RECODE_TEST_URL and RECODE_TEST_TOKEN (a fresh account's
// token from Settings → Integrations); otherwise these tests are skipped.
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { ApiError, ReCodeClient } = require("../src/api");
const { createMock, loadExtension } = require("./vscode-mock");

const URL = process.env.RECODE_TEST_URL;
const TOKEN = process.env.RECODE_TEST_TOKEN;
const skip = !URL || !TOKEN ? "set RECODE_TEST_URL and RECODE_TEST_TOKEN to run" : false;

const TWO_SUM = "def two_sum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        if target - n in seen:\n            return [seen[target - n], i]\n        seen[n] = i\n";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

test("API client", { skip }, async (t) => {
  const api = new ReCodeClient({ baseUrl: URL + "/", token: TOKEN });
  await t.test("me / today / challenges / leaderboard", async () => {
    const me = await api.me();
    assert.ok(me.username);
    const today = await api.today();
    assert.ok(today.slug && today.starter_code.python);
    const list = await api.challenges();
    assert.strictEqual(list[0].slug, today.slug);
    assert.ok(Array.isArray(await api.leaderboard(5)));
  });
  await t.test("bad token is a 401", async () => {
    const bad = new ReCodeClient({ baseUrl: URL, token: "nope".repeat(10) });
    await assert.rejects(bad.me(), (e) => e instanceof ApiError && e.status === 401);
  });
  await t.test("server down is a friendly message", async () => {
    const down = new ReCodeClient({ baseUrl: "http://127.0.0.1:9", token: TOKEN, timeoutMs: 3000 });
    await assert.rejects(down.me(), (e) => e.status === 0 && /Can't reach/.test(e.message));
  });
});

test("extension end to end", { skip }, async (t) => {
  const workspace = fs.mkdtempSync(path.join(os.tmpdir(), "recode-ws-"));
  const mock = createMock({ workspace, config: { serverUrl: URL, language: "python", confirmSubmit: false } });
  const ext = loadExtension(mock);
  let api = await ext.activate(mock.context);

  await t.test("starts signed out with a Sign in prompt", async () => {
    assert.strictEqual(mock.log.contexts["recode.signedIn"], false);
    assert.deepStrictEqual(await mock.vscode.__tree.getChildren(), []);
  });

  await t.test("sign in validates the token, stores it and loads the sidebar", async () => {
    mock.answers.input.push(URL, "wrong-token-wrong-token-xx");
    mock.answers.message.push(undefined); // dismiss "Try again"
    await mock.vscode.commands.executeCommand("recode.signIn");
    assert.ok(mock.log.error.some((m) => /wasn't accepted/.test(m)));
    assert.strictEqual(mock.secrets.has("recode.apiToken"), false);

    mock.answers.input.push(URL, TOKEN);
    await mock.vscode.commands.executeCommand("recode.signIn");
    assert.strictEqual(mock.secrets.get("recode.apiToken"), TOKEN);
    assert.strictEqual(mock.log.contexts["recode.signedIn"], true);
    const sections = await mock.vscode.__tree.getChildren();
    assert.deepStrictEqual(sections.map((s) => s.label), ["Today", "You", "Top 5 today", "Problems"]);
    const today = await mock.vscode.__tree.getChildren(sections[0]);
    assert.strictEqual(today[1].label, "Closes in");
    const problems = await mock.vscode.__tree.getChildren(sections[3]);
    assert.ok(problems.length >= 1 && problems[0].command.command === "recode.pullProblem");
  });

  let solutionPath;
  await t.test("pull today's problem writes files and opens them", async () => {
    await mock.vscode.commands.executeCommand("recode.pullToday");
    const opened = mock.log.opened.at(-1);
    assert.ok(opened.startsWith(path.join(workspace, "recode")));
    const dir = path.dirname(opened);
    assert.ok(fs.existsSync(path.join(dir, "PROBLEM.md")));
    assert.ok(fs.existsSync(path.join(dir, ".recode.json")));
    assert.match(fs.readFileSync(opened, "utf8"), /^# /);
    assert.strictEqual(mock.log.previews.at(-1), path.join(dir, "PROBLEM.md"));
    const lenses = mock.lenses(mock.makeDocument(opened));
    assert.deepStrictEqual(lenses.map((l) => l.command.command), ["recode.run", "recode.submit", "recode.openInBrowser"]);
  });

  await t.test("pull a past problem by picking it from the list", async () => {
    mock.answers.quickPick.push((items) => items.find((i) => i.label === "Two Sum"));
    await mock.vscode.commands.executeCommand("recode.pullProblem");
    solutionPath = mock.log.opened.at(-1);
    assert.match(solutionPath, /two-sum-/);
  });

  await t.test("run the starter code: examples fail, details in the output panel", async () => {
    await sleep(3200); // the server allows one run every 3s
    await mock.vscode.commands.executeCommand("recode.run", mock.vscode.Uri.file(solutionPath));
    assert.ok(mock.log.warn.some((m) => /ReCode run: Some tests failed/.test(m)), JSON.stringify(mock.log));
  });

  await t.test("submit a correct solution: solved with a score", async () => {
    fs.writeFileSync(solutionPath, TWO_SUM);
    await sleep(3200);
    mock.answers.message.push(undefined); // ignore "Open leaderboard"
    await mock.vscode.commands.executeCommand("recode.submit", mock.vscode.Uri.file(solutionPath));
    assert.ok(mock.log.info.some((m) => /Solved: \d+(\.\d+)?\/100 \(practice\)/.test(m)), JSON.stringify(mock.log.info));
  });

  await t.test("files that aren't Python/JS get a clear message", async () => {
    const md = path.join(path.dirname(solutionPath), "PROBLEM.md");
    await mock.vscode.commands.executeCommand("recode.run", mock.vscode.Uri.file(md));
    assert.ok(mock.log.error.some((m) => /accepts Python \(\.py\) and JavaScript/.test(m)));
  });

  await t.test("sign out clears the token", async () => {
    await mock.vscode.commands.executeCommand("recode.signOut");
    assert.strictEqual(mock.secrets.has("recode.apiToken"), false);
    assert.strictEqual(mock.log.contexts["recode.signedIn"], false);
  });

  mock.context.subscriptions.forEach((s) => s.dispose && s.dispose());
  fs.rmSync(workspace, { recursive: true, force: true });
});
