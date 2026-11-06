// The ReCode sidebar: today's problem, you, the live top 5 and recent problems.
const vscode = require("vscode");
const { capitalize, formatDuration, timeLeft } = require("./format");

const DIFFICULTY_ICON = { easy: "pass", medium: "warning", hard: "flame" };

function item(label, { description, tooltip, icon, command, contextValue, collapsible, id } = {}) {
  const node = new vscode.TreeItem(label, collapsible || vscode.TreeItemCollapsibleState.None);
  if (id) node.id = id;
  if (description !== undefined) node.description = String(description);
  if (tooltip) node.tooltip = tooltip;
  if (icon) node.iconPath = new vscode.ThemeIcon(icon);
  if (command) node.command = command;
  if (contextValue) node.contextValue = contextValue;
  return node;
}

class ReCodeTree {
  constructor(state) {
    this.state = state;
    this._changed = new vscode.EventEmitter();
    this.onDidChangeTreeData = this._changed.event;
  }

  refresh() { this._changed.fire(undefined); }

  getTreeItem(node) { return node; }

  getChildren(node) {
    const s = this.state;
    if (!s.signedIn) return []; // the welcome view (Sign in button) shows instead
    if (!node) {
      if (s.error) {
        return [item(s.error, { icon: "error", tooltip: s.error, command: { command: "recode.refresh", title: "Retry" }, description: "click to retry" })];
      }
      if (!s.today) return [item("Loading…", { icon: "loading~spin" })];
      const expanded = vscode.TreeItemCollapsibleState.Expanded;
      const collapsed = vscode.TreeItemCollapsibleState.Collapsed;
      return [
        item("Today", { id: "sec-today", collapsible: expanded, contextValue: "section" }),
        item("You", { id: "sec-you", collapsible: expanded, contextValue: "section" }),
        item("Top 5 today", { id: "sec-board", collapsible: expanded, contextValue: "section" }),
        item("Problems", { id: "sec-problems", collapsible: collapsed, contextValue: "section" }),
      ];
    }
    switch (node.id) {
      case "sec-today": return this.todayItems();
      case "sec-you": return this.youItems();
      case "sec-board": return this.boardItems();
      case "sec-problems": return this.problemItems();
      default: return [];
    }
  }

  todayItems() {
    const ch = this.state.today;
    const e = ch.entry;
    const items = [
      item(ch.title, {
        id: "today-title",
        description: capitalize(ch.difficulty),
        icon: DIFFICULTY_ICON[ch.difficulty] || "circle-outline",
        tooltip: "Pull this problem into your workspace",
        command: { command: "recode.pullToday", title: "Pull today's problem" },
      }),
      item("Closes in", { id: "today-left", description: timeLeft(ch.closes_at), icon: "clock" }),
    ];
    if (e && e.solved) {
      items.push(item("Solved", { id: "today-result", description: `${e.score}/100 in ${formatDuration(e.solve_seconds)}`, icon: "pass-filled" }));
    } else if (e) {
      items.push(item("In progress", { id: "today-result", description: `${e.failed_attempts} failed attempt${e.failed_attempts === 1 ? "" : "s"}`, icon: "debug-start" }));
    } else {
      items.push(item("Not started", { id: "today-result", description: "pull it to start", icon: "circle-large-outline" }));
    }
    return items;
  }

  youItems() {
    const me = this.state.me;
    if (!me) return [];
    const st = me.streak;
    const state = { active: "locked in today", pending: "solve today to keep it", recoverable: "at risk", broken: "start again today", none: "solve today to start" }[st.state] || st.state;
    return [
      item(me.name, { id: "you-name", description: me.team ? `team ${me.team.name}` : "solo", icon: "account" }),
      item(`${st.current} day streak`, { id: "you-streak", description: state, icon: "flame" }),
      item("Streak freezes", { id: "you-freezes", description: st.freezes, icon: "snowflake" }),
      item("Solved", { id: "you-solved", description: `${me.stats.solved} · avg ${me.stats.avg_score}`, icon: "check-all" }),
    ];
  }

  boardItems() {
    const rows = this.state.board || [];
    if (!rows.length) return [item("No solves yet today", { id: "board-empty", icon: "circle-large-outline" })];
    const me = this.state.me && this.state.me.username;
    return rows.map((r) => item(`${r.rank}. ${r.name}`, {
      id: `board-${r.kind}-${r.key}`,
      description: `${r.score}${r.kind === "team" ? " · team" : ""}${r.kind === "player" && r.key === me ? " · you" : ""}`,
      icon: r.rank === 1 ? "star-full" : r.kind === "team" ? "organization" : "person",
      command: { command: "recode.openInBrowser", title: "Open leaderboard", arguments: ["/leaderboard/"] },
    }));
  }

  problemItems() {
    return (this.state.problems || []).map((p) => item(p.title, {
      id: `problem-${p.slug}`,
      description: `${p.is_today ? "today" : p.release_date.slice(5)}${p.solved ? ` · ${p.score}` : ""}`,
      icon: p.solved ? "pass-filled" : DIFFICULTY_ICON[p.difficulty] || "circle-outline",
      tooltip: `${p.title} (${p.difficulty})${p.is_today ? " — ranked" : " — practice"}\nClick to pull it into your workspace.`,
      command: { command: "recode.pullProblem", title: "Pull problem", arguments: [p.slug] },
    }));
  }
}

module.exports = { ReCodeTree };
