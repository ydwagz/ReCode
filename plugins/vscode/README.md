# ReCode for VS Code

Solve the ReCode daily problem without leaving your editor.

- **ReCode sidebar:** today's problem with a live countdown, your result and streak, the top 5 today, and recent problems. Click any problem to pull it.
- **Pull a problem:** creates `recode/<problem>/solution.py` (or `.js`) and opens the problem description beside it.
- **Run examples** (`Ctrl+Alt+R`) and **Submit** (`Ctrl+Alt+Enter`) from the buttons above line 1 of the solution, the editor toolbar, or the sidebar.
- **Results** appear in the *ReCode* output panel, test by test. Solving it shows your score.
- **Status bar** shows your streak and the time left; click it for every action.

## Install

1. In VS Code open **Extensions**, click **…** (top right) → **Install from VSIX…**
2. Pick `recode-1.1.0.vsix` from this folder.

## Connect

1. Start your ReCode website (`python manage.py runserver`).
2. Click the **ReCode** icon in the activity bar → **Sign in**.
3. Enter the website address (default `http://127.0.0.1:8000`) and your token from **Settings → Integrations** on the website.

The token is kept in VS Code's secure storage, not in your settings.

## Settings

| Setting | Default | What it does |
|---|---|---|
| `recode.serverUrl` | `http://127.0.0.1:8000` | Address of your ReCode website |
| `recode.language` | `python` | `python` or `javascript` for new solution files |
| `recode.folder` | `recode` | Folder in your workspace where problems are saved |
| `recode.openProblemOnPull` | `true` | Open the problem description beside the code |
| `recode.confirmSubmit` | `true` | Ask before submitting (failed submissions cost points) |
| `recode.showOutputOnRun` | `true` | Show the output panel after Run and Submit |

## Development

No build step and no dependencies. To try changes, open this folder in VS Code and press `F5`.

```bash
npm test                      # unit tests
RECODE_TEST_URL=http://127.0.0.1:8000 RECODE_TEST_TOKEN=<token> npm test   # plus live tests against a server
npm run package               # builds recode-<version>.vsix
```
