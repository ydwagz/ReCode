// A small stand-in for the `vscode` module so the extension can be exercised under plain Node.
const path = require("path");
const fs = require("fs");
const Module = require("module");

function createMock({ workspace, config = {}, token } = {}) {
  const log = { info: [], warn: [], error: [], contexts: {}, opened: [], previews: [], external: [], configUpdates: {} };
  const answers = { input: [], quickPick: [], message: [] }; // queued replies, consumed in order
  const commands = new Map();
  let lensProvider = null;
  const secrets = new Map(token ? [["recode.apiToken", token]] : []);

  class EventEmitter { constructor() { this.listeners = []; this.event = (fn) => { this.listeners.push(fn); return { dispose() {} }; }; } fire(v) { this.listeners.forEach((fn) => fn(v)); } dispose() {} }
  class TreeItem { constructor(label, collapsibleState) { this.label = label; this.collapsibleState = collapsibleState; } }
  class ThemeIcon { constructor(id) { this.id = id; } }
  class Range { constructor(a, b, c, d) { Object.assign(this, { a, b, c, d }); } }
  class CodeLens { constructor(range, command) { this.range = range; this.command = command; } }
  const Uri = {
    file: (p) => ({ fsPath: p, scheme: "file", toString: () => "file://" + p }),
    parse: (s) => ({ toString: () => s, scheme: s.split(":")[0] }),
  };

  function makeDocument(p) {
    return {
      uri: Uri.file(p), fileName: p, isDirty: false,
      getText: () => fs.readFileSync(p, "utf8"),
      save: async () => true,
    };
  }
  const reply = (kind) => (...args) => {
    log[kind].push(args[0]);
    const next = answers.message.shift();
    return Promise.resolve(typeof next === "function" ? next(...args) : next);
  };

  const vscode = {
    EventEmitter, TreeItem, ThemeIcon, Range, CodeLens, Uri,
    TreeItemCollapsibleState: { None: 0, Collapsed: 1, Expanded: 2 },
    StatusBarAlignment: { Left: 1, Right: 2 },
    ProgressLocation: { Notification: 15 },
    ViewColumn: { One: 1, Beside: -2 },
    ConfigurationTarget: { Global: 1 },
    window: {
      activeTextEditor: undefined,
      createOutputChannel: () => ({ lines: [], appendLine(l) { this.lines.push(l); }, show() {}, dispose() {} }),
      createStatusBarItem: () => ({ text: "", tooltip: "", show() {}, dispose() {} }),
      createTreeView: (id, opts) => { vscode.__tree = opts.treeDataProvider; return { dispose() {} }; },
      showInformationMessage: reply("info"),
      showWarningMessage: reply("warn"),
      showErrorMessage: reply("error"),
      showInputBox: async (opts) => {
        const v = answers.input.shift();
        if (v !== undefined && opts.validateInput) { const problem = opts.validateInput(v); if (problem) throw new Error("validation: " + problem); }
        return v;
      },
      showQuickPick: async (items) => { const pick = answers.quickPick.shift(); const list = await items; return typeof pick === "function" ? pick(list) : pick; },
      showOpenDialog: async () => undefined,
      showTextDocument: async (doc) => { log.opened.push(doc.fileName); vscode.window.activeTextEditor = { document: doc }; return {}; },
      withProgress: async (_opts, task) => task({ report() {} }),
    },
    workspace: {
      workspaceFolders: workspace ? [{ uri: Uri.file(workspace) }] : undefined,
      getConfiguration: () => ({
        get: (k) => (k in config ? config[k] : undefined),
        update: async (k, v) => { config[k] = v; log.configUpdates[k] = v; },
      }),
      openTextDocument: async (target) => makeDocument(typeof target === "string" ? target : target.fsPath),
      onDidChangeConfiguration: () => ({ dispose() {} }),
    },
    commands: {
      registerCommand: (id, fn) => { commands.set(id, fn); return { dispose() {} }; },
      executeCommand: async (id, ...args) => {
        if (id === "setContext") { log.contexts[args[0]] = args[1]; return; }
        if (id === "markdown.showPreviewToSide") { log.previews.push(args[0].fsPath); return; }
        if (commands.has(id)) return commands.get(id)(...args);
        throw new Error("unknown command " + id);
      },
    },
    languages: { registerCodeLensProvider: (_sel, provider) => { lensProvider = provider; return { dispose() {} }; } },
    env: { openExternal: async (uri) => { log.external.push(uri.toString()); return true; } },
  };

  const context = {
    subscriptions: [],
    secrets: {
      get: async (k) => secrets.get(k),
      store: async (k, v) => { secrets.set(k, v); },
      delete: async (k) => { secrets.delete(k); },
    },
    globalState: { get: () => undefined, update: async () => {} },
  };

  return { vscode, context, log, answers, commands, secrets, config, lenses: (doc) => (lensProvider ? lensProvider.provideCodeLenses(doc) : []), makeDocument };
}

/** Load extension.js with `require("vscode")` pointing at the mock. */
function loadExtension(mock) {
  const root = path.resolve(__dirname, "..");
  const original = Module._load;
  Module._load = function (request, parent, isMain) {
    if (request === "vscode") return mock.vscode;
    return original.call(this, request, parent, isMain);
  };
  for (const key of Object.keys(require.cache)) if (key.startsWith(root) && !key.includes(`${path.sep}test${path.sep}`)) delete require.cache[key];
  try { return require(path.join(root, "extension.js")); } finally { Module._load = original; }
}

module.exports = { createMock, loadExtension };
