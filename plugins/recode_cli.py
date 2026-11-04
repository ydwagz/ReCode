#!/usr/bin/env python3
"""ReCode CLI — pull, run and submit the daily challenge from any editor.

    export RECODE_URL=http://127.0.0.1:8000
    export RECODE_TOKEN=<token from Settings → Integrations>

    python recode_cli.py me
    python recode_cli.py pull [--lang python|javascript] [--challenge SLUG]
    python recode_cli.py test solution.py          # runs the examples locally, no server needed
    python recode_cli.py run solution.py            # runs the examples on the server
    python recode_cli.py submit solution.py [--team]

Only the Python standard library is used.
"""

import argparse
import json
import os
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request

META_FILE = ".recode.json"


def api(method, path, payload=None):
    base = os.environ.get("RECODE_URL", "http://127.0.0.1:8000").rstrip("/")
    token = os.environ.get("RECODE_TOKEN")
    if not token:
        sys.exit("Set RECODE_TOKEN (Settings → Integrations on the website).")
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{base}/api/v1/{path}", data=data, method=method,
        headers={"Authorization": f"Token {token}", "Content-Type": "application/json", "User-Agent": "recode-cli/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as err:
        try:
            body = json.load(err)
        except ValueError:
            body = {"error": f"HTTP {err.code}"}
        sys.exit(f"✗ {body.get('error', err)}")
    except urllib.error.URLError as err:
        sys.exit(f"✗ Can't reach {base}: {err.reason}")


def language_for(path):
    return "javascript" if pathlib.Path(path).suffix in (".js", ".mjs") else "python"


def load_meta(path):
    meta_path = pathlib.Path(path).resolve().parent / META_FILE
    return json.loads(meta_path.read_text()) if meta_path.exists() else {}


def print_result(res):
    r = res["result"]
    icons = {"accepted": "✓", "wrong": "✗", "error": "!", "timeout": "⏱"}
    print(f"{icons.get(r['status'], '?')} {r['status'].upper()}  {r['passed']}/{r['total']} tests  {r['runtime_ms']} ms")
    if r.get("error"):
        print("  " + r["error"].replace("\n", "\n  "))
    for i, case in enumerate(r["cases"], 1):
        if case["passed"]:
            continue
        if case["expected"] is None:
            print(f"  test {i}: hidden test failed {case['error'] or ''}")
        elif case["error"]:
            print(f"  test {i}: {case['error']}")
        else:
            print(f"  test {i}: got {json.dumps(case['got'])}, expected {json.dumps(case['expected'])}")
        if case.get("stdout"):
            print("    stdout: " + case["stdout"].strip().replace("\n", "\n    "))
    entry = res.get("entry")
    if entry and entry["solved"]:
        b = entry["breakdown"]
        print(f"\n🎉 Solved! {entry['score']}/100 "
              f"(correct {b['correctness']}, attempts {b['attempts']}, speed {b['speed']}, efficiency {b['efficiency']}"
              + (f", hints -{b['hint_penalty']}" if b["hint_penalty"] else "") + ")")
    elif entry:
        print(f"\nFailed attempts so far: {entry['failed_attempts']}")


def cmd_me(args):
    me = api("GET", "me/")
    s = me["streak"]
    print(f"{me['name']} (@{me['username']})" + (f" · team {me['team']['name']}" if me["team"] else ""))
    print(f"🔥 streak {s['current']} ({s['state']}) · 🧊 {s['freezes']} freezes · best {s['longest']}")
    print(f"solved {me['stats']['solved']} · avg score {me['stats']['avg_score']}")


def cmd_pull(args):
    path = f"challenges/{args.challenge}/" if args.challenge else "today/"
    ch = api("GET", path)["challenge"]
    ext = "js" if args.lang == "javascript" else "py"
    folder = pathlib.Path(args.dir or ch["slug"])
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"solution.{ext}"
    comment = "//" if ext == "js" else "#"
    header = "\n".join(f"{comment} {line}".rstrip() for line in (
        [f"{ch['title']} ({ch['difficulty']}) — closes {ch['closes_at']}", ""] + ch["description"].splitlines()
        + ["", "Examples:"] + [f"  {json.dumps(e['args'])} -> {json.dumps(e['expected'])}" for e in ch["examples"]]
    ))
    if not target.exists() or args.force:
        target.write_text(header + "\n\n" + ch["starter_code"][args.lang])
    (folder / META_FILE).write_text(json.dumps({"challenge": ch["slug"], "function": ch["function"], "examples": ch["examples"]}, indent=2))
    print(f"✓ {ch['title']} → {target}")


def cmd_test(args):
    """Run the examples locally with your own interpreter (no server, no rate limits)."""
    meta = load_meta(args.file)
    if not meta:
        sys.exit("No .recode.json next to this file — run `pull` first.")
    lang = language_for(args.file)
    fn = meta["function"][lang]
    source = pathlib.Path(args.file).read_text()
    if lang == "python":
        harness = source + "\nimport json, sys\nfor case in json.loads(sys.argv[1]):\n    print(json.dumps({fn}(*case['args'])))\n".format(fn=fn)
        cmd = [sys.executable, "-c", harness, json.dumps(meta["examples"])]
    else:
        harness = source + f"\nfor (const c of JSON.parse(process.argv[1])) console.log(JSON.stringify({fn}(...c.args)));\n"
        cmd = ["node", "-e", harness, json.dumps(meta["examples"])]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if proc.returncode:
        sys.exit(proc.stderr)
    outputs = [line for line in proc.stdout.splitlines() if line.strip()][-len(meta["examples"]):]
    passed = 0
    for i, (example, out) in enumerate(zip(meta["examples"], outputs), 1):
        ok = json.loads(out) == example["expected"]
        passed += ok
        print(f"{'✓' if ok else '✗'} example {i}: got {out}" + ("" if ok else f", expected {json.dumps(example['expected'])}"))
    print(f"{passed}/{len(meta['examples'])} examples passed locally")


def _remote(args, endpoint):
    meta = load_meta(args.file)
    payload = {"code": pathlib.Path(args.file).read_text(), "language": language_for(args.file)}
    if args.challenge or meta.get("challenge"):
        payload["challenge"] = args.challenge or meta["challenge"]
    if getattr(args, "team", False):
        payload["mode"] = "team"
    print_result(api("POST", endpoint, payload))


def main():
    parser = argparse.ArgumentParser(description="ReCode command line plugin")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("me", help="show your streak and stats").set_defaults(func=cmd_me)
    p = sub.add_parser("pull", help="download today's challenge")
    p.add_argument("--lang", choices=["python", "javascript"], default="python")
    p.add_argument("--challenge", help="challenge slug (default: today)")
    p.add_argument("--dir", help="output folder (default: the challenge slug)")
    p.add_argument("--force", action="store_true", help="overwrite an existing solution file")
    p.set_defaults(func=cmd_pull)
    for name, func, text in (("test", cmd_test, "run examples locally"),
                             ("run", lambda a: _remote(a, "run/"), "run examples on the server (free)"),
                             ("submit", lambda a: _remote(a, "submit/"), "submit for a score")):
        p = sub.add_parser(name, help=text)
        p.add_argument("file")
        p.add_argument("--challenge")
        if name == "submit":
            p.add_argument("--team", action="store_true", help="submit as your team's entry")
        p.set_defaults(func=func)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
