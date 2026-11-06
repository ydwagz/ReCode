// ReCode for VS Code: pull the daily problem, run and submit from your editor.
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
const { ApiError, ReCodeClient } = require("./src/api");
const fmt = require("./src/format");
const { ReCodeTree } = require("./src/sidebar");

const TOKEN_KEY = "recode.apiToken";
const META_FILE = ".recode.json";
const REFRESH_MS = 5 * 60 * 1000;
const TICK_MS = 30 * 1000;

let output;

function activate(context) {
  output = vscode.window.createOutputChannel("ReCode");
  const state = { signedIn: false, me: null, today: null, board: [], problems: [], error: null };
  const tree = new ReCodeTree(state);
  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  status.command = "recode.menu";
  status.show();
  const lensChanged = new vscode.EventEmitter();
  context.subscriptions.push(output, status, lensChanged, vscode.window.createTreeView("recode.sidebar", { treeDataProvider: tree }));

  const config = () => vscode.workspace.getConfiguration("recode");
  const serverUrl = () => String(config().get("serverUrl") || "http://127.0.0.1:8000").replace(/\/+$/, "");

  async function client() {
    const token = await context.secrets.get(TOKEN_KEY);
    if (!token) throw new ApiError("Sign in to ReCode first.", 401);
    return new ReCodeClient({ baseUrl: serverUrl(), token });
  }

  // ------------------------------------------------------------------ state
  async function setSignedIn(value) {
    state.signedIn = value;
    await vscode.commands.executeCommand("setContext", "recode.signedIn", value);
  }

  function renderStatus() {
    if (!state.signedIn) {
      status.text = "$(sign-in) ReCode";
      status.tooltip = "Sign in to ReCode";
      return;
    }
    if (!state.today || !state.me) {
      status.text = "$(sync~spin) ReCode";
      status.tooltip = state.error || "Loading…";
      return;
    }
    const solved = state.today.entry && state.today.entry.solved;
    status.text = `$(flame) ${state.me.streak.current}  ${solved ? "$(pass-filled) solved" : `$(clock) ${fmt.timeLeft(state.today.closes_at)}`}`;
    status.tooltip = `${state.today.title} (${state.today.difficulty})\n` +
      (solved ? `Solved: ${state.today.entry.score}/100` : `Closes in ${fmt.timeLeft(state.today.closes_at)}`) +
      `\n${state.me.streak.current} day streak\nClick for ReCode actions`;
  }

  async function refresh({ quiet = true } = {}) {
    if (!state.signedIn) { renderStatus(); tree.refresh(); return; }
    try {
      const api = await client();
      const [me, today, board, problems] = await Promise.all([api.me(), api.today(), api.leaderboard(5), api.challenges()]);
      Object.assign(state, { me, today, board, problems, error: null });
    } catch (err) {
      state.error = err.message;
      if (err.status === 401) await setSignedIn(false);
      if (!quiet) vscode.window.showErrorMessage(`ReCode: ${err.message}`);
    }
    renderStatus();
    tree.refresh();
    lensChanged.fire();
  }

  // ------------------------------------------------------------ files
  async function problemsRoot() {
    const folders = vscode.workspace.workspaceFolders;
    if (folders && folders.length) return path.join(folders[0].uri.fsPath, config().get("folder") || "recode");
    const saved = context.globalState.get("recode.root");
    if (saved && fs.existsSync(saved)) return saved;
    const picked = await vscode.window.showOpenDialog({ canSelectFolders: true, canSelectFiles: false, openLabel: "Keep ReCode problems here" });
    if (!picked || !picked.length) return null;
    await context.globalState.update("recode.root", picked[0].fsPath);
    return picked[0].fsPath;
  }

  function metaFor(document) {
    if (!document || document.uri.scheme !== "file") return null;
    const file = path.join(path.dirname(document.uri.fsPath), META_FILE);
    try { return JSON.parse(fs.readFileSync(file, "utf8")); } catch (_) { return null; }
  }

  async function pull(slug) {
    const api = await client();
    const ch = await vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title: "ReCode: fetching the problem…" },
      () => (slug ? api.challenge(slug) : api.today()),
    );
    const root = await problemsRoot();
    if (!root) return;
    const language = config().get("language") || "python";
    const dir = path.join(root, ch.slug);
    fs.mkdirSync(dir, { recursive: true });
    const solution = path.join(dir, fmt.solutionFileName(language));
    if (!fs.existsSync(solution)) {
      const starter = ch.starter_code[language] || ch.starter_code.python;
      fs.writeFileSync(solution, fmt.solutionHeader(ch, language) + starter);
    }
    fs.writeFileSync(path.join(dir, "PROBLEM.md"), fmt.problemMarkdown(ch, language));
    fs.writeFileSync(path.join(dir, META_FILE), JSON.stringify(fmt.meta(ch), null, 2));
    const doc = await vscode.workspace.openTextDocument(solution);
    await vscode.window.showTextDocument(doc, { viewColumn: vscode.ViewColumn.One });
    if (config().get("openProblemOnPull") !== false) {
      await vscode.commands.executeCommand("markdown.showPreviewToSide", vscode.Uri.file(path.join(dir, "PROBLEM.md")));
    }
    lensChanged.fire();
  }

  // ------------------------------------------------------------ run / submit
  async function currentSolution(uri) {
    const editor = vscode.window.activeTextEditor;
    const document = uri ? await vscode.workspace.openTextDocument(uri) : editor && editor.document;
    if (!document) throw new ApiError("Open your solution file first.", 400);
    const language = fmt.languageForFile(document.fileName);
    if (!language) throw new ApiError("ReCode accepts Python (.py) and JavaScript (.js) files.", 400);
    if (document.isDirty) await document.save();
    const m = metaFor(document);
    return { document, language, code: document.getText(), challenge: m ? m.challenge : undefined, title: m ? m.title : "today's problem" };
  }

  function show(response, action) {
    const result = fmt.formatResult(response, action);
    output.appendLine(`── ${new Date().toLocaleTimeString()} ${"─".repeat(40)}`);
    result.lines.forEach((l) => output.appendLine(l));
    output.appendLine("");
    if (config().get("showOutputOnRun") !== false) output.show(true);
    return result;
  }

  async function run(uri) {
    const sol = await currentSolution(uri);
    const api = await client();
    const response = await vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title: `ReCode: running the examples for ${sol.title}…` },
      () => api.run(sol),
    );
    const result = show(response, "Run");
    const say = result.ok ? vscode.window.showInformationMessage : vscode.window.showWarningMessage;
    say(`ReCode run: ${result.summary}`);
  }

  async function chooseMode(api, slug) {
    const me = state.me || (await api.me());
    if (!me.team) return undefined;
    const ch = slug ? await api.challenge(slug) : await api.today();
    if (ch.entry) return undefined; // already playing: mode is locked
    const pick = await vscode.window.showQuickPick(
      [{ label: "Solo", description: "ranked as you", mode: "solo" }, { label: `With ${me.team.name}`, description: "one shared entry", mode: "team" }],
      { placeHolder: "How do you want to play this one?" },
    );
    if (!pick) throw new ApiError("Cancelled.", -1);
    return pick.mode;
  }

  async function submit(uri) {
    const sol = await currentSolution(uri);
    const api = await client();
    const confirm = config().get("confirmSubmit") !== false;
    if (confirm) {
      const go = await vscode.window.showWarningMessage(
        `Submit ${path.basename(sol.document.fileName)} for ${sol.title}? A failed submission costs attempt points.`,
        { modal: true }, "Submit",
      );
      if (go !== "Submit") return;
    }
    const mode = await chooseMode(api, sol.challenge);
    const response = await vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title: "ReCode: judging all tests…" },
      () => api.submit({ ...sol, mode }),
    );
    const result = show(response, "Submit");
    if (result.solved) {
      vscode.window.showInformationMessage(`🎉 ReCode: ${result.summary}`, "Open leaderboard").then((choice) => {
        if (choice) vscode.env.openExternal(vscode.Uri.parse(serverUrl() + "/leaderboard/"));
      });
    } else {
      vscode.window.showWarningMessage(`ReCode submit: ${result.summary}`, "Show details").then((c) => c && output.show());
    }
    refresh();
  }

  // ------------------------------------------------------------ sign in
  async function signIn() {
    const url = await vscode.window.showInputBox({
      title: "ReCode server",
      prompt: "The address of your ReCode website",
      value: serverUrl(),
      ignoreFocusOut: true,
      validateInput: (v) => (/^https?:\/\/\S+$/.test(v.trim()) ? null : "Start with http:// or https://"),
    });
    if (!url) return;
    const token = await vscode.window.showInputBox({
      title: "ReCode token",
      prompt: "Paste your plugin token from Settings → Integrations on the website",
      password: true,
      ignoreFocusOut: true,
      validateInput: (v) => (v.trim().length >= 20 ? null : "That doesn't look like a ReCode token."),
    });
    if (!token) return;
    const api = new ReCodeClient({ baseUrl: url.trim(), token: token.trim() });
    let me;
    try {
      me = await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: "ReCode: checking your token…" }, () => api.me());
    } catch (err) {
      const again = await vscode.window.showErrorMessage(`ReCode: ${err.status === 401 ? "That token wasn't accepted." : err.message}`, "Try again");
      if (again) return signIn();
      return;
    }
    await config().update("serverUrl", api.baseUrl, vscode.ConfigurationTarget.Global);
    await context.secrets.store(TOKEN_KEY, token.trim());
    await setSignedIn(true);
    vscode.window.showInformationMessage(`ReCode: signed in as ${me.name}.`);
    await refresh();
  }

  async function signOut() {
    await context.secrets.delete(TOKEN_KEY);
    await setSignedIn(false);
    Object.assign(state, { me: null, today: null, board: [], problems: [], error: null });
    renderStatus();
    tree.refresh();
    vscode.window.showInformationMessage("ReCode: signed out.");
  }

  async function menu() {
    if (!state.signedIn) return signIn();
    const picks = [
      { label: "$(cloud-download) Pull today's problem", run: () => pull() },
      { label: "$(play) Run examples", run: () => run() },
      { label: "$(check) Submit current file", run: () => submit() },
      { label: "$(globe) Open today's problem in the browser", run: () => openInBrowser(state.today ? state.today.url : "/recode/") },
      { label: "$(list-ordered) Open the leaderboard", run: () => openInBrowser("/leaderboard/") },
      { label: "$(refresh) Refresh", run: () => refresh({ quiet: false }) },
      { label: "$(sign-out) Sign out", run: signOut },
    ];
    const pick = await vscode.window.showQuickPick(picks, { placeHolder: "ReCode" });
    if (pick) await pick.run();
  }

  function openInBrowser(pathname) {
    return vscode.env.openExternal(vscode.Uri.parse(serverUrl() + (typeof pathname === "string" ? pathname : "/")));
  }

  // ------------------------------------------------------------ wiring
  const guard = (fn) => async (...args) => {
    try { await fn(...args); } catch (err) {
      if (err && err.status === -1) return; // cancelled
      const message = err && err.message ? err.message : String(err);
      if (err && err.status === 401) {
        const choice = await vscode.window.showErrorMessage(`ReCode: ${message}`, "Sign in");
        if (choice) await signIn();
      } else {
        vscode.window.showErrorMessage(`ReCode: ${message}`);
      }
    }
  };
  const commands = {
    "recode.signIn": signIn,
    "recode.signOut": signOut,
    "recode.refresh": () => refresh({ quiet: false }),
    "recode.pullToday": () => pull(),
    "recode.pullProblem": async (slug) => {
      if (!slug) {
        const api = await client();
        const list = await api.challenges();
        const pick = await vscode.window.showQuickPick(list.map((p) => ({
          label: p.title, description: `${p.difficulty}${p.is_today ? " · today" : ""}${p.solved ? ` · solved ${p.score}` : ""}`, slug: p.slug,
        })), { placeHolder: "Pick a problem to pull" });
        if (!pick) return;
        slug = pick.slug;
      }
      await pull(slug);
    },
    "recode.run": (uri) => run(uri),
    "recode.submit": (uri) => submit(uri),
    "recode.openInBrowser": (p) => openInBrowser(p),
    "recode.menu": menu,
  };
  for (const [id, fn] of Object.entries(commands)) {
    context.subscriptions.push(vscode.commands.registerCommand(id, guard(fn)));
  }

  // Run / Submit buttons at the top of any pulled solution file.
  context.subscriptions.push(vscode.languages.registerCodeLensProvider(
    [{ language: "python", scheme: "file" }, { language: "javascript", scheme: "file" }],
    {
      onDidChangeCodeLenses: lensChanged.event,
      provideCodeLenses(document) {
        const m = metaFor(document);
        if (!m) return [];
        const top = new vscode.Range(0, 0, 0, 0);
        return [
          new vscode.CodeLens(top, { title: "▶ Run examples", command: "recode.run", arguments: [document.uri] }),
          new vscode.CodeLens(top, { title: "✓ Submit", command: "recode.submit", arguments: [document.uri] }),
          new vscode.CodeLens(top, { title: "Open in browser", command: "recode.openInBrowser", arguments: [m.url || "/"] }),
        ];
      },
    },
  ));

  context.subscriptions.push(vscode.workspace.onDidChangeConfiguration((e) => {
    if (e.affectsConfiguration("recode.serverUrl")) refresh();
  }));

  const ticker = setInterval(() => { renderStatus(); tree.refresh(); }, TICK_MS);
  const refresher = setInterval(() => refresh(), REFRESH_MS);
  context.subscriptions.push({ dispose: () => { clearInterval(ticker); clearInterval(refresher); } });

  // Start up: signed in if a token is stored.
  return (async () => {
    await setSignedIn(Boolean(await context.secrets.get(TOKEN_KEY)));
    renderStatus();
    await refresh();
    // Exposed for tests.
    return { state, tree, refresh, commands };
  })();
}

function deactivate() {}

module.exports = { activate, deactivate };
