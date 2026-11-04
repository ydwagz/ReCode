// ReCode VS Code extension. Zero dependencies: uses Node's global fetch (VS Code >= 1.80).
const vscode = require("vscode");
const path = require("path");
const fs = require("fs");

const TOKEN_KEY = "recode.apiToken";
let output;
let statusItem;

async function api(context, method, endpoint, body) {
  const token = await context.secrets.get(TOKEN_KEY);
  if (!token) throw new Error("No API token yet. Run “ReCode: Set API Token”.");
  const base = vscode.workspace.getConfiguration("recode").get("serverUrl").replace(/\/$/, "");
  const res = await fetch(`${base}/api/v1/${endpoint}`, {
    method,
    headers: { Authorization: `Token ${token}`, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({ ok: false, error: `HTTP ${res.status}` }));
  if (!data.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

function currentFile() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) throw new Error("Open your solution file first.");
  const file = editor.document.fileName;
  const language = /\.m?js$/.test(file) ? "javascript" : "python";
  const metaPath = path.join(path.dirname(file), ".recode.json");
  const meta = fs.existsSync(metaPath) ? JSON.parse(fs.readFileSync(metaPath, "utf8")) : {};
  return { code: editor.document.getText(), language, challenge: meta.challenge };
}

function showResult(title, res) {
  const r = res.result;
  output.clear();
  output.appendLine(`${title}: ${r.status.toUpperCase()} — ${r.passed}/${r.total} tests, ${r.runtime_ms} ms`);
  if (r.error) output.appendLine(r.error);
  r.cases.forEach((c, i) => {
    if (c.passed) return output.appendLine(`  ✓ test ${i + 1}`);
    if (c.expected === null) output.appendLine(`  ✗ test ${i + 1} (hidden) ${c.error || ""}`);
    else if (c.error) output.appendLine(`  ✗ test ${i + 1}: ${c.error}`);
    else output.appendLine(`  ✗ test ${i + 1}: got ${JSON.stringify(c.got)}, expected ${JSON.stringify(c.expected)}`);
    if (c.stdout) output.appendLine(`    stdout: ${c.stdout.trim()}`);
  });
  if (res.entry && res.entry.solved) {
    const b = res.entry.breakdown;
    output.appendLine(`\n🎉 Solved! ${res.entry.score}/100 (correct ${b.correctness}, attempts ${b.attempts}, speed ${b.speed}, efficiency ${b.efficiency}${b.hint_penalty ? `, hints -${b.hint_penalty}` : ""})`);
    vscode.window.showInformationMessage(`ReCode: solved for ${res.entry.score} points! 🎉`);
  } else if (r.status !== "accepted") {
    vscode.window.showWarningMessage(`ReCode: ${r.status} (${r.passed}/${r.total})`);
  }
  output.show(true);
}

function guard(fn) {
  return async (...args) => {
    try { await fn(...args); } catch (err) { vscode.window.showErrorMessage(`ReCode: ${err.message}`); }
  };
}

function activate(context) {
  output = vscode.window.createOutputChannel("ReCode");
  statusItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  statusItem.command = "recode.status";
  statusItem.text = "$(flame) ReCode";
  statusItem.show();
  context.subscriptions.push(output, statusItem);

  const register = (id, fn) => context.subscriptions.push(vscode.commands.registerCommand(id, guard(fn)));

  register("recode.setToken", async () => {
    const token = await vscode.window.showInputBox({ prompt: "Paste your ReCode token (Settings → Integrations)", password: true, ignoreFocusOut: true });
    if (!token) return;
    await context.secrets.store(TOKEN_KEY, token.trim());
    const me = await api(context, "GET", "me/");
    statusItem.text = `$(flame) ${me.streak.current}`;
    vscode.window.showInformationMessage(`ReCode: connected as ${me.username}.`);
  });

  register("recode.status", async () => {
    const me = await api(context, "GET", "me/");
    statusItem.text = `$(flame) ${me.streak.current}`;
    vscode.window.showInformationMessage(`🔥 ${me.streak.current} day streak (${me.streak.state}) · 🧊 ${me.streak.freezes} freezes · ${me.stats.solved} solved`);
  });

  register("recode.pull", async () => {
    const folder = vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
    if (!folder) throw new Error("Open a folder first.");
    const lang = vscode.workspace.getConfiguration("recode").get("language");
    const { challenge: ch } = await api(context, "GET", "today/");
    const dir = path.join(folder.uri.fsPath, ch.slug);
    fs.mkdirSync(dir, { recursive: true });
    const file = path.join(dir, lang === "javascript" ? "solution.js" : "solution.py");
    const c = lang === "javascript" ? "//" : "#";
    const header = [`${ch.title} (${ch.difficulty}) — closes ${ch.closes_at}`, "", ...ch.description.split("\n"), "", "Examples:",
      ...ch.examples.map((e) => `  ${JSON.stringify(e.args)} -> ${JSON.stringify(e.expected)}`)].map((l) => `${c} ${l}`.trimEnd()).join("\n");
    if (!fs.existsSync(file)) fs.writeFileSync(file, `${header}\n\n${ch.starter_code[lang]}`);
    fs.writeFileSync(path.join(dir, ".recode.json"), JSON.stringify({ challenge: ch.slug, function: ch.function, examples: ch.examples }, null, 2));
    await vscode.window.showTextDocument(await vscode.workspace.openTextDocument(file));
  });

  register("recode.run", async () => {
    const payload = currentFile();
    await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: "ReCode: running examples…" }, async () => {
      showResult("Run", await api(context, "POST", "run/", payload));
    });
  });

  register("recode.submit", async () => {
    const payload = currentFile();
    const mode = await vscode.window.showQuickPick(["solo", "team"], { placeHolder: "Submit as… (ignored if you already started)" });
    if (!mode) return;
    await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: "ReCode: judging…" }, async () => {
      showResult("Submit", await api(context, "POST", "submit/", { ...payload, mode }));
    });
  });
}

function deactivate() {}

module.exports = { activate, deactivate };
