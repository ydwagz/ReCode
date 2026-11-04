# ReCode for VS Code

Pull, run and submit the ReCode daily challenge without leaving your editor.

## Install

```bash
cd plugins/vscode
npx @vscode/vsce package
```

Then in VS Code, open *Extensions → … → Install from VSIX* and pick the `recode-1.0.0.vsix` file. You can also open this folder in VS Code and press <kbd>F5</kbd> to launch a dev instance.

## Use

1. Run **ReCode: Set API Token** and paste the token from *Settings → Integrations* on the website.
2. Set `recode.serverUrl` to your ReCode server. The default is `http://127.0.0.1:8000`.
3. Run **ReCode: Pull Today's Challenge**. It creates `<slug>/solution.py` (or `.js`) with the problem statement as a comment.
4. Run **ReCode: Run Examples** to check against the examples. Runs are free.
5. Run **ReCode: Submit Current File** to submit for a score.

The status bar shows your current streak.
